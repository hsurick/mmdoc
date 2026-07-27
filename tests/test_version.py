"""The package version is single-sourced from pyproject.toml (via package metadata)."""

import tomllib
from pathlib import Path

import mmdoc


def test_dunder_version_matches_pyproject():
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
    assert mmdoc.__version__ == declared
