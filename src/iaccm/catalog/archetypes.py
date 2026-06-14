"""The profile-archetype vocabulary.

A deliberately coarse, copyright-clean controlled vocabulary of ~20 gross profile shapes
spanning the repertoire. A human or agent picks the 1-2 closest archetypes for an unknown
profile, which narrows the candidate forms to open in the PDF. The silhouettes are our own
original schematic drawings (``svg``) — never crops of copyrighted plates.

This is the antidote to the founding bug: the funnel groups forms by *gross shape across all
wares*, so picking "conical knobbed lid" surfaces the lid forms in CLAIR-A, CLAIR-C and
CLAIR-D together, instead of a text search silently dropping a ware.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .models import PartType


class Archetype(BaseModel):
    id: str
    name: str
    gloss: str
    part_types: list[PartType] = Field(default_factory=list)
    svg: str | None = None  # TODO: original schematic silhouette (NOT a plate crop)


ARCHETYPES: list[Archetype] = [
    # --- open forms ---
    Archetype(id="O-PLATE-FLAT", name="flat plate", gloss="shallow, near-flat floor, simple rim", part_types=[PartType.RIM, PartType.BASE]),
    Archetype(id="O-DISH-FLARED", name="flaring dish", gloss="open dish, walls flare from a low foot", part_types=[PartType.RIM, PartType.BASE]),
    Archetype(id="O-BOWL-HEMI", name="hemispherical bowl", gloss="rounded half-sphere wall", part_types=[PartType.RIM, PartType.WALL]),
    Archetype(id="O-BOWL-CARIN", name="carinated bowl", gloss="sharp angle (carination) in the wall", part_types=[PartType.RIM, PartType.WALL]),
    Archetype(id="O-BOWL-FLANGE", name="flanged bowl", gloss="projecting horizontal flange below the rim", part_types=[PartType.RIM]),
    Archetype(id="O-CUP-CONICAL", name="conical cup", gloss="straight-sided cone opening upward", part_types=[PartType.RIM, PartType.WALL]),
    Archetype(id="O-BASIN-DEEP", name="deep basin / mortarium", gloss="thick, deep open form, often heavy rim", part_types=[PartType.RIM]),
    # --- lids ---
    Archetype(id="L-CONE-KNOB", name="conical knobbed lid", gloss="cone rising to a central knob handle", part_types=[PartType.LID, PartType.KNOB]),
    Archetype(id="L-DOME", name="domed lid", gloss="smoothly domed, knob optional", part_types=[PartType.LID, PartType.KNOB]),
    Archetype(id="L-DISC-FLAT", name="flat disc lid", gloss="flat, plate-like lid", part_types=[PartType.LID]),
    Archetype(id="L-FLANGE-LUG", name="flanged / lugged lid", gloss="edge with a projecting collar or internal seating lug", part_types=[PartType.LID]),
    # --- closed forms ---
    Archetype(id="C-JAR-NECK", name="necked jar", gloss="constricted neck, everted rim", part_types=[PartType.RIM]),
    Archetype(id="C-JUG", name="jug / pitcher", gloss="closed pouring form, single handle", part_types=[PartType.RIM, PartType.HANDLE]),
    Archetype(id="C-FLASK-UNG", name="flask / unguentarium", gloss="small narrow-mouthed closed form", part_types=[PartType.RIM]),
    Archetype(id="C-AMPH-RIM", name="amphora rim/neck", gloss="thick transport-amphora rim and neck", part_types=[PartType.RIM]),
    Archetype(id="C-AMPH-TOE", name="amphora toe", gloss="solid spike/toe base of an amphora", part_types=[PartType.BASE]),
    # --- bases & handles ---
    Archetype(id="B-RING-FOOT", name="ring foot", gloss="annular foot ring below a floor", part_types=[PartType.FOOT, PartType.BASE]),
    Archetype(id="B-FLAT", name="flat base", gloss="simple flat resting base", part_types=[PartType.BASE]),
    Archetype(id="B-PEDESTAL", name="pedestal foot", gloss="raised, splaying foot or stem", part_types=[PartType.FOOT]),
    Archetype(id="H-STRAP-ROD", name="strap / rod handle", gloss="handle section, strap (flat) or rod (round)", part_types=[PartType.HANDLE]),
]

ARCHETYPES_BY_ID: dict[str, Archetype] = {a.id: a for a in ARCHETYPES}
