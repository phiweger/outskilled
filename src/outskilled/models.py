"""Skill data model. The Skill dataclass is the canonical record of one
installed skill — its metadata, on-disk location, body, and category path.

See SPEC.md §2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Skill:
    """One installed, validated skill.

    Attributes:
        name: Frontmatter `name`. Globally unique within a registry.
        description: Frontmatter `description`, whitespace-normalised.
        body: SKILL.md body (everything after the closing `---`).
        skill_dir: Filesystem root of the skill (parent of SKILL.md).
        category_path: Path from the discovering root to `skill_dir.parent`,
            as POSIX-style segments joined with `/`. Empty for a flat
            skill. E.g. `code/refactor` for `code/refactor/extract-method/`.
        when_to_use: Optional trigger-phrase prose (§3.6).
        always_load: If True, hosts inline the body into the system
            prompt at startup (§3.7).
        license: Optional SPDX-ish licence string.
        compatibility: Optional free-form compatibility note (≤500 chars).
        allowed_tools: Optional list of tool name patterns the skill needs.
        metadata: Optional host-specific extension bag.
    """

    name: str
    description: str
    body: str
    skill_dir: Path
    category_path: str = ""
    when_to_use: str | None = None
    always_load: bool = False
    license: str | None = None
    compatibility: str | None = None
    allowed_tools: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def location(self) -> str:
        """`<location>` rendered into the XML manifest.

        Category path + name, separated by `/`. Falls back to bare
        name for flat skills.
        """
        if not self.category_path:
            return self.name
        return f"{self.category_path}/{self.name}"
