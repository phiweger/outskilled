"""Render an installed skill set as a system-prompt manifest.

XML form is canonical (SPEC §4.1); markdown form is provided for
hosts that want a lighter render (SPEC §4.2).
"""

from __future__ import annotations

from collections.abc import Iterable
from xml.sax.saxutils import escape

from skillfull.models import Skill

_XML_QUOTE_ENTITIES = {'"': "&quot;", "'": "&apos;"}


def _escape(text: str) -> str:
    """XML-escape `&`, `<`, `>`, `"`, and `'`."""
    return escape(text, _XML_QUOTE_ENTITIES)


def render_xml(skills: Iterable[Skill]) -> str:
    """Render skills as an `<available_skills>` XML block.

    Skills are emitted in lexicographic order of `location` so the
    output is deterministic (prompt caching depends on this).
    `<when_to_use>` is emitted only when the skill sets the field.
    """
    sorted_skills = sorted(skills, key=lambda s: s.location)
    if not sorted_skills:
        return "<available_skills>\n</available_skills>"
    lines = ["<available_skills>"]
    for skill in sorted_skills:
        lines.append("  <skill>")
        lines.append(f"    <name>{_escape(skill.name)}</name>")
        lines.append(f"    <description>{_escape(skill.description)}</description>")
        if skill.when_to_use:
            lines.append(f"    <when_to_use>{_escape(skill.when_to_use)}</when_to_use>")
        lines.append(f"    <location>{_escape(skill.location)}</location>")
        lines.append("  </skill>")
    lines.append("</available_skills>")
    return "\n".join(lines)


def render_markdown(skills: Iterable[Skill]) -> str:
    """Render skills as a markdown bullet list.

    Same sort order as `render_xml`. Backticks in descriptions stay
    literal (skill descriptions occasionally contain code-shaped
    snippets); pipes are not relevant here. `when_to_use` is appended
    in italics on the same line when set.
    """
    sorted_skills = sorted(skills, key=lambda s: s.location)
    if not sorted_skills:
        return "(no skills installed)"
    lines = []
    for s in sorted_skills:
        suffix = f" — *{s.when_to_use}*" if s.when_to_use else ""
        lines.append(f"- **{s.name}** (`{s.location}`): {s.description}{suffix}")
    return "\n".join(lines)
