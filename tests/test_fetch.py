import base64
import shutil
import subprocess
import urllib.error

import pytest

import mmdoc
from mmdoc.commands.fetch import extract_doc_id, fetch_gdoc
from mmdoc.commands.validate import validate_mmdoc
from mmdoc.core.format import parse_frontmatter

pandoc_required = pytest.mark.skipif(
    shutil.which("pandoc") is None, reason="pandoc not installed"
)

# 1x1 red PNG
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

_DOC_ID = "1AbCdEfGhIjKlMnOpQrStUvWxYz-_0123456789abc"
_URL = f"https://docs.google.com/document/d/{_DOC_ID}/edit"


def _make_docx_with_image(dirpath):
    """A docx whose first heading is '# Title' (H1 fallback source)."""
    img = dirpath / "pic.png"
    img.write_bytes(_TINY_PNG)
    md = dirpath / "src.md"
    md.write_text(f"# Title\n\nIntro paragraph.\n\n![a tiny red dot]({img})\n\nOutro.\n")
    docx = dirpath / "report.docx"
    subprocess.run(
        ["pandoc", str(md), "-f", "markdown-implicit_figures", "-o", str(docx)],
        check=True,
    )
    return docx


def _make_docx_without_headings(dirpath):
    """A docx with body text only — no H1 to derive a title from."""
    md = dirpath / "plain.md"
    md.write_text("Just a paragraph.\n\nAnd another one.\n")
    docx = dirpath / "plain.docx"
    subprocess.run(["pandoc", str(md), "-o", str(docx)], check=True)
    return docx


def test_extract_doc_id_from_edit_url():
    assert extract_doc_id(_URL) == _DOC_ID


def test_extract_doc_id_ignores_query_params_and_fragment():
    url = f"https://docs.google.com/document/d/{_DOC_ID}/edit?tab=t.0#heading=h.abc"
    assert extract_doc_id(url) == _DOC_ID


def test_extract_doc_id_rejects_non_google_doc_urls():
    with pytest.raises(ValueError):
        extract_doc_id("https://example.com/document/d/abc123/edit")
    with pytest.raises(ValueError):
        extract_doc_id("https://docs.google.com/spreadsheets/d/abc123/edit")


@pandoc_required
def test_fetch_gdoc_produces_valid_mmdoc_with_provenance(tmp_path):
    docx = _make_docx_with_image(tmp_path)
    seen: list[str] = []

    def downloader(doc_id: str) -> tuple[bytes, str | None]:
        seen.append(doc_id)
        return docx.read_bytes(), None

    out = fetch_gdoc(
        _URL, out=str(tmp_path / "result"), date="2026-07-26", downloader=downloader
    )

    assert seen == [_DOC_ID]
    assert out == tmp_path / "result"

    result = validate_mmdoc(out)
    assert result.ok, result.errors

    fm = parse_frontmatter((out / "index.md").read_text())
    assert fm["source"] == _URL
    assert fm["converted"] == "2026-07-26"
    assert fm["converter"] == f"mmdoc {mmdoc.__version__}"


@pandoc_required
def test_fetch_gdoc_title_from_content_disposition_filename(tmp_path, monkeypatch):
    docx = _make_docx_with_image(tmp_path)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    out = fetch_gdoc(
        _URL,
        out=None,
        date="2026-07-26",
        downloader=lambda _id: (docx.read_bytes(), "Quarterly Report.docx"),
    )

    # the real doc name wins over both the H1 and the gdoc-<id> slug
    assert out.name == "quarterly-report"
    fm = parse_frontmatter((cwd / "quarterly-report" / "index.md").read_text())
    assert fm["title"] == "Quarterly Report"


@pandoc_required
def test_fetch_gdoc_title_falls_back_to_first_h1(tmp_path, monkeypatch):
    docx = _make_docx_with_image(tmp_path)  # first heading: "# Title"
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    out = fetch_gdoc(
        _URL, out=None, date="2026-07-26", downloader=lambda _id: (docx.read_bytes(), None)
    )

    assert out.name == "title"
    fm = parse_frontmatter((cwd / "title" / "index.md").read_text())
    assert fm["title"] == "Title"


@pandoc_required
def test_fetch_gdoc_title_falls_back_to_gdoc_slug_without_filename_or_h1(
    tmp_path, monkeypatch
):
    docx = _make_docx_without_headings(tmp_path)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    out = fetch_gdoc(
        _URL, out=None, date="2026-07-26", downloader=lambda _id: (docx.read_bytes(), None)
    )

    assert out.name == f"gdoc-{_DOC_ID[:8]}"
    fm = parse_frontmatter((cwd / f"gdoc-{_DOC_ID[:8]}" / "index.md").read_text())
    assert fm["title"] == f"gdoc-{_DOC_ID[:8]}"


@pandoc_required
def test_fetch_gdoc_out_override_still_wins_but_title_stays_real(tmp_path):
    docx = _make_docx_with_image(tmp_path)

    out = fetch_gdoc(
        _URL,
        out=str(tmp_path / "custom"),
        date="2026-07-26",
        downloader=lambda _id: (docx.read_bytes(), "My Doc.docx"),
    )

    assert out == tmp_path / "custom"
    fm = parse_frontmatter((out / "index.md").read_text())
    assert fm["title"] == "My Doc"


def test_fetch_gdoc_http_error_explains_link_sharing(tmp_path):
    def downloader(doc_id: str) -> tuple[bytes, str | None]:
        raise urllib.error.HTTPError(
            url="x", code=403, msg="Forbidden", hdrs=None, fp=None
        )

    with pytest.raises(RuntimeError, match="link-shared"):
        fetch_gdoc(_URL, out=str(tmp_path / "o"), date="2026-07-26", downloader=downloader)
