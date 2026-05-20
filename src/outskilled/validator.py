"""Validation of parsed SKILL.md frontmatter against SPEC.md §3."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from outskilled.errors import SkillValidationError, UnsafeSkillNameError

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MAX_WHEN_TO_USE_LENGTH = 512
MAX_COMPATIBILITY_LENGTH = 500

ALLOWED_FRONTMATTER_KEYS = frozenset(
    {
        "name",
        "description",
        "when_to_use",
        "always_load",
        "license",
        "compatibility",
        "allowed-tools",
        "metadata",
    }
)


def normalize_unicode(value: str) -> str:
    """NFKC-normalise a string. Used to compare names to dirnames."""
    return unicodedata.normalize("NFKC", value)


def validate_frontmatter_keys(fm: dict[str, object], skill_dir: Path) -> None:
    """SPEC §2.3: unknown top-level keys are an error by default."""
    unknown = sorted(set(fm) - ALLOWED_FRONTMATTER_KEYS)
    if unknown:
        raise SkillValidationError(
            f"Skill at {skill_dir}: unknown frontmatter keys {unknown!r}. "
            f"Allowed: {sorted(ALLOWED_FRONTMATTER_KEYS)}"
        )


def validate_name(name: object, skill_dir: Path) -> str:
    """SPEC §3.1."""
    if not isinstance(name, str):
        raise SkillValidationError(f"Skill at {skill_dir}: `name` must be a string")
    if not name:
        raise SkillValidationError(f"Skill at {skill_dir}: `name` must be non-empty")
    if len(name) > MAX_NAME_LENGTH:
        raise SkillValidationError(
            f"Skill at {skill_dir}: `name` {name!r} exceeds {MAX_NAME_LENGTH} chars"
        )
    if not NAME_RE.match(name):
        raise SkillValidationError(
            f"Skill at {skill_dir}: `name` {name!r} must be kebab-case "
            f"(lowercase [a-z0-9]+ segments joined by single hyphens)"
        )
    if "claude" in name or "anthropic" in name:
        raise SkillValidationError(
            f"Skill at {skill_dir}: `name` {name!r} uses a reserved substring "
            f"(`claude` or `anthropic`)"
        )
    if normalize_unicode(name) != normalize_unicode(skill_dir.name):
        raise SkillValidationError(
            f"Skill `name` {name!r} must match its directory name "
            f"{skill_dir.name!r} (NFKC-normalised)"
        )
    return name


def validate_description(description: object, skill_dir: Path) -> str:
    """SPEC §3.2. Returns the whitespace-normalised description."""
    if not isinstance(description, str):
        raise SkillValidationError(f"Skill at {skill_dir}: `description` must be a string")
    normalised = " ".join(description.strip().split())
    if not normalised:
        raise SkillValidationError(
            f"Skill at {skill_dir}: `description` must be non-empty"
        )
    if len(normalised) > MAX_DESCRIPTION_LENGTH:
        raise SkillValidationError(
            f"Skill at {skill_dir}: `description` exceeds {MAX_DESCRIPTION_LENGTH} chars "
            f"({len(normalised)} given)"
        )
    if "<" in normalised or ">" in normalised:
        raise SkillValidationError(
            f"Skill at {skill_dir}: `description` must not contain `<` or `>` "
            f"(would break XML manifests)"
        )
    return normalised


def validate_when_to_use(value: object, skill_dir: Path) -> str | None:
    """SPEC §3.6. Returns the whitespace-normalised string or None."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise SkillValidationError(f"Skill at {skill_dir}: `when_to_use` must be a string")
    normalised = " ".join(value.strip().split())
    if not normalised:
        return None
    if len(normalised) > MAX_WHEN_TO_USE_LENGTH:
        raise SkillValidationError(
            f"Skill at {skill_dir}: `when_to_use` exceeds {MAX_WHEN_TO_USE_LENGTH} chars "
            f"({len(normalised)} given)"
        )
    if "<" in normalised or ">" in normalised:
        raise SkillValidationError(
            f"Skill at {skill_dir}: `when_to_use` must not contain `<` or `>` "
            f"(would break XML manifests)"
        )
    return normalised


def validate_always_load(value: object, skill_dir: Path) -> bool:
    """SPEC §3.7. Defaults to False when absent or None."""
    if value is None:
        return False
    if not isinstance(value, bool):
        raise SkillValidationError(
            f"Skill at {skill_dir}: `always_load` must be a bool, got {type(value).__name__}"
        )
    return value


def validate_license(value: object, skill_dir: Path) -> str | None:
    """`license` is optional; when present it MUST be a string."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise SkillValidationError(
            f"Skill at {skill_dir}: `license` must be a string, got {type(value).__name__}"
        )
    return value


def validate_compatibility(value: object, skill_dir: Path) -> str | None:
    """SPEC §3.3."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise SkillValidationError(f"Skill at {skill_dir}: `compatibility` must be a string")
    if len(value) > MAX_COMPATIBILITY_LENGTH:
        raise SkillValidationError(
            f"Skill at {skill_dir}: `compatibility` exceeds {MAX_COMPATIBILITY_LENGTH} chars"
        )
    return value


def validate_allowed_tools(value: object, skill_dir: Path) -> tuple[str, ...]:
    """`allowed-tools` must be a list of strings."""
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise SkillValidationError(
            f"Skill at {skill_dir}: `allowed-tools` must be a list of strings"
        )
    return tuple(value)


def validate_metadata(value: object, skill_dir: Path) -> dict[str, str]:
    """`metadata` must be a flat dict of string keys to string values."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SkillValidationError(
            f"Skill at {skill_dir}: `metadata` must be a mapping"
        )
    coerced: dict[str, str] = {}
    for k, v in value.items():
        if not isinstance(k, str):
            raise SkillValidationError(
                f"Skill at {skill_dir}: `metadata` keys must be strings"
            )
        coerced[k] = str(v)
    return coerced


def validate_path_component(value: str, label: str = "skill_name") -> None:
    """SPEC §3.4. Reject `/`, `\\`, `..` in user-supplied names."""
    if not value:
        raise UnsafeSkillNameError(f"{label} must not be empty")
    if "/" in value or "\\" in value or ".." in value:
        raise UnsafeSkillNameError(f"{label} contains unsafe path characters: {value!r}")
