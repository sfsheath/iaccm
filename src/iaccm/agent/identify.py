"""The identification cascade as a plain, testable dialog controller (docs/method.md).

The archaeologist opens with whatever they know, in free text ("I think it's an amphora" …
"Italian Sigillata, deep bowl"), optionally with a photo and/or profile drawing. Each turn the
controller hands the model the *retrieved candidate set* and asks it to RANK within that set —
the model compares, it never recalls a form from memory (CLAUDE.md rule 3) — then surfaces the
single best discriminating question for the human to answer (rule 4), until they converge on one
form. Retrieval supplies the full breadth set; the model orders, never drops (rule 2).

Kept deliberately simple (no LangGraph yet): a stateless structured call per turn, with the
conversation replayed in the prompt. Revisit a graph engine only if branching/interrupts grow.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from ..catalog.archetypes import ARCHETYPES
from ..catalog.models import FormRecord, PartType
from ..catalog.store import CatalogStore
from ..ingest.pdf import _to_part_types, render_candidate_crops  # reused seams
from ..model import ModelClient, get_model_client
from ..retrieve.search import Retriever
from .guidance import available_categories, load_category, load_method, normalize_category

# Cap the candidate block sent to the ranking call. 120 shows the largest single-part set that still
# fits comfortably (e.g. all 109 amphora toes) in full, and only trims the very large parts (rim,
# wall, base…) — by VISIBLE RANK within the part set, with a "widen" affordance, never by hidden
# ware/family pruning (docs/method.md; CLAUDE.md rule 2).
_CANDIDATE_CAP = 120

# How many candidate DRAWINGS to render + attach to the rank call. Kept small (each is a few image
# tokens) and family-stratified so every shape-plausible ware gets a drawing; raised on widen.
_DRAWING_CAP = 10
_DRAWING_CAP_WIDE = 24

_ARCH_IDS = {a.id for a in ARCHETYPES}  # valid archetype vocabulary (filter the model's triage)

_SYSTEM = (
    "You are an expert in Mediterranean ceramics helping an archaeologist identify a sherd. "
    "Work in TWO layers and keep them distinct:\n"
    "1) HYPOTHESIS (your knowledge): from the fabric, surface/gloss, decoration and form — plus "
    "the GUIDANCE keys provided — triage to a ware FAMILY (e.g. terra sigillata, Italian or "
    "Gaulish, vs. African Red Slip vs. black gloss …) and, when you can, name a likely typological "
    "form by its common cross-reference (e.g. 'Dragendorff 29', 'Hayes 50'). Ground every "
    "hypothesis in OBSERVABLES you can point to — describe the fabric, slip/gloss, decoration and "
    "profile you actually SEE (do not assert a ware from colour alone; slip colour overlaps across "
    "red-slip wares). Never recall a fact from thin air.\n"
    "2) IDENTIFICATION (the deliverable): a specific form chosen ONLY from the supplied candidate "
    "catalogue, by visual comparison — never invent a catalogue form or citation from memory.\n"
    "Rules: treat the archaeologist's stated ware/fabric as a strong (not absolute) constraint. "
    "Tag each catalogue match — 'in_family' (same ware family as your hypothesis), 'cross_ref' "
    "(matched only via a shared cross-reference number; beware shape-lineage false matches — an "
    "ARS form that cites 'Drag. 29' is NOT Italian Sigillata), or 'shape_analogue' (a cross-family "
    "lookalike). If your hypothesised family is NOT present among the candidates, say so plainly "
    "in coverage_note and DO NOT present shape-analogues as the answer. Only put a form in "
    "`conclusion` when it is an 'in_family' match (or one the archaeologist confirms). When "
    "candidates stay close, ask the SINGLE most discriminating question. You propose; the "
    "archaeologist decides."
)

_SYSTEM_TRIAGE = (
    "You are an expert in Mediterranean ceramics helping an archaeologist identify a sherd. "
    "This is the TRIAGE step — your knowledge / HYPOTHESIS layer; no catalogue is shown yet, "
    "so do not name a catalogue form. From the photo, the fabric/surface/decoration and the "
    "archaeologist's notes:\n"
    "1) Name the broad ware CATEGORY (its diagnostic key then loads).\n"
    "2) Report the observable diagnostic PART(s) of THIS fragment — rim, base, foot, wall, "
    "handle, knob, lid, spout, toe, complete. List EVERY part you can see: the next step retrieves "
    "the FULL candidate set for exactly these parts across all wares, so naming too few parts can "
    "hide the right form, while naming an extra costs only breadth. Use 'unknown' ONLY if you "
    "genuinely cannot tell, and then set part_question to ask which part it is.\n"
    "3) Read the fabric/surface/decoration to a ware FAMILY (fabric_reading, ware_family).\n"
    "4) When you can, name a likely typological form by its common cross-reference (e.g. "
    "'Dragendorff 29', 'Africana I') — grounded in observables you can point to, never recalled "
    "from thin air. You propose; the archaeologist decides."
)


class RankedCandidate(BaseModel):
    form_id: str  # must be one of the supplied candidate ids
    match_kind: Literal["in_family", "cross_ref", "shape_analogue"] = "shape_analogue"
    score: float  # 0..1 plausibility given everything known so far
    why: str  # one line: what fits, what doesn't


class TriageResult(BaseModel):
    """Call 1 — the HYPOTHESIS layer, produced WITHOUT a candidate list (rule-3 safe)."""

    understood: str = ""  # restatement of the user's stated knowledge as soft constraints
    category: str = ""  # broad triage category (fineware/coarseware/amphora/lamp); loads its key
    observed_parts: list[str] = Field(default_factory=list)  # every diagnostic part visible
    archetype_ids: list[str] = Field(default_factory=list)  # 1–2 gross shapes read from the photo
    fabric_reading: str = ""  # surface/fabric/decoration read and the family it implies
    ware_family: str = ""  # the triaged ware family + one-line rationale
    typological_hypothesis: str = ""  # likely form via cross-ref, grounded in cited observables
    part_question: str = ""  # set when no diagnostic part is determinable — asks the human


class RankResult(BaseModel):
    """Call 2 — the IDENTIFICATION layer, constrained to the retrieved part-bounded candidates."""

    candidates: list[RankedCandidate] = Field(default_factory=list)  # most likely first
    coverage_note: str = ""  # set when the hypothesised family is absent from the candidates
    question: str = ""  # the single best discriminator to ask the human; "" if concluding
    conclusion: str = ""  # chosen in-family catalogue form_id when confident; else ""
    confidence: str = "low"  # low | moderate | high


class TurnResult(BaseModel):
    understood: str = ""  # restatement of the user's stated knowledge as soft constraints
    category: str = ""  # broad triage category (fineware/coarseware/amphora/lamp); loads its key
    observed_parts: list[str] = Field(default_factory=list)  # the parts that bounded retrieval
    fabric_reading: str = ""  # surface/fabric/decoration read and the family it implies
    ware_family: str = ""  # the triaged ware family + one-line rationale (knowledge layer)
    typological_hypothesis: str = ""  # likely form via cross-ref, grounded in cited observables
    coverage_note: str = ""  # set when the hypothesised family is absent from the candidates
    candidates: list[RankedCandidate] = Field(default_factory=list)  # most likely first
    candidates_note: str = ""  # e.g. "showing top 120 of 1017 rim candidates — say 'widen'"
    question: str = ""  # the single best discriminator to ask the human; "" if concluding
    conclusion: str = ""  # chosen in-family catalogue form_id when confident; else ""
    confidence: str = "low"  # low | moderate | high


def _archetype_menu() -> str:
    return "\n".join(f"  {a.id}: {a.gloss}" for a in ARCHETYPES)


def _stratify_by_ware(forms: list[FormRecord], n: int) -> list[FormRecord]:
    """Pick up to ``n`` forms favouring WARE diversity: the best-ranked form of each not-yet-seen
    ware first, then backfill by rank. So every shape-plausible family gets a drawing in front of
    the model and a family-level error (e.g. ARS vs Italian sigillata) can be corrected visually,
    even when one ware dominates the ranked list."""
    picked: list[FormRecord] = []
    picked_ids: set[str] = set()
    for f in forms:  # one best representative per ware
        if f.ware not in {p.ware for p in picked}:
            picked.append(f)
            picked_ids.add(f.id)
            if len(picked) >= n:
                return picked
    for f in forms:  # backfill remaining slots by rank
        if f.id not in picked_ids:
            picked.append(f)
            picked_ids.add(f.id)
            if len(picked) >= n:
                break
    return picked


def _cap(total: int, show_all: bool) -> int:
    """How many ranked candidates to show: all of them when widened, else the top-N cap. Omission
    is by VISIBLE RANK within the (already part-bounded) set — never by hiding a ware (rule 2)."""
    return total if show_all else min(total, _CANDIDATE_CAP)


def _candidate_block(forms: list[FormRecord]) -> str:
    lines = []
    for f in forms:
        date = f"{f.date_start}..{f.date_end}" if f.date_start is not None else "n/a"
        parts = ",".join(p.value for p in f.part_types)
        xref = f"; refs: {', '.join(f.cross_refs)}" if f.cross_refs else ""
        lines.append(
            f"- {f.id} [{f.vessel_class}] parts={parts} date={date}: {f.description}{xref}"
        )
    return "\n".join(lines)


class Identifier:
    """Drives one identification dialogue over a catalog."""

    def __init__(
        self, catalog: CatalogStore | None = None, client: ModelClient | None = None
    ) -> None:
        self.catalog = catalog or CatalogStore()
        self.retriever = Retriever(self.catalog)
        self.client = client or get_model_client()
        self.images: list[Path] = []
        self.history: list[tuple[str, str]] = []  # (speaker, text)
        self.category: str = ""  # set once the sherd triages; loads that category's key
        self.part_types: list[PartType] = []  # last triaged observable parts (re-derived each turn)
        self.show_all: bool = False  # widen: send the full part set, not the top-N cap

    def step(
        self, user_text: str, images: list[Path] | None = None, show_all: bool = False
    ) -> TurnResult:
        """One dialogue turn as a two-call cascade (docs/method.md). Call 1 (TRIAGE) reads the photo
        to a category + the observable PART(s) + a family hypothesis, no catalogue shown. Call 2
        (RANK) compares the photo against the candidate set retrieved for exactly those parts.
        Narrowing by the observed part — never by an inferred ware (rule 2) — is what keeps the set
        tractable and the dialogue converging, instead of ranking the whole catalogue every turn."""
        if images:
            self.images = list(images)
        self.show_all = show_all
        convo = "\n".join(f"{who.upper()}: {text}" for who, text in self.history)
        cats = ", ".join(available_categories())

        # --- Call 1: TRIAGE (hypothesis layer; NO candidate list, so rule 3 cannot be violated) ---
        cat_key = load_category(self.category) if self.category else ""  # prior turn's category key
        triage_prompt = (
            f"METHOD & PRINCIPLES (ware-neutral; includes the triage key):\n{load_method()}\n\n"
            + (
                f"DIAGNOSTIC KEY — category '{self.category}' (use it):\n{cat_key}\n\n"
                if cat_key
                else f"(No category key loaded yet. Triage to one of: {cats}.)\n\n"
            )
            + f"ARCHETYPE VOCABULARY (gross shapes):\n{_archetype_menu()}\n\n"
            + (f"CONVERSATION SO FAR:\n{convo}\n\n" if convo else "")
            + f"THE ARCHAEOLOGIST SAYS:\n{user_text}\n\n"
            f"Triage now. Set `category` (one of: {cats}); list ALL `observed_parts` you can see "
            "(rim/base/foot/wall/handle/knob/lid/spout/toe/complete — 'unknown' only if truly "
            "indeterminate, then set `part_question`). Set `archetype_ids` to the 1–2 gross shapes "
            "from the ARCHETYPE VOCABULARY that best match the sherd's silhouette. Read "
            "`fabric_reading`/`ware_family`; give a `typological_hypothesis` by cross-reference if "
            "you can, grounded in observables."
        )
        triage = self.client.parse(
            triage_prompt, TriageResult, system=_SYSTEM_TRIAGE, images=self.images
        )
        norm = normalize_category(triage.category) if triage.category else None
        if norm:
            self.category = norm
            cat_key = load_category(self.category)  # reload for the rank call's guidance

        # --- Resolve observed part(s); retrieve the part-bounded breadth set (rule 2) -------------
        parts = _to_part_types(triage.observed_parts)
        real: list[PartType] = [p for p in parts if p != PartType.UNKNOWN]
        self.part_types = real or parts
        boost_text = f"{convo}\n{user_text}"
        prefer_wares, cross_ref_terms = self.retriever.boost_terms(boost_text)
        # The gross shape read from the photo orders shape-matching forms (any ware) to the top, so
        # a drawing slot isn't wasted on an amphora when the sherd is a bowl (ordering only, never a
        # filter — rule 2). Filter to the real vocabulary in case the model invents an id.
        archetypes = [a for a in triage.archetype_ids if a in _ARCH_IDS]
        ranked = (
            self.retriever.candidates_for_parts(
                real, archetype_ids=archetypes, prefer_wares=prefer_wares,
                cross_ref_terms=cross_ref_terms,
            )
            if real
            else self.retriever.all_candidates(
                archetype_ids=archetypes, prefer_wares=prefer_wares,
                cross_ref_terms=cross_ref_terms,
            )
        )

        # No diagnostic part visible: ask which part it is rather than rank the whole catalogue.
        if not real and triage.part_question:
            return self._finish(
                user_text,
                TurnResult(
                    understood=triage.understood,
                    category=self.category,
                    observed_parts=triage.observed_parts,
                    fabric_reading=triage.fabric_reading,
                    ware_family=triage.ware_family,
                    typological_hypothesis=triage.typological_hypothesis,
                    question=triage.part_question,
                ),
            )

        # Breadth guard (rule 2): the part-bounded set must be COMPLETE before any scaling.
        for p in real:
            if not self.retriever.verify_breadth(ranked, p):  # pragma: no cover - invariant
                raise RuntimeError(f"breadth violated: candidate set incomplete for part {p.value}")

        # --- Scale by VISIBLE RANK within the part set (never hide a ware — rule 2) ---------------
        forms = [c.form for c in ranked]
        total = len(forms)
        cap = _cap(total, self.show_all)
        shown = forms[:cap]
        note = ""
        if cap < total:
            label = "/".join(p.value for p in real) or "candidate"
            note = (
                f"(showing top {cap} of {total} {label} candidates by rank — "
                "say 'widen' / tick Show all to see the rest)"
            )

        # --- Render candidate DRAWINGS for visual comparison (rule 3: ground in the plates) -------
        # Family-stratified so each shape-plausible ware contributes a drawing; the FULL text set is
        # still sent (breadth, rule 2) — drawings are a visible-rank, family-diverse subset, never a
        # filter. Forms whose PDF/bbox can't be rendered stay text-only.
        n_draw = _DRAWING_CAP_WIDE if self.show_all else _DRAWING_CAP
        crops = render_candidate_crops(_stratify_by_ware(shown, n_draw), n_draw)
        rank_images = list(self.images) + [p for p, _ in crops]
        k = len(self.images)
        image_key = ""
        if crops:
            lines = [
                f"  image {k + i + 1}: drawing of candidate {fid}"
                for i, (_, fid) in enumerate(crops)
            ]
            sherd = f"  image 1–{k}: the SHERD photo(s) to identify.\n" if k else ""
            image_key = "ATTACHED IMAGES:\n" + sherd + "\n".join(lines) + "\n\n"

        # --- Call 2: RANK / COMPARE (identification layer; constrained to the retrieved set) ------
        triage_summary = (
            f"- category: {self.category}\n"
            f"- observed part(s): {', '.join(p.value for p in self.part_types)}\n"
            f"- fabric reading: {triage.fabric_reading}\n"
            f"- ware family (hypothesis): {triage.ware_family}\n"
            f"- typological hypothesis: {triage.typological_hypothesis}"
        )
        rank_prompt = (
            f"METHOD & PRINCIPLES (ware-neutral):\n{load_method()}\n\n"
            + (f"DIAGNOSTIC KEY — category '{self.category}':\n{cat_key}\n\n" if cat_key else "")
            + f"YOUR TRIAGE (the hypothesis to test against the catalogue):\n{triage_summary}\n\n"
            + (f"{note}\n" if note else "")
            + image_key
            + "CANDIDATE FORMS — retrieved for the observed part(s); the identification MUST be "
            f"one of these (ordered, never filtered by ware):\n{_candidate_block(shown)}\n\n"
            + (f"CONVERSATION SO FAR:\n{convo}\n\n" if convo else "")
            + f"THE ARCHAEOLOGIST SAYS:\n{user_text}\n\n"
            "Compare the SHERD's profile and decoration against the attached candidate DRAWINGS — "
            "a text description is no substitute for the drawing. Rank the candidates by fit, "
            "tagging "
            "each `match_kind` (in_family/cross_ref/shape_analogue); prefer a form whose DRAWING "
            "matches what you see (a form with no attached drawing is still valid — judge it from "
            "text). If your hypothesised family is absent from the candidates, set `coverage_note` "
            "and do NOT offer shape-analogues as the answer. Then either ask the single most "
            "discriminating `question`, or `conclude` — but only on an in-family catalogue match."
        )
        rank = self.client.parse(rank_prompt, RankResult, system=_SYSTEM, images=rank_images)

        # Conclusion backstop: only a catalogue form the model itself tagged `in_family` may be
        # asserted — never a cross-family shape-analogue or a cross_ref false-match (the
        # ARS-for-Italian-sigillata failure). The reasoning still surfaces via hypothesis/notes.
        conclusion = rank.conclusion
        if conclusion and not any(
            c.form_id == conclusion and c.match_kind == "in_family" for c in rank.candidates
        ):
            conclusion = ""

        return self._finish(
            user_text,
            TurnResult(
                understood=triage.understood,
                category=self.category,
                observed_parts=triage.observed_parts,
                fabric_reading=triage.fabric_reading,
                ware_family=triage.ware_family,
                typological_hypothesis=triage.typological_hypothesis,
                coverage_note=rank.coverage_note,
                candidates=rank.candidates,
                candidates_note=note,
                question=rank.question,
                conclusion=conclusion,
                confidence=rank.confidence,
            ),
        )

    def _finish(self, user_text: str, result: TurnResult) -> TurnResult:
        """Append the turn to history (the assistant's most salient line) and return the result."""
        self.history.append(("archaeologist", user_text))
        reply = (
            result.conclusion
            or result.question
            or result.typological_hypothesis
            or result.understood
        )
        self.history.append(("assistant", reply))
        return result
