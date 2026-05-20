"""parse_frontmatter tests — SPEC.md §2."""

from __future__ import annotations

import pytest

from skillfull import parse_frontmatter
from skillfull.errors import SkillParseError


def test_parses_dict_and_body() -> None:
    content = "---\nname: x\ndescription: y\n---\n\n# body line\nmore\n"
    fm, body = parse_frontmatter(content)
    assert fm == {"name": "x", "description": "y"}
    assert body.startswith("# body line")


def test_missing_frontmatter_block_raises() -> None:
    with pytest.raises(SkillParseError, match="must begin with"):
        parse_frontmatter("no frontmatter\nbody only\n")


def test_handles_empty_body() -> None:
    fm, body = parse_frontmatter("---\nname: x\ndescription: y\n---\n")
    assert fm == {"name": "x", "description": "y"}
    assert body == ""


def test_malformed_yaml_raises() -> None:
    with pytest.raises(SkillParseError, match="Malformed"):
        parse_frontmatter("---\nname: [unterminated\n---\nbody\n")


def test_non_dict_yaml_raises() -> None:
    with pytest.raises(SkillParseError, match="must be a YAML mapping"):
        parse_frontmatter("---\n[just, a, list]\n---\nbody\n")


def test_empty_frontmatter_block_returns_empty_dict() -> None:
    fm, body = parse_frontmatter("---\n---\nbody\n")
    assert fm == {}
    assert body == "body\n"
