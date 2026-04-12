"""OPML and feed parsing helpers."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def parse_opml_feed_urls(opml_path: str) -> list[dict[str, str]]:
    raw = open(opml_path, "rb").read()
    text = CONTROL_CHARS_RE.sub("", raw.decode("utf-8", errors="replace"))
    root = ET.fromstring(text)
    feeds: list[dict[str, str]] = []
    for outline in root.findall(".//outline"):
        xml_url = outline.attrib.get("xmlUrl")
        if xml_url:
            feeds.append({"title": outline.attrib.get("text", "Okänd kanal"), "xml_url": xml_url})

    unique: list[dict[str, str]] = []
    seen = set()
    for item in feeds:
        if item["xml_url"] not in seen:
            seen.add(item["xml_url"])
            unique.append(item)
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
    root = ET.fromstring(xml_text)
    root_name = _tag_name(root)
    items: list[dict[str, Any]] = []

    if root_name == "feed":  # Atom
        feed_title = _entry_text(root, ["title"]) or fallback_channel
        for entry in root.findall("{*}entry"):
            published_raw = _entry_text(entry, ["published", "updated"])
            published_dt = _parse_date(published_raw)
            items.append(
                {
                    "title": _entry_text(entry, ["title"]) or "Utan titel",
                    "channel": feed_title,
                    "published": published_dt,
                    "published_iso": published_dt.isoformat(),
                    "link": _entry_link(entry),
                }
            )
    else:  # RSS
        channel = root.find(".//channel")
        channel_name = fallback_channel
        if channel is not None:
            ch_title = channel.findtext("title")
            if ch_title:
                channel_name = ch_title.strip()
            for entry in channel.findall("item"):
                published_dt = _parse_date(entry.findtext("pubDate"))
                items.append(
                    {
                        "title": (entry.findtext("title") or "Utan titel").strip(),
                        "channel": channel_name,
                        "published": published_dt,
                        "published_iso": published_dt.isoformat(),
                        "link": (entry.findtext("link") or "#").strip(),
                    }
                )
    return items


def collect_latest_youtube_videos(feeds: list[dict[str, str]], max_items: int = 24) -> list[dict[str, Any]]:
    videos: list[dict[str, Any]] = []
    for feed in feeds:
        try:
            with urlopen(feed["xml_url"], timeout=12) as response:
                xml_text = response.read().decode("utf-8", errors="replace")
            feed_items = _parse_feed_xml(xml_text, feed["title"])
            videos.extend(feed_items[:4])
        except (URLError, TimeoutError, ET.ParseError):
            continue

    videos.sort(key=lambda x: x["published"], reverse=True)
    return videos[:max_items]
