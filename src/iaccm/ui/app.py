"""Gradio workbench: the narrowing loop. Upload a sherd photo / profile drawing, say what you
know in free text, and watch the candidate set narrow toward a single published form — the
archaeologist reacts in natural language at each turn (docs/method.md).

Candidate plates are shown as whole PDF pages for now ("whole pages first"); isolated-profile
crops come once bbox localization is refined. gradio is imported lazily so this module stays cheap.
"""

from __future__ import annotations

from pathlib import Path


def _render_candidate_pages(result, max_pages: int = 4) -> list[tuple[str, str]]:
    """Map the top ranked candidates to their source pages, dedupe, render whole pages."""
    from ..catalog.store import CatalogStore
    from ..ingest.pdf import find_source_pdf, render_region

    forms = {f.id: f for f in CatalogStore()}
    gallery: list[tuple[str, str]] = []
    seen: set[tuple[str | None, int]] = set()
    for c in result.candidates:
        f = forms.get(c.form_id)
        if not f or f.source is None or f.source.page_pdf is None:
            continue
        key = (f.source.source_file, f.source.page_pdf)
        if key in seen:
            continue
        pdf = find_source_pdf(f.source.checksum, f.source.source_file)
        if pdf is None:
            continue
        img = render_region(pdf, f.source.page_pdf, None)  # whole page
        seen.add(key)
        gallery.append((str(img), f"{c.form_id} — {c.why}"))
        if len(gallery) >= max_pages:
            break
    return gallery


# Curated cloud presets, shown only when that provider's key is in the environment (loaded from .env
# by config._load_dotenv). Ollama entries are discovered at runtime from a running server.
_ANTHROPIC_PRESETS = [("Anthropic / Claude Opus 4.8", "anthropic", "claude-opus-4-8")]
_FEATHERLESS_PRESETS = [
    ("Featherless / Qwen2.5-VL-72B", "featherless", "Qwen/Qwen2.5-VL-72B-Instruct"),
    ("Featherless / Qwen3-VL-32B", "featherless", "Qwen/Qwen3-VL-32B-Instruct"),
    ("Featherless / Qwen3-VL-235B (thinking)", "featherless", "Qwen/Qwen3-VL-235B-A22B-Thinking"),
]


def _ollama_models() -> list[tuple[str, str, str]]:
    """Installed models on a running Ollama (``OLLAMA_HOST`` or localhost), else []. Short timeout
    so the UI starts instantly when Ollama isn't running."""
    import json
    import os
    import urllib.request

    host = os.environ.get("OLLAMA_HOST") or "http://localhost:11434"
    if not host.startswith("http"):
        host = "http://" + host
    try:
        with urllib.request.urlopen(host.rstrip("/") + "/api/tags", timeout=0.6) as r:
            data = json.load(r)
    except Exception:
        return []
    return [
        (f"Ollama / {m['name']}", "ollama", m["name"])
        for m in data.get("models", [])
        if m.get("name")
    ]


def _available_presets() -> list[tuple[str, str, str]]:
    """Model-picker entries for the providers usable right now: a cloud provider appears only when
    its key is present; Ollama appears only when its server answers (with its installed models)."""
    import os

    out: list[tuple[str, str, str]] = []
    if os.environ.get("FEATHERLESS_API_KEY"):  # listed first → the picker's default
        out += _FEATHERLESS_PRESETS
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("IACCM_MODEL_API_KEY"):
        out += _ANTHROPIC_PRESETS
    out += _ollama_models()
    return out


def _colour_note(surface: str | None, fabric: str | None) -> str:
    """Render eyedropper-sampled colours as a short note appended to the user's message, so the
    model has them as observables (surface slip vs the colour of a fresh break)."""
    bits = []
    if surface:
        bits.append(f"surface/slip {surface}")
    if fabric:
        bits.append(f"fresh-break fabric {fabric}")
    return f" [sampled colours — {'; '.join(bits)}]" if bits else ""


def build_app(provider: str | None = None, model: str | None = None):
    """Build and return the Gradio Blocks app. ``provider``/``model`` (the `iaccm ui --provider …`
    flags) set the picker's default; the user switches model in the dropdown. Keys from .env."""
    import gradio as gr  # lazy import

    # Gradio detects the ``evt: gr.SelectData`` param via ``typing.get_type_hints``, which resolves
    # annotations against the handler's *module* globals — not this function's locals. With ``gr``
    # imported lazily here, that lookup fails silently (NameError → {}), Gradio sets
    # collects_event_data=False, and the eyedropper's click coords get misbound. Bind ``gr`` into
    # module globals so the annotation resolves and SelectData is injected correctly.
    globals().setdefault("gr", gr)

    from ..agent.identify import Identifier
    from ..config import get_settings
    from ..model import get_model_client

    get_settings()  # load .env keys into the environment before checking provider availability
    presets = _available_presets() or [("(.env default)", "", "")]
    default_label = presets[0][0]
    if provider or model:  # a launch flag pre-selects (adding a custom entry if it's not a preset)
        match = next((lbl for lbl, p, m in presets if p == provider and m == model), None)
        if match:
            default_label = match
        else:
            default_label = f"{provider or 'default'} / {model or 'default'}"
            presets.insert(0, (default_label, provider or "", model or ""))
    by_label = {lbl: (p, m) for lbl, p, m in presets}

    def show_uploads(files):
        """Preview uploads as thumbnails, and load the first into the colour-sampling image."""
        paths = [str(f) for f in (files or [])]
        return paths, (paths[0] if paths else None)

    def sample_color(image, mode, surface, fabric, evt: gr.SelectData):
        """Eyedropper: set the surface or fabric colour from the clicked pixel (RGB → hex)."""
        if image is None or evt.index is None:
            return surface, fabric
        x, y = int(evt.index[0]), int(evt.index[1])
        h, w = image.shape[0], image.shape[1]
        if not (0 <= y < h and 0 <= x < w):
            return surface, fabric
        px = image[y, x]
        hexc = f"#{int(px[0]):02x}{int(px[1]):02x}{int(px[2]):02x}"
        return (surface, hexc) if mode == "fabric" else (hexc, fabric)

    def _client_for(label):
        prov, mod = by_label.get(label, (None, None))
        return get_model_client(provider=prov, model=mod) if (prov or mod) else get_model_client()

    def on_send(user_text, files, show_all, surface_color, fabric_color, model_label,
                chat_history, ident):
        if not user_text and not files:
            return chat_history or [], [], ident, ""
        if ident is None:
            ident = Identifier(client=_client_for(model_label))
        else:
            # honour the current dropdown WITHOUT wiping history — switching model mid-conversation
            # just rebinds the backend; the replayed dialogue carries over to the new model.
            ident.client = _client_for(model_label)
        imgs = [Path(f) for f in (files or [])]
        sent_text = (user_text or "") + _colour_note(surface_color, fabric_color)  # inject colours
        chat_history = chat_history or []
        chat_history.append({"role": "user", "content": sent_text or "(image only)"})

        # A model/backend failure (e.g. an open model returning non-JSON, or an API error) must NOT
        # wipe the conversation — surface it as a chat message and keep the history so the user can
        # retry or switch models. (The Identifier records a turn only on success, so its replayed
        # history stays clean.)
        try:
            result = ident.step(
                sent_text or "(see attached image)", images=imgs or None, show_all=bool(show_all)
            )
        except Exception as e:  # noqa: BLE001 — any backend error should land in the chat, not crash
            msg = str(e).strip() or type(e).__name__
            chat_history.append(
                {"role": "assistant", "content": f"⚠️ **Error** ({model_label}): {msg[:800]}"}
            )
            return chat_history, [], ident, ""

        parts: list[str] = []
        if result.understood:
            parts.append(f"**Understood:** {result.understood}")
        if result.observed_parts:
            parts.append(f"**Reading part(s):** {', '.join(result.observed_parts)}")
        if result.candidates:
            top = "\n".join(
                f"- **{c.form_id}** ({c.score:.2f}) — {c.why}" for c in result.candidates[:5]
            )
            parts.append(f"**Most likely:**\n{top}")
        if result.candidates_note:
            parts.append(f"_{result.candidates_note}_")
        if result.question:
            parts.append(f"**To narrow further:** {result.question}")
        if result.conclusion:
            parts.append(f"**Conclusion ({result.confidence}):** {result.conclusion}")
        chat_history.append({"role": "assistant", "content": "\n\n".join(parts) or "(no result)"})
        try:
            gallery = _render_candidate_pages(result)
        except Exception:  # noqa: BLE001 — a render hiccup shouldn't drop a good result
            gallery = []
        return chat_history, gallery, ident, ""

    with gr.Blocks(title="IACCM — sherd identification") as app:
        gr.Markdown("# IACCM\nNarrow a sherd to a published form — tell me what you know.")
        ident_state = gr.State()
        with gr.Row():
            with gr.Column(scale=2):
                model_pick = gr.Dropdown(
                    choices=list(by_label.keys()),
                    value=default_label,
                    label="Model (provider / model)",
                )
                files = gr.File(
                    label="Sherd photo(s) / profile drawing",
                    file_count="multiple",
                    file_types=["image"],
                )
                uploads = gr.Gallery(
                    label="Uploaded",
                    columns=3,
                    height=140,
                    object_fit="contain",
                    interactive=False,
                    show_label=True,
                )
                sample_img = gr.Image(
                    label="Sample colours — click the sherd (first photo)",
                    type="numpy",
                    height=240,
                )
                sample_mode = gr.Radio(
                    ["surface", "fabric"], value="surface", label="Click sets which colour"
                )
                with gr.Row():
                    surface_pick = gr.ColorPicker(label="Surface / slip", value=None)
                    fabric_pick = gr.ColorPicker(label="Fabric (fresh break)", value=None)
                msg = gr.Textbox(
                    label="What do you know?",
                    placeholder="e.g. 'ARS C, looks like a deep bowl, marli rim'",
                    lines=2,
                )
                show_all = gr.Checkbox(
                    label="Show all candidates (no top-N cap)",
                    value=False,
                )
                send = gr.Button("Send", variant="primary")
            with gr.Column(scale=3):
                chat = gr.Chatbot(label="Narrowing", height=380)
                gallery = gr.Gallery(label="Candidate plate pages", columns=2, height=380)

        inputs = [msg, files, show_all, surface_pick, fabric_pick, model_pick, chat, ident_state]
        outputs = [chat, gallery, ident_state, msg]
        files.change(show_uploads, files, [uploads, sample_img])
        sample_img.select(
            sample_color, [sample_img, sample_mode, surface_pick, fabric_pick],
            [surface_pick, fabric_pick],
        )
        send.click(on_send, inputs, outputs)
        msg.submit(on_send, inputs, outputs)
        # No model_pick.change handler: switching model keeps the conversation; on_send swaps the
        # backend on the next turn (the dialogue history is replayed to the new model).
    return app


def launch(provider: str | None = None, model: str | None = None, **kwargs) -> None:
    build_app(provider=provider, model=model).launch(**kwargs)
