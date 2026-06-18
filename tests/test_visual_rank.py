"""Visual comparison in the RANK step: candidate DRAWINGS are rendered and attached to the model
call (CLAUDE.md rule 3), family-stratified so every shape-plausible ware gets one in front of the
model. Deterministic — no model, no real PDFs (rendering is monkeypatched)."""

from __future__ import annotations

from pathlib import Path

from iaccm.agent import identify
from iaccm.agent.identify import Identifier, RankResult, TriageResult, _stratify_by_ware
from iaccm.catalog.models import FormRecord, PartType, SourcePointer
from iaccm.catalog.store import CatalogStore
from iaccm.ingest import pdf as pdfmod


def _form(id_, ware, *, sf="a.pdf", page=10, bbox=(0.1, 0.2, 0.3, 0.4)) -> FormRecord:
    return FormRecord(
        id=id_, ware=ware, vessel_class="bowl", part_types=[PartType.WALL],
        source=SourcePointer(short_title="t", source_file=sf, page_printed=page, page_pdf=page,
                             checksum="c", bbox=list(bbox) if bbox else None),
    )


def test_render_candidate_crops(monkeypatch) -> None:
    calls: list[tuple] = []

    def fake_render(pdf, page, bbox, dpi=200):
        calls.append((pdf.name, page, bbox))
        return Path(f"/crop/{pdf.name}_{page}.png")

    def fake_find(cs, sf):
        return None if sf == "missing.pdf" else Path(f"/pdf/{sf}")

    monkeypatch.setattr(pdfmod, "find_source_pdf", fake_find)
    monkeypatch.setattr(pdfmod, "render_region", fake_render)

    a = _form("A", "ARS", sf="a.pdf", page=10, bbox=(0.1, 0.2, 0.3, 0.4))
    b = _form("B", "ITS", sf="b.pdf", page=20, bbox=None)        # → whole page (bbox None)
    c = _form("C", "ARS", sf="missing.pdf", page=30)            # → PDF unresolvable, skipped
    d = FormRecord(id="D", ware="X", vessel_class="", part_types=[PartType.WALL])  # no source
    dup = _form("A2", "ARS", sf="a.pdf", page=10, bbox=(0.1, 0.2, 0.3, 0.4))       # same region

    out = pdfmod.render_candidate_crops([a, b, c, d, dup], n=10)
    assert [fid for _, fid in out] == ["A", "B"]   # C/D skipped, dup removed, order kept
    assert calls[1] == ("b.pdf", 20, None)         # bbox-less form rendered whole-page


def test_render_candidate_crops_caps(monkeypatch) -> None:
    monkeypatch.setattr(pdfmod, "find_source_pdf", lambda cs, sf: Path(f"/pdf/{sf}"))
    monkeypatch.setattr(pdfmod, "render_region",
                        lambda pdf, page, bbox, dpi=200: Path(f"/c/{page}.png"))
    forms = [_form(str(i), "ARS", sf=f"{i}.pdf", page=i) for i in range(20)]
    assert len(pdfmod.render_candidate_crops(forms, n=5)) == 5


def test_stratify_picks_minority_ware_first() -> None:
    # many ARS bowls, one ITS bowl ranked 4th: with only 2 drawing slots the ITS must still be shown
    forms = [_form("a1", "ARS"), _form("a2", "ARS"), _form("a3", "ARS"),
             _form("its", "Italian terra sigillata"), _form("a4", "ARS")]
    picked = _stratify_by_ware(forms, 2)
    wares = {p.ware for p in picked}
    assert "Italian terra sigillata" in wares and "ARS" in wares


def test_step_attaches_sherd_then_candidate_drawings(tmp_path, monkeypatch) -> None:
    store = CatalogStore(tmp_path / "catalog.jsonl")
    store.save([_form("ARS Form 1", "ARS", sf="ars.pdf", page=5),
                _form("Italian terra sigillata Conspectus 1", "Italian terra sigillata",
                      sf="ett.pdf", page=6)])

    # stub the rendering so no real PDFs are needed; one crop per candidate
    monkeypatch.setattr(
        identify, "render_candidate_crops",
        lambda forms, n, dpi=200: [(Path(f"/crop/{f.id}.png"), f.id) for f in forms[:n]],
    )

    captured: dict = {}

    class Stub:
        model_name = "stub"

        def parse(self, prompt, schema, **kw):
            if schema is TriageResult:
                return TriageResult(observed_parts=["wall"], archetype_ids=[])
            captured["images"] = kw.get("images")
            captured["prompt"] = prompt
            return RankResult()

        def generate(self, *a, **k):
            return ""

    sherd = tmp_path / "sherd.png"
    sherd.write_bytes(b"x")
    Identifier(catalog=store, client=Stub()).step("a red bowl wall", images=[sherd])

    imgs = captured["images"]
    assert imgs[0] == sherd                                   # sherd photo first
    assert {p.name for p in imgs[1:]} == {"ARS Form 1.png",   # then a drawing per candidate ware
                                          "Italian terra sigillata Conspectus 1.png"}
    assert "image 2: drawing of candidate" in captured["prompt"]   # the image→form KEY is present
