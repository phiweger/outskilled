"""outskilled — filesystem-based agent skill loader.

See `SPEC.md` for the canonical rules and `README.md` for the usage
sketch.

Pydantic-AI integration lives under the optional `outskilled.pydanticai`
submodule and is importable only when the `pydantic-ai` extra is
installed:

    pip install "outskilled[pydantic-ai]"

    from outskilled.pydanticai import attach_skills, skill_aware_agent
"""

from outskilled.errors import (
    DuplicateSkillError,
    SkillError,
    SkillParseError,
    SkillValidationError,
    UnknownSkillError,
    UnsafeSkillNameError,
)
from outskilled.manifest import render_markdown, render_xml
from outskilled.models import Skill
from outskilled.parser import parse_frontmatter
from outskilled.registry import SkillRegistry

__version__ = "0.1.0"
SPEC_VERSION = "0.2"

__all__ = [
    "DuplicateSkillError",
    "SPEC_VERSION",
    "Skill",
    "SkillError",
    "SkillParseError",
    "SkillRegistry",
    "SkillValidationError",
    "UnknownSkillError",
    "UnsafeSkillNameError",
    "__version__",
    "parse_frontmatter",
    "render_markdown",
    "render_xml",
]
