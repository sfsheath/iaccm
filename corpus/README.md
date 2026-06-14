# corpus/ — your own typology PDFs (never committed)

Git-ignored on purpose. **Source typologies are copyrighted**; the app processes the copy *you*
legally hold, on *your* machine, for *your* research. Nothing here is redistributed.

Drop your PDFs here, then run `iaccm ingest corpus/<file>.pdf` to build a local index. The index
that you can share with collaborators contains only **facts and derived data** — form numbers,
descriptions, date ranges, page pointers, and original archetype silhouettes — never the plates
or book text (see `../docs/copyright.md`). Each PDF is bound to its index records by a content
checksum, so a colleague's bundle renders nothing until the matching PDF is present locally.

Seed index expects:

- `Lattara_6_Dicocer_dictionnaire_des_ceram.pdf` — DICOCER (Lattara 6).
