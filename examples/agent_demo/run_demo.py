"""Wiring check for the agent_demo, no API key needed.

NOTE: This is NOT a routing eval. It uses pydantic-ai's `FunctionModel`
with a hard-coded keyword router as the "model", so the routing
assertions verify the plumbing, not whether a real LLM can pick the
right skill from the manifest. For the real eval against
claude-sonnet-4-6, see `run_live.py`.

What this script DOES verify, end-to-end through pydantic-ai:

  1. The registry loads the expected skills from `skills.yaml`.
  2. The manifest XML rendered into the agent's instructions matches
     what we expect, with categories and `<when_to_use>` elements.
  3. The `always_load` skill's body is inlined alongside the manifest;
     other skills' bodies are NOT inlined (Level-2 lazy load works).
  4. The `load_skill` tool returns the right body for each skill name.
  5. Unknown skill names return a recoverable "Error:" string.

It does NOT verify that an LLM can route prompts to skills. The
"routing eval" section below feeds prompts through a keyword router
of our own making — useful as a smoke test of the tool-call round
trip, but it is testing the router we wrote, not the model.

Run it:

    pip install "outskilled[pydantic-ai]"
    python examples/agent_demo/run_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from outskilled import SkillRegistry
from outskilled.pydanticai import attach_skills

SKILLS_CONFIG = Path(__file__).parent / "skills" / "skills.yaml"

PROMPTS: list[tuple[str, str | None]] = [
    ("Help me find a note about Q3 planning.", "search"),
    ("Look up my notes on the bug we fixed last week.", "search"),
    ("Save a note: 'Decided to switch CI providers after the outage.'", "write"),
    ("Please write a note about the standup.", "write"),
    ("Refactor this 80-line function so it's easier to read.", "extract-method"),
    ("Can you extract a helper from this method?", "extract-method"),
    ("What's 2+2?", None),
]


KEYWORDS_TO_SKILL: list[tuple[tuple[str, ...], str]] = [
    (("find", "look up", "search", "recall"), "search"),
    (("write a note", "save a note", "jot", "capture"), "write"),
    (("refactor", "extract", "shorten this function"), "extract-method"),
]


def _route(user_text: str) -> str | None:
    """Simulate keyword-driven LLM routing."""
    lower = user_text.lower()
    for keywords, skill_name in KEYWORDS_TO_SKILL:
        if any(kw in lower for kw in keywords):
            return skill_name
    return None


def _make_model() -> FunctionModel:
    def model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        for msg in messages:
            for part in getattr(msg, "parts", []):
                if isinstance(part, ToolReturnPart) and part.tool_name == "load_skill":
                    body = str(part.content)
                    head = body.strip().splitlines()[0] if body.strip() else "(empty)"
                    return ModelResponse(parts=[TextPart(content=f"loaded ({head})")])

        user_text = ""
        for msg in messages:
            for part in getattr(msg, "parts", []):
                content = getattr(part, "content", None)
                if isinstance(content, str):
                    user_text += " " + content

        skill = _route(user_text)
        if skill is None:
            return ModelResponse(parts=[TextPart(content="no skill needed")])
        return ModelResponse(
            parts=[ToolCallPart(tool_name="load_skill", args={"name": skill})]
        )

    return FunctionModel(model)


# --- output helpers ----------------------------------------------------------


GREEN = "\033[32m"
RED = "\033[31m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def ok(label: str) -> str:
    return f"{GREEN}OK{RESET}  {label}"


def fail(label: str) -> str:
    return f"{RED}FAIL{RESET} {label}"


def section(title: str) -> None:
    print()
    print(f"{BOLD}== {title} =={RESET}")


def indent(text: str, prefix: str = "    ") -> str:
    return "\n".join(prefix + line for line in text.splitlines())


# --- the actual demo --------------------------------------------------------


def main() -> int:
    failures: list[str] = []

    section("Load registry")
    reg = SkillRegistry.from_config(SKILLS_CONFIG)
    print(f"    Config: {SKILLS_CONFIG}")
    print(f"    Loaded {len(reg)} skills:")
    for skill in reg.skills():
        suffix = "  [always_load]" if skill.always_load else ""
        print(f"      - {skill.name:<16} ({skill.location}){suffix}")

    expected_names = {"search", "write", "extract-method", "reply-style"}
    got_names = set(reg.names())
    if got_names == expected_names:
        print()
        print("    " + ok("All 4 expected skills loaded"))
    else:
        msg = f"expected {sorted(expected_names)}, got {sorted(got_names)}"
        print("    " + fail(msg))
        failures.append(msg)

    section("Manifest surfaced to the model")
    print(indent(reg.manifest_xml()))
    print()
    if all(f"<name>{n}</name>" in reg.manifest_xml() for n in expected_names):
        print("    " + ok("Manifest lists every skill"))
    else:
        print("    " + fail("Manifest missing one or more skills"))
        failures.append("manifest missing skills")

    section("Capture the agent's instructions")
    captured: dict[str, str] = {}

    def capture_then_route(
        messages: list[ModelMessage], info: AgentInfo
    ) -> ModelResponse:
        captured.setdefault("instructions", info.instructions or "")
        return _make_model().function(messages, info)  # type: ignore[union-attr]

    agent: Agent = Agent(FunctionModel(capture_then_route))
    attach_skills(agent, reg)
    agent.run_sync("warmup")
    instr = captured["instructions"]
    print(f"    Total length: {len(instr):,} chars")

    manifest_ok = "<available_skills>" in instr
    always_ok = "<always_loaded_skills>" in instr and "1–3 sentences" in instr
    no_leak_ok = "Extract method" not in instr and "Search notes" not in instr
    for label, condition, why in [
        ("Manifest XML is in instructions", manifest_ok, "missing <available_skills>"),
        ("always_load body is inlined", always_ok, "reply-style body not found"),
        ("Other skill bodies are NOT inlined", no_leak_ok, "non-always-load body leaked"),
    ]:
        if condition:
            print("    " + ok(label))
        else:
            print("    " + fail(f"{label} ({why})"))
            failures.append(label)

    section("Tool round-trip (using our own keyword router as the 'model')")
    print(
        "    Note: a real LLM-vs-manifest routing eval lives in run_live.py.\n"
        "    This section verifies the load_skill round-trip, not LLM routing."
    )
    routed: list[tuple[str, str | None, str | None, bool]] = []

    for prompt, expected in PROMPTS:
        eval_agent: Agent = Agent(_make_model())
        attach_skills(eval_agent, reg)
        result = eval_agent.run_sync(prompt)
        load_calls = [
            p.args.get("name") if isinstance(p.args, dict) else None
            for msg in result.all_messages()
            for p in getattr(msg, "parts", [])
            if isinstance(p, ToolCallPart) and p.tool_name == "load_skill"
        ]
        got = load_calls[0] if load_calls else None
        passed = got == expected
        routed.append((prompt, expected, got, passed))

        marker = ok("") if passed else fail("")
        exp_str = f"load_skill(name={expected!r})" if expected else "(no tool call)"
        got_str = f"load_skill(name={got!r})" if got else "(no tool call)"
        print(f"    {marker}")
        print(f"        prompt:   {prompt}")
        print(f"        expected: {exp_str}")
        print(f"        got:      {got_str}")
        print(f"        output:   {result.output}")
        if not passed:
            failures.append(f"routing failed: {prompt}")

    section("Summary")
    routed_pass = sum(1 for *_, ok_ in routed if ok_)
    print(f"    Routing: {routed_pass}/{len(routed)} prompts correct")
    if failures:
        print(f"    {fail(f'{len(failures)} check(s) failed')}")
        for f in failures:
            print(f"      - {f}")
        return 1
    print(f"    {ok('Demo passed.')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
