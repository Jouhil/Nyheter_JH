#!/usr/bin/env python3
"""Targeted diagnostic for why a specific YouTube video is not visible in the app."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parent
YOUTUBE_JSON = ROOT / "docs" / "data" / "youtube-latest.json"
YOUTUBE_DEBUG_JSON = ROOT / "docs" / "data" / "youtube-debug.json"
OPML_PATH = ROOT / "youtube_prenumerationer.opml"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _parse_opml_feeds(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    feeds: list[dict[str, str]] = []
    for outline in root.findall(".//outline"):
        xml_url = outline.attrib.get("xmlUrl")
        if xml_url:
            feeds.append(
                {
                    "title": outline.attrib.get("text", "Okänd kanal"),
                    "xml_url": xml_url,
                    "html_url": outline.attrib.get("htmlUrl", ""),
                }
            )
    return feeds


def _parse_date(video: dict) -> datetime | None:
    unix = video.get("published_at_unix")
    if isinstance(unix, (int, float)) and unix > 0:
        return datetime.fromtimestamp(unix, tz=timezone.utc)
    iso = video.get("published_at_utc")
    if isinstance(iso, str) and iso:
        try:
            return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            return None
    return None


def _short_decision(video: dict) -> dict:
    signals: list[str] = []
    url = str(video.get("url") or "").lower()
    if "/shorts/" in url:
        signals.append("url_contains_/shorts/")

    duration = video.get("duration")
    if isinstance(duration, (int, float)) and duration > 0 and duration <= 60:
        signals.append("duration_<=_60s")

    title = str(video.get("title") or "").lower()
    if re.search(r"#shorts\\b", title):
        signals.append("title_contains_#shorts")
    if re.search(r"\\bshorts\\b", title):
        signals.append("title_contains_word_shorts")

    return {
        "is_short": bool(signals),
        "signals": signals,
        "reason": signals[0] if signals else None,
    }


def _fmt_bool(v: bool) -> str:
    return "JA" if v else "NEJ"


@dataclass
class AppDecision:
    in_json: bool
    short_filtered: bool
    in_24h: bool
    published_at: str | None


def _evaluate_app_decision(video: dict) -> AppDecision:
    now = datetime.now(timezone.utc)
    lower = now - timedelta(hours=24)
    published = _parse_date(video)
    short_dec = _short_decision(video)
    in_24h = bool(published and lower <= published <= now)
    return AppDecision(
        in_json=True,
        short_filtered=short_dec["is_short"],
        in_24h=in_24h,
        published_at=published.isoformat() if published else None,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("video_id")
    parser.add_argument("--expected-channel", default="", help="Förväntat kanalnamn (om känt)")
    parser.add_argument("--expected-feed", default="", help="Förväntad feed-url (om känd)")
    parser.add_argument("--probe-feeds", action="store_true", help="Försök hämta alla OPML-feeds och logga status")
    args = parser.parse_args()

    payload = _load_json(YOUTUBE_JSON)
    videos = payload.get("videos") if isinstance(payload, dict) else []
    videos = videos if isinstance(videos, list) else []

    print(f"[1] Kontroll: video_id={args.video_id}")
    matches = [v for v in videos if v.get("video_id") == args.video_id]
    print(f"- Finns i docs/data/youtube-latest.json: {_fmt_bool(bool(matches))}")

    if matches:
        video = matches[0]
        app_decision = _evaluate_app_decision(video)
        short_dec = _short_decision(video)
        print("\n[2] Video finns i JSON -> varför syns/inte syns i docs/app.js")
        print(f"- Kanal: {video.get('channel')}")
        print(f"- Publicerad (UTC): {app_decision.published_at}")
        print(f"- short-decision.is_short: {_fmt_bool(app_decision.short_filtered)}")
        print(f"- short-decision.signals: {short_dec['signals']}")
        print(f"- 24h-decision (inom senaste 24h): {_fmt_bool(app_decision.in_24h)}")
        if app_decision.short_filtered:
            print("- ROOT CAUSE: Filtreras bort i app.js shorts-filter.")
        elif not app_decision.in_24h:
            print("- ROOT CAUSE: Filtreras bort i app.js 24h-filter.")
        else:
            print("- ROOT CAUSE: Ska synas i appen (ingen filterträff i app.js).")
        return 0

    print("\n[2] Video finns INTE i youtube-latest.json -> build-steget är felställe")
    feeds = _parse_opml_feeds(OPML_PATH)
    print(f"- OPML-feeds i builden: {len(feeds)} st")

    if args.expected_channel:
        channel_match = [f for f in feeds if args.expected_channel.lower() in (f.get("title") or "").lower()]
        print(f"- Förväntad kanal '{args.expected_channel}' finns i OPML: {_fmt_bool(bool(channel_match))}")
        for feed in channel_match:
            print(f"  • {feed['title']} -> {feed['xml_url']}")

    if args.expected_feed:
        exact = any((f.get("xml_url") or "") == args.expected_feed for f in feeds)
        print(f"- Förväntad feed-url finns i OPML: {_fmt_bool(exact)}")

    if args.probe_feeds and feeds:
        print("\n[2b] Feed-probe (live i nuvarande miljö)")
        opener = build_opener(ProxyHandler({}))
        for feed in feeds:
            url = feed["xml_url"]
            request = Request(url, headers={"User-Agent": "DailyBriefingBot/diagnose"})
            try:
                with opener.open(request, timeout=10) as response:
                    _ = response.read(256)
                print(f"- FETCH OK: {feed['title']} | {url}")
            except (URLError, TimeoutError, HTTPError) as exc:
                print(f"- FETCH FAIL: {feed['title']} | {url} | {exc}")

    debug = _load_json(YOUTUBE_DEBUG_JSON)
    if debug:
        print("\n[3] Debugstatus från senaste build")
        print(f"- feeds_fetched_ok: {debug.get('feeds_fetched_ok')}")
        print(f"- feeds_failed: {debug.get('feeds_failed')}")
        failed = debug.get("failed_feed_urls") or []
        print(f"- failed_feed_urls (antal): {len(failed)}")
    else:
        print("\n[3] Ingen docs/data/youtube-debug.json hittades -> kan inte verifiera fetch-status per feed för senaste körningen.")

    print("\n[4] Exakt steg som gör att videon inte syns i appen")
    print("- Videon stoppas före frontend, i generate_briefing.py -> collect_latest_youtube_videos(...).")
    print("- Eftersom video_id inte finns i youtube-latest.json når den aldrig docs/app.js-filterlogik.")
    print("- Praktiskt innebär det: antingen saknas rätt kanal/feed i OPML, eller feeden hämtades inte, eller posten filtrerades innan JSON-skrivning.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
