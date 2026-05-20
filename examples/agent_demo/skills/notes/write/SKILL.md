---
name: write
description: How to write a new note with title, body, tags, and creation date metadata.
when_to_use: When the user asks to write, save, jot down, capture, or add a new note.
---

# Write a note

A note is a markdown document with frontmatter:

```markdown
---
title: <short title>
created: <ISO date>
tags: [tag1, tag2]
---

<body in 1–5 short paragraphs>
```

Process:

1. Use the user's words for the body. Don't paraphrase unless asked.
2. Derive a title from the first sentence (≤8 words, no trailing period).
3. Today's date in `YYYY-MM-DD` form for `created`.
4. Pick 1–3 lowercase tags from the body's main nouns.
5. Confirm the title + tags with the user before saving.
