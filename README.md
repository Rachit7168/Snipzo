# Snipzo

Paste or upload a long-form video and get 3–10 ready-to-post vertical Shorts, each with captions, a hook title, description, and hashtags.

**Core promise:** from a source video to a publishable Short in under 5 minutes, with no editing skills needed.

This repository is the Python foundation for that pipeline (CLI first, web app later). Ingest is upload-based (and later YouTube OAuth for videos you own). Arbitrary YouTube downloads are out of scope because they violate YouTube's Terms of Service.

## Pipeline

| Stage | What happens | CLI (planned) |
|---|---|---|
| **Ingest** | Validate a local video, create a project, extract audio | `snipzo ingest` |
| **Transcribe** | Speech-to-text with word-level timestamps | `snipzo transcribe` |
| **Pick** | Segment the transcript and score highlight clips | `snipzo pick` |
| **Reframe** | Convert 16:9 to 9:16, tracking the speaker | `snipzo reframe` |
| **Render** | Captions, hook overlay, audio polish, 1080×1920 MP4 | `snipzo render` |
| **Metadata** | Title, description, hashtags, and tags | `snipzo metadata` |

Placeholder subcommands are already wired into the CLI. Implementations land in later issues.

## Requirements

- Python 3.11 or later
- FFmpeg (and `ffprobe`) on your `PATH` for later pipeline stages

## Setup

```bash
git clone https://github.com/Rachit7168/Snipzo.git
cd Snipzo
git checkout dev
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env       # optional; see settings below
```

Check that the CLI is installed:

```bash
snipzo --version
snipzo --help
```

Run the quality checks (the same ones CI runs on `dev` and `main`):

```bash
ruff check .
mypy
pytest
```

### Configuration

Settings are loaded from environment variables (and an optional `.env` file) with the `SNIPZO_` prefix. See `.env.example` for the full list.

| Variable | Default | Purpose |
|---|---|---|
| `SNIPZO_WORK_DIR` | `./data` | Project working directory |
| `SNIPZO_ANTHROPIC_API_KEY` | unset | Claude API key (clip selection and metadata) |
| `SNIPZO_WHISPER_MODEL` | `large-v3` | Transcription model size |
| `SNIPZO_LOG_LEVEL` | `INFO` | Log verbosity |

### Docker

The image includes FFmpeg and the `snipzo` CLI:

```bash
docker build -t snipzo .
docker run --rm snipzo --version
```

## Project layout

```
src/snipzo/
  cli.py          # Typer entry point (`snipzo`)
  config.py       # pydantic-settings configuration
  ingest/         # Step 2: local upload
  transcribe/     # Step 3: word-level transcription
  pick/           # Step 4: segmentation and highlight selection
  reframe/        # Step 5: 9:16 smart crop
  render/         # Step 6: captions, overlays, export
  metadata/       # Step 7: titles, descriptions, hashtags
```

PRs should target the `dev` branch, not `main`.
