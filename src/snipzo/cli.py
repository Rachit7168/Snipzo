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
def transcribe(
    project: Annotated[
        str,
        typer.Argument(help="Project ID or path to a project directory."),
    ],
    work_dir: Annotated[
        Path | None,
        typer.Option(
            "--work-dir",
            help="Project working directory (defaults to SNIPZO_WORK_DIR or ./data).",
        ),
    ] = None,
) -> None:
    """Transcribe a project with word-level timestamps."""
    from snipzo.transcribe import transcribe_project

    try:
        updated, transcript = transcribe_project(project, _settings(work_dir))
    except SnipzoError as exc:
        _fail(exc)
        return
    word_count = len(transcript.words)
    typer.echo(
        f"Transcribed project {updated.id} ({transcript.language}, "
        f"{word_count} words) -> {updated.transcript_path}"
    )


@app.command()
def pick(
    project: Annotated[
        str,
        typer.Argument(help="Project ID or path to a project directory."),
    ],
    work_dir: Annotated[
        Path | None,
        typer.Option(
            "--work-dir",
            help="Project working directory (defaults to SNIPZO_WORK_DIR or ./data).",
        ),
    ] = None,
    top_n: Annotated[
        int | None,
        typer.Option("--top-n", help="Number of clips to keep (default: 5)."),
    ] = None,
) -> None:
    """Score and select highlight clips from a transcript."""
    from snipzo.pick import pick_clips

    try:
        updated, clipset = pick_clips(project, _settings(work_dir), top_n=top_n)
    except SnipzoError as exc:
        _fail(exc)
        return
    typer.echo(
        f"Picked {len(clipset.clips)} clips for project {updated.id} "
        f"({clipset.scorer}) -> {updated.clips_path}"
    )
    for clip in clipset.clips:
        typer.echo(
            f"  {clip.id}  {clip.start:.1f}-{clip.end:.1f}s  "
            f"score={clip.score:.2f}  {clip.reason}"
        )


@app.command()
def reframe(
    project: Annotated[
        str,
        typer.Argument(help="Project ID or path to a project directory."),
    ],
    work_dir: Annotated[
        Path | None,
        typer.Option(
            "--work-dir",
            help="Project working directory (defaults to SNIPZO_WORK_DIR or ./data).",
        ),
    ] = None,
) -> None:
    """Compute a 9:16 crop path for each selected clip."""
    from snipzo.reframe import reframe_project

    try:
        updated, paths = reframe_project(project, _settings(work_dir))
    except SnipzoError as exc:
        _fail(exc)
        return
    typer.echo(
        f"Reframed {len(paths)} clips for project {updated.id} -> {updated.crops_dir}"
    )
    for path in paths:
        typer.echo(f"  {path.clip_id}: {path.mode} ({len(path.keyframes)} keyframes)")


@app.command()
def render() -> None:
    """Render vertical Shorts with captions and a hook overlay."""
    _not_implemented(6)


@app.command()
def metadata() -> None:
    """Generate titles, descriptions, and hashtags for each clip."""
    _not_implemented(7)
