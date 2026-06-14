# Copyright firewall

This is a load-bearing design constraint, not a footnote. Build every feature to respect it.

## The line

- **Facts are free.** Form numbers (e.g. `CLAIR-C Dn9.11`), names, date ranges, the
  vessel class, page numbers, and attribute descriptions *we author* are facts or our own
  expression. These may be stored and shared.
- **The plates and book text are copyrighted.** Line drawings and the typology's own prose
  live **only** in the user's own legally-obtained PDF. They are rendered on demand from that
  local file and are **never** bundled, exported, or committed.

## Consequences for the code

1. `corpus/` is git-ignored. Source PDFs never enter version control.
2. Rendered pages/crops are a transient cache, also ignored. Do not add a feature that exports
   plate images.
3. The **shareable index bundle** = catalog records + original archetype silhouettes + page
   pointers + (optionally) derived feature vectors. No plates, no book text.
4. Page pointers reference a source by short title + page (`DICOCER (Lattara 6), p. 188`) and
   bind to a user's file by content checksum. A colleague's bundle renders nothing until the
   matching PDF is present locally.
5. Derived feature vectors (embeddings) are representations, not reproductions; still, keep them
   out of the public bundle unless we are confident they cannot reconstruct the image.

When in doubt: would this let someone who lacks the book obtain its drawings or text? If yes,
it does not ship.
