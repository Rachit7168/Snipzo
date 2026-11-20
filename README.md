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

Generate a hook title (under 100 characters), description, hashtags (including #Shorts), and tags. Uses Claude when `SNIPZO_ANTHROPIC_API_KEY` is set, otherwise a heuristic:

```bash
snipzo metadata PROJECT_ID --work-dir ./data
```

Metadata JSON is saved next to each render as `renders/<clip-id>.json`.

Run the full pipeline with one command (metadata is generated *before* render so hook titles are burned into the Shorts). Completed stages are skipped if you resume with `--project`:

```bash
snipzo run path/to/video.mp4 --work-dir ./data
# later: snipzo run --project PROJECT_ID --work-dir ./data
```

Evaluate a folder of videos and record human ratings (usable without edits, 1-5 score, notes):

```bash
snipzo eval run path/to/videos --out-dir ./evals --work-dir ./data
# fill usable/rating/notes in ./evals/ratings.csv, then:
snipzo eval summary ./evals/ratings.csv
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
  pipeline.py     # Step 8: snipzo run (resumable)
  eval/           # Step 8: ratings CSV harness
```

PRs should target the `dev` branch, not `main`.

## Demo

From a local long-form video to vertical Shorts in one command. No API keys are required: clip picking and metadata use a deterministic heuristic when `SNIPZO_ANTHROPIC_API_KEY` is unset. Set that key to use Claude instead.

```bash
git clone https://github.com/Rachit7168/Snipzo.git
cd Snipzo
git checkout dev
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,pipeline]"

mkdir -p /workspace/snipzo-demo
# Public-domain talking-head interview (Voice of America / US government work),
# from Wikimedia Commons — not YouTube:
# https://commons.wikimedia.org/wiki/File:VOA_Interview,_Part_2-_Chelsea_Football_Star_Antonio_Rudiger.webm
curl -L --fail -o /workspace/snipzo-demo/source.webm \
  "https://commons.wikimedia.org/wiki/Special:FilePath/VOA_Interview,_Part_2-_Chelsea_Football_Star_Antonio_Rudiger.webm"
ffmpeg -y -i /workspace/snipzo-demo/source.webm -c:v libx264 -pix_fmt yuv420p -c:a aac \
  /workspace/snipzo-demo/source.mp4

snipzo run /workspace/snipzo-demo/source.mp4 --work-dir /workspace/snipzo-demo/work

# Shorts and metadata JSON:
#   /workspace/snipzo-demo/work/<project-id>/renders/clip-*.mp4
#   /workspace/snipzo-demo/work/<project-id>/renders/clip-*.json
# Copy the Shorts and extract a preview frame:
PROJECT=$(ls -1d /workspace/snipzo-demo/work/*/project.json | head -n1)
PROJECT_DIR=$(dirname "$PROJECT")
mkdir -p /workspace/snipzo-demo/renders
cp -a "$PROJECT_DIR/renders/." /workspace/snipzo-demo/renders/
FIRST=$(ls "$PROJECT_DIR"/renders/clip-*.mp4 | head -n1)
ffmpeg -y -ss 2 -i "$FIRST" -frames:v 1 /workspace/snipzo-demo/frame.png
```

Attribution: Voice of America / VOA Africa. Public domain (US government work).
