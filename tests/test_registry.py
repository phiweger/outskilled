"""SkillRegistry tests — discovery, arbitrary nesting, validation, load."""

from __future__ import annotations

from pathlib import Path

import pytest

from skillfull import (
    DuplicateSkillError,
    Skill,
    SkillError,
    SkillRegistry,
    SkillValidationError,
    UnknownSkillError,
    UnsafeSkillNameError,
)


def _write(parent: Path, dirname: str, frontmatter: str, body: str = "body\n") -> Path:
    skill_dir = parent / dirname
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n\n{body}", encoding="utf-8")
    return skill_dir


# --- discovery ----------------------------------------------------------------


def test_flat_skill_loaded(tmp_path: Path) -> None:
    _write(tmp_path, "alpha", "name: alpha\ndescription: first")
    reg = SkillRegistry([tmp_path])
    assert reg.names() == ["alpha"]
    sk = reg.skills()[0]
    assert isinstance(sk, Skill)
    assert sk.category_path == ""
    assert sk.location == "alpha"


def test_nested_two_levels(tmp_path: Path) -> None:
    _write(tmp_path / "notes", "search", "name: search\ndescription: find")
    _write(tmp_path / "notes", "write", "name: write\ndescription: save")
    reg = SkillRegistry([tmp_path])
    assert reg.names() == ["search", "write"]
    locs = reg.locations()
    assert locs == ["notes/search", "notes/write"]


def test_arbitrary_nesting_three_plus_levels(tmp_path: Path) -> None:
    _write(tmp_path / "code" / "refactor", "extract-method",
           "name: extract-method\ndescription: pull out a function")
    _write(tmp_path / "code" / "review" / "deep", "spotter",
           "name: spotter\ndescription: catch issues")
    reg = SkillRegistry([tmp_path])
    assert reg.locations() == ["code/refactor/extract-method", "code/review/deep/spotter"]


def test_multiple_roots(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    _write(a, "one", "name: one\ndescription: from a")
    _write(b, "two", "name: two\ndescription: from b")
    reg = SkillRegistry([a, b])
    assert reg.names() == ["one", "two"]


def test_missing_root_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        SkillRegistry([tmp_path / "does-not-exist"])


def test_dirs_without_skill_md_ignored(tmp_path: Path) -> None:
    (tmp_path / "not-a-skill").mkdir()
    (tmp_path / "not-a-skill" / "README.md").write_text("nope", encoding="utf-8")
    _write(tmp_path, "valid", "name: valid\ndescription: ok")
    reg = SkillRegistry([tmp_path])
    assert reg.names() == ["valid"]


# --- duplicates ---------------------------------------------------------------


def test_duplicate_name_across_roots_fatal(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    _write(a, "same", "name: same\ndescription: a")
    _write(b, "same", "name: same\ndescription: b")
    with pytest.raises(DuplicateSkillError):
        SkillRegistry([a, b])


def test_duplicate_name_within_root_fatal(tmp_path: Path) -> None:
    _write(tmp_path / "cat1", "shared", "name: shared\ndescription: a")
    _write(tmp_path / "cat2", "shared", "name: shared\ndescription: b")
    with pytest.raises(DuplicateSkillError):
        SkillRegistry([tmp_path])


# --- validation propagation ---------------------------------------------------


def test_name_dirname_mismatch_raises(tmp_path: Path) -> None:
    _write(tmp_path, "actual-dir", "name: different-name\ndescription: x")
    with pytest.raises(SkillValidationError):
        SkillRegistry([tmp_path])


def test_unknown_frontmatter_key_raises(tmp_path: Path) -> None:
    _write(tmp_path, "skill-a", "name: skill-a\ndescription: x\ntags: [a, b]")
    with pytest.raises(SkillValidationError, match="unknown frontmatter keys"):
        SkillRegistry([tmp_path])


# --- load ---------------------------------------------------------------------


def test_load_returns_body_without_frontmatter(tmp_path: Path) -> None:
    _write(tmp_path, "skill-x", "name: skill-x\ndescription: hi", body="# x body\n")
    reg = SkillRegistry([tmp_path])
    body = reg.load("skill-x")
    assert body.lstrip().startswith("# x body")
    assert "---" not in body.splitlines()[0]


def test_load_unknown_raises(tmp_path: Path) -> None:
    _write(tmp_path, "real", "name: real\ndescription: x")
    reg = SkillRegistry([tmp_path])
    with pytest.raises(UnknownSkillError):
        reg.load("missing")


def test_load_rejects_traversal(tmp_path: Path) -> None:
    _write(tmp_path, "real", "name: real\ndescription: x")
    reg = SkillRegistry([tmp_path])
    for bad in ("../etc/passwd", "real/../oops", "a\\b"):
        with pytest.raises(UnsafeSkillNameError):
            reg.load(bad)


# --- optional fields surface on the Skill ------------------------------------


def test_optional_fields_captured(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "rich",
        "name: rich\n"
        "description: full bag\n"
        "license: MIT\n"
        "compatibility: python>=3.12\n"
        "allowed-tools: [bash, python]\n"
        "metadata:\n  team: perception\n",
    )
    reg = SkillRegistry([tmp_path])
    sk = reg.skills()[0]
    assert sk.license == "MIT"
    assert sk.compatibility == "python>=3.12"
    assert sk.allowed_tools == ("bash", "python")
    assert sk.metadata == {"team": "perception"}


# --- registry shape -----------------------------------------------------------


def test_contains_and_len(tmp_path: Path) -> None:
    _write(tmp_path, "a", 'name: a\ndescription: "first"')
    _write(tmp_path, "b", 'name: b\ndescription: "second"')
    reg = SkillRegistry([tmp_path])
    assert "a" in reg
    assert "missing" not in reg
    assert 42 not in reg  # type: ignore[operator]
    assert len(reg) == 2


# --- get ---------------------------------------------------------------------


def test_get_returns_skill(tmp_path: Path) -> None:
    _write(tmp_path, "one", "name: one\ndescription: x")
    reg = SkillRegistry([tmp_path])
    sk = reg.get("one")
    assert isinstance(sk, Skill)
    assert sk.name == "one"


def test_get_unknown_raises(tmp_path: Path) -> None:
    _write(tmp_path, "one", "name: one\ndescription: x")
    reg = SkillRegistry([tmp_path])
    with pytest.raises(UnknownSkillError):
        reg.get("missing")


def test_get_rejects_traversal(tmp_path: Path) -> None:
    _write(tmp_path, "one", "name: one\ndescription: x")
    reg = SkillRegistry([tmp_path])
    with pytest.raises(UnsafeSkillNameError):
        reg.get("../etc/passwd")


# --- when_to_use & always_load fields ----------------------------------------


def test_when_to_use_captured(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "trigger",
        "name: trigger\ndescription: x\nwhen_to_use: when the user asks Y",
    )
    reg = SkillRegistry([tmp_path])
    assert reg.get("trigger").when_to_use == "when the user asks Y"


def test_always_load_defaults_false(tmp_path: Path) -> None:
    _write(tmp_path, "plain", "name: plain\ndescription: x")
    reg = SkillRegistry([tmp_path])
    assert reg.get("plain").always_load is False
    assert reg.always_loaded() == []


def test_always_loaded_returns_marked_skills_only(tmp_path: Path) -> None:
    _write(tmp_path, "always", "name: always\ndescription: x\nalways_load: true")
    _write(tmp_path, "lazy", "name: lazy\ndescription: y")
    reg = SkillRegistry([tmp_path])
    loaded = reg.always_loaded()
    assert [s.name for s in loaded] == ["always"]


# --- from_config -------------------------------------------------------------


def test_from_config_loads_relative_root(tmp_path: Path) -> None:
    _write(tmp_path, "one", "name: one\ndescription: x")
    (tmp_path / "skills.yaml").write_text("roots: [.]\n", encoding="utf-8")
    reg = SkillRegistry.from_config(tmp_path / "skills.yaml")
    assert reg.names() == ["one"]


def test_from_config_resolves_relative_to_config_file(tmp_path: Path) -> None:
    skills_dir = tmp_path / "bundle" / "skills"
    skills_dir.mkdir(parents=True)
    _write(skills_dir, "alpha", "name: alpha\ndescription: x")
    config = tmp_path / "bundle" / "skills.yaml"
    config.write_text("roots:\n  - skills\n", encoding="utf-8")
    reg = SkillRegistry.from_config(config)
    assert reg.names() == ["alpha"]


def test_from_config_supports_multiple_roots(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    _write(a, "one", "name: one\ndescription: x")
    _write(b, "two", "name: two\ndescription: y")
    config = tmp_path / "skills.yaml"
    config.write_text("roots:\n  - a\n  - b\n", encoding="utf-8")
    reg = SkillRegistry.from_config(config)
    assert reg.names() == ["one", "two"]


def test_from_config_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        SkillRegistry.from_config(tmp_path / "does-not-exist.yaml")


def test_from_config_missing_roots_key_raises(tmp_path: Path) -> None:
    config = tmp_path / "skills.yaml"
    config.write_text("strict: true\n", encoding="utf-8")
    with pytest.raises(SkillError, match="`roots`"):
        SkillRegistry.from_config(config)


def test_from_config_non_string_root_raises(tmp_path: Path) -> None:
    config = tmp_path / "skills.yaml"
    config.write_text("roots: [42]\n", encoding="utf-8")
    with pytest.raises(SkillError, match="list of strings"):
        SkillRegistry.from_config(config)


def test_from_config_accepts_string_path(tmp_path: Path) -> None:
    _write(tmp_path, "one", "name: one\ndescription: x")
    (tmp_path / "skills.yaml").write_text("roots: [.]\n", encoding="utf-8")
    reg = SkillRegistry.from_config(str(tmp_path / "skills.yaml"))
    assert reg.names() == ["one"]


# --- resolve_resource --------------------------------------------------------


def test_resolve_resource_returns_path(tmp_path: Path) -> None:
    skill_dir = _write(tmp_path, "one", "name: one\ndescription: x")
    refs = skill_dir / "references"
    refs.mkdir()
    (refs / "note.md").write_text("hello", encoding="utf-8")
    reg = SkillRegistry([tmp_path])
    target = reg.resolve_resource("one", "references/note.md")
    assert target.read_text() == "hello"


def test_resolve_resource_rejects_escape(tmp_path: Path) -> None:
    _write(tmp_path, "one", "name: one\ndescription: x")
    (tmp_path / "other.txt").write_text("secret", encoding="utf-8")
    reg = SkillRegistry([tmp_path])
    with pytest.raises(SkillError, match="escapes skill"):
        reg.resolve_resource("one", "../other.txt")


def test_resolve_resource_missing_file_raises(tmp_path: Path) -> None:
    _write(tmp_path, "one", "name: one\ndescription: x")
    reg = SkillRegistry([tmp_path])
    with pytest.raises(FileNotFoundError):
        reg.resolve_resource("one", "references/nope.md")


def test_resolve_resource_unknown_skill_raises(tmp_path: Path) -> None:
    _write(tmp_path, "one", "name: one\ndescription: x")
    reg = SkillRegistry([tmp_path])
    with pytest.raises(UnknownSkillError):
        reg.resolve_resource("missing", "references/x.md")


def test_resolve_resource_empty_path_raises_value_error(tmp_path: Path) -> None:
    _write(tmp_path, "one", "name: one\ndescription: x")
    reg = SkillRegistry([tmp_path])
    with pytest.raises(ValueError, match="non-empty"):
        reg.resolve_resource("one", "")


def test_resolve_resource_escape_raises_unsafe_skill_name(tmp_path: Path) -> None:
    _write(tmp_path, "one", "name: one\ndescription: x")
    (tmp_path / "other.txt").write_text("secret", encoding="utf-8")
    reg = SkillRegistry([tmp_path])
    with pytest.raises(UnsafeSkillNameError, match="escapes skill"):
        reg.resolve_resource("one", "../other.txt")


# --- SPEC §1.2 — reserved subdirs and nested SKILL.md pruning ----------------


def test_reserved_subdir_references_is_not_walked(tmp_path: Path) -> None:
    """A SKILL.md placed under references/ MUST be ignored."""
    outer = _write(tmp_path, "outer", "name: outer\ndescription: x")
    refs = outer / "references"
    refs.mkdir()
    # An obvious anti-pattern: a SKILL.md inside the reserved dir.
    (refs / "SKILL.md").write_text(
        "---\nname: references\ndescription: oops\n---\n", encoding="utf-8"
    )
    reg = SkillRegistry([tmp_path])
    assert reg.names() == ["outer"]


def test_reserved_subdir_scripts_is_not_walked(tmp_path: Path) -> None:
    outer = _write(tmp_path, "outer", "name: outer\ndescription: x")
    scripts = outer / "scripts"
    scripts.mkdir()
    (scripts / "SKILL.md").write_text(
        "---\nname: scripts\ndescription: oops\n---\n", encoding="utf-8"
    )
    reg = SkillRegistry([tmp_path])
    assert reg.names() == ["outer"]


def test_reserved_subdir_assets_is_not_walked(tmp_path: Path) -> None:
    outer = _write(tmp_path, "outer", "name: outer\ndescription: x")
    assets = outer / "assets"
    assets.mkdir()
    (assets / "SKILL.md").write_text(
        "---\nname: assets\ndescription: oops\n---\n", encoding="utf-8"
    )
    reg = SkillRegistry([tmp_path])
    assert reg.names() == ["outer"]


def test_nested_skill_md_inside_skill_is_pruned(tmp_path: Path) -> None:
    """SPEC §1.2: once a SKILL.md is found, do not descend further."""
    outer = _write(tmp_path, "outer", "name: outer\ndescription: x")
    inner = outer / "internal-not-a-skill"
    inner.mkdir()
    (inner / "SKILL.md").write_text(
        "---\nname: internal-not-a-skill\ndescription: oops\n---\n",
        encoding="utf-8",
    )
    reg = SkillRegistry([tmp_path])
    assert reg.names() == ["outer"]


def test_reserved_dir_name_at_root_is_walked(tmp_path: Path) -> None:
    """`references` etc. is only reserved INSIDE a skill — at the root level
    it is a normal category directory."""
    refs_root = tmp_path / "references"
    refs_root.mkdir()
    _write(refs_root, "alpha", "name: alpha\ndescription: x")
    reg = SkillRegistry([tmp_path])
    assert reg.names() == ["alpha"]


def test_hidden_dirs_skipped(tmp_path: Path) -> None:
    """`.git`, `.venv`, etc. should not break discovery or register skills."""
    hidden = tmp_path / ".git"
    hidden.mkdir()
    (hidden / "SKILL.md").write_text(
        "---\nname: git\ndescription: oops\n---\n", encoding="utf-8"
    )
    _write(tmp_path, "alpha", "name: alpha\ndescription: x")
    reg = SkillRegistry([tmp_path])
    assert reg.names() == ["alpha"]


# --- license validation ------------------------------------------------------


def test_license_optional(tmp_path: Path) -> None:
    _write(tmp_path, "one", "name: one\ndescription: x")
    assert SkillRegistry([tmp_path]).get("one").license is None


def test_license_string_passes_through(tmp_path: Path) -> None:
    _write(tmp_path, "one", "name: one\ndescription: x\nlicense: Apache-2.0")
    assert SkillRegistry([tmp_path]).get("one").license == "Apache-2.0"


def test_license_non_string_raises(tmp_path: Path) -> None:
    _write(tmp_path, "one", "name: one\ndescription: x\nlicense: 42")
    with pytest.raises(SkillValidationError, match="`license` must be a string"):
        SkillRegistry([tmp_path])


# --- missing frontmatter reaches the user with a clear error ----------------


def test_missing_frontmatter_block_produces_clear_error(tmp_path: Path) -> None:
    skill_dir = tmp_path / "broken"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# just a body\n", encoding="utf-8")
    from skillfull.errors import SkillParseError

    with pytest.raises(SkillParseError, match="must begin with"):
        SkillRegistry([tmp_path])
