"""Per-source ingest profiles.

DICOCER and Sciallano & Sibella 1994 are the same *genre* (published ceramic typologies) but
idiosyncratic in layout, identity scheme, media and metadata. A ``SourceProfile`` bundles the
scalar knobs (offset, dpi, title) plus a source-specific ``prompt_body`` that describes that book's
layout/identity/metadata conventions. They all sit on top of one shared ``BASE_PROMPT`` that owns
the non-negotiables (breadth-before-depth, paraphrase-don't-copy, archetype tagging, bbox, the
copyright firewall) so every future source inherits them. Adding a third book is a registry entry,
not a fork (CLAUDE.md: "ingest them all").

Keep these concrete: params + a prompt string. No prompt-fragment DSL, no checksum auto-detection —
design discovered from real books, not imagined ones.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from ..catalog.archetypes import ARCHETYPES
from ..catalog.models import PartType


class SourceProfile(BaseModel):
    slug: str  # selector, e.g. "dicocer" | "sciallano-1994"
    short_title: str  # stored on every SourcePointer.short_title
    page_offset: int  # printed page + offset = 1-based PDF page
    dpi: int = 200
    # The render TOPOLOGY — the one thing that ever forks code. "forms-per-page": many forms on a
    # plate (DICOCER). "entry-per-page": one catalogue entry per page, occasionally a spread
    # (Sciallano). "class-window": one entry spanning MULTIPLE pages whose continuation pages carry
    # no identity anchor, so it is rendered as one multi-image call (Peacock & Williams). See
    # ingest/windows.py.
    layout: Literal["forms-per-page", "entry-per-page", "class-window"]
    prompt_body: str  # source-specific layout/identity/metadata instructions
    # class-window only: a regex with ONE integer capture group that locates an entry header on a
    # rendered page's text layer (used to set window boundaries; extraction stays visual). Match is
    # MULTILINE — anchor with ^ so a running-text mention ("see Class 27") is not mistaken for a
    # header. Required when layout == "class-window".
    window_header: str | None = None


def _archetype_menu() -> str:
    return "\n".join(f"  {a.id}: {a.name} — {a.gloss}" for a in ARCHETYPES)


# Non-negotiables shared by every source. {layout_body} is the per-profile section; the page
# context (title + printed page) is appended last by build_prompt().
BASE_PROMPT = """You are cataloguing the published ceramic typology "{short_title}" \
(printed page {printed_page}). The page image is attached.

Breadth is critical (this is the project's first rule): enumerate EVERY distinct published form
relevant to this page — never skip one and never merge two forms into one. A missed form becomes
an unfindable candidate later.

Copyright: return FACTS ONLY. Paraphrase diagnostic features IN YOUR OWN WORDS — never copy the
book's sentences verbatim. We store pointers and facts, never page content.

{layout_body}

For each form return:
- ware: see the layout note above.
- form_id: see the layout note above.
- vessel_class: the shape word(s) exactly as printed in the book's own language (do not translate \
yourself — it is canonicalized to English downstream).
- part_types: zero or more of: {part_values}.
- description: a SHORT paraphrase of the diagnostic features (rim, wall, base, decoration).
- origin / contents: production origin/region and transported product if the page states them
  (e.g. origin "Baetica", contents "wine"); else null.
- date_start / date_end: years if given (negative = BCE), else null.
- cross_refs: any printed equivalences to OTHER typologies (e.g. "Hayes 50B", "Lamboglia 40").
- archetype_ids: the 1–2 closest gross-shape archetypes from this controlled vocabulary:
{archetype_menu}
- figure_label / item_label: the printed plate/figure label and the item number on it, if shown.
- bbox: if this form's PROFILE DRAWING appears on this page, a tight normalized box
  [x0,y0,x1,y1] (0–1, origin top-left) around just that drawing; null if it is only described.
"""


_DICOCER_BODY = """This page is a typology plate: it may carry MANY distinct numbered forms, \
grouped under a running ware header.
- ware: the running ware/header on the page (e.g. "CLAIR-C").
- form_id: the printed catalogue number exactly as shown (e.g. "Dn 9.11", "16")."""


_SCIALLANO_BODY = """This page is one catalogue entry: ONE named amphora type per page (a few span \
two pages — use the same id on both so they merge). Some pages are section dividers or photo-only \
spreads with no new type — return no forms for those.
- ware: the production-region / cultural family, in French as the book groups them, e.g.
  "Amphore italique", "Amphore gauloise", "Amphore de Bétique", "Amphore africaine",
  "Amphore grecque", "Amphore orientale". This is the coarse retrieval axis; the finer place goes
  in `origin`.
- form_id: the canonical type NAME as printed and as specialists cite it — e.g. "Dressel 1A",
  "Gauloise 4", "Pascual 1", "Beltrán IIB", "Africaine II", "Late Roman 1". This book has no
  catalogue numbers; the name IS the identity.
- part_types: whole amphorae are rarely found whole — users photograph a sherd. Tag EVERY \
diagnostic part the drawing shows (rim, handle, toe, wall) AND `complete`, so a rim/toe/handle \
sherd still retrieves this type. Do not tag `complete` alone.
- The metadata box gives origin (Origine), contents (Produit transporté) and date range (Époque
  de circulation) — read them into `origin` / `contents` / `date_start` / `date_end`.
- The row of small drawings at the bottom are dated provenance VARIANTS of the same type — \
summarize them in `description` (with their dates if useful); do NOT emit them as separate forms.
- figure_label: the type title printed at the top of the entry (the robust locator for this book).
- bbox: the main large profile drawing near the top of the entry."""


_PEACOCK_BODY = """The attached images are ONE catalogue entry (a "class") of this book, spanning \
one or more pages. The FIRST image carries the entry header "CLASS N (...)"; later images are its \
continuation (sections ORIGIN, OCCURRENCE, PRINCIPAL CONTENT, DATE RANGE, FABRIC) and its profile \
drawing. The continuation pages do NOT repeat the class number, so use the header to fix identity.
Return EXACTLY ONE form: the class named in the "CLASS N" header. The TOP of the first image may \
show the tail of the PREVIOUS class, and the BOTTOM of the last image may show the head of the \
NEXT class — IGNORE both; extract only the named class.
- form_id: the entry number written as "Class N" (e.g. "Class 4"). This IS the identity.
- ware: the broad amphora family the class belongs to (e.g. "Roman amphora"); the specific \
production region goes in `origin`, not here.
- cross_refs: EVERY concordance the entry prints — the equivalent names in other typologies, \
chiefly the ones in the header parentheses (e.g. "Dressel 1B", "Ostia XX", "Camulodunum 181", \
"Callender 1"). These are how specialists cross-cite the type; capture them all.
- description: a SHORT paraphrase of DISTINCTIVE FEATURES (fold in a diagnostic phrase from FABRIC \
or OCCURRENCE if useful). Your own words — never copy the book's sentences.
- origin: the ORIGIN section (production area). contents: the PRINCIPAL CONTENT (transported good).
- date_start / date_end: the DATE RANGE in years (negative = BCE).
- part_types: tag EVERY diagnostic part the profile drawing shows (rim, handle, toe, wall) AND \
`complete`, so a sherd of any part still retrieves this class. Do not tag `complete` alone.
- figure_label: the drawing's printed caption (e.g. "Fig. 29").
- bbox: a tight box around the MAIN profile drawing only.
- bbox_image_index: the 0-based position, among the attached images, of the image the drawing is \
on (first attached image = 0). Required so the citation points at the right page."""


_ETTLINGER_BODY = """This is a two-page SPREAD of the Conspectus catalogue of Italian terra \
sigillata (Arretine). The LEFT page is descriptive text for ONE numbered Form (header "Form N", \
multilingual — German / English / French); the RIGHT page is that Form's plate ("Tafel"), with \
profile drawings of the Form's sub-types and their examples. There is NO usable text layer — read \
everything from the image.

Emit ONE record per TYPE at the X.Y level (e.g. 18.1, 18.2, 18.3) — the typology's \
granularity. The THIRD decimal (18.2.1, 18.2.2 …) marks specific EXAMPLE drawings of a type; do \
NOT emit a record per example. If a Form has no sub-types (only Form N with examples N.1, N.2 …), \
emit a single record with form_id "Conspectus N".
- ware: "Italian terra sigillata".
- form_id: the type number as "Conspectus X.Y" (e.g. "Conspectus 18.2"); this is the identity.
- vessel_class: the English shape word for this type (cup, bowl, dish, plate, beaker, lid …).
- item_label: the SINGLE most representative example number for this type (e.g. "18.2.2") — the \
nearest example a sherd would be matched to; null if the plate shows no sub-numbered examples.
- bbox: a tight box around that representative example drawing on the RIGHT (plate) half.
- part_types: tag every diagnostic part the profile shows (rim, wall, base, foot) AND `complete`.
- description: a SHORT paraphrase of the rim/wall/foot profile that distinguishes THIS type (and \
the spread of its examples). Your own words — never copy the book's sentences.
- origin / date_start / date_end: from the Form's text (Production, Date) if stated — usually \
given at the Form level and shared by its types.
- cross_refs: EVERY concordance the entry prints (Goudineau, Haltern, Dragendorff, Oxé …).
- figure_label: the plate label, e.g. "Tafel 17" (the plate number may differ from the Form no.).
A spread that is front-matter or back-matter (no "Form N" plate) has no forms — return none."""


_HAYES_BODY = """This is a page of Hayes 1972, a scanned typology of Late Roman fine wares. A page \
is one of two kinds — handle each:
(a) a TEXT catalogue page: bold "FORM N" headers, each followed by a prose description and then a \
numbered list of dated example specimens ("50. Ostia… D. c. 38…"). The running header is the \
BOOK TITLE, not the ware — ignore it.
(b) a FIGURE plate: grouped profile line-drawings, each labelled "FORM N", at a stated scale (e.g. \
"scale 1:3"), with no descriptive prose.
- form_id: the form label as "Form N", keeping any letter suffix with NO space ("Form 8A", \
"Form 99B"). Use this EXACT spelling on both text and figure pages so the two halves merge.
- ware: use the authoritative WARE stated above; it is not printed on the page.
- On a TEXT page, per FORM: paraphrase the diagnostic features (rim/wall/base/decoration) into \
`description` in your own words; SUMMARIZE the numbered dated examples into ONE `date_start`/\
`date_end` range for the form (negative = BCE) — do NOT emit individual specimens as forms; put \
printed equivalences (Lamboglia, Salomonson, Waagé, Ostia, Atlante…) in `cross_refs`; leave `bbox` \
null. Emit one record per FORM (often several per page).
- On a FIGURE plate, per labelled drawing: emit a record with `bbox` tight around THAT drawing and \
the part_types / archetype_ids you can read from its profile; `description` may be empty.
- A page that is neither (front matter, maps, photo plates) has no forms — return none."""


PROFILES: dict[str, SourceProfile] = {
    "dicocer": SourceProfile(
        slug="dicocer",
        short_title="DICOCER (Lattara 6)",
        page_offset=2,
        layout="forms-per-page",
        prompt_body=_DICOCER_BODY,
    ),
    "sciallano-1994": SourceProfile(
        slug="sciallano-1994",
        short_title="Sciallano & Sibella 1994",
        page_offset=0,  # user passes PDF page numbers directly; page_pdf is the locator of record
        layout="entry-per-page",
        prompt_body=_SCIALLANO_BODY,
    ),
    "peacock-1991": SourceProfile(
        slug="peacock-1991",
        short_title="Peacock & Williams 1991",
        page_offset=19,  # printed 82 → 1-based PDF 101 (catalogue Classes 1–55, printed pp.82–211)
        layout="class-window",
        window_header=r"^\s*CLASS\s+(\d{1,2})\b",  # all-caps header at line start; (n) = class no.
        prompt_body=_PEACOCK_BODY,
    ),
    "ettlinger-1990": SourceProfile(
        slug="ettlinger-1990",
        short_title="Ettlinger Conspectus 1990",
        page_offset=0,  # scanned two-page spreads; pass 1-based PDF page numbers (no text layer)
        dpi=200,  # large landscape pages, small reference text
        layout="entry-per-page",  # one Form per spread, but many X.Y type records per spread
        prompt_body=_ETTLINGER_BODY,
    ),
    "hayes-1972": SourceProfile(
        slug="hayes-1972",
        short_title="Hayes 1972 Late Roman Pottery",
        page_offset=0,  # scanned, no text layer; pass 1-based PDF page numbers (like Ettlinger)
        dpi=200,
        layout="forms-per-page",  # many "FORM N" per page; ware supplied per section via --ware
        prompt_body=_HAYES_BODY,
    ),
}


def get_profile(slug: str) -> SourceProfile:
    try:
        return PROFILES[slug]
    except KeyError:
        known = ", ".join(sorted(PROFILES))
        raise KeyError(f"unknown source profile {slug!r}; known: {known}") from None


def build_prompt(profile: SourceProfile, printed_page: int, ware: str | None = None) -> str:
    """Compose the full extraction prompt: shared base + profile layout body + page context.

    ``ware`` (from ``iaccm ingest --ware``) is for section-organized books whose ware never appears
    on the page: it is stated as authoritative context so the model assigns it to every form."""
    prompt = BASE_PROMPT.format(
        short_title=profile.short_title,
        printed_page=printed_page,
        layout_body=profile.prompt_body,
        part_values=", ".join(p.value for p in PartType),
        archetype_menu=_archetype_menu(),
    )
    if ware:
        prompt += (
            f"\nWARE (authoritative for this page range): every form on this page belongs to "
            f'"{ware}". Use it as the `ware` for all of them; ignore the page\'s running header.\n'
        )
    return prompt


__all__ = ["SourceProfile", "PROFILES", "get_profile", "build_prompt"]
