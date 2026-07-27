---
title: mmdoc — CLI Design (v0.1)
date: 2026-06-30
status: design — architecture + command specs; all sub-decisions resolved 2026-07-26
summary: How the mmdoc CLI is structured and what each subcommand does. Decisions locked 2026-06-30 - Typer, Pandoc (hybrid), Python 3.11+. The format target is ../FORMAT.md; the why is NOTES.md; the plan is OVERVIEW.md.
---

# mmdoc — CLI Design (v0.1)

The `mmdoc` CLI is the **muscle** of the project: a standalone command that creates,
converts, validates, and exports mmdoc folders. The agent skill (component 4) shells out to
it, and humans/CI can run it directly. It only rearranges bytes on disk — it never changes how
a model ingests images — so all its work happens **once, at write time**.

**Locked decisions:** Typer (CLI framework) · Pandoc, hybrid (conversion engine) · Python 3.11+
· distributed via **both PyPI** (`pip install mmdoc` / `uv tool install mmdoc`) **and a Homebrew
tap** (`brew install hsurick/mmdoc/mmdoc`). Output always conforms to `../FORMAT.md`.

---

## 1. Architecture

- **One Python package, `mmdoc`,** exposing a Typer app with subcommands.
- **Hybrid conversion strategy:**
  - **Pandoc** (external binary, called via `subprocess`) handles rich document → Markdown +
    media: `.docx`, `.odt`, `.epub`, `.html`. Its `--extract-media` flag writes embedded images
    to files and rewrites references — the core of `normalize`.
  - **Python libraries** handle the gaps Pandoc doesn't own: extracting base64 data-URIs from an
    existing `.md`, cleaning Notion-export zips, reading the OS clipboard, downloading *remote*
    images (Pandoc does not fetch `http(s)` images — important for Google Docs HTML), validating,
    and exporting.
- **Dependency preflight:** every command that needs Pandoc checks for it first and exits with a
  clear, actionable message (`brew install pandoc`) if it's missing.
- **Single source of truth:** the skill never reimplements conversion logic — it calls these
  subcommands. Same behavior for human, CI, and agent.

---

## 2. Tech stack & dependencies

| Concern | Choice | Notes |
|---|---|---|
| CLI framework | **Typer** | type-hint-driven; built on Click. |
| Doc→MD+media | **Pandoc** (external) | docx; `--extract-media`. |
| HTML→MD | **Pandoc** | reuse the same engine for clipboard HTML. |
| Frontmatter | **PyYAML** | parse/emit `index.md` YAML. |
| Google Docs `fetch` | **stdlib `urllib`** | unauthenticated public docx-export endpoint (link-shared docs only); no OAuth, no Drive API, no extra dependency. |
| Clipboard read | **`osascript`/`pbpaste`** (external) | macOS pasteboard, all flavors; zero extra deps (`core/clipboard.py`). |

Python **3.11+** (modern typing, `tomllib` in stdlib). Not dependencies: **httpx** (remote-URL
image download is deferred — refs are kept as-is and `validate` warns) and **Pillow** (no image
inspection needed; `describe` was dropped).

---

## 3. Project layout

```
mmdoc/
  pyproject.toml              # metadata, deps, console_scripts entry: mmdoc = mmdoc.cli:app
  src/mmdoc/
    cli.py                    # Typer app; registers subcommands
    commands/
      clip.py  export.py  fetch.py  init.py  normalize.py  paste.py  setup.py  validate.py
    core/
      format.py              # slugging, image naming (img-NNN), frontmatter read/write, ref rewriting
      pandoc.py              # subprocess wrapper + preflight check
      clipboard.py           # OS pasteboard read via osascript/pbpaste (all flavors)
      convert.py             # base64 data-URI extraction (.md → files)
    assets/                   # bundled agent skill (installed by `mmdoc setup`)
  tests/
```

---

## 4. Command specifications

Conventions: `<target>` is an mmdoc folder; commands that emit one always produce a `../FORMAT.md`-
valid folder (one `index.md`, root-level `img-NNN.*`, rewritten relative refs).

### `mmdoc init <name>`
- **Does:** scaffold an empty mmdoc — create folder `<name>/` and `index.md` with a frontmatter
  template (`title`, `date` prefilled; `author`/`tags`/`summary` stubbed).
- **Build order:** step 2 (with the skeleton). Simplest command; validates the skeleton works.

### `mmdoc normalize <source> [--out <target>]`
The workhorse. Detects the source type and routes it:
- **`.docx` / `.odt` / `.epub` / `.html` (file):** `pandoc <src> -t gfm -o index.md
  --extract-media=<target>`, then post-process: rename extracted media to `img-NNN.*` at the
  folder root, rewrite refs, ensure/insert frontmatter.
- **`.md` with base64 data-URIs:** Python-extract each `data:image/...;base64,...`, decode to
  `img-NNN.*`, replace the data-URI with a relative ref; copy remaining text through.
- **`.zip` (Notion-style export):** unzip to temp, locate the Markdown + asset files, strip
  vendor cruft (e.g. Notion's hash suffixes in names/links), reorganize into the folder.
- **folder (loose/messy):** collect Markdown + images, standardize image names/refs, assemble.
- **Output:** a valid mmdoc at `--out` (default: source name as a sibling folder).
- **Build order:** step 2. Highest immediate utility.

### `mmdoc fetch <google-doc-url> [--out <target>]`
- **Does:** download the doc via Google's **unauthenticated public export endpoint**
  (`https://docs.google.com/document/d/<ID>/export?format=docx`) using stdlib `urllib` —
  **no OAuth, no Drive API, no extra dependency** — then run the `normalize` docx path on it.
  Reusing the docx pipeline means images come through losslessly with zero extra conversion code.
- **Scope: link-shared docs only** ("Anyone with the link" can view). A private doc fails with
  a `RuntimeError` telling the user to link-share it; OAuth for private docs is deferred.
- **Provenance:** stamps `source` (the URL), `converted` (date), and `converter`
  (`mmdoc <version>`) into the frontmatter.
- **Title & folder name (2026-07-26):** the doc's real title is taken from the export's
  Content-Disposition filename, falling back to the first `# H1` of the converted
  markdown, falling back to `gdoc-<first 8 chars of ID>`. It becomes the frontmatter
  `title` and — slugified — the default output folder name (`--out` overrides).
- **Note:** sidesteps the clipboard entirely — the cleanest path for Google Docs.
- **Built 2026-07-26.**

### `mmdoc clip` (added 2026-07-03 — the multi-paste / positioning answer)

- **Does:** snapshot the pasteboard's richest flavor (html > image > text) into a
  user-global staging area (`~/.mmdoc/clips/`) as files (`clips/NNN/` → markdown +
  `img-NNN.*`), print the clip number.
  Repeatable: each copy+clip is an independent snapshot (clipboard contents don't survive
  the next copy — the snapshot is what makes multiple pastes per prompt possible).
- **Why:** replicates the mechanism behind Claude Code's Ctrl+V image paste (app-level
  pasteboard read + placeholder + resolve-at-read) for rich content, which we can't add to
  Claude Code's input box ourselves. The user references clips positionally in prose with
  `{clip:N}`; the mmdoc skill instructs the agent to read staged clip N at that point (text
  as text, images down the image path). Merging into an mmdoc happens after, agent-driven —
  "only the useful parts."
- **Ergonomics:** a global OS hotkey (Shortcuts/Raycast/skhd) bound to `mmdoc clip` makes
  the flow copy → tap hotkey → continue. Division of labor: plain screenshots keep using
  Claude Code's native Ctrl+V; `clip` exists for rich text+images the harness can't ingest.
- **Staging location (decided 2026-07-06):** `~/.mmdoc/clips/NNN/` (user-global, printed on
  clip; `--root` overrides). **Built 2026-07-06** — text/image/HTML(data-URI) paths working.
- **Clipboard swap (2026-07-26):** after staging, `clip` replaces the clipboard with the
  literal token `{clip:N}` (via `pbcopy`; injectable writer for tests) so the user can
  immediately Cmd+V the reference into a prompt; `--keep` preserves the clipboard. The
  confirmation line names both the token and the staging dir.

### `mmdoc paste <target>`
- **Does:** read the **OS pasteboard directly** (not the terminal) and branch on the richest
  available flavor:
  - **image bytes** → save `img-NNN.png`, append `![](img-NNN.png)`.
  - **HTML** (Google Docs/Notion/web) → `pandoc -f html -t gfm-raw_html --wrap=none`, then:
    **data-URI images** (verified: Google Docs inlines them as base64 — the primary case, no
    network needed) → existing `extract_base64_images`. **Remote-URL images** (some
    websites/exports): download deferred — refs are kept as-is and `validate` warns.
    *(Pipeline empirically proven 2026-07-05 — see NOTES §2.)*
  - **plain text** → append as Markdown.
- **Append or create:** appends to an existing `<target>` mmdoc (image numbering continues the
  folder's sequence) or, when `<target>` doesn't exist, creates it with a templated `index.md`.
  (Agent-assisted merge — restructure/rewrite rather than blind append — is a skill behavior
  layered on top, component 4.)
- **Clipboard read (decided):** macOS via `osascript`/`pbpaste` — zero extra deps; shipped in
  `core/clipboard.py`. Linux (`xclip`/`wl-paste`) deferred.
- **Built 2026-07-06.** The original pain.

### `mmdoc describe` — DROPPED (2026-07-26)
- Cut from scope: agents with vision write alt text themselves when they read an image
  (the skill instructs exactly this), so a standalone vision-API command — with its
  provider/key decisions — is dead weight. Revisit only if batch alt-texting of large
  corpora becomes a real need.

### `mmdoc validate <target>`
- **Does:** enforce `../FORMAT.md` §7 — error on: missing/duplicate `index.md`, unparseable
  frontmatter or missing `title`/`date`, unresolved image refs. Warn on: orphan images, missing
  alt text, disallowed image formats. Exit non-zero on errors (CI-friendly).
- **Build order:** step 6.

### `mmdoc setup [--dry-run]`
- **Does:** one-shot post-install wiring for Claude Code users:
  1. **Pandoc preflight** — reports whether Pandoc is on PATH; if missing, prints
     `brew install pandoc` (informational — never fails).
  2. **Installs the agent skill** — writes the bundled `SKILL.md` (shipped as package
     data, drift-guarded against the repo copy by a test) to
     `~/.claude/skills/mmdoc/SKILL.md`, overwriting any previous copy.
  3. **CLAUDE.md read convention** — maintains a block wrapped in
     `<!-- mmdoc:begin -->` / `<!-- mmdoc:end -->` markers in `~/.claude/CLAUDE.md`
     (created if absent): the mmdoc read rules (alt text is a summary; convert-before-read
     via `mmdoc normalize`; `mmdoc validate` after edits).
- **Idempotent:** re-running overwrites the skill file and *replaces* the marked block
  in place — it never duplicates it; content outside the markers is untouched.
- **`--dry-run`:** print the action lines without writing anything.
- **Build order:** after step 10 — ships with the distribution story.

### `mmdoc export <target> [--to html|pdf|docx]`
- **Does:** convert an mmdoc back to a single shareable artifact for humans —
  - **html:** self-contained file with images inlined as data-URIs (portable single file).
  - **pdf / docx:** via Pandoc (`index.md` + co-located images → `-o out.pdf|out.docx`).
- **Default `--to` (decided):** `html` — self-contained (`--standalone --embed-resources`) and
  needs no LaTeX toolchain; `pdf` errors cleanly without a LaTeX engine.
- **Build order:** step 8.

---

## 5. Distribution

- `pyproject.toml` with a `console_scripts` entry point `mmdoc = mmdoc.cli:app`.
- **Decision (2026-07-26): distribution is both PyPI and a brew tap.**
  - **PyPI:** `pip install mmdoc` / `uv tool install mmdoc`.
  - **Brew tap:** `brew install hsurick/mmdoc/mmdoc` — the formula declares `depends_on "pandoc"`
    (Pandoc handled by the package manager) and pulls the PyPI sdist as its source artifact.
  - **User flow (either channel):** install, then `mmdoc setup` (one-shot Claude Code wiring —
    skill + CLAUDE.md convention).
- **Prerequisite:** Pandoc on PATH (preflight-checked; the brew formula installs it, PyPI
  users `brew install pandoc`).

---

## 6. Remaining sub-decisions

All resolved (2026-07-26): `describe` dropped; `export` default = `html`
(`--standalone --embed-resources`, self-contained); clipboard read = `osascript`/`pbpaste`
(zero extra deps — shipped in `core/clipboard.py`); `fetch` = unauthenticated
link-shared export endpoint via stdlib urllib (private-doc OAuth deferred).
