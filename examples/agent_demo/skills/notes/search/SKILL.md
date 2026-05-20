---
name: search
description: How to search a notes collection by keywords, tags, or date filters.
when_to_use: When the user asks to find, locate, look up, or recall an existing note.
---

# Search notes

1. Extract the key nouns and tags from the user's query.
2. Build a query: prioritise exact tag matches, then keyword matches
   in titles, then in body text.
3. If the user gave a time hint ("last week", "in March"), filter by
   note creation date.
4. Return the top 3 matches as `- title (yyyy-mm-dd): one-line excerpt`.
5. If no notes match, say so plainly. Do not invent results.
