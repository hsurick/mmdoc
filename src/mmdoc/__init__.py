"""mmdoc — a folder-based multimodal document format and CLI for AI-native research."""

from importlib.metadata import PackageNotFoundError, version

try:
    # Read from the installed package metadata so pyproject.toml stays the
    # single source of truth for the version.
    __version__ = version("mmdoc")
except PackageNotFoundError:  # pragma: no cover — source tree without an install
    __version__ = "0.0.0+unknown"
