import pytest

from mmdoc.core.format import (
    add_frontmatter_fields,
    ensure_frontmatter,
    parse_frontmatter,
    render_index,
    set_frontmatter_field,
    slugify,
)


def test_slugify_lowercases_and_hyphenates_spaces():
    assert slugify("District Technology Priorities") == "district-technology-priorities"


def test_slugify_drops_punctuation():
    assert slugify("Q3 2026 Report!") == "q3-2026-report"


def test_slugify_collapses_and_trims_whitespace():
    assert slugify("  Foo   Bar  ") == "foo-bar"


def test_slugify_keeps_existing_hyphens_without_doubling():
    assert slugify("multi-modal docs") == "multi-modal-docs"


def test_render_index_minimal_has_required_frontmatter_and_heading():
    assert render_index(title="My Doc", date="2026-06-30") == (
        "---\n"
        "title: My Doc\n"
        "date: 2026-06-30\n"
        "---\n"
        "\n"
        "# My Doc\n"
    )


def test_render_index_includes_optional_fields_when_given():
    out = render_index(
        title="My Doc",
        date="2026-06-30",
        author="Rick Hsu",
        tags=["districts", "tech"],
        summary="An analysis.",
    )
    assert "author: Rick Hsu" in out
    assert "tags: [districts, tech]" in out
    assert "summary: An analysis." in out


def test_render_index_omits_optional_fields_when_absent():
    out = render_index(title="My Doc", date="2026-06-30")
    assert "author:" not in out
    assert "tags:" not in out
    assert "summary:" not in out


def test_ensure_frontmatter_adds_block_when_missing():
    out = ensure_frontmatter("# Hello\n\nbody", title="My Doc", date="2026-06-30")
    assert out == "---\ntitle: My Doc\ndate: 2026-06-30\n---\n\n# Hello\n\nbody"


def test_ensure_frontmatter_leaves_existing_block_untouched():
    text = "---\ntitle: Already\ndate: 2026-01-01\n---\n\n# Hi"
    assert ensure_frontmatter(text, title="X", date="2026-06-30") == text


def test_parse_frontmatter_returns_mapping():
    text = "---\ntitle: My Doc\ndate: 2026-06-30\ntags: [a, b]\n---\n\n# Body"
    fm = parse_frontmatter(text)
    assert fm == {"title": "My Doc", "date": "2026-06-30", "tags": ["a", "b"]}


def test_parse_frontmatter_returns_none_when_absent():
    assert parse_frontmatter("# Just a heading\n\nbody") is None


def test_render_index_title_with_colon_roundtrips():
    out = render_index(title="mmdoc: A Multimodal Format", date="2026-07-06")
    fm = parse_frontmatter(out)
    assert fm["title"] == "mmdoc: A Multimodal Format"


def test_ensure_frontmatter_title_with_colon_roundtrips():
    out = ensure_frontmatter("body", title="Q3 Review: Final", date="2026-07-06")
    fm = parse_frontmatter(out)
    assert fm["title"] == "Q3 Review: Final"


def test_parse_frontmatter_returns_none_on_invalid_yaml_instead_of_crashing():
    text = "---\ntitle: a: b: c: [unclosed\n---\n\nbody"
    assert parse_frontmatter(text) is None


def test_add_frontmatter_fields_inserts_before_closing_delimiter():
    text = "---\ntitle: T\ndate: 2026-07-26\n---\n\n# T\n\nbody\n"
    out = add_frontmatter_fields(text, {"converter": "mmdoc 0.1.0"})
    fm = parse_frontmatter(out)
    assert fm == {"title": "T", "date": "2026-07-26", "converter": "mmdoc 0.1.0"}
    # body untouched
    assert out.endswith("---\n\n# T\n\nbody\n")


def test_add_frontmatter_fields_url_value_roundtrips():
    text = "---\ntitle: T\ndate: 2026-07-26\n---\n\n# T\n"
    url = "https://docs.google.com/document/d/abc123/edit?tab=t.0"
    out = add_frontmatter_fields(text, {"source": url, "converted": "2026-07-26"})
    fm = parse_frontmatter(out)
    assert fm["source"] == url
    assert fm["converted"] == "2026-07-26"
    assert fm["title"] == "T"


def test_add_frontmatter_fields_raises_when_no_frontmatter():
    with pytest.raises(ValueError):
        add_frontmatter_fields("# Just a heading\n\nbody\n", {"a": "b"})


def test_set_frontmatter_field_replaces_existing_value():
    text = "---\ntitle: gdoc-1AbCdEfG\ndate: 2026-07-26\n---\n\n# T\n\nbody\n"
    out = set_frontmatter_field(text, "title", "Quarterly Report: Q3")
    fm = parse_frontmatter(out)
    assert fm["title"] == "Quarterly Report: Q3"
    assert fm["date"] == "2026-07-26"
    assert out.endswith("---\n\n# T\n\nbody\n")


def test_set_frontmatter_field_inserts_when_missing():
    text = "---\ntitle: T\ndate: 2026-07-26\n---\n\nbody\n"
    out = set_frontmatter_field(text, "author", "Rick")
    fm = parse_frontmatter(out)
    assert fm == {"title": "T", "date": "2026-07-26", "author": "Rick"}


def test_set_frontmatter_field_raises_without_frontmatter():
    with pytest.raises(ValueError):
        set_frontmatter_field("# Just a heading\n", "title", "X")
