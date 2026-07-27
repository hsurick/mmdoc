"""``mmdoc clip`` — snapshot the clipboard into a numbered staging dir.

Each copy+clip is an independent snapshot, which is what makes multiple pastes
per prompt possible: the user references them positionally as ``{clip:N}`` and
an agent reads staged clip N at that point. After staging, the clipboard itself
is replaced with the literal ``{clip:N}`` token (unless ``keep``), so the user
can immediately Cmd+V the reference into a prompt.
"""

import subprocess
from collections.abc import Callable
from pathlib import Path

from mmdoc.core.clipboard import ClipboardContent, read_clipboard
from mmdoc.core.convert import extract_base64_images
from mmdoc.core.pandoc import html_to_gfm

DEFAULT_CLIP_ROOT = Path.home() / ".mmdoc" / "clips"


def _write_clipboard(text: str) -> None:
    """Replace the system clipboard with ``text`` (macOS ``pbcopy``)."""
    subprocess.run(["pbcopy"], input=text, text=True, check=True)


def clip_snapshot(
    root: str | None = None,
    content: ClipboardContent | None = None,
    keep: bool = False,
    write_clipboard: Callable[[str], None] | None = None,
) -> Path:
    """Stage the clipboard's richest flavor as files; return the snapshot dir.

    Unless ``keep`` is true, the clipboard is then replaced with the snapshot's
    ``{clip:N}`` token via ``write_clipboard`` (injectable for tests; defaults
    to ``pbcopy``).
    """
    if content is None:
        content = read_clipboard()
    if content.kind == "empty":
        raise ValueError("clipboard is empty — copy something first")

    base = Path(root) if root is not None else DEFAULT_CLIP_ROOT
    base.mkdir(parents=True, exist_ok=True)
    number = max((int(p.name) for p in base.iterdir() if p.name.isdigit()), default=0) + 1
    target = base / f"{number:03d}"
    target.mkdir()

    if content.kind == "html":
        markdown, images = extract_base64_images(html_to_gfm(content.data))
    elif content.kind == "image":
        markdown, images = "![](img-001.png)", [("img-001.png", content.data)]
    else:  # text
        markdown, images = content.data, []

    (target / "content.md").write_text(markdown.strip() + "\n")
    for name, data in images:
        (target / name).write_bytes(data)

    if not keep:
        (write_clipboard or _write_clipboard)(f"{{clip:{number}}}")
    return target
