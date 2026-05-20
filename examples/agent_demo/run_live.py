"""End-to-end skill-routing eval with a real LLM.

Talks to Anthropic's API. For each prompt, attaches the bundled
skills to a pydantic-ai Agent and asserts the model picks the
expected skill purely from the manifest in its instructions — no
keyword stub, no mocking, no shortcuts.

Usage:

    pip install "outskilled[pydantic-ai]" anthropic
    export ANTHROPIC_API_KEY=...
    python examples/agent_demo/run_live.py

Optional env vars:

    OUTSKILLED_EVAL_MODEL   # default: anthropic:claude-sonnet-4-6
    OUTSKILLED_EVAL_SAMPLES # default: 1 — runs per prompt; reports hit-rate

Exit codes:

    0  every prompt routed to its expected skill (or skipped for "no
       skill needed" prompts and the model emitted no tool call).
    1  one or more prompts routed wrong.
    2  ANTHROPIC_API_KEY missing or pydantic-ai import failed.

The eval is intentionally small (eight prompts) so it costs little to
run. Each run is a single sample by default; bump `OUTSKILLED_EVAL_SAMPLES`
to N to run each prompt N times and report a hit-rate per prompt.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.messages import ToolCallPart

from outskilled.pydanticai import attach_skills

SKILLS_CONFIG = Path(__file__).parent / "skills" / "skills.yaml"

DEFAULT_MODEL = "anthropic:claude-sonnet-4-6"


@dataclass(frozen=True)
class Case:
    prompt: str
    expected: str | None  # None means "no skill needed"
    rationale: str  # for human reading of the output


CASES: list[Case] = [
    Case(
        prompt="Help me find a note about Q3 planning.",
        expected="search",
        rationale="explicit 'find a note' phrasing",
    ),
    Case(
        prompt="Where did I put my notes on the bug we fixed last week?",
        expected="search",
        rationale="locate-existing-note paraphrase without the word 'search'",
    ),
    Case(
        prompt="Save a note: 'Decided to switch CI providers after the outage.'",
        expected="write",
        rationale="explicit save-a-note request",
    ),
    Case(
        prompt="Jot down that the standup is moving to 10am.",
        expected="write",
        rationale="'jot down' synonym for note-writing",
    ),
    Case(
        prompt="This 80-line function does too much, can you refactor it?",
        expected="extract-method",
        rationale="explicit refactor request on a long function",
    ),
    Case(
        prompt="Pull the parsing logic out of this method into its own helper.",
        expected="extract-method",
        rationale="paraphrase: extract helper from a method",
    ),
    Case(
        prompt="What's the capital of Portugal?",
        expected=None,
        rationale="trivia, no skill applies",
    ),
    Case(
        prompt="Thanks, that's all for now.",
        expected=None,
        rationale="conversational closer, no skill applies",
    ),
]


# --- output helpers ----------------------------------------------------------


GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def ok(label: str = "") -> str:
    return f"{GREEN}OK{RESET}   {label}"


def fail(label: str = "") -> str:
    return f"{RED}FAIL{RESET} {label}"


def partial(label: str = "") -> str:
    return f"{YELLOW}MEH{RESET}  {label}"


def section(title: str) -> None:
    print()
    print(f"{BOLD}== {title} =={RESET}")


# --- single-run helper -------------------------------------------------------


def first_load_skill_name(agent_result) -> str | None:
    """Return the `name` arg of the first load_skill call, or None."""
    for msg in agent_result.all_messages():
        for part in getattr(msg, "parts", []):
            if isinstance(part, ToolCallPart) and part.tool_name == "load_skill":
                args = part.args if isinstance(part.args, dict) else {}
                name = args.get("name")
                if isinstance(name, str):
                    return name
    return None


def run_one(model: str, case: Case) -> tuple[str | None, str]:
    """Run a single prompt against the model. Returns (loaded_skill, output)."""
    agent: Agent = Agent(model)
    attach_skills(agent, SKILLS_CONFIG)
    result = agent.run_sync(case.prompt)
    return first_load_skill_name(result), str(result.output)


# --- main --------------------------------------------------------------------


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            f"{fail('ANTHROPIC_API_KEY is not set.')} "
            "This eval needs a real model — set the env var and rerun.",
            file=sys.stderr,
        )
        return 2

    model = os.environ.get("OUTSKILLED_EVAL_MODEL", DEFAULT_MODEL)
    try:
        samples = max(1, int(os.environ.get("OUTSKILLED_EVAL_SAMPLES", "1")))
    except ValueError:
        samples = 1

    section("Configuration")
    print(f"    Model:   {model}")
    print(f"    Samples: {samples} per prompt")
    print(f"    Cases:   {len(CASES)}")
    print(f"    Skills:  {SKILLS_CONFIG}")

    section("Routing eval")
    pass_count = 0
    total_runs = 0
    rows: list[tuple[Case, int, list[str | None]]] = []

    for case in CASES:
        hits: list[str | None] = []
        for _ in range(samples):
            try:
                loaded, _output = run_one(model, case)
            except Exception as exc:  # network / API failures
                print(f"    {fail('exception')} {case.prompt!r}: {exc}")
                hits.append("__error__")
                continue
            hits.append(loaded)

        case_hits = sum(1 for h in hits if h == case.expected)
        rows.append((case, case_hits, hits))
        pass_count += case_hits
        total_runs += samples

        if case_hits == samples:
            marker = ok()
        elif case_hits == 0:
            marker = fail()
        else:
            marker = partial(f"{case_hits}/{samples}")

        exp_str = (
            f"load_skill(name={case.expected!r})"
            if case.expected
            else "(no tool call)"
        )
        print(f"    {marker}")
        print(f"        prompt:    {case.prompt}")
        print(f"        rationale: {case.rationale}")
        print(f"        expected:  {exp_str}")
        for i, h in enumerate(hits, 1):
            if h == "__error__":
                got = "(exception)"
            elif h is None:
                got = "(no tool call)"
            else:
                got = f"load_skill(name={h!r})"
            tag = "OK" if h == case.expected else "X"
            prefix = f"sample {i}" if samples > 1 else "got"
            print(f"        {prefix}: {got}  [{tag}]")

    section("Summary")
    print(f"    Hit rate: {pass_count}/{total_runs} ({pass_count / total_runs:.0%})")

    fails = [c for c, hits, _ in rows if hits < samples]
    if not fails:
        print(f"    {ok('Every prompt routed correctly on every sample.')}")
        return 0

    miss_count = len([c for c, hits, _ in rows if hits == 0])
    if miss_count == 0:
        print(
            f"    {partial(f'{len(fails)} prompt(s) flaky — at least one sample misrouted.')}"
        )
    else:
        print(f"    {fail(f'{miss_count} prompt(s) misrouted on every sample.')}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
