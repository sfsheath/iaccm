"""Class-window topology for multi-page catalogue-entry typologies (e.g. Peacock & Williams 1991).

Some books give one named type per *multi-page* entry, with the type's identity header ("CLASS N")
printed only on the first page — continuation pages carry no anchor at all. Rendering such a book
one page at a time loses every continuation page's metadata, because a model that sees only a
continuation page cannot know which type it belongs to (its running header is generic). Instead we
scan the text layer ONLY to find header boundaries, then render each type's full page span as one
multi-image model call so the model reads the whole entry at once.

CLAUDE.md rule 2 (breadth — never prune a candidate on a lossy signal): this scan is a *router*,
not a filter. The text layer sets window *boundaries* only; extraction stays fully visual, so no
type is ever dropped because of bad OCR. The one place OCR could still hurt — a mangled "CLASS"
token silently fusing two types into one window — is caught by a hard contiguity check that RAISES
rather than proceeds. That fused-window failure is the founding-bug shape, so we fail loud.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel

from .profiles import SourceProfile


def _assert_contiguous(nums: list[int], source_name: str) -> None:
    """Rule-2 guard: detected class numbers must form an unbroken run. A missing integer between the
    min and max means a header went undetected — almost always an OCR-mangled "CLASS" that fused its
    class into the previous window. Fail loud with the gap rather than ship a silently-merged (and
    therefore unfindable) type. Pure/standalone so the property is unit-testable without a PDF."""
    if not nums:
        raise ValueError(f"class_windows: no class headers detected in {source_name}")
    missing = sorted(set(range(nums[0], nums[-1] + 1)) - set(nums))
    if missing:
        raise ValueError(
            f"class_windows: class numbers not contiguous in {source_name}; detected {nums}, "
            f"missing {missing}. An undetected header likely fused two classes — check the page "
            f"text/OCR around the gap before ingesting (CLAUDE.md rule 2: breadth)."
        )


class ClassWindow(BaseModel):
    """One catalogue class to render as a single multi-image call.

    ``key`` is the class sequence number — both the id anchor and the resume-sidecar key (so an
    interrupted class-window ingest resumes by class, not by page). ``pages_pdf`` is the inclusive
    1-based PDF page span; consecutive windows overlap by one page (the next header's page) so a
    class whose tail bleeds onto the next header's page is still fully captured."""

    key: int
    header_printed: int  # printed page carrying this class's header (the citation's page_printed)
    pages_pdf: list[int]  # 1-based PDF pages to render, in order; index 0 is the header page


def class_windows(
    pdf_path: Path, profile: SourceProfile, printed_pages: Iterable[int]
) -> list[ClassWindow]:
    """Find class headers in ``printed_pages`` (the scan range) and build one window per class.

    ``printed_pages`` is the printed-page range from ``--pages``; each is converted to a 1-based PDF
    page via ``profile.page_offset`` and its text layer scanned for ``profile.window_header``. A
    class whose header falls in the range is ingested; its window runs to the next header's page
    (overlap by one) or, for the last class, to the end of the scan range.

    Raises ``ValueError`` if no header is found, if ``window_header`` is unset, or if the detected
    class numbers are not contiguous (a gap means an OCR-mangled header fused two classes — the
    breadth-violating failure we must never pass over silently)."""
    import fitz  # PyMuPDF, lazy import

    if profile.window_header is None:
        raise ValueError(
            f"profile {profile.slug!r} has layout 'class-window' but no window_header regex"
        )
    header_re = re.compile(profile.window_header, re.MULTILINE)

    pdf_pages = sorted({p + profile.page_offset for p in printed_pages})
    if not pdf_pages:
        raise ValueError("class_windows: empty page range")

    # Ordered (class_number, header_pdf_page); first occurrence of a number wins.
    headers: list[tuple[int, int]] = []
    seen: set[int] = set()
    with fitz.open(Path(pdf_path)) as doc:
        npages = doc.page_count
        scan_max = max(p for p in pdf_pages if 1 <= p <= npages)
        for page_pdf in pdf_pages:
            if not (1 <= page_pdf <= npages):
                continue
            text = doc[page_pdf - 1].get_text("text")
            for m in header_re.finditer(text):
                num = int(m.group(1))
                if num not in seen:
                    seen.add(num)
                    headers.append((num, page_pdf))

    if not headers:
        raise ValueError(
            f"class_windows: no header matching {profile.window_header!r} in pages "
            f"{pdf_pages[0]}–{pdf_pages[-1]} of {Path(pdf_path).name} — wrong offset or range?"
        )

    headers.sort(key=lambda h: h[1])  # by page order
    nums = [n for n, _ in headers]
    _assert_contiguous(nums, Path(pdf_path).name)

    windows: list[ClassWindow] = []
    for i, (num, page_pdf) in enumerate(headers):
        end = headers[i + 1][1] if i + 1 < len(headers) else scan_max
        pages = list(range(page_pdf, max(page_pdf, end) + 1))  # inclusive; overlap-by-one at end
        windows.append(
            ClassWindow(key=num, header_printed=page_pdf - profile.page_offset, pages_pdf=pages)
        )
    return windows


__all__ = ["ClassWindow", "class_windows", "_assert_contiguous"]
