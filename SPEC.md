# Agent Skill Spec (v0.2)

A skill is a folder containing a `SKILL.md` file that teaches an agent
how to handle a specific class of task. Skills are loaded on demand
via a host-defined mechanism (a tool call, a slash command, an
explicit import); the only thing this spec defines is the *file
format* and *discovery rules* so a skill written for one host runs in
another.

This document is the source of truth. Reference implementation lives
under `src/outskilled/`.

---

## 1. Directory layout

A **skill** is any directory whose root contains a file named exactly
`SKILL.md`. Discovery walks the filesystem rooted at one or more
**skill roots** and treats every directory with that marker as a
skill.

Arbitrary nesting is allowed. Paths between a skill root and a skill
form a **category path** (zero or more segments). A flat layout is
just the zero-segment case.

```
# flat (one skill per top-level directory)
skills/
├── flowchart-to-mermaid/
│   ├── SKILL.md
│   └── references/
│       └── mermaid-cheatsheet.md
├── table-formatting/SKILL.md
└── footnotes/SKILL.md

# nested (categories)
skills/
├── notes/
│   ├── search/SKILL.md
│   └── write/SKILL.md
└── code/
    └── refactor/
        └── extract-method/SKILL.md
```

The category path for `code/refactor/extract-method/SKILL.md` is
`code/refactor` — two segments deep.

### 1.1 Skill root resolution

A host MAY supply multiple skill roots. Discovery walks each root in
the order supplied. The skill *name* (see §2.1) must be globally
unique across all roots; the same name appearing in two roots is an
error, not a silent override.

### 1.2 Reserved subdirectories inside a skill

The following subdirectory names inside a skill folder are reserved by
convention (Anthropic documents them; we adopt the same names):

| Path | Purpose |
|---|---|
| `references/` | Reference documents the SKILL.md body links to. Loaded on demand by the body's instructions. |
| `scripts/` | Executable scripts the SKILL.md body invokes (via bash, not by source-reading). |
| `assets/` | Templates, fixtures, sample data the body references. |

These directories are NOT scanned by the discovery walker — discovery
only looks for `SKILL.md` markers. A subdirectory inside a skill is
*not* a nested skill even if it happens to contain a `SKILL.md`
(which would be unusual; if it happens, hosts SHOULD surface a warning).

---

## 2. SKILL.md file format

```
---
<YAML frontmatter>
---

<Markdown body>
```

The file MUST begin with a YAML frontmatter block delimited by `---`
on its own line, followed by a markdown body. Implementations MAY
accept files without frontmatter for backwards compatibility, but
SHOULD warn.

### 2.1 Frontmatter — required fields

| Field | Type | Constraints |
|---|---|---|
| `name` | string | See validation §3.1. Must match the skill's parent directory name (after Unicode NFKC normalisation). |
| `description` | string | See validation §3.2. The single most important field — determines when the agent activates the skill. |

### 2.2 Frontmatter — optional fields

| Field | Type | Purpose |
|---|---|---|
| `when_to_use` | string | Trigger phrases distinct from the prose `description` — "use when the user asks for X", "apply if you see Y". Read by hosts when rendering the manifest; see §3.6. ≤512 chars. |
| `always_load` | bool | If `true`, hosts SHOULD inline this skill's body into the system prompt at startup in addition to listing it in the manifest. Use for reference content that applies to every response (style guides, project conventions). Default `false`. See §3.7. |
| `license` | string | SPDX identifier or short licence name. Hosts MAY display in a manifest. |
| `compatibility` | string | Free-form host/runtime compatibility note, e.g. `"requires python>=3.12; needs poppler"`. ≤500 chars. |
| `allowed-tools` | list[string] | Tool name patterns the skill expects the host to expose. Hosts MAY validate. |
| `metadata` | dict[string, string] | Host-specific extension bag. Keys/values are strings. |

### 2.3 Unknown frontmatter keys

Unknown top-level frontmatter keys are an **error** by default.
Implementations MAY provide a `--lenient` or equivalent mode that
demotes unknown keys to warnings, but the default is strict to surface
typos and version skew.

### 2.4 Body

Markdown. No structural constraints beyond standard CommonMark + GFM.
The body may reference files under `references/`, `scripts/`,
`assets/` using relative paths.

---

## 3. Validation rules

### 3.1 Name

- MUST be a non-empty string.
- MUST be ≤64 characters.
- MUST match `^[a-z0-9]+(-[a-z0-9]+)*$` — kebab-case, lowercase
  alphanumeric segments separated by single hyphens. No leading or
  trailing hyphens, no consecutive hyphens, no underscores, no
  uppercase, no spaces.
- MUST NOT contain the substrings `claude` or `anthropic` (reserved
  per Anthropic's skill conventions).
- MUST equal the skill's parent directory name after Unicode NFKC
  normalisation.

### 3.2 Description

- MUST be a non-empty string after whitespace normalisation.
- MUST be ≤1024 characters.
- MUST NOT contain `<` or `>` (avoid breaking XML manifests).
- SHOULD include trigger phrases — "when you see X", "if the user
  asks for Y" — since the description is what the agent uses to
  decide *whether* to activate the skill.

### 3.3 Compatibility

If present, MUST be a string of ≤500 characters.

### 3.4 Path traversal

A host loading a skill body by name MUST validate the name against
path-traversal characters (`/`, `\`, `..`) before resolving on disk
(A-04). The discovery walker is path-safe by construction since it
only resolves names it has already seen on the filesystem, but a tool
that takes a user-supplied skill name (e.g. an LLM tool call) MUST
validate.

### 3.5 Failure mode

Validation failures during discovery MUST crash startup loudly. Skills
are part of the agent's runtime configuration; a silently-skipped bad
skill is the exact failure mode that produces "why didn't the agent
use the flowchart skill" bug reports.

### 3.6 When-to-use

If present, MUST be a string of ≤512 characters after whitespace
normalisation. Same XML-significant-character rule as §3.2: MUST NOT
contain `<` or `>`. The field is additive to `description` for the
purpose of routing: the agent uses both, with `description` answering
"what does this skill do?" and `when_to_use` answering "when should
I reach for it?".

### 3.7 Always-load

If present, MUST be a boolean. Defaults to `false` when absent. When
`true`, hosts that surface a system-prompt manifest SHOULD also inline
the body alongside the manifest. The field is opt-in because most
skills are tasks (Level 2 — load on activation) rather than standing
reference content (Level 1 inlining).

---

## 4. Manifest format

The **manifest** is the structured listing of installed skills that
the host renders into the agent's system prompt. Hosts SHOULD use the
XML form below — it matches Anthropic's recommended convention for
Claude models and gives the agent the information it needs to call a
`load_skill`-style tool later.

### 4.1 XML manifest (canonical)

```xml
<available_skills>
  <skill>
    <name>flowchart-to-mermaid</name>
    <description>How to transcribe a flowchart into mermaid syntax.</description>
    <when_to_use>When you see boxes-and-arrows or the user asks to draw a flowchart.</when_to_use>
    <location>flowchart-to-mermaid</location>
  </skill>
  <skill>
    <name>extract-method</name>
    <description>How to safely refactor a long function by extracting a sub-block.</description>
    <location>code/refactor/extract-method</location>
  </skill>
</available_skills>
```

- `<location>` is the relative path from the skill root to the skill
  directory, joined with `/`. For a flat skill (no category path) it
  is just the skill name. E.g. `flowchart-to-mermaid` for a flat
  skill, `code/refactor/extract-method` for a two-segment category
  path.
- `<when_to_use>` is emitted only when the frontmatter sets the field;
  it is otherwise omitted (not rendered as an empty element).
- Skills MUST be sorted by `<location>` lexicographically for
  deterministic prompt caching.
- HTML/XML-significant characters in `<description>` and
  `<when_to_use>` MUST be XML-escaped (`&`, `<`, `>`, `"`, `'`).

### 4.2 Markdown manifest (alternative)

For hosts that prefer markdown:

```
- **flowchart-to-mermaid** (`flowchart-to-mermaid`): How to transcribe …
- **extract-method** (`code/refactor/extract-method`): How to safely refactor …
```

Same sort order, same escaping concerns (markdown doesn't need XML
escaping but pipe and backtick still want care).

---

## 5. Progressive disclosure

Skills are designed around three loading levels (per Anthropic's
documentation):

- **Level 1 — Metadata, always loaded.** `name` + `description` +
  `when_to_use` from every installed skill go into the system prompt
  at startup via the manifest. ~100–200 tokens per skill. Skills with
  `always_load: true` (§2.2) also have their bodies inlined here.
- **Level 2 — Body, loaded on activation.** When the agent decides a
  skill applies, the host loads `SKILL.md`'s body into the context.
  Typically <5,000 tokens.
- **Level 3 — Files referenced by the body.** `references/`,
  `scripts/`, `assets/` are read only when the body's instructions
  call for them. For scripts the body invokes the script via bash and
  reads its output — the script source never enters context.

Hosts MUST surface Level 1 (the manifest); SHOULD provide a
`load_skill` tool or equivalent for Level 2; MAY automate Level 3 (or
leave it to the body's instructions).

---

## 6. Versioning

Spec version is in the document title (`v0.2`). Bumping the spec:

- **Patch** (`v0.2.0` → `v0.2.1`) — wording clarifications, no
  behavioural change.
- **Minor** (`v0.2` → `v0.3`) — new optional field, new manifest
  variant, additional validation rule that does not invalidate
  conforming skills.
- **Major** (`v0.x` → `v1.0`) — breaking change to required fields
  or the discovery model. Conforming skills under v0.x may not work.

Implementations SHOULD record the spec version they target.

### 6.1 v0.2 changes (from v0.1)

- Added optional `when_to_use` frontmatter field (§2.2, §3.6).
- Added optional `always_load` frontmatter field (§2.2, §3.7).
- Manifest XML gains an optional `<when_to_use>` child element (§4.1).
- Resolved the §7 "activation hints" open question by going with the
  free-prose `when_to_use` field rather than a structured list.

All v0.1 skills validate unchanged.

---

## 7. Open questions

Things not yet pinned down:

- **Skill versioning.** Should `SKILL.md` itself carry a `version`
  field, separate from the spec version? Useful for cache keying;
  unclear whether hosts care.
- **Cross-skill references.** Skills currently refer to each other by
  name in prose ("see the `footnotes` skill"). A structured `relates_to`
  field could let manifests render edges between skills.

---

## 8. Conformance checklist

A SKILL.md is **conforming** if all of the following hold:

- [ ] File begins with a `---`-delimited YAML frontmatter block.
- [ ] Frontmatter includes `name` and `description`.
- [ ] `name` passes §3.1.
- [ ] `description` passes §3.2.
- [ ] All other frontmatter keys are in the optional-fields set §2.2.
- [ ] Parent directory name equals `name` (NFKC-normalised).
- [ ] Within a skill root, `name` is globally unique.

A host implementation is **conforming** if:

- [ ] Discovery walks arbitrary nesting and finds every `SKILL.md`.
- [ ] Validation failures crash startup loudly.
- [ ] Manifest is sorted and properly escaped.
- [ ] Path traversal is rejected before resolving a name to disk.
