# bundle/ — the shareable derived product

This directory holds the **distributable** output of ingest: `catalog.jsonl`, one JSON record per
published typology form. It is committed to the repo on purpose.

It contains **facts only** — our own paraphrased descriptions, dates, part types, archetype tags,
printed-page pointers, normalized profile bounding boxes, and cross-references between typologies.
It contains **no** copyrighted plate images and **no** verbatim book text, so distributing it is
fine (docs/copyright.md). The copyright firewall is about the source PDFs, not the derived facts.

To use a distributed bundle: drop your own copy of the cited PDFs into `corpus/` and the pointers
resolve against your file (matched by checksum, else by filename, else the only PDF present).
Rendered crops/pages are produced locally on demand and stay git-ignored (`.cache/`, `*.plate.png`).
