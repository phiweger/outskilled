"""End-to-end skill-routing eval.

Wires the example skills directory into a pydantic-ai Agent, then runs
a small suite of prompts through a deterministic `FunctionModel` that
simulates a keyword-routed LLM. The asserts confirm that:

  1. The manifest in the model's instructions includes every skill.
  2. The `reply-style` skill (always_load: true) is inlined.
  3. The model can call `load_skill` to fetch the right body for each
     prompt (Level 2 progressive disclosure).
  4. Unknown skill names yield a recoverable error string rather than
     crashing the run.

Runs in CI — no API key, no network.
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

from outskilled.pydanticai import attach_skills  # noqa: E402

SKILLS_CONFIG = Path(__file__).parent / "skills" / "skills.yaml"


# --- Keyword router ----------------------------------------------------------


KEYWORDS_TO_SKILL = [
    (("find", "look up", "search", "recall"), "search"),
    (("write a note", "save a note", "jot", "capture"), "write"),
    (("refactor", "extract", "shorten this function"), "extract-method"),
]


def _route(user_text: str) -> str | None:
    """Pick the skill whose trigger phrases appear in the user's text."""
    lower = user_text.lower()
    for keywords, skill_name in KEYWORDS_TO_SKILL:
        if any(kw in lower for kw in keywords):
            return skill_name
    return None


def _make_routed_model() -> FunctionModel:
    """A FunctionModel that:
       - On its first call, inspects the user's prompt, picks a skill
         via `_route`, and calls `load_skill` for it.
       - On its second call (after the tool result is in messages),
         emits "done: <skill-name>".
       - If no skill matches the prompt, just emits "no skill needed".
    """

    def model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        # Step 2: already saw a load_skill return → finish.
        for msg in messages:
            for part in getattr(msg, "parts", []):
                if isinstance(part, ToolReturnPart) and part.tool_name == "load_skill":
                    return ModelResponse(parts=[TextPart(content=f"done: {part.content[:50]}")])

        # Step 1: route based on the user prompt.
        user_text = ""
        for msg in messages:
            for part in getattr(msg, "parts", []):
                content = getattr(part, "content", None)
                if isinstance(content, str):
                    user_text += " " + content

        skill = _route(user_text)
        if skill is None:
            return ModelResponse(parts=[TextPart(content="no skill needed")])
        return ModelResponse(parts=[ToolCallPart(tool_name="load_skill", args={"name": skill})])

    return FunctionModel(model)


# --- Fixtures ----------------------------------------------------------------


@pytest.fixture
def agent_and_state() -> tuple[Agent, dict[str, str]]:
    captured: dict[str, str] = {}

    def instrumented_model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        captured.setdefault("instructions", info.instructions or "")
        return _make_routed_model().function(messages, info)  # type: ignore[union-attr]

    agent: Agent = Agent(FunctionModel(instrumented_model))
    attach_skills(agent, SKILLS_CONFIG)
    return agent, captured


# --- (1) Manifest content ----------------------------------------------------


def test_manifest_lists_every_skill(agent_and_state) -> None:
    agent, state = agent_and_state
    agent.run_sync("hello")
    instr = state["instructions"]
    assert "<name>search</name>" in instr
    assert "<name>write</name>" in instr
    assert "<name>extract-method</name>" in instr
    assert "<name>reply-style</name>" in instr


def test_manifest_contains_locations_with_categories(agent_and_state) -> None:
    agent, state = agent_and_state
    agent.run_sync("hello")
    instr = state["instructions"]
    assert "<location>notes/search</location>" in instr
    assert "<location>notes/write</location>" in instr
    assert "<location>code/refactor/extract-method</location>" in instr


# --- (2) always_load inlining ------------------------------------------------


def test_reply_style_body_inlined(agent_and_state) -> None:
    agent, state = agent_and_state
    agent.run_sync("hello")
    instr = state["instructions"]
    assert "<always_loaded_skills>" in instr
    assert "Reply in **1–3 sentences**" in instr
    # The other skills' bodies are NOT inlined (Level 2 only).
    assert "Extract method" not in instr
    assert "Search notes" not in instr


# --- (3) Routing — model picks the right skill per prompt -------------------


@pytest.mark.parametrize(
    "prompt,expected_skill",
    [
        ("Help me find a note about Q3 planning", "search"),
        ("Look up my notes on the bug we fixed last week", "search"),
        ("Save a note: bought milk today", "write"),
        ("Please write a note about the standup", "write"),
        ("Refactor this function, it's 80 lines long", "extract-method"),
        ("Can you extract a helper from this method?", "extract-method"),
    ],
)
def test_agent_routes_prompt_to_expected_skill(prompt: str, expected_skill: str) -> None:
    agent: Agent = Agent(_make_routed_model())
    attach_skills(agent, SKILLS_CONFIG)
    result = agent.run_sync(prompt)

    load_calls = [
        (p.tool_name, p.args)
        for msg in result.all_messages()
        for p in getattr(msg, "parts", [])
        if isinstance(p, ToolCallPart) and p.tool_name == "load_skill"
    ]
    assert load_calls == [
        ("load_skill", {"name": expected_skill})
    ], f"Expected the agent to load {expected_skill!r}, got {load_calls}"
    assert "done:" in result.output


def test_unrelated_prompt_does_not_load_a_skill() -> None:
    agent: Agent = Agent(_make_routed_model())
    attach_skills(agent, SKILLS_CONFIG)
    result = agent.run_sync("What's 2+2?")
    load_calls = [
        p
        for msg in result.all_messages()
        for p in getattr(msg, "parts", [])
        if isinstance(p, ToolCallPart) and p.tool_name == "load_skill"
    ]
    assert load_calls == []
    assert "no skill needed" in result.output


# --- (4) Recoverable errors --------------------------------------------------


def test_load_skill_with_bad_name_returns_error_string() -> None:
    def model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        already_tried = any(
            isinstance(p, ToolReturnPart) and p.tool_name == "load_skill"
            for msg in messages
            for p in getattr(msg, "parts", [])
        )
        if already_tried:
            return ModelResponse(parts=[TextPart(content="recovered")])
        return ModelResponse(
            parts=[ToolCallPart(tool_name="load_skill", args={"name": "nonexistent"})]
        )

    agent: Agent = Agent(FunctionModel(model))
    attach_skills(agent, SKILLS_CONFIG)
    result = agent.run_sync("trigger")

    tool_returns = [
        p.content
        for msg in result.all_messages()
        for p in getattr(msg, "parts", [])
        if isinstance(p, ToolReturnPart) and p.tool_name == "load_skill"
    ]
    assert any("Error:" in str(c) for c in tool_returns)
    # The agent kept running rather than crashing — that's the point.
    assert result.output == "recovered"
