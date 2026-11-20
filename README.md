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
pip install -e ".[dev,pipeline]"
cp .env.example .env       # optional; see settings below
```

Check that the CLI is installed:

```bash
snipzo --version
snipzo --help
```

Ingest a local video (copies it into a project folder, probes it with `ffprobe`, and extracts 16 kHz mono WAV audio):

```bash
snipzo ingest path/to/video.mp4 --work-dir ./data
```

Transcribe the project with word-level timestamps (uses faster-whisper with the `base` model by default; CI tests mock this so they never download a model):

```bash
snipzo transcribe PROJECT_ID --work-dir ./data
```

Install the optional `pipeline` extra to get faster-whisper (and PySceneDetect for optional scene cuts). Set `SNIPZO_TRANSCRIBER=deepgram` and `SNIPZO_DEEPGRAM_API_KEY` to use the hosted backend instead.

Pick highlight clips from the transcript (Claude when `SNIPZO_ANTHROPIC_API_KEY` is set, otherwise a deterministic heuristic). Boundaries snap to sentence ends with 0.2s padding:

```bash
snipzo pick PROJECT_ID --work-dir ./data
```

Compute a 9:16 crop path for each clip (face tracking when MediaPipe or OpenCV is available, otherwise a center crop; blurred-background fallback when no face is found):

```bash
snipzo reframe PROJECT_ID --work-dir ./data
```

Render 1080×1920 30fps H.264 Shorts with word-by-word captions, a hook title, a progress bar, and loudness normalization:

```bash
snipzo render PROJECT_ID --work-dir ./data --style bold-yellow
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
| `SNIPZO_ANTHROPIC_API_KEY` | unset | Claude API key (clip selection and metadata); heuristic fallback if unset |
| `SNIPZO_ANTHROPIC_MODEL` | `claude-sonnet-4-5` | Claude model |
| `SNIPZO_CLIP_COUNT` | `5` | Number of highlight clips |
| `SNIPZO_CLIP_MIN_SECONDS` | `20` | Minimum clip length |
| `SNIPZO_CLIP_MAX_SECONDS` | `60` | Maximum clip length |
| `SNIPZO_CAPTION_STYLE` | `bold-yellow` | Caption preset (`bold-yellow` or `clean-white`) |
| `SNIPZO_WHISPER_MODEL` | `base` | faster-whisper model size (use `small` or `large-v3` if you want) |
| `SNIPZO_TRANSCRIBER` | `faster-whisper` | `faster-whisper` or `deepgram` |
| `SNIPZO_DEEPGRAM_API_KEY` | unset | Required for the Deepgram backend |
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
