# IACCM — Identification of Archaeological Ceramics in the Central Mediterranean

An open-source, local-first tool for identifying photographs of ceramic sherds — especially
small diagnostic fragments (rims, bases, handles, lids) — against **published typologies the
user supplies as PDFs**. A multimodal LLM works the identification *in dialog*: it takes your
opening notes and photos, retrieves candidate forms from a pre-built index, opens only the
relevant plate pages from your own PDF, asks targeted questions when a diagnostic is ambiguous,
and proposes a ranked identification with citations.

## Why it is built this way

The hard part of sherd ID is **not pruning the right answer too early**. A small fragment is
ambiguous and a confident model narrows to a wrong type before looking at the full candidate
set. The architecture forces *breadth before depth*: the candidate set is made explicit and
exhaustive from the index, the model only does *constrained visual comparison* against retrieved
plates, and the human is asked for the one discriminator that settles it. That also makes a
laptop-sized model viable — it never recalls a typology from memory.

See `docs/method.md` (the cascade) and `docs/copyright.md` (the firewall around source PDFs).

## Architecture

```
photo + notes ─▶ triage ─▶ retrieve candidates ─▶ open local plate pages ─▶
                 (part/ware)  (structured + vector    (render from YOUR pdf)
                              + archetype funnel)
            ─▶ compare (VLM) ─▶ ask user a discriminator ─▶ rank + cite ─▶ record
```

| Concern | Module |
|---|---|
| Settings / paths / model provider | `src/iaccm/config.py` |
| Model access (OpenAI-compatible) | `src/iaccm/model/` |
| PDF → records | `src/iaccm/ingest/` |
| Form catalog + ~20 profile archetypes | `src/iaccm/catalog/` |
| Candidate retrieval (breadth-enforcing) | `src/iaccm/retrieve/` |
| Dialog agent (LangGraph, human-in-the-loop) | `src/iaccm/agent/` |
| UI (Gradio workbench) | `src/iaccm/ui/` |
| CLI | `src/iaccm/cli.py` |

## Distribution model

Cross-platform (Windows + macOS) native Python app — **not** Docker (no Metal in containers on
macOS; containers are friction on laptops). The redistributable artifact is the **index bundle**
(facts + archetypes + page pointers), never the PDFs. Each user adds their own legally-held PDFs
to `corpus/`; the app binds them to the index by checksum.

## Model

Talks to any OpenAI-compatible endpoint. Default: local **Ollama** with `qwen2.5-vl:7b`; point
at a remote open-weights provider for larger models. Configured in `.env` — never hardcoded.

## Quickstart (development)

```bash
uv venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
cp .env.example .env                       # edit for your model provider
# put your typology PDF(s) in corpus/
iaccm ingest corpus/Lattara_6_Dicocer_dictionnaire_des_ceram.pdf
iaccm ui
pytest
```

## Status

Walking skeleton: modules are stubbed with typed interfaces and `NotImplementedError` + TODOs.
First end-to-end target is `eval/cases/dn9_11_lid.yaml` — a real sherd that must resolve to
**DICOCER CLAIR-C Dn9.11**. Pick up the build in Claude Code; start from `docs/method.md` and the
hard rules in `CLAUDE.md`.
