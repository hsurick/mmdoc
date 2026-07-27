---
name: mmdoc
description: Work with mmdoc multimodal documents (folder = index.md + co-located images). Use when converting a docx/Google-Doc/base64-markdown into an mmdoc, ingesting clipboard content, merging new content into an existing mmdoc, validating one, answering questions about a document that contains images, or resolving a {clip:N} token appearing anywhere in a prompt.
---

# mmdoc — multimodal documents for agents

An **mmdoc** is a folder containing exactly one `index.md` (YAML frontmatter: `title`,
`date`) and any number of image files at the folder root, referenced by relative path:
`![what it shows and why it matters](img-001.png)`. Normative spec: `FORMAT.md`.

## Why this exists

Whether a model can *see* an image is decided by a content-type label at the API
boundary, never discovered from file contents. An image stored as a separate file and
opened with the Read tool goes down the vision path (~1.5k tokens, actually seen). The
same image as a base64 string inside markdown read as text costs ~200k garbage tokens
and remains invisible. Every rule below follows from this.

## Reading an mmdoc

1. Search with `rg` over `index.md` — alt text is part of the search surface.
2. Read `index.md` for the prose. Treat alt text as a lossy summary.
3. Open an image file only when the question needs visual detail the alt text lacks.

## The convert-before-read guard (MANDATORY)

When handed any of the following, do NOT read it into context directly:

- a `.docx` — images are trapped in a zip; text readers drop them
- a `.md` containing `data:image/...;base64,` — the 200k-token trap
- a messy export folder

Instead run `uv run mmdoc normalize <source> [-o <target>]`, then read the resulting
folder. If pandoc is missing, tell the user to `brew install pandoc`.

**PDFs are the exception:** the API has a native `document` block (each page = text
layer + page raster), so reading a PDF directly is safe and images are visible. For a
one-off question, just Read it. But note the costs — every page bills ~1.5-2k image
tokens on *every* read, and PDFs are invisible to grep and un-editable — so a PDF
that will live in the corpus long-term is still worth converting (no PDF conversion
path exists yet — do not invent one).

## Creating and validating

- New doc: `uv run mmdoc init "<Title>"` (folder name is slugified; title preserved).
- Always finish any mmdoc-writing task with `uv run mmdoc validate <folder>` and fix
  errors it reports. Warnings about empty alt text: write alt text yourself from the
  image content if you have read it (one sentence: what it shows + why it matters).

## Merging new content into an existing mmdoc

When the user wants pasted/converted content added to an existing doc:

1. Get the new content into staged files first (via `normalize`, or a staging dir).
2. Read the staged markdown; read the target's `index.md`.
3. Merge *editorially* — place content in the right section, keep only what's useful,
   renumber incoming images to continue the target's `img-NNN` sequence, move the
   image files in, and rewrite their refs.
4. `uv run mmdoc validate` the result.

## Clipboard ingestion (Google Docs / Notion / rich content)

The terminal strips pastes to plain text; the pasteboard holds the full content
(Google Docs embeds images as base64 data-URIs in the HTML flavor). Two commands
read the pasteboard directly:

- `uv run mmdoc paste <target>` — land the clipboard in an mmdoc: appends to an
  existing one (image numbering continues its sequence) or creates it.
- `uv run mmdoc clip [--root <dir>] [--keep]` — snapshot the clipboard to a numbered
  staging dir (default `~/.mmdoc/clips/NNN/`, containing `content.md` + images). When
  the user writes `{clip:N}` in a prompt, read staging dir N at that point in their
  text (its markdown as text; open its images only if visual detail is needed).
  Multiple snapshots let one prompt reference several pastes positionally.
  After staging, `clip` **replaces the clipboard** with the literal token `{clip:N}`
  so the user can immediately paste the reference into a prompt — a bare `{clip:N}`
  in their text is that pasted token, not content; resolve it from the staging dir.
  `--keep` leaves the clipboard unchanged instead.
- **Loose clip references:** when the user points at a clip without a number — "my
  last clip", "the clip with the chart", "what I copied earlier" — list
  `~/.mmdoc/clips/`, read each snapshot's `content.md` (newest first), and pick the
  one whose content matches their description; open images only if the words don't
  settle it.

After pasting, alt text is empty — if you read the image, write one-sentence alt
text into the ref. Then `uv run mmdoc validate <target>`.

## Fetching Google Docs and exporting for humans

- `uv run mmdoc fetch <google-doc-url> [-o <target>]` — downloads a **link-shared**
  Google Doc (exported as docx) and converts it to an mmdoc, stamping provenance
  (`source`/`converted`/`converter`) in the frontmatter. Private docs fail with a
  clear error — tell the user to enable link sharing (OAuth not yet supported).
- `uv run mmdoc export <folder> [--to html|docx|pdf]` — mmdoc → one shareable file.
  Default html is fully self-contained (images inlined). pdf needs a LaTeX engine.

## Command inventory (do not invent others)

`init`, `normalize` (.md/.docx), `paste`, `clip`, `fetch`, `export`, `validate`, `setup`.
There is no `describe` — when you read an image, write its one-sentence alt text
yourself.
