"""Core mmdoc format helpers: slugging, frontmatter, the index.md template."""

import re

import yaml


def slugify(text: str) -> str:
    """Convert arbitrary text to a lowercase-kebab-case slug.

    Lowercases, replaces every run of non-alphanumeric characters with a single
    hyphen, and trims leading/trailing hyphens.
    """
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _yaml_value(value: str) -> str:
    """Render a string as a YAML scalar, double-quoting it when a bare scalar
    would be ambiguous or invalid (colons, quotes, leading symbols, etc.)."""
    if re.search(r'[:#\[\]{}&*!|>\'"%@`,]', value) or value != value.strip():
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def render_index(
    title: str,
    date: str,
    author: str | None = None,
    tags: list[str] | None = None,
    summary: str | None = None,
) -> str:
    """Render the text of an ``index.md`` with YAML frontmatter and a title heading.

    ``title`` and ``date`` are required; the other fields are emitted only when given.
    """
    lines = ["---", f"title: {_yaml_value(title)}", f"date: {date}"]
    if author is not None:
        lines.append(f"author: {_yaml_value(author)}")
    if tags is not None:
        lines.append(f"tags: [{', '.join(_yaml_value(t) for t in tags)}]")
    if summary is not None:
        lines.append(f"summary: {_yaml_value(summary)}")
    lines += ["---", "", f"# {title}", ""]
    return "\n".join(lines)


def ensure_frontmatter(text: str, title: str, date: str) -> str:
    """Return ``text`` with a YAML frontmatter block, adding one if absent.

    If ``text`` already begins with a ``---`` frontmatter block it is returned
    unchanged; otherwise a minimal block with ``title`` and ``date`` is prepended.
    """
    if text.startswith("---\n") or text.startswith("---\r\n"):
        return text
    return f"---\ntitle: {_yaml_value(title)}\ndate: {date}\n---\n\n{text}"


def add_frontmatter_fields(text: str, fields: dict[str, str]) -> str:
    """Return ``text`` with ``fields`` appended inside its YAML frontmatter block.

    Each field is inserted as a ``key: value`` line just before the closing
    ``---`` delimiter, with values rendered via ``_yaml_value`` (so URLs and
    other colon-bearing strings stay parseable). Raises ``ValueError`` if
    ``text`` has no (closed) frontmatter block.
    """
    if not (text.startswith("---\n") or text.startswith("---\r\n")):
        raise ValueError("text has no YAML frontmatter block")
    lines = text.splitlines(keepends=True)
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            inserted = [f"{key}: {_yaml_value(value)}\n" for key, value in fields.items()]
            return "".join(lines[:i] + inserted + lines[i:])
    raise ValueError("frontmatter block is never closed")


def set_frontmatter_field(text: str, key: str, value: str) -> str:
    """Return ``text`` with frontmatter field ``key`` set to ``value``.

    Replaces the field's existing line in place, or inserts one before the
    closing ``---`` when the field is absent. Raises ``ValueError`` if ``text``
    has no (closed) frontmatter block.
    """
    if not (text.startswith("---\n") or text.startswith("---\r\n")):
        raise ValueError("text has no YAML frontmatter block")
    lines = text.splitlines(keepends=True)
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            new_line = f"{key}: {_yaml_value(value)}\n"
            for j in range(1, i):
                if lines[j].split(":", 1)[0].strip() == key:
                    lines[j] = new_line
                    return "".join(lines)
            return "".join(lines[:i] + [new_line] + lines[i:])
    raise ValueError("frontmatter block is never closed")


def parse_frontmatter(text: str) -> dict | None:
    """Return the YAML frontmatter of ``text`` as a dict, or ``None`` if absent.

    Uses YAML's BaseLoader so all scalar values stay strings (e.g. an ISO date is
    ``"2026-06-30"``, not a ``datetime.date``). Returns ``{}`` for an empty block.
    """
    if not (text.startswith("---\n") or text.startswith("---\r\n")):
        return None
    lines = text.splitlines()
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            try:
                data = yaml.load("\n".join(lines[1:i]), Loader=yaml.BaseLoader)
            except yaml.YAMLError:
                return None
            return data if isinstance(data, dict) else {}
    return None
