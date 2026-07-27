"""``mmdoc normalize`` — convert foreign content into an mmdoc folder."""

import re
import shutil
import subprocess
from pathlib import Path

from mmdoc.core.convert import extract_base64_images
from mmdoc.core.format import ensure_frontmatter, slugify
from mmdoc.core.pandoc import require_pandoc, strip_hard_breaks

# A markdown image whose target points into Pandoc's extracted media dir:
#   ![alt](./media/rId9.png)  or  ![alt](media/rId9.png)
_MEDIA_REF = re.compile(r"\]\((?:\./)?media/(?P<name>[^)]+)\)")

# Source extensions routed through Pandoc.
_PANDOC_SUFFIXES = {".docx"}


def normalize(source: str, out: str | None, date: str) -> Path:
    """Convert ``source`` into a valid mmdoc folder and return its path.

    With ``out`` unset, the output is a sibling folder named from the slugified
    source stem. Raises ``ValueError`` for source types not yet supported.
    """
    src = Path(source)
    target = Path(out) if out is not None else src.parent / slugify(src.stem)

    suffix = src.suffix.lower()
    if suffix == ".md":
        _normalize_markdown(src, target, date)
    elif suffix in _PANDOC_SUFFIXES:
        _normalize_pandoc(src, target, date)
    else:
        raise ValueError(f"unsupported source type: {suffix or src.name}")

    return target


def _normalize_markdown(src: Path, target: Path, date: str) -> None:
    new_text, images = extract_base64_images(src.read_text())
    body = ensure_frontmatter(new_text, title=src.stem, date=date)

    target.mkdir(parents=True, exist_ok=False)
    (target / "index.md").write_text(body)
    for name, data in images:
        (target / name).write_bytes(data)


def _normalize_pandoc(src: Path, target: Path, date: str) -> None:
    require_pandoc()
    target.mkdir(parents=True, exist_ok=False)

    # Run with cwd=target so extracted media + refs come out relative ("media/…").
    subprocess.run(
        [
            "pandoc",
            str(src.resolve()),
            "-t",
            "gfm-raw_html",
            "--wrap=none",
            "--extract-media=.",
            "-o",
            "index.md",
        ],
        cwd=target,
        check=True,
    )

    index = target / "index.md"
    media_dir = target / "media"
    mapping: dict[str, str] = {}

    def rename_ref(match: re.Match) -> str:
        name = match.group("name")
        if name not in mapping:
            ext = name.rsplit(".", 1)[-1] if "." in name else "png"
            new_name = f"img-{len(mapping) + 1:03d}.{ext}"
            mapping[name] = new_name
            (media_dir / name).rename(target / new_name)
        return f"]({mapping[name]})"

    text = _MEDIA_REF.sub(rename_ref, index.read_text())
    text = strip_hard_breaks(text)  # same cleanup the clipboard HTML path gets
    text = ensure_frontmatter(text, title=src.stem, date=date)
    index.write_text(text)

    if media_dir.exists():
        shutil.rmtree(media_dir)
