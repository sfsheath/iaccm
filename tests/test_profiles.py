"""Per-source ingest-profile contract tests — no model calls, no PDFs.

This is the seam that keeps "adding a typology is a config entry" honest: every entry in PROFILES
must be self-consistent and compose a prompt without blowing up, so a new book's registry entry
fails CI here (cheaply) rather than at ingest time. Add a book → it is exercised automatically.
"""

from __future__ import annotations

import re

import pytest

from iaccm.ingest.profiles import PROFILES, SourceProfile, build_prompt

PROFILE_ITEMS = sorted(PROFILES.items())


@pytest.mark.parametrize("slug,profile", PROFILE_ITEMS, ids=[s for s, _ in PROFILE_ITEMS])
def test_profile_is_well_formed(slug: str, profile: SourceProfile) -> None:
    assert profile.slug == slug, "registry key must equal the profile's own slug"
    assert profile.short_title.strip()
    assert isinstance(profile.page_offset, int)
    assert profile.dpi > 0
    assert profile.layout in {"forms-per-page", "entry-per-page", "class-window"}
    assert profile.prompt_body.strip()


@pytest.mark.parametrize("slug,profile", PROFILE_ITEMS, ids=[s for s, _ in PROFILE_ITEMS])
def test_build_prompt_composes(slug: str, profile: SourceProfile) -> None:
    # Must not raise KeyError on the format placeholders, and must carry the shared non-negotiables.
    prompt = build_prompt(profile, 100)
    assert profile.short_title in prompt
    assert "Breadth is critical" in prompt  # the breadth rule is inherited by every source
    assert "Paraphrase" in prompt  # the copyright firewall is inherited by every source
    assert profile.prompt_body[:40] in prompt  # the layout body was actually injected


@pytest.mark.parametrize("slug,profile", PROFILE_ITEMS, ids=[s for s, _ in PROFILE_ITEMS])
def test_class_window_requires_header_regex(slug: str, profile: SourceProfile) -> None:
    if profile.layout != "class-window":
        return
    assert profile.window_header, "class-window layout needs a window_header regex"
    rx = re.compile(profile.window_header, re.MULTILINE)
    assert rx.groups >= 1, "window_header must have one capture group (the class number)"
    # It must match a real header line and NOT a running-text reference (the false-positive risk).
    assert rx.search("CLASS 4 (Dressel 1B)")
    assert not rx.search("as discussed for Class 27 above")
