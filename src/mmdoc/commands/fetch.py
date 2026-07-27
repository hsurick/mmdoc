"""``mmdoc fetch`` — download a Google Doc as .docx and convert it to an mmdoc.

The doc is exported via Google's public docx export endpoint, which works for
link-shared docs without authentication; the downloaded file then reuses the
existing ``normalize`` docx pipeline. Private docs would need OAuth, which is
not yet supported.
"""

import re
import shutil
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

from mmdoc import __version__
from mmdoc.commands.normalize import normalize
from mmdoc.core.format import add_frontmatter_fields, set_frontmatter_field, slugify

_DOC_URL = re.compile(r"^https://docs\.google\.com/document/d/(?P<id>[A-Za-z0-9_-]+)")

_EXPORT_URL = "https://docs.google.com/document/d/{doc_id}/export?format=docx"

# The downloader maps a doc ID to (docx bytes, Content-Disposition filename or
# None). Injectable for tests; the default hits the public export endpoint.
Downloader = Callable[[str], tuple[bytes, str | None]]

_H1 = re.compile(r"^#\s+(?P<title>.+?)\s*$", re.MULTILINE)


def extract_doc_id(url: str) -> str:
    """Return the document ID from a Google Doc URL.

    Raises ``ValueError`` if ``url`` is not a Google Doc URL.
    """
    match = _DOC_URL.match(url)
    if match is None:
        raise ValueError(f"not a Google Doc URL: {url}")
    return match.group("id")


def _download_docx(doc_id: str) -> tuple[bytes, str | None]:
    """Download the doc exported as .docx (stdlib only, no auth).

    Returns the bytes plus the filename Google sends in the Content-Disposition
    header — the doc's real title (with a ``.docx`` suffix).
    """
    with urllib.request.urlopen(_EXPORT_URL.format(doc_id=doc_id)) as response:
        return response.read(), response.headers.get_filename()


def _title_from_filename(filename: str | None) -> str | None:
    """The doc title carried by the export's Content-Disposition filename."""
    if filename is None:
        return None
    title = filename.removesuffix(".docx").strip()
    return title or None


def _first_h1(markdown: str) -> str | None:
    """The text of the first ``# H1`` heading in ``markdown``'s body, if any."""
    body = markdown
    if markdown.startswith("---\n"):  # skip the frontmatter block
        end = markdown.find("\n---", 4)
        if end != -1:
            body = markdown[end + 4 :]
    match = _H1.search(body)
    return match.group("title") if match else None


def fetch_gdoc(
    url: str,
    out: str | None,
    date: str,
    downloader: Downloader | None = None,
) -> Path:
    """Fetch the Google Doc at ``url`` and convert it into an mmdoc folder.

    The doc's real title is taken from the export's Content-Disposition
    filename, falling back to the first ``# H1`` of the converted markdown,
    falling back to ``gdoc-<first 8 chars of the ID>``. It becomes the
    frontmatter ``title`` and (slugified) the default output folder name;
    ``out`` overrides the folder. The generated ``index.md`` is stamped with
    ``source``/``converted``/``converter`` provenance fields.
    """
    doc_id = extract_doc_id(url)
    if downloader is None:
        downloader = _download_docx

    try:
        data, filename = downloader(doc_id)
    except urllib.error.URLError as exc:  # HTTPError is a URLError subclass
        raise RuntimeError(
            f"could not download Google Doc {doc_id}: {exc}. The doc must be "
            "link-shared ('Anyone with the link' can view) to fetch it without "
            "auth; private docs need OAuth, which is not yet supported."
        ) from exc

    slug_fallback = f"gdoc-{doc_id[:8]}"
    with tempfile.TemporaryDirectory() as tmp:
        docx = Path(tmp) / f"{slug_fallback}.docx"
        docx.write_bytes(data)
        staging = normalize(str(docx), out=str(Path(tmp) / "converted"), date=date)

        index = staging / "index.md"
        text = index.read_text()
        title = _title_from_filename(filename) or _first_h1(text) or slug_fallback
        text = set_frontmatter_field(text, "title", title)
        text = add_frontmatter_fields(
            text,
            {"source": url, "converted": date, "converter": f"mmdoc {__version__}"},
        )
        index.write_text(text)

        if out is not None:
            target = Path(out)
        elif title == slug_fallback:
            target = Path(slug_fallback)
        else:
            target = Path(slugify(title) or slug_fallback)
        if target.exists():
            raise FileExistsError(f"output folder already exists: {target}")
        shutil.move(str(staging), str(target))
    return target
