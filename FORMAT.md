---
title: mmdoc — Format Specification (v0.1)
date: 2026-06-30
status: v0.1 — sub-decisions locked 2026-06-30
summary: The precise standard an mmdoc must follow. This is the fixed target the CLI writes into and validate checks against. Rationale lives in docs/NOTES.md; the build plan lives in docs/OVERVIEW.md.
---

# mmdoc — Format Specification (v0.1)

An **mmdoc** is a directory that bundles one Markdown document with its image assets so AI
agents can search, read, reason over, and edit multimodal research using ordinary file tools.

All sub-decisions were locked 2026-06-30 (summary table at the end).

---

## 1. Structure

An mmdoc is a **directory**. Inside it:

```
district-analysis/              ← the mmdoc (bare folder; no extension in v0.1 — see §7)
  index.md                      ← exactly 1 entry file (required)
  img-001.png                   ← N image files (0 or more), at the folder root
  img-002.jpg
```

- Exactly one `index.md` (required) — it is the document.
- Zero or more image files, co-located at the folder root.
- Text-only documents stay as a plain `.md` file — they are **not** wrapped in a folder. The
  mmdoc form is only for documents that carry images.

---

## 2. The entry file: `index.md`

Standard Markdown with **YAML frontmatter**. Frontmatter schema:

| Field | Required | Type | Notes |
|---|---|---|---|
| `title` | yes | string | Human title of the document. |
| `date` | yes | string | ISO `YYYY-MM-DD`. |
| `author` | no | string | |
| `tags` | no | list of strings | For search/organization. |
| `summary` | no | string | One-line abstract. |
| `source` | no | string | Provenance: original file/URL this doc was converted from. |
| `converted` | no | string | Provenance: ISO date of conversion. Stamped by the CLI. |
| `converter` | no | string | Provenance: tool + version that produced it. Stamped by the CLI. |

The three provenance fields (added 2026-07-06, idea from DocLang) are optional and normally
written by ingestion tooling (`normalize`/`fetch`/`paste`), not by hand.

Body is ordinary Markdown. Images are referenced with **relative paths** and **descriptive
alt text** (§4): `![what it shows and why it matters](img-001.png)`.

---

## 3. Images

- **Location (locked):** folder **root**, alongside `index.md` — refs are just `img-001.png`.
- **Naming (locked):** sequential `img-NNN.ext`, zero-padded to 3 digits (`img-001.png`).
  Descriptive names (`mtss-framework.png`) are allowed and preferred when meaningful.
- **Allowed formats:** `.png`, `.jpg`/`.jpeg`, `.gif`, `.webp`. (SVG out of scope for v0.1.)
- Every image **should** be referenced by `index.md`. Unreferenced files are *orphans* —
  `validate` warns (§7).

---

## 4. Alt text (load-bearing, not decoration)

Alt text does double duty and is the single most important authoring rule:

1. **Search surface** — `rg "budget allocation"` matches the image-reference line, making
   visual content discoverable by text search.
2. **Semantic summary** — lets an agent reason *without* loading the image; it only `Read`s the
   actual image file when visual detail matters.

**Rule:** every image reference **should** carry alt text saying **what the image shows and why
it matters in context** — not `screenshot` or `slide 3`. `validate` warns on missing/empty alt
text; an agent that reads the image writes the alt text itself.

**Length (added 2026-07-06):** alt text is **one sentence**. It lives on a single line inside
`![...]`, so longer text makes every grep hit unreadable — put extended discussion in the prose
around the image, not in the brackets.

**Alt text is a lossy summary (added 2026-07-06):** it is written once, at authoring/conversion
time, and cannot anticipate every question a future reader will ask. Readers (human or agent)
MUST still open the image file when a question needs visual detail the alt text does not carry.
Do not treat good alt text as a reason to skip image reads.

---

## 5. Tables

- v0.1 uses **Markdown tables only**, inline in `index.md`.
- Co-located CSV (`![table: enrollment data](data-001.csv)`) for large/complex tabular data is
  **deferred to a future version** (see `docs/OVERVIEW.md` → Deferred to future versions).

---

## 6. Folder name & the `.mmdoc` extension

- **Folder name:** the document slug, lowercase-kebab-case (e.g. `district-analysis`).
- **Extension (locked):** **omit for now** — bare `district-analysis/` folders. `.mmdoc` is
  deferred polish (globbing / tooling identity) that can be added later without changing any
  file contents.

---

## 7. Validity rules (what `validate` checks)

An mmdoc is **valid** when:

1. The directory contains **exactly one** `index.md`.
2. `index.md` frontmatter parses and includes `title` and `date`.
3. **Every** image reference in `index.md` resolves to a file that exists in the folder.

`validate` additionally **warns** (non-fatal) when:

- An image file exists but is never referenced (orphan).
- An image reference has missing or empty alt text.
- An image is not an allowed format (§3).

---

## 8. Nesting

**Locked:** flat — an mmdoc does **not** contain other mmdocs in v0.1. Revisit on real need.

---

## 9. Agent read convention (the `CLAUDE.md` snippet)

Projects using mmdocs add this to their instructions:

```
Documents stored as a folder containing an index.md plus image files are multimodal
research documents (mmdoc). index.md holds the text with relative image references.
When you encounter an image reference like ![description](img-001.png), the alt text
is a summary — read the actual image file from the same folder only when you need
visual detail. To search, grep index.md (alt text is included). To edit, edit index.md
normally and add/replace co-located image files.
```

---

## Sub-decisions (locked 2026-06-30)

| § | Decision | Locked value | Deferred alternative |
|---|---|---|---|
| 3 | Image location | folder root | `images/` subfolder |
| 3 | Image naming | sequential `img-NNN` (descriptive allowed) | — |
| 5 | Tables | Markdown only | co-located CSV refs (future) |
| 6 | `.mmdoc` extension | omit | adopt later |
| 8 | Nesting | flat | nested mmdocs (future) |
