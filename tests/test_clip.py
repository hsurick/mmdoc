from mmdoc.commands.clip import clip_snapshot
from mmdoc.core.clipboard import ClipboardContent

# Every call injects a writer so tests never touch the real clipboard.
_DISCARD = lambda text: None  # noqa: E731


def test_clip_stages_text_snapshot_in_numbered_dir(tmp_path):
    out = clip_snapshot(
        root=str(tmp_path),
        content=ClipboardContent("text", "hello"),
        write_clipboard=_DISCARD,
    )

    assert out == tmp_path / "001"
    assert (out / "content.md").read_text() == "hello\n"


def test_clip_numbers_snapshots_sequentially(tmp_path):
    clip_snapshot(
        root=str(tmp_path),
        content=ClipboardContent("text", "one"),
        write_clipboard=_DISCARD,
    )
    out = clip_snapshot(
        root=str(tmp_path),
        content=ClipboardContent("text", "two"),
        write_clipboard=_DISCARD,
    )

    assert out == tmp_path / "002"
    assert (out / "content.md").read_text() == "two\n"


def test_clip_stages_image_snapshot_as_file_plus_ref(tmp_path):
    png = b"\x89PNG fake"
    out = clip_snapshot(
        root=str(tmp_path),
        content=ClipboardContent("image", png),
        write_clipboard=_DISCARD,
    )

    assert (out / "img-001.png").read_bytes() == png
    assert "![](img-001.png)" in (out / "content.md").read_text()


def test_clip_replaces_clipboard_with_token(tmp_path):
    written: list[str] = []

    clip_snapshot(
        root=str(tmp_path),
        content=ClipboardContent("text", "hello"),
        write_clipboard=written.append,
    )

    assert written == ["{clip:1}"]


def test_clip_token_number_tracks_the_snapshot_number(tmp_path):
    clip_snapshot(
        root=str(tmp_path),
        content=ClipboardContent("text", "one"),
        write_clipboard=_DISCARD,
    )
    written: list[str] = []
    clip_snapshot(
        root=str(tmp_path),
        content=ClipboardContent("text", "two"),
        write_clipboard=written.append,
    )

    assert written == ["{clip:2}"]


def test_clip_keep_does_not_write_the_clipboard(tmp_path):
    written: list[str] = []

    out = clip_snapshot(
        root=str(tmp_path),
        content=ClipboardContent("text", "hello"),
        keep=True,
        write_clipboard=written.append,
    )

    assert written == []
    assert (out / "content.md").read_text() == "hello\n"
