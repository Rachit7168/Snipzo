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
def render(
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
    style: Annotated[
        str | None,
        typer.Option("--style", help="Caption style: bold-yellow or clean-white."),
    ] = None,
) -> None:
    """Render vertical Shorts with captions and a hook overlay."""
    from snipzo.render import render_project

    try:
        updated, renders = render_project(
            project, _settings(work_dir), style_id=style
        )
    except SnipzoError as exc:
        _fail(exc)
        return
    typer.echo(
        f"Rendered {len(renders)} Shorts for project {updated.id} "
        f"-> {updated.renders_dir}"
    )
    for item in renders:
        typer.echo(
            f"  {item.clip_id}: {item.path} "
            f"({item.width}x{item.height} @ {item.fps:.0f}fps, {item.duration:.1f}s)"
        )


@app.command()
def metadata(
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
    """Generate titles, descriptions, and hashtags for each clip."""
    from snipzo.metadata import generate_metadata

    try:
        updated, items = generate_metadata(project, _settings(work_dir))
    except SnipzoError as exc:
        _fail(exc)
        return
    typer.echo(f"Wrote metadata for {len(items)} clips in project {updated.id}")
    for item in items:
        typer.echo(f"  {item.clip_id}: {item.title}")


@app.command()
def run(
    video: Annotated[
        Path | None,
        typer.Argument(help="Path to a local video file."),
    ] = None,
    project: Annotated[
        str | None,
        typer.Option("--project", help="Resume an existing project ID or path."),
    ] = None,
    work_dir: Annotated[
        Path | None,
        typer.Option(
            "--work-dir",
            help="Project working directory (defaults to SNIPZO_WORK_DIR or ./data).",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Re-run every stage, even if artifacts exist."),
    ] = False,
    top_n: Annotated[
        int | None,
        typer.Option("--top-n", help="Number of clips to keep (default: 5)."),
    ] = None,
    style: Annotated[
        str | None,
        typer.Option("--style", help="Caption style: bold-yellow or clean-white."),
    ] = None,
    eval_csv: Annotated[
        Path | None,
        typer.Option(
            "--eval-csv",
            help="Append clip rows to this ratings CSV for later human review.",
        ),
    ] = None,
) -> None:
    """Run ingest, transcribe, pick, metadata, reframe, and render.

    Metadata runs before render so hook titles are burned into the Shorts.
    Completed stages are skipped unless --force is passed.
    """
    from snipzo.eval.harness import ratings_rows_for_project, write_ratings_template
    from snipzo.pipeline import run_pipeline

    if video is None and project is None:
        typer.secho("Provide a video path or --project to resume.", err=True)
        raise typer.Exit(code=1)
    if video is not None and not video.exists():
        typer.secho(f"Video not found: {video}", err=True)
        raise typer.Exit(code=1)

    def on_progress(stage: str, message: str) -> None:
        typer.echo(f"[{stage}] {message}")

    try:
        updated = run_pipeline(
            video,
            _settings(work_dir),
            project_ref=project,
            force=force,
            top_n=top_n,
            style_id=style,
            on_progress=on_progress,
        )
    except SnipzoError as exc:
        _fail(exc)
        return
    typer.echo(f"Done. Project {updated.id} -> {updated.renders_dir}")
    if eval_csv is not None:
        write_ratings_template(
            eval_csv, ratings_rows_for_project(updated, video=video), append=True
        )
        typer.echo(f"Ratings template: {eval_csv}")


eval_app = typer.Typer(
    name="eval",
    help="Run a test set and summarize human clip ratings.",
    no_args_is_help=True,
)
app.add_typer(eval_app, name="eval")


@eval_app.command("run")
def eval_run(
    videos: Annotated[
        Path,
        typer.Argument(
            help="A video file, a directory of videos, or a text list of paths."
        ),
    ],
    out_dir: Annotated[
        Path,
        typer.Option("--out-dir", help="Directory for the ratings CSV."),
    ] = Path("evals"),
    work_dir: Annotated[
        Path | None,
        typer.Option(
            "--work-dir",
            help="Project working directory (defaults to SNIPZO_WORK_DIR or ./data).",
        ),
    ] = None,
    top_n: Annotated[
        int | None,
        typer.Option("--top-n", help="Number of clips to keep per video (default: 5)."),
    ] = None,
    style: Annotated[
        str | None,
        typer.Option("--style", help="Caption style: bold-yellow or clean-white."),
    ] = None,
) -> None:
    """Run the pipeline on a test set and write a ratings CSV (usable/rating/notes)."""
    from snipzo.eval import run_eval_set

    def on_progress(stage: str, message: str) -> None:
        typer.echo(f"[{stage}] {message}")

    try:
        projects, csv_path = run_eval_set(
            videos,
            _settings(work_dir),
            out_dir,
            top_n=top_n,
            style_id=style,
            on_progress=on_progress,
        )
    except SnipzoError as exc:
        _fail(exc)
        return
    typer.echo(
        f"Evaluated {len(projects)} video(s). Fill usable/rating/notes in {csv_path}"
    )
    typer.echo("Then run: snipzo eval summary " + str(csv_path))


@eval_app.command("summary")
def eval_summary_cmd(
    ratings: Annotated[
        Path,
        typer.Argument(
            help="Ratings CSV produced by `snipzo eval run` or `--eval-csv`."
        ),
    ],
) -> None:
    """Report the percent of rated clips marked usable without edits."""
    from snipzo.eval import eval_summary

    try:
        stats = eval_summary(ratings)
    except SnipzoError as exc:
        _fail(exc)
        return
    typer.echo(
        f"{stats['usable']}/{stats['rated']} rated clips usable without edits "
        f"({stats['usable_percent']}%). "
        f"{stats['clips']} clip rows total."
    )

