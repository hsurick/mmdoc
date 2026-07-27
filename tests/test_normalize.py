import base64
import shutil
import subprocess

import pytest

from mmdoc.commands.normalize import normalize

pandoc_required = pytest.mark.skipif(
    shutil.which("pandoc") is None, reason="pandoc not installed"
)

# 1x1 red PNG
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _make_docx_with_image(dirpath):
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


def test_normalize_base64_markdown_produces_valid_mmdoc(tmp_path):
    raw = b"\x89PNG\r\n\x1a\n fake png"
    b64 = base64.b64encode(raw).decode()
    src = tmp_path / "Meeting Notes.md"
    src.write_text(f"# Notes\n\n![a chart](data:image/png;base64,{b64})\n")

    out = normalize(str(src), out=None, date="2026-06-30")

    # default output: a sibling folder named from the slugified source stem
    assert out == tmp_path / "meeting-notes"
    assert (out / "img-001.png").read_bytes() == raw

    index = (out / "index.md").read_text()
    assert "data:image" not in index
    assert "![a chart](img-001.png)" in index
    # frontmatter synthesized (source had none): title from stem + date
    assert index.startswith("---\n")
    assert "title: Meeting Notes" in index
    assert "date: 2026-06-30" in index


def test_normalize_respects_explicit_out(tmp_path):
    src = tmp_path / "doc.md"
    src.write_text("# Hi\n")

    out = normalize(str(src), out=str(tmp_path / "custom"), date="2026-06-30")

    assert out == tmp_path / "custom"
    assert (out / "index.md").is_file()


def test_normalize_rejects_unsupported_source_type(tmp_path):
    src = tmp_path / "thing.xyz"
    src.write_text("x")

    with pytest.raises(ValueError):
        normalize(str(src), out=None, date="2026-06-30")


@pandoc_required
def test_normalize_docx_extracts_images_and_rewrites_refs(tmp_path):
    docx = _make_docx_with_image(tmp_path)

    out = normalize(str(docx), out=str(tmp_path / "result"), date="2026-06-30")

    assert sorted(p.name for p in out.glob("img-*")) == ["img-001.png"]
    assert not (out / "media").exists()
    assert (out / "img-001.png").read_bytes().startswith(b"\x89PNG")

    index = (out / "index.md").read_text()
    assert "![a tiny red dot](img-001.png)" in index
    assert "media/" not in index
    assert "Intro paragraph." in index
    assert "Outro." in index
    assert index.startswith("---\n")
    assert "date: 2026-06-30" in index


@pandoc_required
def test_normalize_docx_strips_hard_break_backslashes(tmp_path):
    # A markdown hard line break (trailing backslash) survives the md -> docx ->
    # gfm round trip as a trailing `\` unless stripped (live-verified on a GDoc).
    md = tmp_path / "src.md"
    md.write_text("Line one\\\nline two\n\nA separate paragraph.\n")
    docx = tmp_path / "hb.docx"
    subprocess.run(["pandoc", str(md), "-o", str(docx)], check=True)

    out = normalize(str(docx), out=str(tmp_path / "o"), date="2026-06-30")

    index = (out / "index.md").read_text()
    assert "line two" in index  # content survived
    assert not any(line.endswith("\\") for line in index.splitlines())


def test_normalize_docx_errors_clearly_when_pandoc_missing(tmp_path, monkeypatch):
    docx = tmp_path / "x.docx"
    docx.write_bytes(b"not really a docx")
    monkeypatch.setattr("mmdoc.core.pandoc.shutil.which", lambda name: None)

    with pytest.raises(RuntimeError, match="pandoc"):
        normalize(str(docx), out=str(tmp_path / "o"), date="2026-06-30")
