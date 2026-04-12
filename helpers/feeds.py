"""OPML and YouTube feed helpers."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener

CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
TAG_RE = re.compile(r"<[^>]+>")
URL_RE = re.compile(r"https?://\S+")
SPACE_RE = re.compile(r"\s+")
XMLURL_RE = re.compile(r'xmlUrl="([^"]+)"')


def parse_opml_feed_urls(opml_path: str) -> list[dict[str, str]]:
    """Parse OPML in a fault-tolerant way and return unique feed URLs."""
    raw = open(opml_path, "rb").read()
    text = CONTROL_CHARS_RE.sub("", raw.decode("utf-8", errors="replace"))

    feeds: list[dict[str, str]] = []
    try:
        root = ET.fromstring(text)
        for outline in root.findall(".//outline"):
            xml_url = outline.attrib.get("xmlUrl")
            if xml_url:
                feeds.append({"title": outline.attrib.get("text", "Okänd kanal"), "xml_url": xml_url})
    except ET.ParseError:
        for index, match in enumerate(XMLURL_RE.findall(text), start=1):
            feeds.append({"title": f"Kanal {index}", "xml_url": match})

    unique: list[dict[str, str]] = []
    seen = set()
    for item in feeds:
        if item["xml_url"] not in seen:
            seen.add(item["xml_url"])
            unique.append(item)

    print(f"[YouTube] OPML: hittade {len(unique)} unika feed-url:er.")
    return unique


def _parse_date(value: str | None) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        dt = parsedate_to_datetime(value)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        pass
    try:
        dt2 = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if not dt2.tzinfo:
            dt2 = dt2.replace(tzinfo=timezone.utc)
        return dt2.astimezone(timezone.utc)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = unescape(value)
    text = TAG_RE.sub(" ", text)
    text = URL_RE.sub("", text)
    return SPACE_RE.sub(" ", text).strip()


def _split_sentences(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?])\s+", text)
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _make_video_summary(title: str, channel: str, source_text: str) -> str:
    clean_source = _clean_text(source_text)
    clean_title = _clean_text(title) or "Videon"
    clean_channel = _clean_text(channel) or "kanalen"

    sentences = _split_sentences(clean_source)
    first = sentences[0] if sentences else f"{clean_title} är en ny video från {clean_channel}."
    first = first.rstrip(".!?") + "."

    if len(sentences) >= 2:
        second = sentences[1]
    elif clean_source:
        words = clean_source.split()
        tail = " ".join(words[20:40]).strip()
        second = tail if tail else f"Innehållet publicerades av {clean_channel} och går att se via länken."
    else:
        second = f"Innehållet publicerades av {clean_channel} och går att se via länken."
    second = second.rstrip(".!?") + "."

    if first == second:
        second = f"Videon kommer från {clean_channel} och kan läsas mer om via länken."
    return f"{first} {second}"


def _tag_name(elem: ET.Element) -> str:
    return elem.tag.split("}")[-1]


def _entry_text(entry: ET.Element, names: list[str]) -> str | None:
    for child in entry:
        if _tag_name(child) in names and child.text:
            return child.text.strip()
    return None


def _entry_link(entry: ET.Element) -> str:
    for child in entry:
        if _tag_name(child) == "link":
            href = child.attrib.get("href")
            if href:
                return href
            if child.text:
                return child.text.strip()
    return "#"


def _parse_feed_xml(xml_text: str, fallback_channel: str) -> list[dict[str, Any]]:
    root = ET.fromstring(CONTROL_CHARS_RE.sub("", xml_text))
    root_name = _tag_name(root)
    items: list[dict[str, Any]] = []

    if root_name == "feed":  # Atom
        feed_title = _entry_text(root, ["title"]) or fallback_channel
        for entry in root.findall("{*}entry"):
            published_raw = _entry_text(entry, ["published", "updated"])
            published_dt = _parse_date(published_raw)
            summary = _entry_text(entry, ["summary", "content", "media:group"]) or ""
            items.append(
                {
                    "title": _entry_text(entry, ["title"]) or "Utan titel",
                    "channel": feed_title,
                    "published": published_dt,
                    "published_iso": published_dt.isoformat(),
                    "link": _entry_link(entry),
                    "summary": _make_video_summary(
                        title=_entry_text(entry, ["title"]) or "",
                        channel=feed_title,
                        source_text=summary,
                    ),
                }
            )
    else:
        channel = root.find(".//channel")
        channel_name = fallback_channel
        if channel is not None:
            ch_title = channel.findtext("title")
            if ch_title:
                channel_name = ch_title.strip()
            for entry in channel.findall("item"):
                published_dt = _parse_date(entry.findtext("pubDate"))
                summary = entry.findtext("description") or ""
                items.append(
                    {
                        "title": (entry.findtext("title") or "Utan titel").strip(),
                        "channel": channel_name,
                        "published": published_dt,
                        "published_iso": published_dt.isoformat(),
                        "link": (entry.findtext("link") or "#").strip(),
                        "summary": _make_video_summary(
                            title=(entry.findtext("title") or ""),
                            channel=channel_name,
                            source_text=summary,
                        ),
                    }
                )
    return items


def collect_latest_youtube_videos(feeds: list[dict[str, str]], max_items: int = 24) -> list[dict[str, Any]]:
    opener = build_opener(ProxyHandler({}))
    videos: list[dict[str, Any]] = []
    for feed in feeds:
        request = Request(
            feed["xml_url"],
            headers={
                "User-Agent": "DailyBriefingBot/1.1 (+https://github.com/actions)",
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
            },
        )
        try:
            with opener.open(request, timeout=15) as response:
                xml_text = response.read().decode("utf-8", errors="replace")
            feed_items = _parse_feed_xml(xml_text, feed["title"])
            videos.extend(feed_items[:4])
        except (URLError, TimeoutError, ET.ParseError) as exc:
            print(f"[YouTube] VARNING: kunde inte läsa {feed['xml_url']}: {exc}")
            continue

    videos.sort(key=lambda x: x["published"], reverse=True)
    videos = videos[:max_items]
    print(f"[YouTube] OK: hämtade totalt {len(videos)} videoposter.")
    return videos
