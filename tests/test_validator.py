"""Validator tests — SPEC.md §3."""

from __future__ import annotations

from pathlib import Path

import pytest

from outskilled.errors import SkillValidationError, UnsafeSkillNameError
from outskilled.validator import (
    MAX_COMPATIBILITY_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
    MAX_WHEN_TO_USE_LENGTH,
    validate_allowed_tools,
    validate_always_load,
    validate_compatibility,
    validate_description,
    validate_frontmatter_keys,
    validate_metadata,
    validate_name,
    validate_path_component,
    validate_when_to_use,
)

# --- §3.1 name ----------------------------------------------------------------


def test_name_kebab_case_passes(tmp_path: Path) -> None:
    d = tmp_path / "good-name"
    d.mkdir()
    assert validate_name("good-name", d) == "good-name"


@pytest.mark.parametrize(
    "bad",
    [
        "Snake_Case",
        "snake_case",
        "UPPER",
        "-leading",
        "trailing-",
        "double--hyphen",
        "with space",
        "",
    ],
)
def test_name_rejects_non_kebab(tmp_path: Path, bad: str) -> None:
    d = tmp_path / "actual-dir"
    d.mkdir()
    with pytest.raises(SkillValidationError):
        validate_name(bad, d)


def test_name_must_match_dirname(tmp_path: Path) -> None:
    d = tmp_path / "actual-name"
    d.mkdir()
    with pytest.raises(SkillValidationError, match="must match its directory name"):
        validate_name("different-name", d)


def test_name_rejects_reserved_substrings(tmp_path: Path) -> None:
    for n in ("claude-helper", "anthropic-thing", "my-claude-skill"):
        d = tmp_path / n
        d.mkdir()
        with pytest.raises(SkillValidationError, match="reserved substring"):
            validate_name(n, d)


def test_name_length_capped(tmp_path: Path) -> None:
    long = "a" + "-a" * (MAX_NAME_LENGTH // 2)
    d = tmp_path / long
    d.mkdir()
    with pytest.raises(SkillValidationError, match="exceeds"):
        validate_name(long + "-extra", d)


# --- §3.2 description ---------------------------------------------------------


def test_description_normalises_whitespace(tmp_path: Path) -> None:
    out = validate_description("   hello\n   world  ", tmp_path)
    assert out == "hello world"


def test_description_must_be_non_empty(tmp_path: Path) -> None:
    with pytest.raises(SkillValidationError, match="non-empty"):
        validate_description("   \n  ", tmp_path)


def test_description_length_capped(tmp_path: Path) -> None:
    with pytest.raises(SkillValidationError, match="exceeds"):
        validate_description("x" * (MAX_DESCRIPTION_LENGTH + 1), tmp_path)


def test_description_rejects_angle_brackets(tmp_path: Path) -> None:
    with pytest.raises(SkillValidationError, match="`<` or `>`"):
        validate_description("has <tag> in it", tmp_path)


# --- §3.3 compatibility -------------------------------------------------------


def test_compatibility_optional(tmp_path: Path) -> None:
    assert validate_compatibility(None, tmp_path) is None


def test_compatibility_length_capped(tmp_path: Path) -> None:
    with pytest.raises(SkillValidationError, match="exceeds"):
        validate_compatibility("x" * (MAX_COMPATIBILITY_LENGTH + 1), tmp_path)


# --- §2.3 unknown keys --------------------------------------------------------


def test_unknown_frontmatter_key_raises(tmp_path: Path) -> None:
    with pytest.raises(SkillValidationError, match="unknown frontmatter keys"):
        validate_frontmatter_keys(
            {"name": "x", "description": "y", "tags": ["a"]}, tmp_path
        )


def test_known_keys_pass(tmp_path: Path) -> None:
    validate_frontmatter_keys(
        {
            "name": "x",
            "description": "y",
            "when_to_use": "when you see X",
            "always_load": True,
            "license": "MIT",
            "compatibility": "ok",
            "allowed-tools": ["bash"],
            "metadata": {"k": "v"},
        },
        tmp_path,
    )


# --- §3.6 when_to_use ---------------------------------------------------------


def test_when_to_use_optional(tmp_path: Path) -> None:
    assert validate_when_to_use(None, tmp_path) is None


def test_when_to_use_normalises_whitespace(tmp_path: Path) -> None:
    assert validate_when_to_use("   when\n  X  ", tmp_path) == "when X"


def test_when_to_use_blank_becomes_none(tmp_path: Path) -> None:
    assert validate_when_to_use("   \n  ", tmp_path) is None


def test_when_to_use_length_capped(tmp_path: Path) -> None:
    with pytest.raises(SkillValidationError, match="exceeds"):
        validate_when_to_use("x" * (MAX_WHEN_TO_USE_LENGTH + 1), tmp_path)


def test_when_to_use_rejects_angle_brackets(tmp_path: Path) -> None:
    with pytest.raises(SkillValidationError, match="`<` or `>`"):
        validate_when_to_use("trigger on <tag>", tmp_path)


def test_when_to_use_rejects_non_string(tmp_path: Path) -> None:
    with pytest.raises(SkillValidationError, match="must be a string"):
        validate_when_to_use(42, tmp_path)


# --- §3.7 always_load ---------------------------------------------------------


def test_always_load_defaults_false_when_absent(tmp_path: Path) -> None:
    assert validate_always_load(None, tmp_path) is False


def test_always_load_passes_through_bool(tmp_path: Path) -> None:
    assert validate_always_load(True, tmp_path) is True
    assert validate_always_load(False, tmp_path) is False


def test_always_load_rejects_non_bool(tmp_path: Path) -> None:
    with pytest.raises(SkillValidationError, match="must be a bool"):
        validate_always_load("yes", tmp_path)
    with pytest.raises(SkillValidationError, match="must be a bool"):
        validate_always_load(1, tmp_path)


# --- allowed-tools / metadata -------------------------------------------------


def test_allowed_tools_must_be_string_list(tmp_path: Path) -> None:
    assert validate_allowed_tools(["bash", "python"], tmp_path) == ("bash", "python")
    assert validate_allowed_tools(None, tmp_path) == ()
    with pytest.raises(SkillValidationError):
        validate_allowed_tools([1, 2], tmp_path)


def test_metadata_must_be_mapping(tmp_path: Path) -> None:
    assert validate_metadata({"a": "b"}, tmp_path) == {"a": "b"}
    assert validate_metadata(None, tmp_path) == {}
    with pytest.raises(SkillValidationError):
        validate_metadata("not a dict", tmp_path)


# --- §3.4 path traversal ------------------------------------------------------


@pytest.mark.parametrize("bad", ["../etc/passwd", "a/b", "a\\b", ".."])
def test_path_component_rejects_traversal(bad: str) -> None:
    with pytest.raises(UnsafeSkillNameError):
        validate_path_component(bad)


def test_path_component_allows_kebab_name() -> None:
    validate_path_component("flowchart-to-mermaid")
