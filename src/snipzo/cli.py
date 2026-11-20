"""Typer CLI entry point for Snipzo."""

from pathlib import Path
from typing import Annotated

import typer

from snipzo import __version__
from snipzo.config import Settings, get_settings
from snipzo.errors import SnipzoError

app = typer.Typer(
    name="snipzo",
    help="Turn long-form videos into ready-to-post vertical Shorts.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"snipzo {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            help="Show the version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """Snipzo command-line interface."""


def _not_implemented(step: int) -> None:
    typer.echo(f"Not implemented yet. Tracked in issue #{step}.")
    raise typer.Exit(code=1)


def _settings(work_dir: Path | None) -> Settings:
    settings = get_settings()
    if work_dir is not None:
        return settings.model_copy(update={"work_dir": work_dir})
    return settings


def _fail(exc: SnipzoError) -> None:
    typer.secho(str(exc), fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1) from exc


@app.command()
def ingest(
    video: Annotated[
        Path,
        typer.Argument(help="Path to a local video file.", exists=True, readable=True),
    ],
    work_dir: Annotated[
        Path | None,
        typer.Option(
            "--work-dir",
            help="Project working directory (defaults to SNIPZO_WORK_DIR or ./data).",
        ),
    ] = None,
) -> None:
    """Import a local video into a new project."""
    from snipzo.ingest import ingest_video

    try:
        project = ingest_video(video, _settings(work_dir))
    except SnipzoError as exc:
        _fail(exc)
        return
    typer.echo(f"Project {project.id} created at {project.root}")
    typer.echo(
        f"Source: {project.source.width}x{project.source.height} "
        f"@ {project.source.fps:.2f} fps, {project.source.duration:.2f}s"
    )
    typer.echo(f"Audio: {project.audio_path}")


@app.command()
def transcribe() -> None:
    """Transcribe a project with word-level timestamps."""
    _not_implemented(3)


@app.command()
def pick() -> None:
    """Score and select highlight clips from a transcript."""
    _not_implemented(4)


@app.command()
def reframe() -> None:
    """Compute a 9:16 crop path for each selected clip."""
    _not_implemented(5)


@app.command()
def render() -> None:
    """Render vertical Shorts with captions and a hook overlay."""
    _not_implemented(6)


@app.command()
def metadata() -> None:
    """Generate titles, descriptions, and hashtags for each clip."""
    _not_implemented(7)
