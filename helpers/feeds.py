"""OPML and YouTube feed helpers."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener
from zoneinfo import ZoneInfo

CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
TAG_RE = re.compile(r"<[^>]+>")
URL_RE = re.compile(r"https?://\S+")
SPACE_RE = re.compile(r"\s+")
SENTENCE_TRIM_RE = re.compile(r"\s*[•|]\s*")
EMOJI_RE = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)
PROMO_RE = re.compile(r"\b(subscribe|follow|patreon|sponsor|sponsored|instagram|twitter|tiktok|merch|affiliate|rabattkod|annons|partnerlänk)\b", re.IGNORECASE)
XMLURL_RE = re.compile(r'xmlUrl="([^"]+)"')
YOUTUBE_ID_RE = re.compile(r"(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})")
SHORT_HINT_RE = re.compile(r"\b(shorts?|#shorts|vertical|reel)\b", re.IGNORECASE)
SHORT_METADATA_RE = re.compile(r"(yt:short|shorts|reel|portrait|9:16)", re.IGNORECASE)
SWEDISH_SUMMARY_HINT_RE = re.compile(
    r"\b(videon|klippet|kanalen|reportaget|genomgång|förklarar|visar|diskuterar)\b",
    re.IGNORECASE,
)


def parse_opml_feed_urls(opml_path: str, debug: bool = False) -> list[dict[str, str]]:
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
    text = re.sub(r"#[\w_]+", "", text)
    text = SENTENCE_TRIM_RE.sub(" ", text)
    text = EMOJI_RE.sub("", text)
    text = re.sub(r"[\*_~=]{2,}", " ", text)
    text = SPACE_RE.sub(" ", text)
    return text.strip(" -|•")


def _split_sentences(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?])\s+", text)
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _dedupe_sentences(sentences: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for sentence in sentences:
        key = sentence.lower().strip(" .!?")
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(sentence)
    return deduped


def _is_useful_sentence(sentence: str) -> bool:
    words = sentence.split()
    if len(words) < 6:
        return False
    if PROMO_RE.search(sentence):
        return False
    lowered = sentence.lower()
    if "http" in lowered or "www." in lowered:
        return False
    return True


def _to_swedish_sentence(sentence: str) -> str:
    cleaned = _clean_text(sentence).rstrip(" .!?")
    if not cleaned:
        return ""

    # Om feed-texten redan innehåller svenska signalord behåll den i stort.
    if SWEDISH_SUMMARY_HINT_RE.search(cleaned):
        return cleaned + "."

    replacements = {
        "video": "videon",
        "episode": "avsnittet",
        "explains": "förklarar",
        "shows": "visar",
        "discusses": "diskuterar",
        "review": "genomgång",
    }
    words = cleaned.split()
    translated_words = [replacements.get(word.lower(), word) for word in words]
    return " ".join(translated_words).rstrip(" .!?") + "."


def _make_video_summary(title: str, source_texts: list[str]) -> str:
    clean_title = _clean_text(title) or "videon"
    text_pool = " ".join(_clean_text(v) for v in source_texts if v)[:2600]

    if not text_pool:
        return f"Videon tar upp {clean_title.lower()} och sätter ämnet i sitt sammanhang. Beskrivningen i feeden är begränsad, men fokus verkar ligga på huvudpoängen."

    candidates = []
    for sentence in _dedupe_sentences(_split_sentences(text_pool)):
        cleaned = _clean_text(sentence)
        if _is_useful_sentence(cleaned):
            candidates.append(cleaned.rstrip(" .!?") + ".")

    if len(candidates) >= 2:
        first = _to_swedish_sentence(candidates[0][:220])
        second = _to_swedish_sentence(candidates[1][:220])
        return f"{first} {second}"
    if len(candidates) == 1:
        return f"{candidates[0]} Videon kompletterar med konkreta detaljer och exempel kring ämnet."
    return f"Videon tar upp {clean_title.lower()} med fokus på centrala delar i innehållet. Feeden innehåller få detaljer, men tonen pekar på en tydlig genomgång."


def _tag_name(elem: ET.Element) -> str:
    return elem.tag.split("}")[-1]


def _entry_text(entry: ET.Element, names: list[str]) -> str | None:
    for child in entry:
        if _tag_name(child) in names:
            text_value = " ".join(part.strip() for part in child.itertext() if part and part.strip())
            if text_value:
                return text_value
    return None


def _entry_text_candidates(entry: ET.Element) -> str:
    candidate_names = {"summary", "content", "description", "subtitle", "transcript", "text"}
    chunks: list[str] = []
    for elem in entry.iter():
        if _tag_name(elem) in candidate_names:
            text_value = " ".join(part.strip() for part in elem.itertext() if part and part.strip())
            if text_value:
                chunks.append(text_value)
    return " ".join(chunks).strip()


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
    collected: list[str] = []
    for child in entry:
        if _tag_name(child) == "group":
            for nested in child:
                if _tag_name(nested) in {"description", "title", "content", "transcript", "credit", "text"}:
                    text_value = " ".join(part.strip() for part in nested.itertext() if part and part.strip())
                    if text_value:
                        collected.append(text_value)
    return " ".join(collected).strip()


def _media_thumbnail(entry: ET.Element) -> str | None:
    for elem in entry.iter():
        if _tag_name(elem) == "thumbnail":
            url = elem.attrib.get("url")
            if url:
                return url.strip()
    return None


def _extract_duration_seconds(entry: ET.Element) -> int | None:
    for elem in entry.iter():
        tag = _tag_name(elem)
        if tag == "duration":
            direct = elem.attrib.get("seconds") or elem.attrib.get("value") or (elem.text or "").strip()
            if direct and direct.isdigit():
                return int(direct)
        if tag == "content":
            duration = elem.attrib.get("duration")
            if duration and duration.isdigit():
                return int(duration)
    return None


def _is_short_candidate(item: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Shorts-filter med både starka och svagare signaler.
    Vi filtrerar direkt vid tydliga träffar (URL /shorts/), annars krävs minst två
    svagare signaler för att minska risken att kasta bort vanliga videos.
    """
    links = " ".join([item.get("link") or "", item.get("secondary_link") or ""]).lower()
    signals: list[str] = []
    if "/shorts/" in links:
        signals.append("url_contains_/shorts/")
        return True, signals

    weak_signals = 0
    duration = item.get("duration_seconds")
    if duration is not None and duration <= 60:
        weak_signals += 1
        signals.append("duration_<=_60s")

    meta_blob = " ".join([
        item.get("title") or "",
        item.get("summary_source") or "",
        item.get("feed_metadata_blob") or "",
    ])
    if SHORT_HINT_RE.search(meta_blob):
        weak_signals += 1
        signals.append("title_or_text_short_hint")
    if SHORT_METADATA_RE.search(meta_blob):
        weak_signals += 1
        signals.append("feed_metadata_short_hint")

    return weak_signals >= 2, signals


def _parse_feed_xml(xml_text: str, fallback_channel: str) -> list[dict[str, Any]]:
    root = ET.fromstring(CONTROL_CHARS_RE.sub("", xml_text))
    root_name = _tag_name(root)
    items: list[dict[str, Any]] = []

    if root_name == "feed":
        feed_title = _entry_text(root, ["title"]) or fallback_channel
        for entry in root.findall("{*}entry"):
            published_raw = _entry_text(entry, ["published", "updated"])
            published_dt = _parse_date(published_raw)
            summary_sources = [
                _entry_text(entry, ["description"]) or "",
                _entry_text(entry, ["summary"]) or "",
                _entry_text(entry, ["content"]) or "",
                _media_group_text(entry),
                _entry_text_candidates(entry),
            ]
            summary_source_text = " ".join(summary_sources)
            raw_link = _entry_link(entry)
            video_id = _extract_youtube_video_id(raw_link, entry)
            links = _build_youtube_links(raw_link, video_id)
            title = _entry_text(entry, ["title"]) or "Utan titel"
            metadata_blob = " ".join(
                f"{elem.tag} {' '.join(f'{k}:{v}' for k, v in elem.attrib.items())}"
                for elem in entry.iter()
            )
            items.append(
                {
                    "title": title,
                    "channel": feed_title,
                    "published": published_dt,
                    "published_iso": published_dt.isoformat(),
                    "link": links["primary"],
                    "secondary_link": links["secondary"],
                    "video_id": video_id,
                    "thumbnail": _media_thumbnail(entry),
                    "duration_seconds": _extract_duration_seconds(entry),
                    "feed_metadata_blob": metadata_blob,
                    "summary_source": summary_source_text,
                    "summary": _make_video_summary(title=title, source_texts=summary_sources),
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
                media_group_parts: list[str] = []
                thumbnail = None
                for child in list(entry):
                    tag = _tag_name(child)
                    if tag == "thumbnail" and child.attrib.get("url"):
                        thumbnail = child.attrib.get("url", "").strip()
                    if tag == "group":
                        for nested in list(child):
                            ntag = _tag_name(nested)
                            if ntag == "thumbnail" and nested.attrib.get("url") and not thumbnail:
                                thumbnail = nested.attrib.get("url", "").strip()
                            if ntag in {"description", "content", "title", "text"}:
                                media_group_parts.append(" ".join(part.strip() for part in nested.itertext() if part and part.strip()))

                summary_sources = [
                    entry.findtext("description") or "",
                    entry.findtext("summary") or "",
                    entry.findtext("content") or "",
                    " ".join(media_group_parts),
                ]
                raw_link = (entry.findtext("link") or "#").strip()
                video_id = _extract_youtube_video_id(raw_link, None)
                links = _build_youtube_links(raw_link, video_id)
                title = (entry.findtext("title") or "Utan titel").strip()
                metadata_blob = " ".join(
                    f"{elem.tag} {' '.join(f'{k}:{v}' for k, v in elem.attrib.items())}"
                    for elem in entry.iter()
                )
                items.append(
                    {
                        "title": title,
                        "channel": channel_name,
                        "published": published_dt,
                        "published_iso": published_dt.isoformat(),
                        "link": links["primary"],
                        "secondary_link": links["secondary"],
                        "video_id": video_id,
                        "thumbnail": thumbnail,
                        "duration_seconds": _extract_duration_seconds(entry),
                        "feed_metadata_blob": metadata_blob,
                        "summary_source": " ".join(summary_sources),
                        "summary": _make_video_summary(title=title, source_texts=summary_sources),
                    }
                )
    return items


def _normalize_video(item: dict[str, Any]) -> dict[str, Any]:
    published = item.get("published")
    published_utc = published.astimezone(timezone.utc) if isinstance(published, datetime) else datetime.min.replace(tzinfo=timezone.utc)
    published_stockholm = published_utc.astimezone(ZoneInfo("Europe/Stockholm"))
    short_match, short_signals = _is_short_candidate(item)

    return {
        "video_id": item.get("video_id"),
        "title": item.get("title") or "Utan titel",
        "channel": item.get("channel") or "Okänd kanal",
        "published_at_utc": published_utc.isoformat(),
        "published_at_stockholm": published_stockholm.isoformat(),
        "thumbnail": item.get("thumbnail") or (
            f"https://i.ytimg.com/vi/{item.get('video_id')}/hqdefault.jpg" if item.get("video_id") else None
        ),
        "summary_source_text": item.get("summary_source") or "",
        "summary": item.get("summary") or "",
        "url": item.get("link") or "#",
        "duration": item.get("duration_seconds"),
        "short_signals": short_signals,
        "is_probable_short": short_match,
    }


def collect_latest_youtube_videos(
    feeds: list[dict[str, str]],
    max_items: int = 24,
    per_feed_items: int = 5,
    lookback_hours: int = 72,
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
        try:
            with opener.open(request, timeout=15) as response:
                raw = response.read()
            xml_text = raw.decode("utf-8", errors="replace")
            feed_items = _parse_feed_xml(xml_text, feed["title"])
            if debug and debug_dir and idx < 3:
                (debug_dir / f"youtube_feed_sample_{idx + 1}.xml").write_text(xml_text, encoding="utf-8")
            videos.extend(feed_items[: max(3, per_feed_items)])
        except (URLError, TimeoutError, ET.ParseError) as exc:
            print(f"[YouTube] VARNING: kunde inte läsa {feed['xml_url']}: {exc}")
            continue

    before_filters = len(videos)
    now_utc = datetime.now(timezone.utc)
    lower_bound = now_utc - timedelta(hours=lookback_hours)
    lookback_videos = [
        item for item in videos
        if isinstance(item.get("published"), datetime) and lower_bound <= item["published"].astimezone(timezone.utc) <= now_utc
    ]
    normalized = [_normalize_video(item) for item in lookback_videos]
    non_short_videos = [item for item in normalized if not item["is_probable_short"]]

    non_short_videos.sort(key=lambda x: x["published_at_utc"], reverse=True)
    filtered = non_short_videos[:max_items]

    print(f"[YouTube] Totalt antal poster före filtrering: {before_filters}")
    print(f"[YouTube] Inom lookback {lookback_hours}h: {len(lookback_videos)}")
    print(f"[YouTube] Efter Shorts-filter: {len(non_short_videos)}")
    print(f"[YouTube] Efter sortering/gräns: {len(filtered)}")
    print(f"[YouTube] Totalt testade feeds: {tested}")

    if debug and debug_dir:
        (debug_dir / "parsed_youtube.json").write_text(
            json.dumps(filtered, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )

    print(f"[YouTube] OK: hämtade totalt {len(filtered)} videoposter.")
    return filtered
