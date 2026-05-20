"""Typed errors. Hosts catch these to surface friendly diagnostics."""

from __future__ import annotations


class SkillError(Exception):
    """Base class for every spec-violation error raised by outskilled."""


class SkillParseError(SkillError):
    """Raised when SKILL.md frontmatter can't be parsed."""


class SkillValidationError(SkillError):
    """Raised when a SKILL.md violates a §3 rule (name, description, …)."""


class DuplicateSkillError(SkillError):
    """Raised when two skills share a name across the discovered roots."""


class UnknownSkillError(KeyError, SkillError):
    """Raised when `load(name)` is called with a name not in the registry.

    Subclasses `KeyError` for compatibility with code that catches the
    builtin shape on dict-like lookups.
    """


class UnsafeSkillNameError(ValueError, SkillError):
    """Raised when a name contains path-traversal characters (A-04)."""
