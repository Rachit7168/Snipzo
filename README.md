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

## Backend API and workers

The `api` extra adds a FastAPI service, Celery workers, a SQLAlchemy/Alembic data model (`users`, `channels`, `projects`, `transcripts`, `clips`, `renders`, `publications`, `jobs`), and blob storage on S3/Cloudflare R2 with a local-filesystem fallback.

```bash
pip install -e ".[dev,api,pipeline]"
```

### With Docker

```bash
docker compose up --build
# API docs: http://localhost:8000/docs
```

This starts `postgres`, `redis`, `api` (runs `snipzo db upgrade`, then uvicorn), `worker` (Celery, queues `gpu` and `cpu`), and `beat` (daily source cleanup).

### Without Docker

```bash
export SNIPZO_DATABASE_URL=sqlite:///./data/snipzo.db   # or a postgresql+psycopg:// URL
export SNIPZO_REDIS_URL=redis://localhost:6379/0
snipzo db upgrade
uvicorn snipzo.api.app:app --reload --port 8000
celery -A snipzo.api.worker worker -Q gpu,cpu --loglevel=INFO   # second terminal
celery -A snipzo.api.worker beat --loglevel=INFO                 # optional: cleanup
```

No Redis? Set `SNIPZO_CELERY_EAGER=true` and jobs run inline in the API process (fine for a laptop demo; uploads block until the Shorts are rendered).

### Using the API

```bash
TOKEN=$(curl -s localhost:8000/auth/register -H 'content-type: application/json' \
  -d '{"email":"me@example.com","password":"a-long-password"}' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s localhost:8000/projects -H "Authorization: Bearer $TOKEN" \
  -F rights_confirmed=true -F file=@video.mp4
curl -s localhost:8000/projects/<id> -H "Authorization: Bearer $TOKEN"   # job progress + clips
```

Each clip in the response has a signed, expiring `download_url` (usable directly in a `<video>` tag). You can also pass `-F source_url=https://.../video.mp4` instead of a file; YouTube/TikTok/Instagram page links are rejected.

Jobs run in two Celery tasks: `snipzo.ingest_transcribe` on the `gpu` queue (Whisper), then `snipzo.highlights_render` on the `cpu` queue (pick, metadata, reframe, FFmpeg render). Run separate workers per queue in production (`-Q gpu` on GPU hosts, `-Q cpu` elsewhere). All workers must share `SNIPZO_WORK_DIR` (or a volume).

Storage: set `SNIPZO_STORAGE_BACKEND=s3`, `SNIPZO_S3_BUCKET`, `SNIPZO_S3_ENDPOINT_URL` (for R2: `https://<account>.r2.cloudflarestorage.com`), and the access keys. Source videos are deleted after `SNIPZO_SOURCE_RETENTION_DAYS` (default 14, max 30) by the `snipzo.cleanup_sources` beat task; you can also add a matching bucket lifecycle rule on the `sources/` prefix.

## Web app

`web/` is a Next.js + Tailwind app with email/password sign-in (Auth.js / NextAuth credentials provider backed by the API's `/auth/login`). Signed-in users can upload a file or paste a direct video URL (with the "I own or have rights to this content" checkbox), watch job progress by stage, preview each Short with its score and reason, and download the MP4.

```bash
# Terminal 1: API (jobs inline, no Redis needed)
SNIPZO_CELERY_EAGER=true uvicorn snipzo.api.app:app --port 8000
# Terminal 2: web
cd web
cp .env.example .env.local   # set NEXTAUTH_SECRET (openssl rand -base64 32)
npm install
npm run dev                  # http://localhost:3000
```

Env vars: `NEXT_PUBLIC_API_URL` (browser → API), `SNIPZO_API_URL` (server → API, defaults to the public URL), `NEXTAUTH_URL`, `NEXTAUTH_SECRET`. With Docker, `docker compose up --build` also starts the web app on port 3000.

## Clip editor

Open a project in the web app and click **Edit** on any Short (`/projects/<id>/clips/<clip-id>`):

- **Trim** start/end on a timeline (sliders or "set to playhead"); clips must be 3–180 s.
- **Captions**: edit the text of each caption group; timing is kept. Changing the trim regenerates captions from the transcript.
- **Title**: hook title (burned into the first seconds), YouTube title, description, hashtags (`#Shorts` is always kept), and caption style preset.
- **Live preview** in the browser (source video in a 9:16 frame with the hook and caption overlay), then **Save & re-render** queues `snipzo.rerender_clip` on the CPU queue and shows the new render version when it finishes.

API: `GET /projects/{id}/clips/{clip_id}/editor` and `PATCH /projects/{id}/clips/{clip_id}` (body fields: `start`, `end`, `hook_title`, `title`, `description`, `hashtags`, `style_id`, `captions`, `rerender`). Edits are stored in the project folder (`clips.json`, `renders/<clip>.json`, `edits/<clip>.json`). Editing requires the source video, so it stops working once the source retention window has passed.

## YouTube: connect, import, publish

1. In Google Cloud, enable **YouTube Data API v3**, create an OAuth client (Web application), and add `http://localhost:8000/youtube/callback` (or your `SNIPZO_GOOGLE_REDIRECT_URI`) as a redirect URI. Start Google's app verification early; the `youtube.upload` scope is sensitive and review can take weeks.
2. Set `SNIPZO_GOOGLE_CLIENT_ID`, `SNIPZO_GOOGLE_CLIENT_SECRET`, `SNIPZO_TOKEN_ENCRYPTION_KEY` (Fernet), and `SNIPZO_WEB_APP_URL` on the API and workers.
3. In the web app, open **Channels → Connect YouTube**. Tokens are stored encrypted (Fernet) and refreshed automatically.

- **Import**: lists videos from your channel's own uploads playlist; `POST /youtube/channels/{id}/import` checks the video's `channelId` matches your connected channel (403 otherwise) and requires the rights checkbox. The Data API does not provide media files, so by default import stops after verifying ownership (HTTP 501, with a message to upload the original). Set `SNIPZO_YOUTUBE_IMPORT_DOWNLOADER=yt-dlp` and install `yt-dlp` on workers to fetch owned videos.
- **Publish**: `POST /projects/{id}/clips/{clip_id}/publish` (and the Publish panel on a project) runs a resumable `videos.insert` upload on the worker with title/description/tags, privacy, optional scheduling (`publishAt`, forced private as YouTube requires), `selfDeclaredMadeForKids`, and the altered/synthetic content disclosure (`containsSyntheticMedia`). Requires the rights confirmation.
- **Legal**: the web app ships template `/privacy` (incl. Google API Services User Data Policy / Limited Use), `/terms`, and `/takedown` pages; notices are stored via `POST /takedown`. Operator process: [docs/TAKEDOWN.md](docs/TAKEDOWN.md).

Tests mock every Google call; no real credentials are needed to run them.

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
  edit.py         # Step 11: trim/caption/title edits and single-clip re-render
  eval/           # Step 8: ratings CSV harness
  api/            # Step 9: FastAPI app, Celery worker, DB models, blob storage
web/              # Step 10: Next.js app (sign-in, upload, progress, preview, download)
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
