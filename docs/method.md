# Identification method — the cascade

This is the *product logic*. The agent code in `src/iaccm/agent` implements it; keep behavior
aligned with this document.

## Principle

A small diagnostic sherd is ambiguous. The danger is narrowing to a wrong type before the full
candidate set has even been looked at. So the method is **coarse → fine, breadth before depth**,
with the model doing constrained visual comparison (never recall) and the human supplying the one
discriminator that settles ties.

## Cascade

1. **Intake.** Collect the user's opening input: photo(s), find-spot/region, fabric notes,
   scale, and which **part** the fragment is (rim, base, wall, handle, knob, lid). Scale matters —
   typology drawings are at 1:4 / 1:5 and diameter is a primary discriminator.
2. **Triage** to a broad category by the most salient signal (usually surface + fabric):
   fine ware, coarse/cooking ware, amphora, lamp. See `docs/typologies/*.md` for the keys.
3. **Part-first when the part recurs across wares.** Lids, bases, and handles appear in many
   wares. Retrieve the *full* candidate set for that part-type across all relevant wares — do not
   let a single ware be dropped on a weak signal. (This is the founding-bug guardrail.)
4. **Retrieve candidates** from the index (structured filter + vector + archetype funnel) and
   open *only* the relevant plate pages from the user's own PDF.
5. **Compare** the photo against the retrieved candidate plates. Identify the one feature that
   separates the leaders.
6. **Ask the human** for that discriminator rather than guessing (e.g. everted/raised rim vs.
   plain rounded edge; presence of sooting; rim diameter).
7. **Conclude**: a ranked identification with the reasoning, a confidence level, citations to the
   user's PDF page(s), and an explicit *what would narrow it further*.
8. **Record** the result as an `eval/cases/*.yaml` regression case.

## Output format

- **Best identification** — form id (e.g. `CLAIR-C Dn9.11`), plain-language name, ware, date range.
- **Ranked candidates** — each with source reference, region, date, and a confidence level.
- **Diagnostic reasoning** — what in the fabric/surface/profile drove the call.
- **Discriminator(s) used** — the feature(s) that separated the leaders, and the human input relied on.
- **What would narrow it** — the photo/section/measurement that would raise confidence.

## Worked reference case (the regression seed)

A brick-red, matte-to-semi-lustrous slipped fragment with a central knob, a rouletted/grooved
upper face, and an **everted, raised rim**. Misread first as a dish base, then as a generic ARS
lid. The full African-lid candidate set is `CLAIR-A 16` (collared edge), `CLAIR-D At53.5` (plain
rounded edge), `CLAIR-C Dn9.11` (internal lug + **raised/everted rim**). The raised rim is the
discriminator → **CLAIR-C Dn9.11** (Deneauve 1974 fig. 9 no. 11 = Atlante I XXXI,10; 450/520).
Encoded in `eval/cases/dn9_11_lid.yaml`.
