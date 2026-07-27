import pytest

from mmdoc.core.clipboard import decode_osascript_data, pick_flavor


def test_decode_osascript_data_extracts_bytes_from_hex_literal():
    # osascript renders binary clipboard data as «data HTML<hex>»
    raw = "«data HTML3c68746d6c3e»"
    assert decode_osascript_data(raw) == b"<html>"


def test_decode_osascript_data_handles_trailing_newline():
    assert decode_osascript_data("«data PNGf89504e47»\n") == bytes.fromhex("89504e47")


def test_decode_osascript_data_rejects_non_data_output():
    with pytest.raises(ValueError):
        decode_osascript_data("not a data literal")


def test_pick_flavor_prefers_html_over_everything():
    flavors = ["«class HTML»", "«class utf8»", "string", "Unicode text"]
    assert pick_flavor(flavors) == "html"


def test_pick_flavor_prefers_image_over_text():
    assert pick_flavor(["«class PNGf»", "string"]) == "image"
    assert pick_flavor(["TIFF picture", "string"]) == "image"


def test_pick_flavor_falls_back_to_text_then_empty():
    assert pick_flavor(["string", "«class utf8»"]) == "text"
    assert pick_flavor([]) == "empty"
