"""Generate daily briefing HTML for GitHub Pages."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from helpers.feeds import collect_latest_youtube_videos, parse_opml_feed_urls
from helpers.html_builder import build_html
from helpers.news import fetch_news
from helpers.smhi import get_weather

# Default location is Stockholm.
# Change latitude/longitude and label here to switch city later.
LOCATION = {
    "name": "Stockholm",
    "lat": 59.3293,
    "lon": 18.0686,
}

ROOT = Path(__file__).resolve().parent
OPML_FILE = ROOT / "youtube_prenumerationer.opml"
OUTPUT_HTML = ROOT / "docs" / "index.html"


def main() -> None:
    print("[1/4] Hämtar väder från SMHI...")
    weather = get_weather(
        lat=LOCATION["lat"],
        lon=LOCATION["lon"],
        location_name=LOCATION["name"],
    )
    if weather.get("error"):
        print(f"[SMHI] Status: FEL - {weather['error']}")
    else:
        print("[SMHI] Status: OK")

    print("[2/4] Läser OPML och hämtar YouTube-feeds...")
    if OPML_FILE.exists():
        youtube_feeds = parse_opml_feed_urls(str(OPML_FILE))
        print(f"[YouTube] Antal feeds i OPML: {len(youtube_feeds)}")
    else:
        youtube_feeds = []
        print(f"VARNING: OPML-fil saknas: {OPML_FILE}")
    videos = collect_latest_youtube_videos(youtube_feeds, max_items=24)
    print(f"[YouTube] Antal videor efter sortering/gräns: {len(videos)}")

    print("[3/4] Hämtar nyheter från RSS...")
    news = fetch_news(max_per_category=8)

    print("[4/4] Bygger HTML...")
    now_iso = datetime.now(timezone.utc).isoformat()
    html = build_html(
        generated_at_iso=now_iso,
        weather=weather,
        videos=videos,
        news_by_category=news,
    )

    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_HTML.write_text(html, encoding="utf-8")

    print(f"Klar: {OUTPUT_HTML}")
    print(f"Antal videos: {len(videos)}")
    for category, items in news.items():
        print(f"[Nyheter] {category}: {len(items)}")


if __name__ == "__main__":
    main()
