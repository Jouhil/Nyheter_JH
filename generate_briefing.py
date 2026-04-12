"""Generate daily briefing HTML for GitHub Pages."""

from __future__ import annotations

import os
import re
import json
from datetime import datetime, timezone
from pathlib import Path

from helpers.feeds import collect_latest_youtube_videos, parse_opml_feed_urls
from helpers.html_builder import build_html
from helpers.news import fetch_news
from helpers.smhi import get_weather

LOCATION = {
    "name": "Göteborg/Säve",
    "lat": 57.7089,
    "lon": 11.9746,
}

ROOT = Path(__file__).resolve().parent
OPML_FILE = ROOT / "youtube_prenumerationer.opml"
OUTPUT_HTML = ROOT / "docs" / "index.html"
OUTPUT_WEATHER_JSON = ROOT / "docs" / "data" / "weather-goteborg.json"
DEBUG_DIR = ROOT / "debug"


class ValidationError(RuntimeError):
    """Raised when the generated briefing does not meet minimum content requirements."""


def _is_debug_enabled() -> bool:
    return os.getenv("DEBUG_BRIEFING", "0").strip() in {"1", "true", "yes"}


def _has_weather_value(weather: dict) -> bool:
    return weather.get("temperature_c") is not None or weather.get("wind_ms") is not None




def _default_hourly_rows() -> list[dict]:
    rows = []
    for _ in range(24):
        rows.append({
            "time": None,
            "temperature": None,
            "weather_code": None,
            "precipitation": None,
            "wind_speed": None,
        })
    return rows


def _default_daily_rows() -> list[dict]:
    rows = []
    for _ in range(10):
        rows.append({
            "date": None,
            "temp_max": None,
            "temp_min": None,
            "weather_code": None,
            "precipitation_sum": None,
        })
    return rows

def _validate_counts(weather: dict, videos: list[dict], news: dict[str, list[dict]]) -> None:
    total_news = sum(len(items) for items in news.values())
    errors: list[str] = []

    if not _has_weather_value(weather):
        weather_warning: str
        if weather.get("error"):
            weather_warning = f"Väder saknas: {weather.get('error')}"
        else:
            weather_warning = "Väder saknas: inga mätvärden i SMHI-data"
        print(f"[VALIDERING] VARNING: {weather_warning}")
        print("[VALIDERING] VARNING: Fortsätter ändå (väder är inte blockerande)")
    if len(videos) == 0:
        print("[VALIDERING] VARNING: Inga YouTube-videos från senaste 24h efter filtrering.")
    if total_news < 3:
        errors.append(f"Nyheter har för få poster totalt ({total_news} < 3)")

    if errors:
        for err in errors:
            print(f"[VALIDERING] FEL: {err}")
        raise ValidationError("; ".join(errors))


def _validate_html_content(html: str, weather: dict, videos: list[dict], news: dict[str, list[dict]]) -> None:
    issues: list[str] = []

    if videos:
        first_video_title = videos[0].get("title", "")
        if first_video_title and first_video_title not in html:
            issues.append("Minst en YouTube-titel hittades inte i HTML")
    if any(news.values()):
        first_news = next((item.get("title", "") for items in news.values() for item in items if item.get("title")), "")
        if first_news and first_news not in html:
            issues.append("Minst en nyhetsrubrik hittades inte i HTML")
    weather_temp = weather.get("temperature_c")
    if weather_temp is not None:
        weather_token = re.escape(str(weather_temp))
        if re.search(weather_token, html) is None:
            issues.append("Minst ett vädervärde hittades inte i HTML")

    if issues:
        for issue in issues:
            print(f"[HTML-VALIDERING] FEL: {issue}")
        raise ValidationError("; ".join(issues))


def main() -> None:
    debug = _is_debug_enabled()
    if debug:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        print(f"[DEBUG] Aktiverat. Skriver debugfiler till: {DEBUG_DIR}")

    print("[1/4] Hämtar väder från Open-Meteo...")
    weather = get_weather(
        lat=LOCATION["lat"],
        lon=LOCATION["lon"],
        location_name=LOCATION["name"],
        debug=debug,
        debug_dir=DEBUG_DIR if debug else None,
    )
    if weather.get("error"):
        print(f"[WEATHER] Status: FEL - {weather['error']}")
    else:
        print("[WEATHER] Status: OK")
    OUTPUT_WEATHER_JSON.parent.mkdir(parents=True, exist_ok=True)
    weather_payload = {
        "location": LOCATION["name"],
        "current": {
            "temperature": weather.get("temperature_c"),
            "wind_speed": weather.get("wind_ms"),
            "precipitation": weather.get("precip_mm_h"),
            "weather_code": weather.get("weather_code"),
            "description": weather.get("description"),
            "forecast_time": weather.get("forecast_time_utc"),
            "feels_like": weather.get("feels_like_c"),
            "temp_min": weather.get("min_c"),
            "temp_max": weather.get("max_c"),
        },
        "hourly_24": weather.get("hourly_24") or _default_hourly_rows(),
        "daily_10": weather.get("daily_10") or _default_daily_rows(),
        "error": weather.get("error"),
    }
    OUTPUT_WEATHER_JSON.write_text(
        json.dumps(weather_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[WEATHER] Skrev lokal väderfil: {OUTPUT_WEATHER_JSON}")
    print("[WEATHER] Preview (första 400 tecken):")
    print(json.dumps(weather_payload, ensure_ascii=False)[:400])

    print("[2/4] Läser OPML och hämtar YouTube-feeds...")
    if OPML_FILE.exists():
        youtube_feeds = parse_opml_feed_urls(str(OPML_FILE), debug=debug)
        print(f"[YouTube] Antal feeds i OPML: {len(youtube_feeds)}")
    else:
        youtube_feeds = []
        print(f"VARNING: OPML-fil saknas: {OPML_FILE}")

    videos = collect_latest_youtube_videos(
        youtube_feeds,
        max_items=24,
        debug=debug,
        debug_dir=DEBUG_DIR if debug else None,
    )
    print(f"[YouTube] Antal videor som skickas till rendering: {len(videos)}")

    print("[3/4] Hämtar nyheter från RSS...")
    news = fetch_news(
        max_per_category=8,
        debug=debug,
        debug_dir=DEBUG_DIR if debug else None,
        interests_path=ROOT / 'config' / 'interests.json',
        opml_path=OPML_FILE,
    )
    for category, items in news.items():
        print(f"[Nyheter] {category}: {len(items)} poster till rendering")

    _validate_counts(weather, videos, news)

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

    _validate_html_content(html, weather, videos, news)

    print(f"Klar: {OUTPUT_HTML}")
    print(f"Antal videos renderade: {len(videos)}")


if __name__ == "__main__":
    main()
