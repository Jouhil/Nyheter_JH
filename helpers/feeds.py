"""OPML and YouTube feed helpers."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener

CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
TAG_RE = re.compile(r"<[^>]+>")
URL_RE = re.compile(r"https?://\S+")
SPACE_RE = re.compile(r"\s+")
XMLURL_RE = re.compile(r'xmlUrl="([^"]+)"')
YOUTUBE_ID_RE = re.compile(r"(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})")


def parse_opml_feed_urls(opml_path: str, debug: bool = False) -> list[dict[str, str]]:
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

    print(f"[YouTube] OPML: hittade {len(feeds)} xmlUrl, {len(unique)} unika feed-url:er.")
    if debug and unique:
        sample_urls = [f["xml_url"] for f in unique[:3]]
        print(f"[YouTube][DEBUG] Exempel feed-url: {sample_urls}")
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
        second = tail if tail else f"Videon kommer från {clean_channel} och handlar om ämnet i titeln."
    else:
        second = f"Videon kommer från {clean_channel} och handlar om ämnet i titeln."
    second = second.rstrip(".!?") + "."

    if first == second:
        second = f"Öppna länken för att se hela genomgången från {clean_channel}."
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




def _extract_youtube_video_id(link: str | None, entry: ET.Element | None = None) -> str | None:
    candidates: list[str] = []
    if link:
        candidates.append(link)
    if entry is not None:
        for child in entry:
            name = _tag_name(child)
            if name == "videoId" and child.text:
                value = child.text.strip()
                if value:
                    return value
            if name == "id" and child.text:
                candidates.append(child.text.strip())
            if name == "link":
                href = child.attrib.get("href")
                if href:
                    candidates.append(href)

    for candidate in candidates:
        match = YOUTUBE_ID_RE.search(candidate)
        if match:
            return match.group(1)
        tail = candidate.rsplit(":", 1)[-1].strip()
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", tail):
            return tail
    return None


def _build_youtube_links(raw_link: str, video_id: str | None) -> dict[str, str | None]:
    if video_id:
        clean = f"https://www.youtube.com/watch?v={video_id}"
        short = f"https://youtu.be/{video_id}"
        return {"primary": clean, "secondary": short}
    return {"primary": raw_link or "#", "secondary": None}
def _media_group_text(entry: ET.Element) -> str:
    for child in entry:
        if _tag_name(child) == "group":
            for nested in child:
                if _tag_name(nested) in {"description", "title"} and nested.text:
                    return nested.text.strip()
    return ""


def _parse_feed_xml(xml_text: str, fallback_channel: str) -> list[dict[str, Any]]:
    root = ET.fromstring(CONTROL_CHARS_RE.sub("", xml_text))
    root_name = _tag_name(root)
    items: list[dict[str, Any]] = []

    if root_name == "feed":  # Atom
        feed_title = _entry_text(root, ["title"]) or fallback_channel
        for entry in root.findall("{*}entry"):
            published_raw = _entry_text(entry, ["published", "updated"])
            published_dt = _parse_date(published_raw)
            summary = _entry_text(entry, ["summary", "content"]) or _media_group_text(entry)
            raw_link = _entry_link(entry)
            video_id = _extract_youtube_video_id(raw_link, entry)
            links = _build_youtube_links(raw_link, video_id)
            items.append(
                {
                    "title": _entry_text(entry, ["title"]) or "Utan titel",
                    "channel": feed_title,
                    "published": published_dt,
                    "published_iso": published_dt.isoformat(),
                    "link": links["primary"],
                    "secondary_link": links["secondary"],
                    "video_id": video_id,
                    "summary": _make_video_summary(
                        title=_entry_text(entry, ["title"]) or "",
                        channel=feed_title,
                        source_text=summary or "",
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
                raw_link = (entry.findtext("link") or "#").strip()
                video_id = _extract_youtube_video_id(raw_link, None)
                links = _build_youtube_links(raw_link, video_id)
                items.append(
                    {
                        "title": (entry.findtext("title") or "Utan titel").strip(),
                        "channel": channel_name,
                        "published": published_dt,
                        "published_iso": published_dt.isoformat(),
                        "link": links["primary"],
                        "secondary_link": links["secondary"],
                        "video_id": video_id,
                        "summary": _make_video_summary(
                            title=(entry.findtext("title") or ""),
                            channel=channel_name,
                            source_text=summary,
                        ),
                    }
                )
    return items


def collect_latest_youtube_videos(
    feeds: list[dict[str, str]],
    max_items: int = 24,
    debug: bool = False,
    debug_dir: Path | None = None,
) -> list[dict[str, Any]]:
    opener = build_opener(ProxyHandler({}))
    videos: list[dict[str, Any]] = []

    tested = 0
    for idx, feed in enumerate(feeds):
        tested += 1
        request = Request(
            feed["xml_url"],
            headers={
                "User-Agent": "DailyBriefingBot/1.1 (+https://github.com/actions)",
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
            },
        )
        if debug:
            print(f"[YouTube][DEBUG] testar URL: {feed['xml_url']}")
        try:
            with opener.open(request, timeout=15) as response:
                status = getattr(response, "status", 200)
                content_type = response.headers.get("Content-Type", "okänd")
                raw = response.read()
            xml_text = raw.decode("utf-8", errors="replace")
            if debug:
                print(
                    f"[YouTube][DEBUG] status={status} content-type={content_type} bytes={len(raw)}"
                )
            feed_items = _parse_feed_xml(xml_text, feed["title"])
            if debug:
                titles = [item["title"] for item in feed_items[:2]]
                print(f"[YouTube][DEBUG] parsade poster={len(feed_items)} första titlar={titles}")
            if debug and debug_dir and idx < 3:
                (debug_dir / f"youtube_feed_sample_{idx + 1}.xml").write_text(xml_text, encoding="utf-8")
            videos.extend(feed_items[:4])
        except (URLError, TimeoutError, ET.ParseError) as exc:
            print(f"[YouTube] VARNING: kunde inte läsa {feed['xml_url']}: {exc}")
            continue

    before_sort = len(videos)
    videos.sort(key=lambda x: x["published"], reverse=True)
    videos = videos[:max_items]
    print(f"[YouTube] Totalt antal poster före sortering: {before_sort}")
    print(f"[YouTube] Totalt antal poster efter sortering/gräns: {len(videos)}")
    print(f"[YouTube] Totalt testade feeds: {tested}")

    if debug and debug_dir:
        sample_file = debug_dir / "youtube_feed_sample.xml"
        sample_written = False
        for i in range(1, 4):
            path = debug_dir / f"youtube_feed_sample_{i}.xml"
            if path.exists():
                sample_file.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
                sample_written = True
                break
        if not sample_written:
            sample_file.write_text("<!-- No YouTube feed could be downloaded in this run -->", encoding="utf-8")
        (debug_dir / "parsed_youtube.json").write_text(
            json.dumps(videos, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )

    print(f"[YouTube] OK: hämtade totalt {len(videos)} videoposter.")
    return videos
