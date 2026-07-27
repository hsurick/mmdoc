"""``mmdoc init`` — scaffold a new, empty mmdoc folder."""

from pathlib import Path

from mmdoc.core.format import render_index, slugify


def init_mmdoc(name: str, date: str) -> Path:
    """Create a new mmdoc folder with a templated ``index.md``.

    The folder is created next to where ``name`` points, with its final path
    component slugified (per ``FORMAT.md``). The raw final component becomes the
    document ``title``. Raises ``FileExistsError`` if the folder already exists.
    """
    given = Path(name)
    slug = slugify(given.name)
    if not slug:
        raise ValueError(
            f"{given.name!r} produces an empty slug (no ASCII letters/digits); "
            "pass a name with Latin characters"
        )
    target = given.parent / slug
    target.mkdir(parents=True, exist_ok=False)
    (target / "index.md").write_text(render_index(title=given.name, date=date))
    return target
