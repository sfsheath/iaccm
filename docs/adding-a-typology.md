# Adding a typology

Ingesting a new published typology is meant to be **a config entry, not a fork**. Per-book knowledge
lives in one `SourceProfile`; code only ever grows when a book introduces a genuinely new *render
topology* (and those are a short, finite list). This page is the runbook.

## The model

- **`src/iaccm/ingest/profiles.py`** — the `PROFILES` registry. One entry per book carries the
  scalar knobs (`slug`, `short_title`, `page_offset`, `dpi`) and a `prompt_body` describing that
  book's layout, identity scheme and metadata conventions. All entries sit on the shared
  `BASE_PROMPT`, which owns the non-negotiables (breadth-before-depth, paraphrase-don't-copy,
  archetype tagging, bbox, the copyright firewall). A new book inherits those for free.
- **`layout`** — the render topology, the *only* field that selects a code path:
  - `forms-per-page` — many numbered forms on one plate (DICOCER).
  - `entry-per-page` — one catalogue entry per page, occasionally a spread (Sciallano & Sibella).
  - `class-window` — one type per *multi-page* entry whose continuation pages have no identity
    anchor; each type is scanned out of the text layer and rendered as one multi-image call
    (Peacock & Williams). See `src/iaccm/ingest/windows.py`.

If your book fits an existing `layout`, **adding it is purely a `PROFILES` entry** — no code. Only a
truly new page topology (continuation pages with no anchor, double-page spreads read as one unit,
etc.) justifies a new `layout` value and its render branch in `ingest/pdf.py`.

## Steps

1. **Drop the PDF in `corpus/`.** It stays git-ignored (copyright firewall) — never committed.
2. **Probe the text layer** to find the printed→PDF offset and the layout genre:
   ```python
   import fitz
   d = fitz.open("corpus/<file>.pdf")
   print(d.load_page(N).get_text("text")[:1500])   # eyeball a catalogue page
   ```
   The offset is `1-based PDF page − printed page` (e.g. printed 82 on PDF page 101 → `page_offset=19`).
   `render_page` is 1-based (`doc[page_pdf-1]`); a mismatch here renders the wrong page.
3. **Add a `PROFILES` entry.** Pick the `layout`; write a `prompt_body` naming this book's `ware`,
   `form_id` (the identity — a catalogue number, a type name, a class number), the section→field
   mapping (origin / contents / dates / cross_refs), and what the `bbox` drawing is. For
   `class-window`, also set `window_header` (a `^`-anchored regex with one integer capture group;
   anchor it so a running-text mention is not mistaken for a header).
4. **Add a `docs/SOURCES.md` entry** mirroring the existing blocks: short title, ingest source slug,
   offset, the `iaccm ingest …` command, and a partial type→page (or class→concordance) index.
5. **Pilot one entry**, eyeball it, then batch-ingest:
   ```bash
   iaccm ingest corpus/<file>.pdf --source <slug> --pages <small-range>      # pilot, live
   iaccm show "<an id it produced>"                                          # confirm the bbox page
   iaccm ingest corpus/<file>.pdf --source <slug> --pages <full> --batch     # full run (~50% cheaper)
   ```
   Ingest is incremental and resumable — a dropped run re-runs the same command and skips finished
   pages/classes.

## Tests that keep it honest

- `tests/test_profiles.py` — a no-model contract test runs over **every** profile automatically
  (slug self-consistent, prompt composes, offset/dpi/layout sane). A malformed new entry fails here.
- `tests/test_windows.py` — for `class-window` books, a corpus-gated test asserts the scanner finds
  the expected contiguous run of classes (the rule-2 guard against an OCR-fused header). Self-skips
  if the PDF is absent.
- `eval/ingest/<slug>.yaml` + `eval/test_ingest.py` — opt-in (`pytest -m ingest`) structural goldens:
  a few **hand-verified** classes must yield a complete record (right id, fields populated, published
  concordances present, drawing located). Hand-verify against the real book — never fabricate.
