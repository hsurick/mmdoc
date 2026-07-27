"""``mmdoc paste`` — land the system clipboard in an mmdoc (append or create)."""

import re
from pathlib import Path

from mmdoc.core.clipboard import ClipboardContent, read_clipboard
from mmdoc.core.convert import extract_base64_images
from mmdoc.core.format import render_index
from mmdoc.core.pandoc import html_to_gfm

_IMG_NUMBER = re.compile(r"^img-(\d+)\.")


def next_image_number(folder: Path) -> int:
    """1 + the highest existing img-NNN number in ``folder`` (1 if none)."""
    numbers = [
        int(m.group(1))
        for p in folder.iterdir()
        if (m := _IMG_NUMBER.match(p.name))
    ]
    return max(numbers, default=0) + 1


def paste_clipboard(
    target: str, date: str, content: ClipboardContent | None = None
) -> Path:
    """Write the clipboard's richest flavor into the mmdoc at ``target``.

    Appends to an existing mmdoc (image numbering continues its sequence) or
    creates a new one. ``content`` is injectable for tests; by default the real
    pasteboard is read.
    """
    if content is None:
        content = read_clipboard()
    if content.kind == "empty":
        raise ValueError("clipboard is empty — copy something first")

    folder = Path(target)
    index = folder / "index.md"
    if not index.is_file():
        folder.mkdir(parents=True, exist_ok=True)
        index.write_text(render_index(title=folder.name, date=date))

    start = next_image_number(folder)

    if content.kind == "html":
        markdown, images = extract_base64_images(html_to_gfm(content.data), start=start)
    elif content.kind == "image":
        name = f"img-{start:03d}.png"
        markdown, images = f"![]({name})", [(name, content.data)]
    else:  # text
        markdown, images = content.data, []

    for name, data in images:
        (folder / name).write_bytes(data)

    existing = index.read_text()
    index.write_text(existing.rstrip("\n") + "\n\n" + markdown.strip() + "\n")
    return folder
