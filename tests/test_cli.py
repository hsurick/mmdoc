import re
import base64
import shutil

import pytest
from typer.testing import CliRunner

from mmdoc.cli import app

runner = CliRunner()

pandoc_required = pytest.mark.skipif(
    shutil.which("pandoc") is None, reason="pandoc not installed"
)


def test_cli_init_creates_mmdoc(tmp_path):
    result = runner.invoke(app, ["init", str(tmp_path / "My Research")])

    assert result.exit_code == 0
    target = tmp_path / "my-research"
    assert (target / "index.md").is_file()
    assert "title: My Research" in (target / "index.md").read_text()


def test_cli_init_reports_the_created_path(tmp_path):
    result = runner.invoke(app, ["init", str(tmp_path / "Notes")])

    assert result.exit_code == 0
    assert "notes" in result.stdout


def test_cli_validate_passes_for_valid_mmdoc(tmp_path):
    d = tmp_path / "doc"
    d.mkdir()
    (d / "index.md").write_text("---\ntitle: T\ndate: 2026-06-30\n---\n\n# T\n")

    result = runner.invoke(app, ["validate", str(d)])

    assert result.exit_code == 0


def test_cli_validate_fails_with_nonzero_exit_for_invalid_mmdoc(tmp_path):
    d = tmp_path / "doc"
    d.mkdir()  # no index.md

    result = runner.invoke(app, ["validate", str(d)])

    assert result.exit_code == 1
    assert "index.md" in result.stdout


def test_cli_paste_uses_clipboard_and_reports_target(tmp_path, monkeypatch):
    from mmdoc.core.clipboard import ClipboardContent

    monkeypatch.setattr(
        "mmdoc.commands.paste.read_clipboard",
        lambda: ClipboardContent("text", "from the clipboard"),
    )

    result = runner.invoke(app, ["paste", str(tmp_path / "doc")])

    assert result.exit_code == 0
    assert "from the clipboard" in (tmp_path / "doc" / "index.md").read_text()


def _stub_clip_clipboard(monkeypatch, text="snap"):
    """Stub both clipboard directions so CLI tests never touch the real one."""
    from mmdoc.core.clipboard import ClipboardContent

    written: list[str] = []
    monkeypatch.setattr(
        "mmdoc.commands.clip.read_clipboard",
        lambda: ClipboardContent("text", text),
    )
    monkeypatch.setattr("mmdoc.commands.clip._write_clipboard", written.append)
    return written


def test_cli_clip_stages_snapshot(tmp_path, monkeypatch):
    _stub_clip_clipboard(monkeypatch)

    result = runner.invoke(app, ["clip", "--root", str(tmp_path / "clips")])

    assert result.exit_code == 0
    assert (tmp_path / "clips" / "001" / "content.md").read_text() == "snap\n"
    assert "001" in result.stdout


def test_cli_clip_swaps_clipboard_for_token_and_says_so(tmp_path, monkeypatch):
    written = _stub_clip_clipboard(monkeypatch)

    result = runner.invoke(app, ["clip", "--root", str(tmp_path / "clips")])

    assert result.exit_code == 0
    assert written == ["{clip:1}"]
    # the confirmation names both the token now on the clipboard...
    assert "{clip:1}" in result.stdout
    # ...and where the content actually lives
    assert str(tmp_path / "clips" / "001") in result.stdout


def test_cli_clip_keep_leaves_clipboard_untouched(tmp_path, monkeypatch):
    written = _stub_clip_clipboard(monkeypatch)

    result = runner.invoke(app, ["clip", "--root", str(tmp_path / "clips"), "--keep"])

    assert result.exit_code == 0
    assert written == []
    assert (tmp_path / "clips" / "001" / "content.md").read_text() == "snap\n"


def test_cli_clip_help_explains_the_swap():
    result = runner.invoke(app, ["clip", "--help"])

    # Rich colorizes help when it detects CI and may inject style codes inside
    # option tokens ("--keep" -> "-", "-keep"), so strip ANSI before asserting.
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    assert result.exit_code == 0
    assert "overwrites" in plain  # summary: save before the next copy overwrites
    assert "--keep" in plain


def test_cli_normalize_base64_markdown(tmp_path):
    raw = b"\x89PNG fake bytes"
    b64 = base64.b64encode(raw).decode()
    src = tmp_path / "notes.md"
    src.write_text(f"# N\n\n![x](data:image/png;base64,{b64})\n")

    result = runner.invoke(app, ["normalize", str(src), "--out", str(tmp_path / "o")])

    assert result.exit_code == 0
    assert (tmp_path / "o" / "img-001.png").read_bytes() == raw
    assert "data:image" not in (tmp_path / "o" / "index.md").read_text()


@pandoc_required
def test_cli_fetch_google_doc_with_stubbed_download(tmp_path, monkeypatch):
    from test_fetch import _make_docx_with_image

    docx = _make_docx_with_image(tmp_path)
    monkeypatch.setattr(
        "mmdoc.commands.fetch._download_docx",
        lambda doc_id: (docx.read_bytes(), None),
    )
    url = "https://docs.google.com/document/d/1XyZAbCdEfGh/edit?tab=t.0"

    result = runner.invoke(app, ["fetch", url, "--out", str(tmp_path / "o")])

    assert result.exit_code == 0
    index = (tmp_path / "o" / "index.md").read_text()
    assert url in index
    assert "img-001.png" in index


@pandoc_required
def test_cli_export_writes_single_html_file(tmp_path):
    d = tmp_path / "doc"
    d.mkdir()
    (d / "index.md").write_text("---\ntitle: T\ndate: 2026-06-30\n---\n\n# T\n\nBody text.\n")

    result = runner.invoke(
        app, ["export", str(d), "--to", "html", "--out", str(tmp_path / "doc.html")]
    )

    assert result.exit_code == 0
    assert "doc.html" in result.stdout
    assert "Body text." in (tmp_path / "doc.html").read_text()
