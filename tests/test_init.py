import pytest

from mmdoc.commands.init import init_mmdoc


def test_init_creates_slugified_folder_with_index(tmp_path):
    target = init_mmdoc(str(tmp_path / "District Analysis"), date="2026-06-30")

    assert target == tmp_path / "district-analysis"
    assert target.is_dir()

    index = target / "index.md"
    assert index.is_file()
    content = index.read_text()
    assert "title: District Analysis" in content
    assert "date: 2026-06-30" in content
    assert "# District Analysis" in content


def test_init_refuses_to_overwrite_existing_folder(tmp_path):
    init_mmdoc(str(tmp_path / "doc"), date="2026-06-30")
    with pytest.raises(FileExistsError):
        init_mmdoc(str(tmp_path / "doc"), date="2026-06-30")


def test_init_rejects_name_that_slugifies_to_nothing(tmp_path):
    with pytest.raises(ValueError, match="slug"):
        init_mmdoc(str(tmp_path / "研究ノート"), date="2026-07-06")
