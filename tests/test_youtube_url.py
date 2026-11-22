from __future__ import annotations

import pytest

from snipzo.api.ytdlp import (
    friendly_from_message,
    friendly_restriction,
    info_from_extract,
)
from snipzo.youtube_url import (
    YoutubeUrlError,
    canonical_watch_url,
    classify_source_url,
    parse_youtube_video_id,
)

VIDEO = "dQw4w9wg9cQ"
CANONICAL = canonical_watch_url(VIDEO)

FORMS = [
    f"https://www.youtube.com/watch?v={VIDEO}",
    f"https://youtube.com/watch?v={VIDEO}",
    f"http://www.youtube.com/watch?v={VIDEO}&feature=share",
    f"https://youtu.be/{VIDEO}",
    f"https://youtu.be/{VIDEO}?t=43",
    f"https://www.youtube.com/shorts/{VIDEO}",
    f"https://youtube.com/shorts/{VIDEO}?feature=share",
    f"https://www.youtube.com/live/{VIDEO}",
    f"https://www.youtube.com/embed/{VIDEO}",
    f"https://www.youtube.com/embed/{VIDEO}?start=30",
    f"https://m.youtube.com/watch?v={VIDEO}",
    f"https://m.youtube.com/shorts/{VIDEO}",
    f"https://music.youtube.com/watch?v={VIDEO}&list=RDxxxxx",
    f"https://www.youtube.com/watch?v={VIDEO}&list=PLxxxx&index=3&t=12s",
    f"https://www.youtube.com/v/{VIDEO}",
    f"https://www.youtube.com/watch?v={VIDEO}&ab_channel=Example",
    f"https://www.youtube-nocookie.com/embed/{VIDEO}",
    f"https://youtu.be/{VIDEO}?si=shareparam",
    f"https://www.youtube.com/watch?v={VIDEO}#t=1m30s",
    f"https://youtube.com/watch?si=abc&v={VIDEO}",
]


@pytest.mark.parametrize("url", FORMS)
def test_parse_normalises_every_common_form(url: str) -> None:
    assert parse_youtube_video_id(url) == VIDEO
    kind, normalised = classify_source_url(url)
    assert kind == "youtube"
    assert normalised == CANONICAL


def test_direct_file_url_is_unchanged() -> None:
    url = "https://cdn.example.com/talks/episode.mp4"
    kind, normalised = classify_source_url(url)
    assert kind == "url"
    assert normalised == url


def test_playlist_only_and_channel_pages_are_rejected() -> None:
    with pytest.raises(YoutubeUrlError, match="single video, not a playlist"):
        parse_youtube_video_id("https://www.youtube.com/playlist?list=PLxxxx")
    with pytest.raises(YoutubeUrlError, match="single video, not a playlist"):
        parse_youtube_video_id("https://www.youtube.com/watch?list=PLxxxx")
    with pytest.raises(YoutubeUrlError, match="channel or playlist"):
        parse_youtube_video_id("https://www.youtube.com/@somechannel")
    with pytest.raises(YoutubeUrlError, match="channel or playlist"):
        parse_youtube_video_id("https://www.youtube.com/channel/UCxxxxxxxxxx")


def test_tiktok_and_instagram_are_rejected() -> None:
    with pytest.raises(YoutubeUrlError, match="TikTok and Instagram"):
        classify_source_url("https://www.tiktok.com/@user/video/123")
    with pytest.raises(YoutubeUrlError, match="TikTok and Instagram"):
        classify_source_url("https://www.instagram.com/reel/AbCde12345/")


def test_friendly_restriction_and_error_messages() -> None:
    private = friendly_restriction({"availability": "private"}) or ""
    assert "private" in private.lower()
    members = friendly_restriction({"availability": "subscriber_only"}) or ""
    assert "members-only" in members
    age = friendly_restriction({"age_limit": 18}) or ""
    assert "age-restricted" in age
    live = friendly_restriction({"live_status": "is_live", "is_live": True}) or ""
    assert "still in progress" in live
    upcoming = friendly_restriction({"live_status": "is_upcoming"}) or ""
    assert "hasn't started" in upcoming
    assert "private" in friendly_from_message("ERROR: Private video").lower()
    bot = friendly_from_message("Sign in to confirm you're not a bot")
    assert "blocked" in bot.lower()
    busy = friendly_from_message("HTTP Error 429: Too Many Requests")
    assert "blocked" in busy.lower()
    # Raw yt-dlp traces must not leak.
    message = friendly_from_message(
        "ERROR: [youtube] abc: extractor raised; traceback in /tmp/yt-dlp"
    )
    assert "/tmp" not in message
    assert "traceback" not in message.lower()


def test_info_from_extract_allows_unlisted_and_maps_fields() -> None:
    info = info_from_extract(
        {
            "id": VIDEO,
            "title": "A public-domain talk",
            "duration": 125.5,
            "thumbnail": "https://i.ytimg.com/vi/dQw4w9wg9cQ/hqdefault.jpg",
            "availability": "unlisted",
        },
        "https://youtu.be/dQw4w9wg9cQ?t=9",
    )
    assert info.video_id == VIDEO
    assert info.title == "A public-domain talk"
    assert info.duration == 125.5
    assert info.url == CANONICAL
