# mmdoc

**A folder-based multimodal document format so AI agents can read and edit
image-bearing docs with ordinary file tools.**

## The problem

Research is text + tables + images, but Markdown can only *reference* images, not hold
them — and AI agents are now the primary readers. Content trapped in a screenshot is
invisible to `grep`; an agent can't see a referenced image without extra steps; converting
a `.docx` or Google Doc to Markdown silently drops the images; and rich copy-paste from
Google Docs or Notion has nowhere to land, because terminals strip everything but plain
text. The worst case: a Markdown file with base64-inlined images, read as text, costs
roughly 200k tokens per image, and the model still can't see the image.

mmdoc fixes this once, at write time: convert content into a plain folder shape, and the
read side needs nothing special.

## The format

An mmdoc is a directory: a single `index.md` (the document) plus any number of
co-located image files at the folder root, referenced by relative path with
descriptive alt text.

```
district-analysis/
  index.md          ← the document: YAML frontmatter + Markdown body
  img-001.png       ← any images, referenced as
  img-002.jpg          ![what it shows and why it matters](img-001.png)
```

The alt text is a one-sentence summary you can grep — `rg "budget allocation"` matches
the reference line, and an agent opens the actual image file only when it needs visual
detail. `grep`, `git`, and editors already work on it; nothing new is needed to read one.

## Install

Via Homebrew (includes pandoc):

```sh
brew install hsurick/mmdoc/mmdoc
```

Or from PyPI (then install pandoc yourself):

```sh
uv tool install mmdoc    # or: pip install mmdoc
brew install pandoc
```

Then wire up Claude Code (installs the agent skill + the CLAUDE.md read convention):

```sh
mmdoc setup
```

## Usage

Copy a chunk of a Google Doc — text and images — then:

```sh
mmdoc paste notes/
```

The text lands in `notes/index.md` and the images land as real files
(`notes/img-001.png`, …) next to it. Or skip the clipboard entirely and pull a
link-shared Google Doc directly:

```sh
mmdoc fetch "https://docs.google.com/document/d/<id>/edit"
```

## Commands

| Command | What it does |
|---|---|
| `mmdoc init <name>` | Start a blank document: a new folder with a ready-to-edit `index.md`. |
| `mmdoc normalize <src>` | Convert a `.docx` or a Markdown file with embedded images into a plain folder. |
| `mmdoc paste <target>` | Add whatever you just copied — text and images — to a document folder. |
| `mmdoc clip` | Save the clipboard as numbered files before your next copy overwrites it; your clipboard then holds `{clip:N}` to paste into a prompt (`--keep` leaves it untouched). |
| `mmdoc fetch <url>` | Turn a shared Google Doc link into a local folder of text + images — no sign-in needed. |
| `mmdoc export <target>` | Bundle a document folder into one shareable file (HTML, Word, or PDF). |
| `mmdoc validate <target>` | Check a document folder for problems like missing images or bad metadata. |
| `mmdoc setup` | Set up Claude Code to work with these document folders (run once). |

## Agent integration

`mmdoc setup` installs the bundled workflow skill to
`~/.claude/skills/mmdoc/` and maintains a marker-delimited read-convention block in
`~/.claude/CLAUDE.md` (idempotent; `--dry-run` supported).

The read convention:

- `index.md` holds the text; alt text is a summary — read the image file only when you
  need visual detail.
- Convert before read: never read a `.docx` or a base64-blob `.md` directly into context;
  run `mmdoc normalize` first.
- After editing an mmdoc, run `mmdoc validate <folder>`.

The format is agent-agnostic: paste the same convention into an `AGENTS.md` (or any
equivalent instruction file) and any agent with file tools can work with mmdocs.

## Spec & design docs

- [FORMAT.md](FORMAT.md) — the normative format specification (v0.1).
- [CLI.md](docs/CLI.md) — CLI architecture and command specs.
- [OVERVIEW.md](docs/OVERVIEW.md) — the problem, goal, and build plan.
- [NOTES.md](docs/NOTES.md) — background reasoning and prior-art survey.

## Status

**v0.1.** Clipboard commands (`paste`, `clip`) are **macOS-only** for now (Linux via
`xclip`/`wl-paste` planned). Roadmap:

- `normalize` support for Notion `.zip` exports.
- `normalize` support for loose/messy folders.
- DocLang (`.dclg`/`.dclx`) importer — bridges Docling document-AI pipelines (and PDFs) into mmdoc.
- TextBundle interop — import/export the existing `.textbundle` format.

## License

Apache-2.0. See [LICENSE](LICENSE).
