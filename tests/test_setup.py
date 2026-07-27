from pathlib import Path

from typer.testing import CliRunner

from mmdoc.cli import app
from mmdoc.commands.setup import run_setup

runner = CliRunner()

BEGIN = "<!-- mmdoc:begin -->"
END = "<!-- mmdoc:end -->"


def test_setup_writes_bundled_skill_to_claude_dir(tmp_path):
    run_setup(claude_dir=str(tmp_path))

    skill = tmp_path / "skills" / "mmdoc" / "SKILL.md"
    assert skill.is_file()
    text = skill.read_text()
    assert "name: mmdoc" in text
    assert "convert-before-read" in text


def test_setup_creates_claude_md_with_marked_snippet(tmp_path):
    run_setup(claude_dir=str(tmp_path))

    text = (tmp_path / "CLAUDE.md").read_text()
    assert BEGIN in text
    assert END in text
    assert "mmdoc normalize" in text
    assert "mmdoc validate" in text
    assert "alt text" in text


def test_setup_twice_does_not_duplicate_snippet_block(tmp_path):
    run_setup(claude_dir=str(tmp_path))
    run_setup(claude_dir=str(tmp_path))

    text = (tmp_path / "CLAUDE.md").read_text()
    assert text.count(BEGIN) == 1
    assert text.count(END) == 1


def test_setup_preserves_existing_claude_md_content(tmp_path):
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# My rules\n\nAlways be excellent.\n")

    run_setup(claude_dir=str(tmp_path))
    run_setup(claude_dir=str(tmp_path))

    text = claude_md.read_text()
    assert "Always be excellent." in text
    assert text.count(BEGIN) == 1


def test_setup_replaces_stale_block_content(tmp_path):
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text(f"intro\n\n{BEGIN}\nold stale text\n{END}\n\noutro\n")

    run_setup(claude_dir=str(tmp_path))

    text = claude_md.read_text()
    assert "old stale text" not in text
    assert "mmdoc normalize" in text
    assert "intro" in text and "outro" in text
    assert text.count(BEGIN) == 1


def test_setup_dry_run_writes_nothing(tmp_path):
    lines = run_setup(claude_dir=str(tmp_path), dry_run=True)

    assert not (tmp_path / "skills").exists()
    assert not (tmp_path / "CLAUDE.md").exists()
    assert lines  # still reports what it would do


def test_setup_reports_each_action(tmp_path):
    lines = run_setup(claude_dir=str(tmp_path))

    joined = "\n".join(lines)
    assert "SKILL.md" in joined
    assert "CLAUDE.md" in joined
    assert "pandoc" in joined


def test_setup_reports_missing_pandoc_without_failing(tmp_path, monkeypatch):
    monkeypatch.setattr("mmdoc.commands.setup.shutil.which", lambda _: None)

    lines = run_setup(claude_dir=str(tmp_path))

    assert any("brew install pandoc" in line for line in lines)
    assert (tmp_path / "skills" / "mmdoc" / "SKILL.md").is_file()


def test_packaged_skill_matches_repo_skill():
    """Drift guard: the bundled asset must equal the repo's canonical skill."""
    from importlib.resources import files

    packaged = (files("mmdoc") / "assets" / "skill" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    repo = (
        Path(__file__).resolve().parent.parent
        / ".claude"
        / "skills"
        / "mmdoc"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert packaged == repo


def test_agents_skill_matches_claude_skill():
    """Drift guard: the .agents skill mirror must equal the canonical .claude skill."""
    repo_root = Path(__file__).resolve().parent.parent
    claude_skill = (repo_root / ".claude" / "skills" / "mmdoc" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    agents_skill = (repo_root / ".agents" / "skills" / "mmdoc" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert agents_skill == claude_skill


def test_agents_md_matches_claude_md():
    """Drift guard: AGENTS.md must be a byte-identical mirror of CLAUDE.md."""
    repo_root = Path(__file__).resolve().parent.parent
    claude_md = (repo_root / "CLAUDE.md").read_text(encoding="utf-8")
    agents_md = (repo_root / "AGENTS.md").read_text(encoding="utf-8")
    assert agents_md == claude_md


def test_cli_setup_wires_claude_dir(tmp_path):
    result = runner.invoke(app, ["setup", "--claude-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert (tmp_path / "skills" / "mmdoc" / "SKILL.md").is_file()
    assert BEGIN in (tmp_path / "CLAUDE.md").read_text()
    assert "CLAUDE.md" in result.stdout


def test_cli_setup_dry_run_writes_nothing(tmp_path):
    result = runner.invoke(app, ["setup", "--dry-run", "--claude-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert not (tmp_path / "CLAUDE.md").exists()
