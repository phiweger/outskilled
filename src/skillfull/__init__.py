"""skillfull — filesystem-based agent skill loader.

See `SPEC.md` for the canonical rules and `README.md` for the usage
sketch.

Pydantic-AI integration lives under the optional `skillfull.pydanticai`
submodule and is importable only when the `pydantic-ai` extra is
installed:

    pip install "skillfull[pydantic-ai]"

    from skillfull.pydanticai import attach_skills, skill_aware_agent
"""

from skillfull.errors import (
    DuplicateSkillError,
    SkillError,
    SkillParseError,
    SkillValidationError,
    UnknownSkillError,
    UnsafeSkillNameError,
)
from skillfull.manifest import render_markdown, render_xml
from skillfull.models import Skill
from skillfull.parser import parse_frontmatter
from skillfull.registry import SkillRegistry

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
