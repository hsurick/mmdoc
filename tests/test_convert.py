import base64

from mmdoc.core.convert import extract_base64_images


def test_extracts_single_base64_image_and_rewrites_ref():
    raw = b"\x89PNG\r\n\x1a\n fake png bytes"
    b64 = base64.b64encode(raw).decode()
    md = f"Intro text\n\n![a slide](data:image/png;base64,{b64})\n\nOutro text\n"

    new_text, images = extract_base64_images(md)

    assert images == [("img-001.png", raw)]
    assert "data:image" not in new_text
    assert "![a slide](img-001.png)" in new_text
    assert "Intro text" in new_text
    assert "Outro text" in new_text


def test_numbers_multiple_images_sequentially():
    a = base64.b64encode(b"aaaa").decode()
    b = base64.b64encode(b"bbbb").decode()
    md = f"![one](data:image/png;base64,{a}) and ![two](data:image/png;base64,{b})"

    new_text, images = extract_base64_images(md)

    assert [name for name, _ in images] == ["img-001.png", "img-002.png"]
    assert "![one](img-001.png)" in new_text
    assert "![two](img-002.png)" in new_text


def test_maps_jpeg_mime_to_jpg_extension():
    b64 = base64.b64encode(b"jpegdata").decode()
    md = f"![photo](data:image/jpeg;base64,{b64})"

    _, images = extract_base64_images(md)

    assert images[0][0] == "img-001.jpg"


def test_leaves_plain_image_refs_untouched():
    md = "![existing](img-007.png)\n\nno data uris here"
    new_text, images = extract_base64_images(md)

    assert images == []
    assert new_text == md


def test_ignores_data_uris_inside_fenced_code_blocks():
    b64 = base64.b64encode(b"real").decode()
    md = (
        "Do NOT write this pattern:\n\n"
        "```\n![bad](data:image/png;base64,aGVsbG8=)\n```\n\n"
        f"But this real one counts: ![good](data:image/png;base64,{b64})\n"
    )
    new_text, images = extract_base64_images(md)

    assert len(images) == 1
    assert images[0] == ("img-001.png", b"real")
    assert "![bad](data:image/png;base64,aGVsbG8=)" in new_text
    assert "![good](img-001.png)" in new_text


def test_numbers_images_from_a_start_offset():
    b64 = base64.b64encode(b"x").decode()
    md = f"![a](data:image/png;base64,{b64}) ![b](data:image/png;base64,{b64})"

    new_text, images = extract_base64_images(md, start=4)

    assert [name for name, _ in images] == ["img-004.png", "img-005.png"]
    assert "![a](img-004.png)" in new_text


def test_ignores_data_uris_inside_inline_code_spans():
    md = "the pattern `![x](data:image/png;base64,aGVsbG8=)` is bad"
    new_text, images = extract_base64_images(md)

    assert images == []
    assert new_text == md
