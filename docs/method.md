# Identification method — the cascade

This is the *product logic*. The agent code in `src/iaccm/agent` implements it; keep behavior
aligned with this document.

## Principle

A small diagnostic sherd is ambiguous. The danger is narrowing to a wrong type before the full
candidate set has even been looked at. So the method is **coarse → fine, breadth before depth**,
with the human supplying the one discriminator that settles ties.

### Two layers — keep them distinct

- **Hypothesis (the model's knowledge).** From fabric, surface/gloss, decoration and form, the
  model triages to a ware **family** and may name a likely form by its common cross-reference
  (e.g. "Dragendorff 29", "Hayes 50"), **grounded in observables it can point to** — never free
  recall. This is encouraged: it steers retrieval and tells the user what to look for.
- **Identification (the deliverable).** A specific form chosen **only from the supplied catalogue**
  by visual comparison, cited to the user's PDF. Never invent a catalogue form or citation from
  memory (the copyright firewall + rule 3 protect *this* layer, not the hypothesis layer).

A catalogue match is tagged **in_family** / **cross_ref** / **shape_analogue**. Only an *in_family*
match (or one the user confirms) may be the conclusion. If the hypothesised family is **not in the
catalogue**, say so plainly (coverage gap) and do **not** dress a cross-family shape-analogue as the
answer. Concluding the wrong family because a catalogue form merely *cites* the right form's
cross-reference number (a shared shape lineage) is the classic failure this rule exists to prevent.

### Breadth invariant (non-negotiable)

Breadth is bounded **only by a directly-observable part-type** (`store.by_part`). Family, ware,
region and cross-reference are **ordering boosts, never membership filters**. A model triage of
"this is terra sigillata" must never remove a candidate before comparison — family triage is the
error-prone step, so gating breadth on it reintroduces the founding bug (CLAIR-C) in a scaling
costume. When the catalogue grows too large to show in full, omit only by **visible rank within a
part-type set** ("N more rims not shown — say 'widen'"), never by hidden family/ware inference.

## Triage key — which diagnostic key to load

Triage to one broad **category** by the most salient signals; the matching key then loads to refine
(it is **not** loaded until the sherd has narrowed to it). Report the category as one token:

| `category` | Salient cue (category-level — not a ware ID) | Key that loads |
|---|---|---|
| `fineware`   | slipped / gloss tableware — cups, bowls, dishes, plates | `docs/typologies/finewares.md` |
| `coarseware` | unslipped or sooted utilitarian / cooking wares, common wares | `docs/typologies/coarsewares.md` |
| `amphora`    | thick-walled transport container; rim+neck, handles, spike/toe | `docs/typologies/amphorae.md` |
| `lamp`       | lamp (nozzle, discus, filling-hole) | `docs/typologies/lamps.md` |

If you cannot yet tell, leave `category` empty and reason from the candidate set; refine it as the
dialogue narrows. The detailed ware discriminators live in the loaded key, never in this file.

## Cascade

1. **Intake.** Collect the user's opening input: photo(s), find-spot/region, fabric notes,
   scale, and which **part** the fragment is (rim, base, wall, handle, knob, lid). Scale matters —
   typology drawings are at 1:4 / 1:5 and diameter is a primary discriminator.
2. **Triage** to a broad category, then toward a ware **family**, by the most salient signals
   (surface, fabric, decoration, form) — *before* ranking any forms — and consult the matching
   `docs/typologies/*.md` key. Weigh signals together; never fix a specific ware from one signal
   alone (gloss, colour, or shape in isolation underdetermines the ware — many families are glossy
   and many are red). The **family- and ware-specific discriminators live in the category/ware
   docs, not here**; this step only gets to the right key. (One general caution: a cross-reference
   number that a form *cites* — a Dragendorff/Hayes/Lamboglia number — is a shape lineage, not a
   ware identification.)
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

## Output format

- **Best identification** — form id (e.g. `CLAIR-C Dn9.11`), plain-language name, ware, date range.
- **Ranked candidates** — each with source reference, region, date, and a confidence level.
- **Diagnostic reasoning** — what in the fabric/surface/profile drove the call.
- **Discriminator(s) used** — the feature(s) that separated the leaders, and the human input relied on.
- **What would narrow it** — the photo/section/measurement that would raise confidence.

Specific worked identifications are not narrated here — they live as regression cases in
`eval/cases/*.yaml`, where each real find encodes its intake, the candidate set retrieval must
surface, and the confirmed conclusion.
