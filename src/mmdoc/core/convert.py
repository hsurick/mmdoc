"""Conversion helpers that turn foreign content into mmdoc pieces."""

import base64
import re

# Markdown image whose target is a base64 data URI:
#   ![alt](data:image/png;base64,iVBOR...)
_DATA_URI_IMAGE = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\("
    r"data:image/(?P<mime>[a-zA-Z0-9.+-]+);base64,"
    r"(?P<data>[A-Za-z0-9+/=\s]+)"
    r"\)"
)

# Map an image MIME subtype to the file extension we store it under.
_MIME_EXT = {
    "png": "png",
    "jpeg": "jpg",
    "jpg": "jpg",
    "gif": "gif",
    "webp": "webp",
    "svg+xml": "svg",
}

# Regions the extractor must not rewrite: fenced code blocks and inline code spans.
_CODE_REGION = re.compile(r"```.*?```|~~~.*?~~~|`[^`\n]*`", re.DOTALL)


def extract_base64_images(
    markdown: str, start: int = 1
) -> tuple[str, list[tuple[str, bytes]]]:
    """Pull base64 data-URI images out of Markdown into separate files.

    Returns the rewritten Markdown (each data URI replaced by a relative
    ``img-NNN.ext`` reference, alt text preserved) and a list of
    ``(filename, raw_bytes)`` pairs in document order, numbered from ``start``
    (so pasted content can continue an existing document's sequence). Data URIs
    inside fenced code blocks or inline code spans are documentation, not
    content — untouched.
    """
    images: list[tuple[str, bytes]] = []

    def replace(match: re.Match) -> str:
        mime = match.group("mime").lower()
        ext = _MIME_EXT.get(mime, mime)
        raw = base64.b64decode("".join(match.group("data").split()))
        name = f"img-{len(images) + start:03d}.{ext}"
        images.append((name, raw))
        return f"![{match.group('alt')}]({name})"

    pieces: list[str] = []
    pos = 0
    for code in _CODE_REGION.finditer(markdown):
        pieces.append(_DATA_URI_IMAGE.sub(replace, markdown[pos : code.start()]))
        pieces.append(code.group(0))
        pos = code.end()
    pieces.append(_DATA_URI_IMAGE.sub(replace, markdown[pos:]))
    return "".join(pieces), images
