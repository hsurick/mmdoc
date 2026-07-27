"""Read the macOS pasteboard directly — all flavors, bypassing the terminal.

The terminal only ever forwards the plain-text flavor of a paste. Reading the
pasteboard via osascript exposes the rich flavors (HTML with embedded images,
image bytes), which is the entire basis of `mmdoc paste`/`clip`.
"""

import re
import subprocess
from dataclasses import dataclass

# osascript renders binary clipboard data as: «data HTML3c68746d6c3e»
_OSA_DATA = re.compile(r"«data [A-Za-z0-9 ]{4}([0-9A-Fa-f]*)»")

_IMAGE_FLAVORS = ("«class PNGf»", "TIFF picture", "«class TIFF»")
_TEXT_FLAVORS = ("string", "«class utf8»", "Unicode text")


@dataclass
class ClipboardContent:
    kind: str  # "html" | "image" | "text" | "empty"
    data: bytes | str


def decode_osascript_data(raw: str) -> bytes:
    """Decode an osascript «data XXXX<hex>» literal into raw bytes."""
    match = _OSA_DATA.search(raw)
    if match is None:
        raise ValueError(f"not an osascript data literal: {raw[:60]!r}")
    return bytes.fromhex(match.group(1))


def pick_flavor(flavors: list[str]) -> str:
    """Choose the richest available flavor: html > image > text > empty."""
    if "«class HTML»" in flavors:
        return "html"
    if any(f in flavors for f in _IMAGE_FLAVORS):
        return "image"
    if any(f in flavors for f in _TEXT_FLAVORS):
        return "text"
    return "empty"


def _osascript(expr: str) -> str:
    return subprocess.run(
        ["osascript", "-e", expr], capture_output=True, text=True, check=True
    ).stdout


def read_clipboard() -> ClipboardContent:
    """Read the pasteboard and return its richest flavor (macOS)."""
    info = _osascript("clipboard info")
    flavors = [part.strip() for part in info.split(",")][::2]
    kind = pick_flavor(flavors)

    if kind == "html":
        html = decode_osascript_data(_osascript("the clipboard as «class HTML»"))
        return ClipboardContent("html", html.decode("utf-8", errors="replace"))
    if kind == "image":
        try:
            data = decode_osascript_data(_osascript("the clipboard as «class PNGf»"))
        except (subprocess.CalledProcessError, ValueError):
            data = decode_osascript_data(_osascript("the clipboard as TIFF picture"))
        return ClipboardContent("image", data)
    if kind == "text":
        text = subprocess.run(["pbpaste"], capture_output=True, text=True).stdout
        return ClipboardContent("text", text)
    return ClipboardContent("empty", b"")
