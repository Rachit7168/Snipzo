FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Extras to install: "" for the CLI only, "api,pipeline" for the API and workers.
# The api and pipeline extras include yt-dlp for YouTube URL imports.
ARG SNIPZO_EXTRAS=""

COPY pyproject.toml README.md alembic.ini ./
COPY src ./src

RUN pip install --no-cache-dir --upgrade pip \
    && if [ -n "$SNIPZO_EXTRAS" ]; then \
         pip install --no-cache-dir ".[${SNIPZO_EXTRAS}]"; \
       else \
         pip install --no-cache-dir .; \
       fi

ENTRYPOINT ["snipzo"]
CMD ["--help"]
