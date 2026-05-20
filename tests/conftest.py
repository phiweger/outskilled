"""Shared fixtures for outskilled tests."""

from __future__ import annotations

from pathlib import Path

import pytest


def write_skill(parent: Path, dirname: str, frontmatter: str, body: str = "body\n") -> Path:
    """Materialise a SKILL.md under `parent/dirname/`.

    The frontmatter argument is the YAML block content (without the
    `---` delimiters).
    """
    skill_dir = parent / dirname
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\n{frontmatter}\n---\n\n{body}",
        encoding="utf-8",
    )
    return skill_dir


@pytest.fixture
def write_skill_factory():
    return write_skill
