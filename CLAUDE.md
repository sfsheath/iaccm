# IACCM — repo guide for agentic coding

**Identification of Archaeological Ceramics in the Central Mediterranean.** A local-first,
open-source, multimodal tool that identifies ceramic sherd photos against user-supplied typology
PDFs, working the identification in dialog with the user.

## Read first

- `docs/method.md` — the identification **cascade** and output format. The *product logic* the
  agent implements; keep code behavior aligned with it.
- `docs/copyright.md` — the **firewall** around source PDFs. Non-negotiable.
- `docs/SOURCES.md` — the typology page index (DICOCER form → printed page). Ingest turns this
  kind of mapping into the structured catalog.
- `docs/typologies/*.md` — per-category diagnostic keys. **Generic, timeless process only** — no
  dated entries, no per-find "user correction" notes. Specific identifications/corrections live as
  regression cases in `eval/cases/*.yaml`, never as prose here (these docs ship to the world).

## Architecture (where things go)

| Concern | Module | Notes |
|---|---|---|
| Settings / paths / model provider | `src/iaccm/config.py` | pydantic-settings, reads `.env`, paths relative to a configurable root |
| Model access | `src/iaccm/model/client.py` | OpenAI-compatible; provider-agnostic |
| PDF → records | `src/iaccm/ingest/` | PyMuPDF render, OCR fallback, structured extraction |
| Form catalog + archetypes | `src/iaccm/catalog/` | one record per published form; ~20 profile archetypes |
| Candidate retrieval | `src/iaccm/retrieve/` | structured filter + vector + archetype funnel |
| Dialog/agent | `src/iaccm/agent/graph.py` | LangGraph; human-in-the-loop interrupts |
| UI | `src/iaccm/ui/app.py` | Gradio workbench |
| CLI | `src/iaccm/cli.py` | `iaccm ingest`, `iaccm ui`, `iaccm id` |

## Hard rules

1. **Copyright firewall.** Never commit, bundle, or export source PDFs or plate images. `corpus/`
   and rendered crops stay git-ignored. The shareable artifact is the index bundle (facts +
   archetypes + page pointers), never the plates. See `docs/copyright.md`.
2. **Breadth before depth — never prune a candidate set on a lossy signal.** Founding bug: a
   ware (CLAIR-C) was dropped because a text search for "couvercle" missed a line-wrapped
   description, so the correct form (Dn9.11) was never rendered. Retrieval must enumerate the
   *full* candidate set for a part-type across all wares; the model compares within it; a
   verification step confirms the conclusion was checked against the whole set, not a subset.
3. **Model does constrained comparison, not recall.** Always ground the model in retrieved plate
   pages and the user's notes. Never ask it to name a type from memory.
4. **Ask the human for the discriminator.** When candidates differ on one feature (everted vs.
   plain rim), the agent asks rather than guesses.
5. **No hardcoded paths or providers.** Everything from `config`. The repo must run unchanged
   after being moved to a different directory.

## Conventions

- Python ≥3.13, typed, `pydantic` models for all cross-module data (catalog records, candidates,
  identification results). `ruff` + `mypy` clean.
- Deterministic, testable seams: ingest and retrieval runnable headless for `eval/`.
- Every correction/identification becomes an `eval/cases/*.yaml` regression case.

## Run / test

```bash
uv pip install -e ".[dev]"
pytest                 # unit + eval regression
iaccm ingest corpus/<file>.pdf
iaccm ui
```

The bar for "it works": index/prompt/model changes still pass `eval/cases/dn9_11_lid.yaml`.

## Suggested first moves (for whoever picks this up)

1. Implement `config.py` + `model/client.py` and prove a round-trip to Ollama.
2. `ingest`: render DICOCER pages, extract per-form records for the Claire wares (no text-only
   pruning — render and read). Populate `catalog`.
3. Author the 20 archetype silhouettes in `catalog/archetypes.py` (original SVGs).
4. `retrieve`: enumerate the full lid candidate set; wire the archetype funnel.
5. `agent/graph.py`: the cascade with a human-in-the-loop `ask_user` interrupt.
6. Make `eval/cases/dn9_11_lid.yaml` pass end to end.
