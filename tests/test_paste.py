import base64
import shutil

import pytest

from mmdoc.commands.paste import paste_clipboard
from mmdoc.core.clipboard import ClipboardContent

pandoc_required = pytest.mark.skipif(
    shutil.which("pandoc") is None, reason="pandoc not installed"
)

_PNG = b"\x89PNG\r\n\x1a\n tiny"


def _gdoc_html(text_before: str, text_after: str) -> str:
    b64 = base64.b64encode(_PNG).decode()
    return (
        f"<p>{text_before}</p>"
        f'<img src="data:image/png;base64,{b64}"/>'
        f"<p>{text_after}</p>"
    )


@pandoc_required
def test_paste_html_creates_new_mmdoc_with_extracted_image(tmp_path):
    content = ClipboardContent("html", _gdoc_html("Before text.", "After text."))

    out = paste_clipboard(str(tmp_path / "notes"), date="2026-07-06", content=content)

    assert out == tmp_path / "notes"
    assert (out / "img-001.png").read_bytes() == _PNG
    index = (out / "index.md").read_text()
    assert index.startswith("---\n")
    assert "Before text." in index
    assert "(img-001.png)" in index
    assert "After text." in index
    assert "data:image" not in index


@pandoc_required
def test_paste_html_appends_and_continues_image_numbering(tmp_path):
    target = tmp_path / "doc"
    target.mkdir()
    (target / "index.md").write_text(
        "---\ntitle: T\ndate: 2026-07-01\n---\n\nOld text ![old](img-001.png)\n"
    )
    (target / "img-001.png").write_bytes(b"old")
    content = ClipboardContent("html", _gdoc_html("New pasted text.", "End."))

    paste_clipboard(str(target), date="2026-07-06", content=content)

    index = (target / "index.md").read_text()
    assert "Old text ![old](img-001.png)" in index
    assert "New pasted text." in index
    assert "(img-002.png)" in index
    assert (target / "img-002.png").read_bytes() == _PNG


def test_paste_text_appends_paragraph(tmp_path):
    target = tmp_path / "doc"
    target.mkdir()
    (target / "index.md").write_text("---\ntitle: T\ndate: 2026-07-01\n---\n\nOld.\n")

    paste_clipboard(
        str(target), date="2026-07-06", content=ClipboardContent("text", "Pasted words.")
    )

    index = (target / "index.md").read_text()
    assert index.rstrip().endswith("Pasted words.")
    assert "Old." in index


def test_paste_image_saves_file_and_appends_ref(tmp_path):
    target = tmp_path / "doc"
    target.mkdir()
    (target / "index.md").write_text("---\ntitle: T\ndate: 2026-07-01\n---\n\nOld.\n")

    paste_clipboard(
        str(target), date="2026-07-06", content=ClipboardContent("image", _PNG)
    )

    assert (target / "img-001.png").read_bytes() == _PNG
    assert "![](img-001.png)" in (target / "index.md").read_text()


def test_paste_empty_clipboard_raises(tmp_path):
    with pytest.raises(ValueError, match="empty"):
        paste_clipboard(
            str(tmp_path / "doc"), date="2026-07-06", content=ClipboardContent("empty", b"")
        )
