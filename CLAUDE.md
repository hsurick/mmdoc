# mmdoc

This repo defines the **mmdoc** format (a folder holding exactly 1 `index.md` plus N
co-located image files) and its reference CLI. `FORMAT.md` is the normative spec;
`docs/CLI.md` specs the CLI; `docs/OVERVIEW.md` owns the plan; `docs/NOTES.md` is background.

## Reading mmdoc documents (applies to any folder shaped like one)

A folder containing an `index.md` plus image files is a multimodal document. Rules:

- `index.md` holds the text; images are referenced as `![description](img-001.png)`.
  The bracketed **alt text is a summary** — read the actual image file (same folder)
  only when you need visual detail. Alt text is greppable; pixels are not.
- **Convert before read:** never read a `.docx`, or a `.md` containing
  `data:image/...;base64,` blobs, directly into context. Run
  `uv run mmdoc normalize <src>` first and read the resulting folder instead
  (raw base64 wastes ~200k tokens per image and you still can't see the image).
- After editing an mmdoc, run `uv run mmdoc validate <folder>`.

## Development

- Python 3.12 via `uv`. Tests: `uv run pytest -q`. CLI: `uv run mmdoc --help`.
- Strict TDD: failing test first, then code. All commands are specced in `docs/CLI.md`
  before implementation.
