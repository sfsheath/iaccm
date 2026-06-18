"""Typed data models shared across modules. Facts only — safe to store and share; no
copyrighted plate content ever lives in these records (see docs/copyright.md)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class PartType(StrEnum):
    RIM = "rim"
    BASE = "base"
    FOOT = "foot"
    WALL = "wall"
    HANDLE = "handle"
    KNOB = "knob"
    LID = "lid"
    SPOUT = "spout"
    TOE = "toe"  # amphora spike/toe (pointed base)
    COMPLETE = "complete"
    UNKNOWN = "unknown"


class SourcePointer(BaseModel):
    """A citation into a user-held PDF — a two-layer locator for one form's profile.

    Layer 1 (semantic, robust, always): page + the printed figure/plate label + the item number
    on that plate, mirroring how the book itself refers to the drawing. Layer 2 (geometry, for
    isolating the drawing): a normalized bbox on the page. Carries a pointer, never page content.
    """

    short_title: str  # e.g. "DICOCER (Lattara 6)"
    source_file: str | None = None  # original PDF filename, to resolve a recipient's drop-in copy
    page_printed: int  # printed page number
    page_pdf: int | None = None  # resolved PDF page (printed + offset)
    checksum: str | None = None  # exact-match verification of the user's local file
    figure_label: str | None = None  # printed plate/figure label, e.g. "Pl. CLAIR-C, fig. 9"
    item_label: str | None = None  # item number within the plate, e.g. "11"
    bbox: list[float] | None = None  # normalized [x0, y0, x1, y1] on the page; None → whole page


class FormRecord(BaseModel):
    """One published typology form."""

    id: str  # e.g. "CLAIR-C Dn9.11"
    ware: str  # e.g. "CLAIR-C"
    vessel_class: str  # canonical English shape, e.g. "lid", "bowl/dish" (see catalog.vessel_class)
    part_types: list[PartType] = Field(default_factory=list)
    description: str = ""  # our own paraphrase of the diagnostic attributes
    attributes: dict[str, str] = Field(default_factory=dict)  # {"rim": "everted/raised", ...}
    origin: str | None = None  # production origin/region, e.g. "Baetica" (amphora discriminator)
    contents: str | None = None  # transported product, e.g. "wine" / "oil" (amphora discriminator)
    date_start: int | None = None  # negative = BCE
    date_end: int | None = None
    archetype_ids: list[str] = Field(default_factory=list)
    cross_refs: list[str] = Field(default_factory=list)  # printed equivalences, e.g. ["Hayes 50B"]
    source: SourcePointer | None = None

    def union(self, other: FormRecord) -> FormRecord:
        """Combine two records that share an ``id`` into one, without either clobbering the other.

        Used when a form is catalogued across pages — e.g. its TEXT entry (description, dates,
        cross-refs) and its FIGURE drawing (bbox, shape-read parts) live on different pages of the
        same book. Field-level: the richer scalar wins, lists dedup-union, and the bbox-bearing
        source pointer is kept so ``show`` can still crop the drawing. Idempotent (``r.union(r) ==
        r``); intended for same-``id`` records, so callers should not union unrelated forms."""

        def richer(a: str, b: str) -> str:
            return a if len(a.strip()) >= len(b.strip()) else b

        def ulist(a: list[str], b: list[str]) -> list[str]:  # order-stable dedup union
            out = list(a)
            out.extend(x for x in b if x not in out)
            return out

        parts: list[PartType] = list(self.part_types)
        parts.extend(p for p in other.part_types if p not in parts)
        parts = [p for p in parts if p != PartType.UNKNOWN] or parts
        # keep whichever source carries a drawing, so the geometry survives
        source = self.source
        if other.source and other.source.bbox and not (self.source and self.source.bbox):
            source = other.source
        return self.model_copy(
            update={
                "ware": self.ware or other.ware,
                "vessel_class": self.vessel_class or other.vessel_class,
                "description": richer(self.description, other.description),
                "attributes": {**other.attributes, **self.attributes},
                "origin": self.origin if self.origin is not None else other.origin,
                "contents": self.contents if self.contents is not None else other.contents,
                "date_start": self.date_start if self.date_start is not None else other.date_start,
                "date_end": self.date_end if self.date_end is not None else other.date_end,
                "archetype_ids": ulist(self.archetype_ids, other.archetype_ids),
                "cross_refs": ulist(self.cross_refs, other.cross_refs),
                "part_types": parts,
                "source": source,
            }
        )


class Candidate(BaseModel):
    form: FormRecord
    score: float = 0.0
    why: str = ""


class Discriminator(BaseModel):
    """A single feature separating leading candidates; surfaced to the human."""

    feature: str  # e.g. "rim profile"
    options: list[str]  # e.g. ["everted/raised", "plain rounded", "collared"]
    splits: dict[str, str] = Field(default_factory=dict)  # option -> form id


class Identification(BaseModel):
    best: Candidate | None = None
    ranked: list[Candidate] = Field(default_factory=list)
    confidence: str = "low"  # low | moderate | high
    reasoning: str = ""
    discriminators_used: list[Discriminator] = Field(default_factory=list)
    what_would_narrow: str = ""
    citations: list[SourcePointer] = Field(default_factory=list)
