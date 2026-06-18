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
    svg: str | None = None  # original schematic silhouette (our line art, NEVER a plate crop)


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
    Archetype(id="C-AMPH-TOE", name="amphora toe", gloss="solid spike/toe base of an amphora", part_types=[PartType.TOE, PartType.BASE]),
    # --- whole transport amphorae (gross body shape, for one-type-per-page typologies) ---
    Archetype(id="A-OVOID", name="ovoid amphora", gloss="rounded ovoid body tapering to a toe (Corinthian, Greco-Italic)", part_types=[PartType.COMPLETE, PartType.RIM, PartType.HANDLE, PartType.TOE, PartType.WALL]),
    Archetype(id="A-FUSIFORM", name="spindle / fusiform amphora", gloss="long slender body tapering at both ends (Massaliote, Ionian)", part_types=[PartType.COMPLETE, PartType.RIM, PartType.HANDLE, PartType.TOE, PartType.WALL]),
    Archetype(id="A-CYLINDRICAL", name="cylindrical amphora", gloss="straight tubular body, short toe (African cylindrical)", part_types=[PartType.COMPLETE, PartType.RIM, PartType.HANDLE, PartType.TOE, PartType.WALL]),
    Archetype(id="A-CARROT", name="carrot / sausage amphora", gloss="elongated body narrowing steadily to a point, no distinct toe", part_types=[PartType.COMPLETE, PartType.RIM, PartType.HANDLE, PartType.TOE, PartType.WALL]),
    Archetype(id="A-FLATBASE", name="flat-bottomed amphora", gloss="ovoid body on a flat base, no toe (Gauloise 4)", part_types=[PartType.COMPLETE, PartType.RIM, PartType.HANDLE, PartType.BASE, PartType.WALL]),
    Archetype(id="A-PIRIFORM", name="piriform / bag amphora", gloss="pear/bag-shaped body widest low down (Almagro, some African)", part_types=[PartType.COMPLETE, PartType.RIM, PartType.HANDLE, PartType.TOE, PartType.WALL]),
    Archetype(id="A-CONICAL-RIBBED", name="conical ribbed amphora", gloss="conical ribbed body narrowing to a point (Late Roman 1/2)", part_types=[PartType.COMPLETE, PartType.RIM, PartType.HANDLE, PartType.TOE, PartType.WALL]),
    # --- bases & handles ---
    Archetype(id="B-RING-FOOT", name="ring foot", gloss="annular foot ring below a floor", part_types=[PartType.FOOT, PartType.BASE]),
    Archetype(id="B-FLAT", name="flat base", gloss="simple flat resting base", part_types=[PartType.BASE]),
    Archetype(id="B-PEDESTAL", name="pedestal foot", gloss="raised, splaying foot or stem", part_types=[PartType.FOOT]),
    Archetype(id="H-STRAP-ROD", name="strap / rod handle", gloss="handle section, strap (flat) or rod (round)", part_types=[PartType.HANDLE]),
]

# --- original schematic silhouettes -------------------------------------------------------
# Each is our own coarse half-profile drawn as a polyline in a 0–100 box (vessel centerline on the
# right, ~x=84). These are deliberately gross "shape tokens," not faithful renderings, and never
# crops of copyrighted plates. They give the human/model a shared visual vocabulary for the coarse
# triage step ("what gross shape is this?"). Refine freely; the ids are the contract, not the art.
_PROFILES: dict[str, list[tuple[int, int]]] = {
    # open forms — rim at top-left, floor running to the axis at bottom
    "O-PLATE-FLAT": [(12, 56), (18, 60), (84, 62)],
    "O-DISH-FLARED": [(10, 34), (30, 52), (40, 66), (60, 66), (60, 70), (84, 70)],
    "O-BOWL-HEMI": [(14, 30), (16, 44), (24, 58), (40, 68), (60, 72), (84, 73)],
    "O-BOWL-CARIN": [(16, 30), (34, 30), (44, 50), (52, 68), (84, 70)],
    "O-BOWL-FLANGE": [(34, 38), (12, 40), (34, 42), (42, 48), (50, 66), (84, 68)],
    "O-CUP-CONICAL": [(20, 28), (44, 70), (84, 72)],
    "O-BASIN-DEEP": [(16, 26), (24, 28), (24, 32), (30, 68), (84, 70)],
    # lids — rim at bottom-left, sloping up to apex/knob near the axis at top
    "L-CONE-KNOB": [(16, 64), (78, 18), (78, 10), (86, 10), (86, 18)],
    "L-DOME": [(16, 62), (30, 40), (52, 24), (74, 18), (86, 16)],
    "L-DISC-FLAT": [(14, 40), (18, 44), (86, 44), (86, 40)],
    "L-FLANGE-LUG": [(16, 40), (28, 40), (28, 48), (40, 34), (62, 30), (86, 28)],
    # closed forms — constricted neck/rim at top, body below, base at bottom
    "C-JAR-NECK": [(58, 14), (50, 18), (48, 30), (28, 52), (46, 78), (84, 80)],
    "C-JUG": [(50, 14), (60, 12), (58, 18), (46, 28), (34, 52), (48, 80), (84, 82)],
    "C-FLASK-UNG": [(54, 12), (50, 14), (50, 30), (44, 40), (48, 64), (60, 78), (84, 80)],
    "C-AMPH-RIM": [(40, 14), (34, 16), (34, 22), (40, 24), (40, 46), (84, 48)],
    "C-AMPH-TOE": [(38, 18), (38, 60), (50, 82), (62, 60), (62, 18)],
    # whole transport amphorae — half-profile, rim at top, toe/base at bottom, axis at right (~x=84)
    "A-OVOID": [(66, 12), (58, 18), (40, 40), (36, 54), (52, 76), (74, 88), (84, 90)],
    "A-FUSIFORM": [(72, 10), (64, 18), (46, 40), (44, 56), (56, 78), (78, 92), (84, 94)],
    "A-CYLINDRICAL": [(60, 14), (40, 22), (38, 30), (38, 66), (46, 80), (64, 90), (84, 92)],
    "A-CARROT": [(40, 16), (38, 24), (44, 50), (56, 72), (76, 90), (84, 92)],
    "A-FLATBASE": [(58, 14), (46, 22), (34, 42), (40, 64), (52, 78), (52, 82), (84, 82)],
    "A-PIRIFORM": [(60, 14), (50, 20), (40, 40), (30, 60), (40, 76), (64, 86), (84, 88)],
    "A-CONICAL-RIBBED": [(36, 18), (40, 28), (48, 46), (58, 66), (76, 88), (84, 90)],
    # bases & handles
    "B-RING-FOOT": [(14, 40), (40, 44), (40, 60), (48, 60), (48, 44), (84, 44)],
    "B-FLAT": [(14, 44), (18, 58), (84, 58)],
    "B-PEDESTAL": [(24, 42), (40, 46), (36, 62), (26, 76), (50, 78), (84, 78)],
    "H-STRAP-ROD": [(40, 18), (28, 30), (28, 70), (40, 82), (52, 70), (52, 30), (40, 18)],
}


def _svg(points: list[tuple[int, int]]) -> str:
    pts = " ".join(f"{x},{y}" for x, y in points)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        f'<polyline points="{pts}" fill="none" stroke="#222" stroke-width="2.5" '
        'stroke-linejoin="round" stroke-linecap="round"/></svg>'
    )


for _a in ARCHETYPES:
    _a.svg = _svg(_PROFILES[_a.id])

ARCHETYPES_BY_ID: dict[str, Archetype] = {a.id: a for a in ARCHETYPES}
