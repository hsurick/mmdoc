---
title: mmdoc — Overview (Problem · Goal · What We're Building · How)
date: 2026-06-29
status: design discussion · core decisions locked 2026-06-30 · remaining sub-decisions resolved 2026-07-26
summary: The working overview — the problem, our goal, the concrete components we're building (what each does, how each is built, and which problem it fixes), and the build approach. Deep mechanics and background understanding live in NOTES.md; the format standard lives in ../FORMAT.md.
---

# mmdoc — Overview

`mmdoc` (**multimodal doc**) is a folder-based document format plus the tooling to create
and maintain it, so AI agents can read and write interleaved text-and-image research using
the file tools they already have — with no changes to the agent harness, GitHub, or any
website.

> This is the working overview. Low-level mechanics and *background understanding that
> explains why the design works but isn't needed to act on it* live in **`NOTES.md`**; the
> precise format standard lives in **`../FORMAT.md`**. This is not a README.

**Core decisions (locked 2026-06-30):** Python · standalone `mmdoc` CLI wrapped by a thin
skill · entry file `index.md` · extra tools in scope: `fetch`, `validate`, `export`.

**Audience (decided 2026-07-02): a public, open-source standard.** We're building this for
anyone to adopt, not just ourselves or one team. Consequences: the FORMAT spec is normative
and versioned; prior art is surveyed honestly (NOTES.md §8); the name is publishable (PyPI
`mmdoc` verified unclaimed); the repo will need a LICENSE and a real README before release.
Adoption strategy per the llms.txt/AGENTS.md lesson: **working tooling first, spec second** —
conventions spread when the tools that produce them are genuinely useful.

---

## The goal

A researcher should be able to take multimodal content from anywhere — a Google Doc, a
Notion page, a `.docx`, a screenshot — and get a single document an AI agent can **search,
read, reason over, and edit**, with the images intact and **without wasting tokens**. Once a
document is in `mmdoc` form it stays agent-friendly forever, for every tool and every future
agent, with zero special configuration on the read side.

**Make multimodal research a first-class, low-cost input for AI agents using only the
tools that already exist.**

---

## The problem

Research is **text + tables + images**, but Markdown can only *reference* images, not hold
them. Since AI agents are now the primary readers of research docs, that gap causes:

1. **Search blindness** — content in a screenshot/slide is invisible to `grep`/`rg`.
2. **Reasoning blindness** — an agent can't see a referenced image without extra steps.
3. **Token waste & cost** — the everyday cost is *lossiness* (images silently dropped on the
   way in); the worst case is catastrophic: base64-in-Markdown read as text burns ~200k
   tokens per image while the model *still can't see it*.
4. **No home for rich paste (the original pain)** — copying interleaved text+images from
   Google Docs/Notion has nowhere to land; Markdown can't hold the images and terminals
   strip everything but plain text.
5. **Lossy ingestion** — converting `.docx`/Google Docs to Markdown drops the images entirely.

---

## What we're building

**Four components.** The format is the target everything writes into; the CLI and clipboard
bridge get content *into* that target; the agent layer reads and maintains it.

### 1. The format (a convention, not code)

- **What it is:** a directory (optionally `name.mmdoc/`) containing a single Markdown
  entry file (`index.md`) and any number of co-located image files, referenced by relative
  path with descriptive alt text.
- **What it does:** gives every tool a shape it already understands — `grep`/`git`/`Read`
  work unmodified, and each image is read **only when needed** (no token waste). Alt text is
  the search surface *and* a summary, so an image is opened only when visual detail matters.
- **How we build it:** write a precise standard — folder layout, `index.md`, image naming,
  alt-text rules, YAML frontmatter, validity rules. No code; it's the standard the rest
  targets. **→ `../FORMAT.md`.**

### 2. The `mmdoc` CLI (Python; the muscle)

- **What it is:** a standalone `mmdoc` command (humans/CI can run it directly), built in
  Python for the best docx/HTML/image/clipboard libraries.
- **What it does — subcommands, grouped:**
  - *Ingest* —
    - **`normalize <src>`** — `.docx` (unzip XML + `word/media/*`), Notion `.zip`,
      base64-Markdown (extract data URIs to files), or a messy folder → clean `mmdoc`.
    - **`fetch <url>`** — pull a link-shared Google Doc via its public docx-export endpoint
      (no OAuth, stdlib only; text + images) → `mmdoc`. Lossless path for the main pain
      source; no clipboard fight.
    - **`paste <target>`** — system clipboard → `mmdoc` (see component 3).
  - *Author* —
    - **`init <name>`** — scaffold an empty `mmdoc` (folder + `index.md` frontmatter template).
  - *Quality & share* —
    - **`validate <target>`** — lint: `index.md` exists, image refs resolve, no orphans, alt
      text present.
    - **`export <target>`** — `mmdoc` → self-contained HTML / PDF / `.docx` for humans.
  - *Wire up* —
    - **`setup`** — one-shot Claude Code wiring: install the bundled agent skill + the
      CLAUDE.md read convention (idempotent).
- **How we build it:** one Python CLI exposing these subcommands; it only rearranges bytes on
  disk (it cannot change how the model ingests images), so it does its work **once, at write
  time**, and the result is permanent.

### 3. The clipboard ingest path

- **What it is:** the mechanism behind `paste` that gets rich clipboard content (text **+**
  images from Google Docs/Notion) into an `mmdoc` — the original pain point.
- **What it does:** reads the **OS pasteboard directly** (not through the terminal, which only
  hands over plain text), captures HTML + embedded image flavors, extracts text and images,
  and **either appends to an existing `mmdoc` or creates a new one**. An agent can then read
  the staged content and **intelligently merge** it (append / restructure / rewrite).
- **How we build it:** a pasteboard reader using native APIs (`osascript`/`pbpaste -Prefer`
  on macOS; `xclip`/`wl-paste` on Linux) that dumps all flavors, feeding `paste`. The
  keybind question is **resolved** (no terminal keybind needed): `mmdoc clip` bound to a
  global OS hotkey — copy → hotkey → reference `{clip:N}` in the prompt; the
  direct-pasteboard `paste` command remains the portable path.

### 4. The agent integration (read & maintain `mmdoc`s)

- **What it is:** the thin skill + instructions that make an agent treat `mmdoc`s correctly.
- **What it does:** (a) on read — search `index.md` (incl. alt text), read images on demand;
  (b) on write/merge — drive the CLI and fold staged/handed-over content into the right
  existing `mmdoc` instead of spawning disconnected fragments;
  (c) **convert-before-read guard** — when handed a base64-`.md`, `.docx`, or Google Doc, run
  `normalize`/`fetch` *first* and read the resulting mmdoc, never the raw bloated source. This
  closes the base64 token-waste loop so the fix can't be accidentally bypassed.
- **How we build it:** a `CLAUDE.md` instruction snippet (the read convention) plus a skill
  that chooses CLI subcommands and performs the merge step on disk. No harness changes.

---

## How each piece fixes the problem

| Problem | Fixed by | The fix |
|---|---|---|
| 1. Search blindness | Format (1) | Text + alt text live in `index.md` → `grep`/`rg` matches them. |
| 2. Reasoning blindness | Format (1) + Agent (4) | Images are real files read on demand down the vision path; alt text covers the rest. |
| 3. Token waste & cost | Format (1) + CLI (2) | Images stored as files, loaded only when needed — never as base64 text; no docx bloat. |
| 4. No home for rich paste | Clipboard (3) | Read the pasteboard directly → land rich text + images in an `mmdoc` (append or new). |
| 5. Lossy ingestion | CLI (2) | `normalize`/`fetch` extract embedded images to files instead of dropping them. |

---

## How we build it (approach & order)

- **Principle: solve it at write time.** Convert content into the folder shape *once* on the
  way in; the read side then needs nothing special, forever, for every tool and agent.
- **Principle: a skill manufactures the folder.** The skill is the front door; it shells out
  to the CLI. It can't bypass the format — it produces it.
- **Build order** (updated 2026-07-02; ✅ = shipped):
  1. ✅ **Format spec** (`../FORMAT.md` v0.1).
  2. ✅ **CLI skeleton + `init` + `normalize`** (base64-md and docx paths; Notion-zip and
     loose-folder still open).
  3. ✅ **`validate`** — quality gate / CI.
  4. ✅ **Agent skill + `CLAUDE.md` convention** (2026-07-06) — read convention +
     convert-before-read guard in `CLAUDE.md`; workflow skill at `.claude/skills/mmdoc/`.
  5. ✅ **Dogfood milestone PASSED** (2026-07-06): a fresh agent given only the 3-line read
     convention took a real Google-Doc-derived mmdoc (empty alt text), reasoned "no summary
     available → must open the image," read it down the vision path, and correctly described
     the contents. The format's core premise is validated end-to-end.
  6. ✅ **Clipboard `paste`/`clip` BUILT** (2026-07-06) — direct pasteboard read (HTML with
     data-URI images / image bytes / text), `paste` appends-or-creates with continued image
     numbering, `clip` stages numbered `{clip:N}` snapshots. Verified against the live
     pasteboard. (Remote-URL images in HTML: deferred — kept as refs, `validate` warns.)
  7. ✅ **`fetch`** (2026-07-26) — link-shared Google Doc → mmdoc via the public docx-export
     endpoint, provenance-stamped (`source`/`converted`/`converter`). Private-doc OAuth deferred.
  8. ~~`describe`~~ **DROPPED** (2026-07-26) — agents with vision write alt text themselves
     when they read an image; a standalone vision-API command is dead weight.
  9. **Remaining `normalize` sources** — Notion `.zip`, loose folder.
  10. ✅ **`export`** (2026-07-26) — mmdoc → self-contained HTML (default; images inlined as
     data URIs) or docx; pdf errors cleanly without a LaTeX engine.
  11. ✅ **`mmdoc setup`** (2026-07-26) — one-shot agent wiring: installs the bundled skill to
     `~/.claude/skills/mmdoc/` and maintains a marker-delimited read-convention block in
     `~/.claude/CLAUDE.md` (idempotent; `--dry-run` supported).
  12. **Open-source release prep** — LICENSE, README; distribution = **both PyPI**
     (`pip install mmdoc` / `uv tool install mmdoc`) **and a brew tap**
     (`brew install hsurick/mmdoc/mmdoc`; formula `depends_on "pandoc"`, pulls the PyPI sdist);
     flow: install, then `mmdoc setup`.
- **Decided (2026-06-30):** CLI framework = **Typer**; conversion engine = **Pandoc (hybrid)**,
  with Python libs for the gaps. **Remaining sub-decisions resolved 2026-07-26:** `describe`
  dropped; `export` default = html; clipboard read = `osascript`/`pbpaste`; `fetch` =
  unauthenticated public export endpoint (no OAuth). See `CLI.md`.

---

## Deferred to future versions

- **Co-located CSV tables** — `![table: …](data-001.csv)` for large/complex tabular data; v0.1
  uses Markdown tables only.
- **`.mmdoc` folder extension** — globbing / tooling identity; v0.1 ships bare folders.
- **Nested mmdocs** — flat only in v0.1.
- **`pack` / `unpack`** — single-file sharing; not in scope yet.
- **Image downscaling on ingest** — Claude already caps image tokens via auto-resize, so this is
  disk/git hygiene + non-Claude providers, not a v0.1 token fix.
- **PDF as a `normalize` input** — common, but PDF→Markdown is hard/lossy; needs a page-image +
  text-extraction approach rather than Pandoc.
- **TextBundle interop** — import/export the existing `.textbundle` format (see NOTES.md §8)
  is nearly trivial (move `assets/`, fold `info.json` into frontmatter); cheap adoption win.
- **DocLang importer** — accept `.dclg`/`.dclx` (LF AI & Data's parser-to-LLM interchange
  format, see NOTES.md §8) as a `normalize` input, bridging document-AI pipelines into mmdoc.
  Bonus: this **closes the deferred PDF gap** — Docling already does PDF→doclang (OCR, tables,
  figure crops) far better than we'd build; we just convert its output. Likely the highest-
  leverage collab move: contribute an "mmdoc" export preset upstream to Docling itself.

---

*For the full reasoning, low-level mechanics, and spec comparison, see `NOTES.md`. For the
precise format standard, see `../FORMAT.md`.*
