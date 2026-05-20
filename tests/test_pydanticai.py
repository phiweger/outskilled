"""Tests for the pydantic-ai adapter.

Skipped automatically when pydantic-ai is not installed (it's an
optional extra). The deterministic tests use pydantic-ai's
`FunctionModel` so no API key or network is required.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pydantic_ai = pytest.importorskip("pydantic_ai")

from pydantic_ai import Agent  # noqa: E402
from pydantic_ai.messages import (  # noqa: E402
    ModelMessage,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel  # noqa: E402

from outskilled import SkillError, SkillRegistry  # noqa: E402
from outskilled.pydanticai import attach_skills, skill_aware_agent  # noqa: E402


def _write(parent: Path, dirname: str, frontmatter: str, body: str = "body\n") -> Path:
    skill_dir = parent / dirname
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n\n{body}", encoding="utf-8")
    return skill_dir


def _last_tool_returns(messages: list[ModelMessage]) -> list[tuple[str, str]]:
    """Pull (tool_name, content) pairs out of the message stream."""
    out: list[tuple[str, str]] = []
    for msg in messages:
        for part in getattr(msg, "parts", []):
            if isinstance(part, ToolReturnPart):
                out.append((part.tool_name, str(part.content)))
    return out


def _make_registry(tmp_path: Path) -> SkillRegistry:
    _write(
        tmp_path,
        "search",
        "name: search\n"
        "description: How to search notes by keyword.\n"
        "when_to_use: When the user asks to find a note.",
        body="# Search\nDo X.\n",
    )
    _write(
        tmp_path,
        "write",
        "name: write\n"
        "description: How to save a new note.\n"
        "when_to_use: When the user asks to write a note.",
        body="# Write\nDo Y.\n",
    )
    _write(
        tmp_path / "code" / "refactor",
        "extract-method",
        "name: extract-method\n"
        "description: How to refactor a long function by extracting helpers.",
        body="# Extract\nSplit it.\n",
    )
    _write(
        tmp_path,
        "reply-style",
        "name: reply-style\n"
        "description: Tone rules for every response.\n"
        "always_load: true",
        body="Be concise. No emojis.\n",
    )
    return SkillRegistry([tmp_path])


# --- attach_skills wiring ----------------------------------------------------


def test_attach_skills_returns_registry(tmp_path: Path) -> None:
    reg = _make_registry(tmp_path)
    agent: Agent = Agent(FunctionModel(lambda m, i: ModelResponse(parts=[TextPart("ok")])))
    out = attach_skills(agent, reg)
    assert out is reg


def test_attach_skills_from_config_path(tmp_path: Path) -> None:
    _make_registry(tmp_path)
    (tmp_path / "skills.yaml").write_text("roots: [.]\n", encoding="utf-8")
    agent: Agent = Agent(FunctionModel(lambda m, i: ModelResponse(parts=[TextPart("ok")])))
    reg = attach_skills(agent, tmp_path / "skills.yaml")
    assert "search" in reg
    assert "extract-method" in reg


def test_skill_aware_agent_constructs_agent(tmp_path: Path) -> None:
    _make_registry(tmp_path)
    (tmp_path / "skills.yaml").write_text("roots: [.]\n", encoding="utf-8")
    agent = skill_aware_agent(
        FunctionModel(lambda m, i: ModelResponse(parts=[TextPart("ok")])),
        skills=tmp_path / "skills.yaml",
    )
    assert isinstance(agent, Agent)


# --- instructions block ------------------------------------------------------


def test_instructions_carry_manifest_and_always_loaded_bodies(tmp_path: Path) -> None:
    reg = _make_registry(tmp_path)
    captured: dict[str, str] = {}

    def capture_instructions(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        captured["instructions"] = info.instructions or ""
        return ModelResponse(parts=[TextPart(content="done")])

    agent: Agent = Agent(FunctionModel(capture_instructions))
    attach_skills(agent, reg)
    agent.run_sync("hello")

    instructions = captured["instructions"]
    # Manifest entries are present.
    assert "<name>search</name>" in instructions
    assert "<location>code/refactor/extract-method</location>" in instructions
    # always_load: true skill has its body inlined alongside the manifest.
    assert "<always_loaded_skills>" in instructions
    assert "Be concise. No emojis." in instructions
    # Non-always-loaded bodies are NOT inlined.
    assert "Do X." not in instructions


def test_instructions_manifest_disabled(tmp_path: Path) -> None:
    reg = _make_registry(tmp_path)
    captured: dict[str, str] = {}

    def capture(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        captured["instructions"] = info.instructions or ""
        return ModelResponse(parts=[TextPart(content="done")])

    agent: Agent = Agent(FunctionModel(capture))
    attach_skills(agent, reg, manifest=False)
    agent.run_sync("hi")
    assert "<available_skills>" not in captured["instructions"]


def test_always_load_opt_out(tmp_path: Path) -> None:
    reg = _make_registry(tmp_path)
    captured: dict[str, str] = {}

    def capture(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        captured["instructions"] = info.instructions or ""
        return ModelResponse(parts=[TextPart(content="done")])

    agent: Agent = Agent(FunctionModel(capture))
    attach_skills(agent, reg, always_load=False)
    agent.run_sync("hi")
    assert "<always_loaded_skills>" not in captured["instructions"]
    assert "Be concise" not in captured["instructions"]


def test_always_load_inlines_even_when_manifest_disabled(tmp_path: Path) -> None:
    """`always_load` bodies are independent of the manifest flag (§3.7)."""
    reg = _make_registry(tmp_path)
    captured: dict[str, str] = {}

    def capture(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        captured["instructions"] = info.instructions or ""
        return ModelResponse(parts=[TextPart(content="done")])

    agent: Agent = Agent(FunctionModel(capture))
    attach_skills(agent, reg, manifest=False, always_load=True)
    agent.run_sync("hi")
    instr = captured["instructions"]
    # No manifest...
    assert "<available_skills>" not in instr
    # ...but the always-loaded body IS inlined.
    assert "<always_loaded_skills>" in instr
    assert "Be concise. No emojis." in instr


def test_no_instructions_registered_when_both_flags_off(tmp_path: Path) -> None:
    """If manifest=False and always_load=False, no instructions hook is set."""
    reg = _make_registry(tmp_path)
    seen: dict[str, str | None] = {}

    def capture(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        seen["instructions"] = info.instructions
        return ModelResponse(parts=[TextPart(content="done")])

    agent: Agent = Agent(FunctionModel(capture))
    attach_skills(agent, reg, manifest=False, always_load=False)
    agent.run_sync("hi")
    # `instructions` is None or empty when no hook registers anything.
    assert not seen["instructions"]


# --- idempotency -------------------------------------------------------------


def test_attach_skills_is_not_idempotent_raises_on_double_call(tmp_path: Path) -> None:
    reg = _make_registry(tmp_path)
    agent: Agent = Agent(FunctionModel(lambda m, i: ModelResponse(parts=[TextPart("ok")])))
    attach_skills(agent, reg)
    with pytest.raises(SkillError, match="already been called"):
        attach_skills(agent, reg)


# --- load_skill tool routing -------------------------------------------------


def _routing_model(target_skill: str):
    """Build a FunctionModel that calls `load_skill(name=target_skill)` once
    and then returns 'done' after seeing the tool result."""

    def model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        already_loaded = any(
            isinstance(p, ToolReturnPart) and p.tool_name == "load_skill"
            for msg in messages
            for p in getattr(msg, "parts", [])
        )
        if already_loaded:
            return ModelResponse(parts=[TextPart(content="done")])
        return ModelResponse(
            parts=[ToolCallPart(tool_name="load_skill", args={"name": target_skill})]
        )

    return model


@pytest.mark.parametrize(
    "skill_name,expected_in_body",
    [
        ("search", "Do X."),
        ("write", "Do Y."),
        ("extract-method", "Split it."),
    ],
)
def test_load_skill_returns_body_for_each_skill(
    tmp_path: Path, skill_name: str, expected_in_body: str
) -> None:
    reg = _make_registry(tmp_path)
    agent: Agent = Agent(FunctionModel(_routing_model(skill_name)))
    attach_skills(agent, reg)

    result = agent.run_sync(f"Please use the {skill_name} skill.")
    tool_returns = _last_tool_returns(result.all_messages())
    load_returns = [content for name, content in tool_returns if name == "load_skill"]
    assert len(load_returns) == 1, f"expected exactly one load_skill call, got {load_returns}"
    assert expected_in_body in load_returns[0]
    assert "done" in result.output


def test_load_skill_unknown_returns_friendly_error(tmp_path: Path) -> None:
    reg = _make_registry(tmp_path)
    agent: Agent = Agent(FunctionModel(_routing_model("does-not-exist")))
    attach_skills(agent, reg)
    result = agent.run_sync("trigger")
    tool_returns = _last_tool_returns(result.all_messages())
    assert any(content.startswith("Error:") for _, content in tool_returns)


def test_load_skill_rejects_traversal_via_tool(tmp_path: Path) -> None:
    reg = _make_registry(tmp_path)
    agent: Agent = Agent(FunctionModel(_routing_model("../etc/passwd")))
    attach_skills(agent, reg)
    result = agent.run_sync("trigger")
    tool_returns = _last_tool_returns(result.all_messages())
    assert any("unsafe" in content.lower() or "Error:" in content for _, content in tool_returns)


# --- optional tools ----------------------------------------------------------


def test_resource_tool_reads_under_skill_dir(tmp_path: Path) -> None:
    reg = _make_registry(tmp_path)
    refs = tmp_path / "search" / "references"
    refs.mkdir()
    (refs / "cheatsheet.md").write_text("KEYS: foo bar", encoding="utf-8")

    def model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        already_read = any(
            isinstance(p, ToolReturnPart) and p.tool_name == "read_skill_resource"
            for msg in messages
            for p in getattr(msg, "parts", [])
        )
        if already_read:
            return ModelResponse(parts=[TextPart(content="done")])
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="read_skill_resource",
                    args={"skill_name": "search", "relative_path": "references/cheatsheet.md"},
                )
            ]
        )

    agent: Agent = Agent(FunctionModel(model))
    attach_skills(agent, reg, resource_tool=True)
    result = agent.run_sync("read it")
    tool_returns = _last_tool_returns(result.all_messages())
    assert ("read_skill_resource", "KEYS: foo bar") in tool_returns


def test_list_skills_tool_returns_manifest(tmp_path: Path) -> None:
    reg = _make_registry(tmp_path)

    def model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        already_listed = any(
            isinstance(p, ToolReturnPart) and p.tool_name == "list_skills"
            for msg in messages
            for p in getattr(msg, "parts", [])
        )
        if already_listed:
            return ModelResponse(parts=[TextPart(content="done")])
        return ModelResponse(parts=[ToolCallPart(tool_name="list_skills", args={})])

    agent: Agent = Agent(FunctionModel(model))
    attach_skills(agent, reg, list_tool=True)
    result = agent.run_sync("what's available?")
    tool_returns = _last_tool_returns(result.all_messages())
    assert any("<available_skills>" in content for _, content in tool_returns)
