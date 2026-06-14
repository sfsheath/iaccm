"""Typed data models shared across modules. Facts only — safe to store and share; no
copyrighted plate content ever lives in these records (see docs/copyright.md)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class PartType(str, Enum):
    RIM = "rim"
    BASE = "base"
    FOOT = "foot"
    WALL = "wall"
    HANDLE = "handle"
    KNOB = "knob"
    LID = "lid"
    SPOUT = "spout"
    COMPLETE = "complete"
    UNKNOWN = "unknown"


class SourcePointer(BaseModel):
    """A citation into a user-held PDF. Carries a pointer, never the page content."""

    short_title: str  # e.g. "DICOCER (Lattara 6)"
    page_printed: int  # printed page number
    page_pdf: int | None = None  # resolved PDF page (printed + offset)
    checksum: str | None = None  # binds the pointer to the user's local file


class FormRecord(BaseModel):
    """One published typology form."""

    id: str  # e.g. "CLAIR-C Dn9.11"
    ware: str  # e.g. "CLAIR-C"
    vessel_class: str  # e.g. "couvercle / lid"
    part_types: list[PartType] = Field(default_factory=list)
    description: str = ""  # our own paraphrase of the diagnostic attributes
    attributes: dict[str, str] = Field(default_factory=dict)  # {"rim": "everted/raised", ...}
    date_start: int | None = None  # negative = BCE
    date_end: int | None = None
    archetype_ids: list[str] = Field(default_factory=list)
    source: SourcePointer | None = None


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
