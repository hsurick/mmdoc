"""The ``mmdoc`` command-line interface."""

import datetime

import typer

from mmdoc.commands.clip import clip_snapshot
from mmdoc.commands.export import export_mmdoc
from mmdoc.commands.fetch import fetch_gdoc
from mmdoc.commands.init import init_mmdoc
from mmdoc.commands.normalize import normalize as normalize_mmdoc
from mmdoc.commands.paste import paste_clipboard
from mmdoc.commands.setup import run_setup
from mmdoc.commands.validate import validate_mmdoc

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """Turn documents into folders of Markdown text + image files
    that people, grep, and AI agents can all read."""


@app.command()
def init(name: str) -> None:
    """Start a blank document: a new folder with a ready-to-edit index.md.

    The folder name is a cleaned-up version of the name you give; the exact
    name you typed is kept as the document's title inside index.md.
    """
    target = init_mmdoc(name, date=datetime.date.today().isoformat())
    typer.echo(f"Created mmdoc at {target}")


@app.command()
def normalize(
    source: str,
    out: str = typer.Option(
        None, "--out", "-o", help="Where to put the folder (default: named after the source)."
    ),
) -> None:
    """Convert a .docx or a Markdown file with embedded images into a plain folder.

    The result is one index.md plus the images as ordinary files next to it.
    Use this before opening a Word document, or a Markdown file whose images
    are baked in as base64 text (which is unreadably huge in raw form).
    """
    target = normalize_mmdoc(source, out=out, date=datetime.date.today().isoformat())
    typer.echo(f"Normalized {source} -> {target}")


@app.command()
def paste(target: str) -> None:
    """Add whatever you just copied — text and images — to a document folder.

    Reads the system clipboard directly, so a copy from Google Docs or Notion
    keeps its images (pasting into a terminal would reduce it to plain text).
    Adds to the end of an existing folder, or creates the folder if it doesn't
    exist yet.
    """
    folder = paste_clipboard(target, date=datetime.date.today().isoformat())
    typer.echo(f"Pasted clipboard into {folder}")


@app.command()
def clip(
    root: str = typer.Option(
        None, "--root", help="Where to save clips (default: ~/.mmdoc/clips)."
    ),
    keep: bool = typer.Option(
        False,
        "--keep",
        help="Leave the clipboard as-is instead of replacing it with the {clip:N} token.",
    ),
) -> None:
    """Save the clipboard as numbered files before your next copy overwrites it.

    Copy something, run this, copy the next thing, run it again: each run saves
    a numbered clip under ~/.mmdoc/clips/NNN/ (text as content.md, images as
    files), so a single agent prompt can refer to several copied things at once.
    Afterwards your clipboard holds the short token {clip:N} — paste that token
    into your prompt where the content belongs and the agent reads the saved
    files there. Use --keep to leave the clipboard untouched instead.
    """
    target = clip_snapshot(root=root, keep=keep)
    token = f"{{clip:{int(target.name)}}}"
    if keep:
        typer.echo(f"Saved clip {target.name}: content is in {target} (clipboard unchanged)")
    else:
        typer.echo(
            f"Saved clip {target.name}: content is in {target}; your clipboard now "
            f"holds the token {token} — paste it into your prompt to reference this clip"
        )


@app.command()
def fetch(
    url: str,
    out: str = typer.Option(
        None, "--out", "-o", help="Where to put the folder (default: named after the doc)."
    ),
) -> None:
    """Turn a shared Google Doc link into a local folder of text + images.

    Works without signing in, as long as the doc is shared as "Anyone with the
    link can view". The doc's text becomes index.md and its images are saved as
    real files next to it.
    """
    target = fetch_gdoc(url, out=out, date=datetime.date.today().isoformat())
    typer.echo(f"Fetched {url} -> {target}")


@app.command()
def export(
    target: str,
    to: str = typer.Option("html", "--to", help="Output format: html, docx, or pdf."),
    out: str = typer.Option(None, "--out", "-o", help="Output file (default: <folder>.<ext>)."),
) -> None:
    """Bundle a document folder into one shareable file (HTML, Word, or PDF).

    HTML (the default) embeds the images, so the single file is all you need
    to send someone. PDF requires a LaTeX engine to be installed.
    """
    path = export_mmdoc(target, to=to, out=out)
    typer.echo(f"Exported {target} -> {path}")


@app.command()
def setup(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be done without writing anything."
    ),
    claude_dir: str = typer.Option(None, "--claude-dir", hidden=True),
) -> None:
    """Set up Claude Code to work with these document folders.

    Installs the mmdoc skill and adds reading rules to ~/.claude/CLAUDE.md so
    Claude converts Word/base64 files before reading them and treats image alt
    text as a summary. Safe to re-run; --dry-run previews the changes.
    """
    for line in run_setup(claude_dir=claude_dir, dry_run=dry_run):
        typer.echo(line)


@app.command()
def validate(target: str) -> None:
    """Check a document folder for problems like missing images or bad metadata.

    Prints each problem found and exits non-zero when the folder is broken,
    so it can gate scripts and CI.
    """
    result = validate_mmdoc(target)
    for warning in result.warnings:
        typer.echo(f"warning: {warning}")
    for error in result.errors:
        typer.echo(f"error: {error}")
    if not result.ok:
        raise typer.Exit(code=1)
    typer.echo(f"{target} is a valid mmdoc ({len(result.warnings)} warning(s)).")
