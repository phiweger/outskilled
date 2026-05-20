"""Pydantic-AI adapter for skillfull.

Wires a `SkillRegistry` into a `pydantic_ai.Agent` so the model sees
the manifest in its instructions (Level 1) and can load skill bodies
on demand via a `load_skill` tool (Level 2). An opt-in
`read_skill_resource` tool exposes Level 3 reference files.

Optional dependency: install via `pip install skillfull[pydantic-ai]`.

Usage::

    from pydantic_ai import Agent
    from skillfull.pydanticai import attach_skills

    agent = Agent("anthropic:claude-sonnet-4-6")
    attach_skills(agent, "skills/skills.yaml")

Or the one-liner factory::

    from skillfull.pydanticai import skill_aware_agent
    agent = skill_aware_agent(
        "anthropic:claude-sonnet-4-6",
        skills="skills/skills.yaml",
    )
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from pydantic_ai import Agent
except ImportError as exc:  # pragma: no cover - guard only
    raise ImportError(
        "pydantic-ai is required for skillfull.pydanticai. "
        "Install with: pip install skillfull[pydantic-ai]"
    ) from exc

from skillfull.errors import SkillError, UnknownSkillError, UnsafeSkillNameError
from skillfull.registry import SkillRegistry

SKILL_INSTRUCTIONS_PREAMBLE = """\
You have access to a set of installed skills. Each skill is a piece of
specialised instructions you can load when relevant to the user's task.

The manifest below lists every skill by `<name>`, `<description>`, and
optional `<when_to_use>`. Use those fields to decide whether a skill
applies, then call the `load_skill` tool with the exact `<name>` to
load the skill's full instructions before acting."""


_ATTACHED_FLAG = "_skillfull_attached"


def attach_skills(
    agent: Agent[Any, Any],
    source: SkillRegistry | Path | str,
    *,
    manifest: bool = True,
    load_tool: bool = True,
    list_tool: bool = False,
    resource_tool: bool = False,
    always_load: bool = True,
) -> SkillRegistry:
    """Wire a SkillRegistry into a pydantic-ai Agent.

    Args:
        agent: The pydantic-ai Agent to extend. Mutated in place.
        source: A `SkillRegistry` instance, or a path to a `skills.yaml`
            config file (str or Path) that `SkillRegistry.from_config`
            can load.
        manifest: If True (default), register an `@agent.instructions`
            function that returns the rendered manifest XML, surfaced
            as Level-1 metadata in the system prompt.
        load_tool: If True (default), register `load_skill(name) -> str`
            as a tool the model can call to fetch a skill body
            (Level 2). Path-traversal-safe.
        list_tool: If True, also register `list_skills() -> str`. Useful
            when `manifest=False` (lazy listing) or as a refresh aid;
            most callers don't need this since the manifest is already
            in the system prompt.
        resource_tool: If True, register `read_skill_resource(skill,
            path) -> str` for Level-3 references (read files under
            `references/`, `scripts/`, `assets/`). Path is constrained
            to the skill's directory.
        always_load: If True (default), inline the body of every skill
            with `always_load: true` (§3.7) into the instructions.
            Independent of `manifest` — bodies are inlined even when
            the manifest is suppressed.

    Returns:
        The `SkillRegistry` actually used — handy for callers that
        passed a config path and want the resolved registry back.

    Raises:
        SkillError: If `attach_skills` has already been called on this
            agent. Idempotency would be ambiguous (which registry
            wins?), so a second call is an error.
    """
    if getattr(agent, _ATTACHED_FLAG, False):
        raise SkillError(
            "attach_skills has already been called on this Agent. "
            "Construct a new Agent if you need a different skill set."
        )
    registry = _coerce_registry(source)

    if manifest or always_load:
        prompt_block = _build_instructions(
            registry,
            include_manifest=manifest,
            inline_always_loaded=always_load,
        )
        if prompt_block:

            @agent.instructions
            def _skillfull_manifest() -> str:
                return prompt_block

    if load_tool:

        @agent.tool_plain
        def load_skill(name: str) -> str:
            """Load the full instructions for a named skill.

            Use this after consulting the <available_skills> manifest in
            your instructions to fetch the skill's full body. The `name`
            argument MUST be the exact value from the manifest's
            <name> element (kebab-case, no slashes).

            Args:
                name: The skill's `name` from the manifest.

            Returns:
                The skill body (markdown). On error, a short message
                starting with "Error:" so the model can recover rather
                than aborting the run.
            """
            try:
                return registry.load(name)
            except (UnknownSkillError, UnsafeSkillNameError) as exc:
                return f"Error: {exc}"

    if list_tool:

        @agent.tool_plain
        def list_skills() -> str:
            """List every installed skill with its description.

            Returns the same `<available_skills>` XML block as the
            instructions manifest. Use only if you need a refresh — the
            manifest is already in your instructions.
            """
            return registry.manifest_xml()

    if resource_tool:

        @agent.tool_plain
        def read_skill_resource(skill_name: str, relative_path: str) -> str:
            """Read a file under a skill's references/, scripts/, or assets/.

            Args:
                skill_name: The skill's `name` from the manifest.
                relative_path: Path relative to the skill's directory.
                    Must not escape it (no `..`).

            Returns:
                The file contents as text, or a short "Error:" message.
            """
            try:
                target = registry.resolve_resource(skill_name, relative_path)
                return target.read_text(encoding="utf-8")
            except (
                UnknownSkillError,
                UnsafeSkillNameError,
                SkillError,
                FileNotFoundError,
                ValueError,
            ) as exc:
                return f"Error: {exc}"

    setattr(agent, _ATTACHED_FLAG, True)
    return registry


def skill_aware_agent(
    model: Any,
    *,
    skills: SkillRegistry | Path | str,
    manifest: bool = True,
    load_tool: bool = True,
    list_tool: bool = False,
    resource_tool: bool = False,
    always_load: bool = True,
    **agent_kwargs: Any,
) -> Agent[Any, Any]:
    """Construct a pydantic-ai Agent with skills pre-attached.

    Convenience wrapper over `Agent(model, **agent_kwargs)` +
    `attach_skills(...)`. All `attach_skills` flags are forwarded.
    """
    agent: Agent[Any, Any] = Agent(model, **agent_kwargs)
    attach_skills(
        agent,
        skills,
        manifest=manifest,
        load_tool=load_tool,
        list_tool=list_tool,
        resource_tool=resource_tool,
        always_load=always_load,
    )
    return agent


def _coerce_registry(source: SkillRegistry | Path | str) -> SkillRegistry:
    if isinstance(source, SkillRegistry):
        return source
    return SkillRegistry.from_config(source)


def _build_instructions(
    registry: SkillRegistry,
    *,
    include_manifest: bool,
    inline_always_loaded: bool,
) -> str:
    """Compose preamble + optional manifest + optional always-loaded bodies.

    Returns the empty string if both flags are off — caller should
    then skip registering the instructions hook entirely.
    """
    parts: list[str] = []
    if include_manifest:
        parts.extend([SKILL_INSTRUCTIONS_PREAMBLE, "", registry.manifest_xml()])
    if inline_always_loaded:
        bodies = registry.always_loaded()
        if bodies:
            if parts:
                parts.append("")
            parts.append("<always_loaded_skills>")
            for skill in bodies:
                parts.append(
                    f'  <skill name="{skill.name}" location="{skill.location}">'
                )
                body = skill.body.rstrip()
                if body:
                    parts.append(body)
                parts.append("  </skill>")
            parts.append("</always_loaded_skills>")
    return "\n".join(parts)
