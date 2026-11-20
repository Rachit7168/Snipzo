"""Typer CLI entry point for Snipzo."""

from typing import Annotated

import typer

from snipzo import __version__

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


@app.command()
def ingest() -> None:
    """Import a local video into a new project."""
    _not_implemented(2)


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
