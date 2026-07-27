import base64
import shutil
import subprocess

import pytest

from mmdoc.commands.export import export_mmdoc

pandoc_required = pytest.mark.skipif(
    shutil.which("pandoc") is None, reason="pandoc not installed"
)

# 1x1 red PNG
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _make_mmdoc(tmp_path, name="report"):
    folder = tmp_path / name
    folder.mkdir()
    (folder / "img-001.png").write_bytes(_TINY_PNG)
    (folder / "index.md").write_text(
        "---\n"
        "title: Report\n"
        "date: 2026-06-30\n"
        "---\n"
        "\n"
        "# Report\n"
        "\n"
        "Intro paragraph.\n"
        "\n"
        "![a tiny red dot](img-001.png)\n"
        "\n"
        "Outro.\n"
    )
    return folder


@pandoc_required
def test_export_html_is_a_single_self_contained_file(tmp_path):
    folder = _make_mmdoc(tmp_path)

    out = export_mmdoc(str(folder))

    # default output: sibling file named after the folder, .html by default
    assert out == tmp_path / "report.html"
    assert out.is_file()
    html = out.read_text()
    # the PNG got inlined as a data URI — no loose files needed
    assert "data:image" in html
    assert "Intro paragraph." in html
    assert "Outro." in html


@pandoc_required
def test_export_html_respects_explicit_out(tmp_path):
    folder = _make_mmdoc(tmp_path)

    out = export_mmdoc(str(folder), out=str(tmp_path / "custom.html"))

    assert out == tmp_path / "custom.html"
    assert out.is_file()


@pandoc_required
def test_export_docx_produces_a_zip_container(tmp_path):
    folder = _make_mmdoc(tmp_path)

    out = export_mmdoc(str(folder), to="docx")

    assert out == tmp_path / "report.docx"
    assert out.read_bytes().startswith(b"PK")


def test_export_rejects_folder_without_index(tmp_path):
    folder = tmp_path / "notadoc"
    folder.mkdir()

    with pytest.raises(ValueError, match="index.md"):
        export_mmdoc(str(folder))


def test_export_rejects_unknown_format(tmp_path):
    folder = _make_mmdoc(tmp_path)

    with pytest.raises(ValueError):
        export_mmdoc(str(folder), to="epub")


def test_export_pdf_explains_latex_requirement_when_pandoc_fails(tmp_path, monkeypatch):
    folder = _make_mmdoc(tmp_path)
    monkeypatch.setattr("mmdoc.commands.export.require_pandoc", lambda: None)

    def boom(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "pandoc", stderr="pdflatex not found")

    monkeypatch.setattr("mmdoc.commands.export.subprocess.run", boom)

    with pytest.raises(RuntimeError, match="LaTeX"):
        export_mmdoc(str(folder), to="pdf")
