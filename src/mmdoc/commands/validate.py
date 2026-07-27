"""``mmdoc validate`` — check that a folder is a well-formed mmdoc (FORMAT.md §7)."""

import re
from dataclasses import dataclass, field
from pathlib import Path

from mmdoc.core.format import parse_frontmatter

_IMAGE_REF = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<path>[^)]+)\)")
_ALLOWED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
_REQUIRED_FRONTMATTER = ("title", "date")


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_mmdoc(path: str | Path) -> ValidationResult:
    """Validate the mmdoc folder at ``path`` against FORMAT.md §7."""
    folder = Path(path)
    result = ValidationResult()

    index = folder / "index.md"
    if not index.is_file():
        result.errors.append(f"missing index.md in {folder}")
        return result

    text = index.read_text()

    frontmatter = parse_frontmatter(text)
    if frontmatter is None:
        result.errors.append("index.md has no YAML frontmatter")
    else:
        for fieldname in _REQUIRED_FRONTMATTER:
            if not frontmatter.get(fieldname):
                result.errors.append(
                    f"frontmatter missing required field: {fieldname}"
                )

    referenced: set[str] = set()
    for match in _IMAGE_REF.finditer(text):
        ref = match.group("path").strip()
        if ref.startswith(("http://", "https://")):
            result.warnings.append(
                f"remote image reference (not a local file): {ref}"
            )
            continue
        normalized = ref.removeprefix("./")
        referenced.add(normalized)
        if not (folder / normalized).is_file():
            result.errors.append(f"image reference does not resolve: {ref}")
        if not match.group("alt").strip():
            result.warnings.append(f"image reference has empty alt text: {ref}")

    for child in sorted(folder.iterdir()):
        if child.is_dir() or child.name == "index.md":
            continue
        if child.suffix.lower() not in _ALLOWED_IMAGE_SUFFIXES:
            result.warnings.append(f"file is not an allowed image format: {child.name}")
        if child.name not in referenced:
            result.warnings.append(f"image file is never referenced (orphan): {child.name}")

    return result
