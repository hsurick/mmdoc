"""Thin wrapper around the external pandoc binary."""

import re
import shutil
import subprocess


def require_pandoc() -> None:
    if shutil.which("pandoc") is None:
        raise RuntimeError(
            "pandoc is required for this conversion but was not found on PATH. "
            "Install it (e.g. `brew install pandoc`) and try again."
        )


def html_to_gfm(html: str) -> str:
    """Convert HTML to GitHub-flavored Markdown (plain image syntax, no wrapping)."""
    require_pandoc()
    result = subprocess.run(
        ["pandoc", "-f", "html", "-t", "gfm-raw_html", "--wrap=none"],
        input=html,
        capture_output=True,
        text=True,
        check=True,
    )
    return strip_hard_breaks(result.stdout)


def strip_hard_breaks(markdown: str) -> str:
    r"""Remove pandoc's `\` hard-line-break clutter (common in Google Docs HTML)."""
    return re.sub(r"[ ]*\\(\n|$)", r"\1", markdown)
