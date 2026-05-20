# agent_demo

End-to-end demo of `skillfull` + `pydantic-ai`. Four skills wired into
an Agent, a plumbing check that runs offline, and a real
LLM-vs-manifest eval against Claude Sonnet 4.6.

```
agent_demo/
├── skills/
│   ├── skills.yaml                          # config (one root: .)
│   ├── reply-style/SKILL.md                 # always_load: true
│   ├── notes/
│   │   ├── search/SKILL.md
│   │   └── write/SKILL.md
│   └── code/refactor/extract-method/SKILL.md
├── run_demo.py                              # offline plumbing check, no API key
├── test_skill_routing.py                    # silent pytest version of the above
└── run_live.py                              # real eval vs. claude-sonnet-4-6
```

## Two scripts, two purposes

- **`run_demo.py` / `test_skill_routing.py`** — **plumbing check**, no
  API key. Uses pydantic-ai's `FunctionModel` with a keyword router as
  the "model", so the routing assertions verify the tool-call round
  trip, manifest content, and `always_load` inlining. They do NOT
  test whether a real LLM can route to the right skill — that is a
  different question, and our keyword stub is no substitute for the
  LLM reading the manifest.
- **`run_live.py`** — **real routing eval**. Runs each prompt through
  an `Agent` backed by `anthropic:claude-sonnet-4-6` and asserts the
  model calls `load_skill(name=...)` based on the manifest alone.
  This is the source of truth for "does skill routing work?".

## Run the offline plumbing check

```bash
pip install -e ".[pydantic-ai]"
python examples/agent_demo/run_demo.py
```

Prints the loaded skills, the exact `<available_skills>` XML the model
sees, OK/FAIL lines per check, and a per-prompt round-trip trace.
Exits non-zero on any failure — fine for CI.

The pytest version covers the same checks plus an extra assertion
that `load_skill` with a bad name returns a recoverable error string:

```bash
pytest examples/agent_demo/test_skill_routing.py -v
```

## Run the live routing eval

```bash
pip install "skillfull[pydantic-ai]" anthropic
export ANTHROPIC_API_KEY=...
python examples/agent_demo/run_live.py
```

Eight prompts (six expected to route to a specific skill, two
expected to need no skill). For each prompt the script prints the
expected `load_skill(...)` call and what the model actually did,
with a per-prompt OK/FAIL plus a final hit rate.

Optional env vars:

| Var | Default | Purpose |
|---|---|---|
| `SKILLFULL_EVAL_MODEL` | `anthropic:claude-sonnet-4-6` | Override the model. |
| `SKILLFULL_EVAL_SAMPLES` | `1` | Runs per prompt; reports hit rate. LLMs are stochastic — bump to 3–5 for a stable read. |

Exit codes: `0` clean pass, `1` one or more prompts misrouted, `2`
config error (missing `ANTHROPIC_API_KEY` etc.).

You should see the model pick `search` for the "find a note" prompt,
`write` for the "save a note" prompt, `extract-method` for the
refactor prompt, and answer the trivia question directly (no skill
needed).

## Why this layout

- `skills.yaml` lives **inside** the skills directory, not at the repo
  root, so the bundle is self-contained. `roots: [.]` resolves to the
  config file's parent.
- Three category depths (flat, one level, two levels) verify
  arbitrary-nesting discovery: no `nested=True` flag needed.
- The `reply-style` skill demonstrates `always_load: true` — standing
  reference content that should influence every reply, not a task the
  agent invokes.
