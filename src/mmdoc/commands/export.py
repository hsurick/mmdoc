"""``mmdoc export`` — convert an mmdoc folder into a single shareable file."""

import subprocess
from pathlib import Path

from mmdoc.core.pandoc import require_pandoc

_FORMATS = ("html", "docx", "pdf")


def export_mmdoc(target: str, to: str = "html", out: str | None = None) -> Path:
    """Export the mmdoc at ``target`` to a single ``to``-format file, return its path.

    With ``out`` unset, the output is a sibling file named ``<folder-name>.<ext>``.
    Raises ``ValueError`` for a non-mmdoc target or an unsupported format, and
    ``RuntimeError`` when PDF export fails for lack of a LaTeX engine.
    """
    if to not in _FORMATS:
        raise ValueError(f"unsupported export format: {to} (expected one of {', '.join(_FORMATS)})")

    folder = Path(target)
    if not (folder / "index.md").is_file():
        raise ValueError(f"{folder} is not an mmdoc folder (no index.md)")

    require_pandoc()
    out_path = Path(out) if out is not None else folder.parent / f"{folder.name}.{to}"

    args = ["pandoc", "index.md", "-o", str(out_path.resolve())]
    if to == "html":
        # One self-contained file: inline relative image refs as data URIs.
        args += ["--standalone", "--embed-resources"]

    try:
        # cwd=folder so index.md's relative image refs resolve.
        subprocess.run(args, cwd=folder, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        if to == "pdf":
            raise RuntimeError(
                "PDF export failed — pandoc needs a LaTeX engine (e.g. tectonic or "
                "pdflatex). Install one (`brew install tectonic`) and try again."
                + (f"\npandoc said: {exc.stderr.strip()}" if exc.stderr else "")
            ) from exc
        raise

    return out_path
