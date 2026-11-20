from typer.testing import CliRunner

from snipzo import __version__
from snipzo.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"snipzo {__version__}" in result.stdout


def test_help_lists_pipeline_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("ingest", "transcribe", "pick", "reframe", "render", "metadata"):
        assert command in result.stdout
