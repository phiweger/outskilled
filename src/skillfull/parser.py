"""SKILL.md frontmatter parser.

See SPEC.md §2 for the file format. Validation of parsed fields
(name format, description length, etc.) lives in `validator.py`.
"""

from __future__ import annotations

import re

import yaml

from skillfull.errors import SkillParseError

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n?---\s*(?:\n|\Z)", re.DOTALL)


def parse_frontmatter(content: str) -> tuple[dict[str, object], str]:
    """Split a SKILL.md into (frontmatter, body).

    Returns `(frontmatter_dict, body_str)` when the file begins with
    a `---`-delimited YAML block (the required form per SPEC §2).

    Raises:
        SkillParseError: If the file doesn't start with a frontmatter
            block, or if the block is present but its YAML is malformed.
    """
    match = _FRONTMATTER_RE.match(content)
    if not match:
        preview = content[:40].rstrip()
        raise SkillParseError(
            "SKILL.md must begin with a `---`-delimited YAML frontmatter "
            f"block (SPEC §2). First chars seen: {preview!r}"
        )
    try:
        loaded = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise SkillParseError(f"Malformed YAML frontmatter: {exc!r}") from exc
    if loaded is not None and not isinstance(loaded, dict):
        raise SkillParseError(
            f"Frontmatter must be a YAML mapping, got {type(loaded).__name__}"
        )
    fm: dict[str, object] = loaded or {}
    body = content[match.end() :]
    return fm, body
