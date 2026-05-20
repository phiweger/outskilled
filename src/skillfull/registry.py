"""Skill registry: discover, validate, and serve.

Walks one or more skill roots, finds every `SKILL.md` regardless of
nesting depth, validates each per SPEC.md §3, and provides the
host-facing API:

  - `names()` — sorted list of skill names
  - `locations()` — sorted list of `category_path/name` locations
  - `skills()` — sorted list of `Skill` objects
  - `manifest_xml()` / `manifest_markdown()` — for the system prompt
  - `load(name)` — return the SKILL.md body for an activated skill
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import yaml

from skillfull.errors import (
    DuplicateSkillError,
    SkillError,
    UnknownSkillError,
    UnsafeSkillNameError,
)
from skillfull.manifest import render_markdown, render_xml
from skillfull.models import Skill
from skillfull.parser import parse_frontmatter
from skillfull.validator import (
    validate_allowed_tools,
    validate_always_load,
    validate_compatibility,
    validate_description,
    validate_frontmatter_keys,
    validate_license,
    validate_metadata,
    validate_name,
    validate_path_component,
    validate_when_to_use,
)

SKILL_FILENAME = "SKILL.md"

# SPEC §1.2: these subdirectory names are reserved inside a skill and
# MUST NOT be walked by the discovery loop.
RESERVED_SUBDIRS = frozenset({"references", "scripts", "assets"})


class SkillRegistry:
    """Discover, validate, and serve skills from one or more roots.

    Construction is eager — every `SKILL.md` under every root is
    parsed and validated up front. Malformed skills crash startup
    (SPEC §3.5); silent skips are an anti-pattern.
    """

    def __init__(self, roots: Iterable[Path]) -> None:
        self._skills: dict[str, Skill] = {}
        for root in roots:
            self._walk(Path(root))

    @classmethod
    def from_config(cls, config_path: Path | str) -> SkillRegistry:
        """Build a registry from a `skills.yaml` config file.

        Schema (all keys optional except `roots`):

            roots:
              - .              # paths are resolved relative to this file
              - ../shared-skills

        Returns a registry whose roots have been resolved against the
        config file's parent directory, so the bundle is portable.

        Raises:
            FileNotFoundError: config file does not exist.
            SkillError: config is malformed (missing/wrong-typed `roots`).
        """
        config_path = Path(config_path).resolve()
        if not config_path.is_file():
            raise FileNotFoundError(f"Config not found: {config_path}")
        with config_path.open(encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        if not isinstance(loaded, dict):
            raise SkillError(
                f"Config {config_path}: top-level must be a mapping, got {type(loaded).__name__}"
            )
        roots = loaded.get("roots", [])
        if not isinstance(roots, list) or not all(isinstance(r, str) for r in roots):
            raise SkillError(
                f"Config {config_path}: `roots` must be a list of strings"
            )
        if not roots:
            raise SkillError(f"Config {config_path}: `roots` must list at least one path")
        base = config_path.parent
        resolved = [(base / r).resolve() for r in roots]
        return cls(resolved)

    def _walk(self, root: Path) -> None:
        """Discover skills under `root` per SPEC §1.1 and §1.2.

        Recursive descent that registers the first `SKILL.md` it sees
        on any branch (the parent dir IS that skill) and stops
        descending below it. Reserved subdirs (§1.2) are pruned. The
        root directory itself is never treated as a skill — it is the
        container.
        """
        if not root.is_dir():
            raise FileNotFoundError(f"Skill root not found: {root}")
        self._descend(root, root, is_root=True)

    def _descend(self, root: Path, current: Path, *, is_root: bool) -> None:
        if not is_root and (current / SKILL_FILENAME).is_file():
            # `current` is a skill directory — register it and stop
            # descending. Anything below is its own private content.
            self._register(root, current)
            return

        for child in sorted(current.iterdir()):
            if not child.is_dir():
                continue
            if child.name.startswith("."):
                continue
            if not is_root and child.name in RESERVED_SUBDIRS:
                continue
            self._descend(root, child, is_root=False)

    def _register(self, root: Path, skill_dir: Path) -> None:
        skill_md = skill_dir / SKILL_FILENAME
        category_path = _relative_category(root, skill_dir)
        skill = self._load_one(skill_dir, skill_md, category_path)
        if skill.name in self._skills:
            prior = self._skills[skill.name].skill_dir
            raise DuplicateSkillError(
                f"Duplicate skill name {skill.name!r}: already loaded from "
                f"{prior}, also present at {skill_dir}"
            )
        self._skills[skill.name] = skill

    def _load_one(self, skill_dir: Path, skill_md: Path, category_path: str) -> Skill:
        content = skill_md.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(content)
        validate_frontmatter_keys(fm, skill_dir)
        name = validate_name(fm.get("name"), skill_dir)
        description = validate_description(fm.get("description"), skill_dir)
        when_to_use = validate_when_to_use(fm.get("when_to_use"), skill_dir)
        always_load = validate_always_load(fm.get("always_load"), skill_dir)
        license_value = validate_license(fm.get("license"), skill_dir)
        compatibility = validate_compatibility(fm.get("compatibility"), skill_dir)
        allowed_tools = validate_allowed_tools(fm.get("allowed-tools"), skill_dir)
        metadata = validate_metadata(fm.get("metadata"), skill_dir)
        return Skill(
            name=name,
            description=description,
            body=body,
            skill_dir=skill_dir,
            category_path=category_path,
            when_to_use=when_to_use,
            always_load=always_load,
            license=license_value,
            compatibility=compatibility,
            allowed_tools=allowed_tools,
            metadata=metadata,
        )

    # --- Host-facing API ----------------------------------------------------

    def names(self) -> list[str]:
        """Sorted skill names."""
        return sorted(self._skills)

    def locations(self) -> list[str]:
        """Sorted skill locations (`category_path/name`)."""
        return sorted(s.location for s in self._skills.values())

    def skills(self) -> list[Skill]:
        """Skills sorted by `location` (manifest order)."""
        return sorted(self._skills.values(), key=lambda s: s.location)

    def always_loaded(self) -> list[Skill]:
        """Skills with `always_load: true`, in manifest order (§3.7)."""
        return [s for s in self.skills() if s.always_load]

    def manifest_xml(self) -> str:
        """Render the `<available_skills>` XML block for the system prompt."""
        return render_xml(self._skills.values())

    def manifest_markdown(self) -> str:
        """Render the markdown bullet-list manifest."""
        return render_markdown(self._skills.values())

    def get(self, name: str) -> Skill:
        """Return the `Skill` record for `name`.

        Raises:
            UnsafeSkillNameError: name contains traversal characters.
            UnknownSkillError: no skill by that name is installed.
        """
        validate_path_component(name)
        if name not in self._skills:
            available = ", ".join(self.names()) or "(none)"
            raise UnknownSkillError(f"Unknown skill: {name!r}. Available: {available}")
        return self._skills[name]

    def load(self, name: str) -> str:
        """Return SKILL.md body (no frontmatter) for `name`.

        Raises:
            UnsafeSkillNameError: name contains traversal characters.
            UnknownSkillError: no skill by that name is installed.
        """
        return self.get(name).body

    def resolve_resource(self, skill_name: str, relative_path: str) -> Path:
        """Resolve a Level-3 resource path under a skill's directory.

        Validates that the resulting path stays inside `skill.skill_dir`
        (rejects `..` traversal). Returns the resolved `Path` without
        reading it — callers decide whether to `read_text()` or invoke
        a script.

        Raises:
            UnsafeSkillNameError: skill_name or relative_path tries to
                traverse outside the skill directory.
            UnknownSkillError: skill not in registry.
            ValueError: relative_path is empty or not a string.
            FileNotFoundError: resolved path does not exist.
        """
        skill = self.get(skill_name)
        if not isinstance(relative_path, str) or not relative_path:
            raise ValueError(
                f"relative_path must be a non-empty string, got {relative_path!r}"
            )
        skill_root = skill.skill_dir.resolve()
        target = (skill_root / relative_path).resolve()
        try:
            target.relative_to(skill_root)
        except ValueError as exc:
            raise UnsafeSkillNameError(
                f"Resource path {relative_path!r} escapes skill {skill_name!r}'s directory"
            ) from exc
        if not target.exists():
            raise FileNotFoundError(
                f"Skill {skill_name!r}: resource {relative_path!r} not found at {target}"
            )
        return target

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._skills

    def __len__(self) -> int:
        return len(self._skills)


def _relative_category(root: Path, skill_dir: Path) -> str:
    """Path segments between `root` and `skill_dir.parent`.

    Empty for a flat skill (where `skill_dir.parent == root`).
    """
    rel = skill_dir.relative_to(root).parent
    return "" if rel == Path(".") else rel.as_posix()
