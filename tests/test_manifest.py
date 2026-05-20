"""Manifest renderer tests — SPEC.md §4."""

from __future__ import annotations

from pathlib import Path

from skillfull import Skill, render_markdown, render_xml


def _skill(
    name: str,
    description: str,
    category: str = "",
    *,
    when_to_use: str | None = None,
) -> Skill:
    return Skill(
        name=name,
        description=description,
        body="",
        skill_dir=Path(f"/tmp/{name}"),
        category_path=category,
        when_to_use=when_to_use,
    )


def test_xml_empty_block() -> None:
    out = render_xml([])
    assert out == "<available_skills>\n</available_skills>"


def test_xml_contains_each_skill_in_sorted_order() -> None:
    skills = [
        _skill("zulu", "last"),
        _skill("alpha", "first"),
        _skill("mike", "middle"),
    ]
    out = render_xml(skills)
    # locations are bare names (no category), so they sort as a/m/z.
    assert out.index("<name>alpha</name>") < out.index("<name>mike</name>")
    assert out.index("<name>mike</name>") < out.index("<name>zulu</name>")
    assert "<available_skills>" in out
    assert out.strip().endswith("</available_skills>")


def test_xml_nested_location_uses_category_path() -> None:
    skill = _skill("extract-method", "pull out a function", category="code/refactor")
    out = render_xml([skill])
    assert "<location>code/refactor/extract-method</location>" in out


def test_xml_escapes_special_chars_in_description() -> None:
    skill = _skill("safe", 'a & b "c" <d>')
    out = render_xml([skill])
    assert "&amp;" in out
    assert "&quot;" in out
    # Even if validation already rejects < and >, the renderer must still escape.
    assert "&lt;d&gt;" in out


def test_markdown_empty_placeholder() -> None:
    assert render_markdown([]) == "(no skills installed)"


def test_markdown_sorted_bullets() -> None:
    skills = [_skill("b", "second"), _skill("a", "first")]
    out = render_markdown(skills)
    lines = out.splitlines()
    assert lines[0].startswith("- **a**")
    assert lines[1].startswith("- **b**")


def test_markdown_shows_location_in_backticks() -> None:
    skill = _skill("extract-method", "do it", category="code/refactor")
    out = render_markdown([skill])
    assert "`code/refactor/extract-method`" in out


# --- when_to_use rendering ---------------------------------------------------


def test_xml_includes_when_to_use_when_present() -> None:
    skill = _skill("trigger", "what it does", when_to_use="when user asks for X")
    out = render_xml([skill])
    assert "<when_to_use>when user asks for X</when_to_use>" in out


def test_xml_omits_when_to_use_when_absent() -> None:
    skill = _skill("plain", "no hint")
    out = render_xml([skill])
    assert "<when_to_use>" not in out


def test_xml_escapes_when_to_use() -> None:
    skill = _skill("safe", "fine", when_to_use='trigger on "quoted" & misc')
    out = render_xml([skill])
    assert "&quot;quoted&quot;" in out
    assert "&amp;" in out


def test_markdown_appends_when_to_use_in_italics() -> None:
    skill = _skill("trigger", "what it does", when_to_use="when user asks for X")
    out = render_markdown([skill])
    assert "*when user asks for X*" in out


def test_markdown_omits_when_to_use_when_absent() -> None:
    skill = _skill("plain", "no hint")
    out = render_markdown([skill])
    assert out == "- **plain** (`plain`): no hint"
