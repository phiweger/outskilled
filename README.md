# skillfull

Filesystem-based agent skill loader. One spec, one reference
implementation, with a first-party adapter for `pydantic-ai`.

A **skill** is a folder containing a `SKILL.md` file — YAML
frontmatter describing what the skill does plus a markdown body
explaining how to do it. `skillfull` discovers skills (arbitrary
nesting supported), validates them against the [spec](SPEC.md), and
renders a system-prompt-ready manifest. The pydantic-ai adapter wires
the manifest into an `Agent`'s instructions and registers a
`load_skill` tool the model uses to fetch a skill's body on demand
(plus opt-in tools for listing skills and reading skill resources).
Two lines of glue and the model can route to the right skill.

## References

Spec & ecosystem:

- https://agentskills.io/home
- https://agentskills.io/skill-creation/best-practices
- https://github.com/agentskills/agentskills
- https://code.claude.com/docs/en/skills
- https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- https://resources.anthropic.com/hubfs/The-Complete-Guide-to-Building-Skill-for-Claude.pdf

Pydantic-AI:

- https://pydantic.dev/docs/ai/overview/coding-agent-skills/
- https://github.com/pydantic/skills
- https://pydantic.dev/docs/ai/core-concepts/capabilities/

## Status

`v0.2` — spec stabilising. Adds optional `when_to_use` and
`always_load` frontmatter fields and a pydantic-ai adapter alongside
the framework-agnostic registry. v0.1 skills continue to validate
unchanged.

## Quickstart

```python
from pathlib import Path
from skillfull import SkillRegistry

# Either pass roots directly...
reg = SkillRegistry([Path("./skills")])

# ...or load them from a config file that lives with your skills:
reg = SkillRegistry.from_config("./skills/skills.yaml")

# Level 1: render the manifest for the system prompt.
print(reg.manifest_xml())

# Level 2: load a skill's body on demand. (The `search` skill ships
# with the example bundle under examples/agent_demo/skills/.)
body = reg.load("search")
```

`SkillRegistry` walks every directory under its roots, treats any
directory containing `SKILL.md` as a skill, and validates against the
spec. Reserved subdirectories inside a skill (`references/`,
`scripts/`, `assets/`) are not descended into. Arbitrary nesting is
supported — the path from a skill root to a skill's parent directory
is the **category path**. The same loader handles flat layouts and
N-level categories without a `nested=True` flag.

### `skills.yaml`

A small declarative config (lives inside your skills directory, so
the bundle is portable):

```yaml
# skills/skills.yaml
roots:
  - .                  # paths are resolved relative to this file
  # - ../shared-skills # optional extra roots
```

`SkillRegistry.from_config(path)` resolves the listed paths relative
to the config file's directory.

## Pydantic-AI integration

Install the extra:

```bash
pip install "skillfull[pydantic-ai]"
```

Attach a registry to an existing `Agent`:

```python
from pydantic_ai import Agent
from skillfull.pydanticai import attach_skills

agent = Agent("anthropic:claude-sonnet-4-6")
attach_skills(agent, "skills/skills.yaml")
```

Or build an Agent with skills already wired up:

```python
from skillfull.pydanticai import skill_aware_agent

agent = skill_aware_agent(
    "anthropic:claude-sonnet-4-6",
    skills="skills/skills.yaml",
)
```

What `attach_skills` adds (each independently togglable):

- **Instructions** (Level 1, on by default): an `@agent.instructions`
  function that returns the rendered `<available_skills>` manifest,
  sorted for deterministic prompt caching.
- **`load_skill(name)` tool** (Level 2, on by default): the model
  calls this to fetch a skill body on demand. Path-traversal-safe.
- **Inlined always-loaded bodies** (on by default): any skill with
  `always_load: true` in its frontmatter has its body inlined into
  the instructions. Independent of the manifest flag — bodies are
  inlined even when the manifest is suppressed.
- **`list_skills` tool** (opt-in): re-renders the manifest at runtime.
- **`read_skill_resource` tool** (Level 3, opt-in): exposes files
  under a skill's `references/`, `scripts/`, `assets/` with path
  safety.

`attach_skills` is not idempotent — calling it twice on the same
`Agent` raises `SkillError`. Build a new `Agent` if you need a
different skill set.

### Try it

A self-contained demo lives under `examples/agent_demo/` — four
skills across three nesting depths, an offline plumbing check, and a
real routing eval against Claude Sonnet 4.6.

```bash
pip install -e ".[pydantic-ai]"

# Plumbing check (no API key). Verifies the manifest + load_skill
# round-trip, NOT whether an LLM routes correctly.
python examples/agent_demo/run_demo.py

# Real routing eval against an actual model.
export ANTHROPIC_API_KEY=...
python examples/agent_demo/run_live.py
```

See `examples/agent_demo/README.md` for the two-script split and what
each one does / doesn't prove.

## Install

```bash
pip install -e .
```

Python 3.12+. One runtime dep: `PyYAML`.

## Spec

See [`SPEC.md`](SPEC.md) for the canonical rules: directory layout,
frontmatter schema, validation, manifest format, progressive
disclosure.

## Layout

```
skillfull/
├── SPEC.md
├── README.md
├── LICENSE
├── pyproject.toml
├── src/skillfull/
│   ├── __init__.py     # public API
│   ├── errors.py       # typed exceptions
│   ├── models.py       # Skill dataclass
│   ├── parser.py       # frontmatter extraction
│   ├── validator.py    # spec §3 rules
│   ├── manifest.py     # XML + markdown renderers
│   ├── registry.py     # discovery + composition
│   └── pydanticai.py   # optional pydantic-ai adapter
├── examples/
│   └── agent_demo/     # end-to-end demo + offline & live runners
├── tests/
└── .github/workflows/
    └── publish.yml     # PyPI publish on Release
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

## Release

Publishing is automated via `.github/workflows/publish.yml`. To cut a
release:

1. Bump `version` in `pyproject.toml` and `__version__` in
   `src/skillfull/__init__.py` (keep them in sync — the workflow
   checks the tag against `pyproject.toml`).
2. Commit, merge to `main`.
3. On GitHub, **Releases → Draft a new release**, create a tag
   matching the bumped version (e.g. `v0.2.1`), publish.

The workflow runs the test suite, builds sdist + wheel, and uploads
to PyPI via trusted publishing (OIDC — no API token in secrets).

One-time PyPI setup (only needed on the first release): on PyPI,
**Your projects → skillfull → Publishing → Add a new publisher**:

| Field | Value |
|---|---|
| Owner | `phiweger` |
| Repository | `skillfull` |
| Workflow filename | `publish.yml` |
| Environment name | `pypi` |

For the very first release (before the project exists on PyPI), use
the [pending publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)
flow under **Your account → Publishing → Add a pending publisher**.
