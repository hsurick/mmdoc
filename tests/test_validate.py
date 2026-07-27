from mmdoc.commands.validate import validate_mmdoc


def _write_mmdoc(tmp_path, index_text, images=()):
    d = tmp_path / "doc"
    d.mkdir()
    (d / "index.md").write_text(index_text)
    for name in images:
        (d / name).write_bytes(b"\x89PNG fake bytes")
    return d


def test_well_formed_mmdoc_has_no_errors_or_warnings(tmp_path):
    d = _write_mmdoc(
        tmp_path,
        "---\ntitle: T\ndate: 2026-06-30\n---\n\n# T\n\n![a chart](img-001.png)\n",
        images=["img-001.png"],
    )
    result = validate_mmdoc(d)
    assert result.ok
    assert result.errors == []
    assert result.warnings == []


def test_missing_index_is_an_error(tmp_path):
    d = tmp_path / "doc"
    d.mkdir()
    result = validate_mmdoc(d)
    assert not result.ok
    assert any("index.md" in e for e in result.errors)


def test_missing_required_frontmatter_field_is_an_error(tmp_path):
    d = _write_mmdoc(tmp_path, "---\ndate: 2026-06-30\n---\n\n# T\n")
    result = validate_mmdoc(d)
    assert not result.ok
    assert any("title" in e for e in result.errors)


def test_no_frontmatter_is_an_error(tmp_path):
    d = _write_mmdoc(tmp_path, "# Just a heading\n\nbody\n")
    result = validate_mmdoc(d)
    assert not result.ok
    assert any("frontmatter" in e.lower() for e in result.errors)


def test_unresolved_image_reference_is_an_error(tmp_path):
    d = _write_mmdoc(
        tmp_path, "---\ntitle: T\ndate: 2026-06-30\n---\n\n![x](missing.png)\n"
    )
    result = validate_mmdoc(d)
    assert not result.ok
    assert any("missing.png" in e for e in result.errors)


def test_orphan_image_is_a_warning_not_an_error(tmp_path):
    d = _write_mmdoc(
        tmp_path,
        "---\ntitle: T\ndate: 2026-06-30\n---\n\nno refs here\n",
        images=["img-001.png"],
    )
    result = validate_mmdoc(d)
    assert result.ok
    assert any("img-001.png" in w for w in result.warnings)


def test_empty_alt_text_is_a_warning(tmp_path):
    d = _write_mmdoc(
        tmp_path,
        "---\ntitle: T\ndate: 2026-06-30\n---\n\n![](img-001.png)\n",
        images=["img-001.png"],
    )
    result = validate_mmdoc(d)
    assert result.ok
    assert any("alt" in w.lower() for w in result.warnings)


def test_remote_image_url_is_not_an_unresolved_error(tmp_path):
    d = _write_mmdoc(
        tmp_path,
        "---\ntitle: T\ndate: 2026-07-06\n---\n\n![logo](https://example.com/logo.png)\n",
    )
    result = validate_mmdoc(d)
    assert result.ok
    assert any("remote" in w.lower() for w in result.warnings)


def test_dot_slash_prefixed_ref_is_not_an_orphan(tmp_path):
    d = _write_mmdoc(
        tmp_path,
        "---\ntitle: T\ndate: 2026-07-06\n---\n\n![a chart](./img-001.png)\n",
        images=["img-001.png"],
    )
    result = validate_mmdoc(d)
    assert result.ok
    assert result.warnings == []


def test_unparseable_frontmatter_is_an_error_not_a_crash(tmp_path):
    d = _write_mmdoc(tmp_path, "---\ntitle: a: b: [broken\n---\n\nbody\n")
    result = validate_mmdoc(d)
    assert not result.ok


def test_disallowed_image_format_is_a_warning(tmp_path):
    d = _write_mmdoc(
        tmp_path,
        "---\ntitle: T\ndate: 2026-06-30\n---\n\n![x](img-001.bmp)\n",
        images=["img-001.bmp"],
    )
    result = validate_mmdoc(d)
    assert any("bmp" in w.lower() or "format" in w.lower() for w in result.warnings)
