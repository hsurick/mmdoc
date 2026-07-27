"""``mmdoc setup`` — one-shot wiring for Claude Code users.

Installs the bundled mmdoc agent skill into ``<claude_dir>/skills/mmdoc/`` and
maintains a marker-delimited read-convention block in ``<claude_dir>/CLAUDE.md``.
Idempotent: re-running overwrites the skill and replaces the block in place.
"""

import re
import shutil
from importlib.resources import files
from pathlib import Path

_BEGIN = "<!-- mmdoc:begin -->"
_END = "<!-- mmdoc:end -->"

_SNIPPET = f"""{_BEGIN}
## Reading mmdoc documents (applies to any folder shaped like one)

A folder containing an `index.md` plus image files is a multimodal document
(mmdoc). Rules:

- `index.md` holds the text; images are referenced as `![description](img-001.png)`.
  The bracketed **alt text is a summary** — read the actual image file (same
  folder) only when you need visual detail. Alt text is greppable; pixels are not.
- **Convert before read:** never read a `.docx`, or a `.md` containing
  `data:image/...;base64,` blobs, directly into context. Run
  `mmdoc normalize <src>` first and read the resulting folder instead
  (raw base64 wastes ~200k tokens per image and you still can't see the image).
- After editing an mmdoc, run `mmdoc validate <folder>`.
{_END}"""

_BLOCK_RE = re.compile(re.escape(_BEGIN) + r".*?" + re.escape(_END), re.DOTALL)


def _bundled_skill() -> str:
    """Return the packaged SKILL.md content (shipped as package data)."""
    return (files("mmdoc") / "assets" / "skill" / "SKILL.md").read_text(
        encoding="utf-8"
    )


def run_setup(claude_dir: str | None = None, dry_run: bool = False) -> list[str]:
    """Wire mmdoc into a Claude Code install; return one line per action.

    ``claude_dir`` defaults to ``~/.claude``. With ``dry_run=True`` nothing is
    written — the returned lines describe what would happen.
    """
    base = Path(claude_dir).expanduser() if claude_dir else Path.home() / ".claude"
    lines: list[str] = []

    # a. Pandoc preflight (informational only — never fails).
    if shutil.which("pandoc"):
        lines.append("pandoc: found on PATH")
    else:
        lines.append(
            "pandoc: NOT found — install it via `brew install pandoc` "
            "(needed by normalize/paste/fetch/export)"
        )

    # b. Install the bundled agent skill.
    skill_path = base / "skills" / "mmdoc" / "SKILL.md"
    if dry_run:
        lines.append(f"would write skill to {skill_path}")
    else:
        skill_path.parent.mkdir(parents=True, exist_ok=True)
        skill_path.write_text(_bundled_skill(), encoding="utf-8")
        lines.append(f"wrote skill to {skill_path}")

    # c. Maintain the marked read-convention block in CLAUDE.md.
    claude_md = base / "CLAUDE.md"
    existing = claude_md.read_text(encoding="utf-8") if claude_md.is_file() else None
    if existing is not None and _BEGIN in existing:
        content = _BLOCK_RE.sub(lambda _: _SNIPPET, existing, count=1)
        action = f"replaced mmdoc block in {claude_md}"
    elif existing is not None:
        content = existing.rstrip("\n") + "\n\n" + _SNIPPET + "\n"
        action = f"appended mmdoc block to {claude_md}"
    else:
        content = _SNIPPET + "\n"
        action = f"created {claude_md} with mmdoc block"

    if dry_run:
        lines.append(f"would have {action}")
    else:
        claude_md.parent.mkdir(parents=True, exist_ok=True)
        claude_md.write_text(content, encoding="utf-8")
        lines.append(action)

    return lines
