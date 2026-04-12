"""News feed collection helpers based on user interests."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import quote_plus
from urllib.request import ProxyHandler, Request, build_opener


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INTERESTS_PATH = ROOT / "config" / "interests.json"

CATEGORY_LABELS = {
    "hockey": "Hockey",
    "football": "Fotboll",
    "golf": "Golf",
    "tech_ai": "AI / Teknik",
}

DEFAULT_INTERESTS: dict[str, dict[str, list[str]]] = {
    "primary_topics": {
        "hockey": [
            "Frölunda",
            "NHL",
            "New York Rangers",
            "NY Rangers",
            "Carolina Hurricanes",
            "Dallas Stars",
            "Florida Panthers",
        ],
        "football": ["ÖIS", "Örgryte IS"],
        "golf": ["golf", "PGA", "DP World Tour", "majors"],
    },
    "secondary_topics": {
        "tech_ai": ["AI", "artificiell intelligens", "teknik"],
    },
}

CATEGORY_BASE_FEEDS: dict[str, list[tuple[str, str]]] = {
    "hockey": [
        ("SVT Sport", "https://www.svt.se/sport/rss.xml"),
        ("Sveriges Radio Sport", "https://api.sr.se/api/rss/program/179"),
        ("NHL.com", "https://www.nhl.com/news/rss"),
    ],
    "football": [
        ("SVT Sport", "https://www.svt.se/sport/rss.xml"),
        ("Fotbollskanalen", "https://www.fotbollskanalen.se/rss/"),
        ("Svensk Fotboll", "https://www.svenskfotboll.se/rss/nyheter/"),
    ],
    "golf": [
        ("Svensk Golf", "https://www.svenskgolf.se/feed/"),
        ("PGA Tour", "https://www.pgatour.com/feed"),
        ("Golf Digest", "https://www.golfdigest.com/feed/rss"),
    ],
    "tech_ai": [
        ("TechCrunch", "https://techcrunch.com/feed/"),
        ("The Verge", "https://www.theverge.com/rss/index.xml"),
        ("OpenAI News", "https://openai.com/news/rss.xml"),
    ],
}

GOOGLE_NEWS_LANG = "hl=sv&gl=SE&ceid=SE:sv"


def _load_interests(path: Path | None) -> dict[str, dict[str, list[str]]]:
    config_path = path or DEFAULT_INTERESTS_PATH
    if config_path.exists():
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError as exc:
            print(f"[Nyheter] VARNING: kunde inte tolka intressefil {config_path}: {exc}")
    return DEFAULT_INTERESTS


def _parse_opml_interest_hints(opml_path: Path | None) -> list[str]:
    if not opml_path or not opml_path.exists():
        return []

    terms: list[str] = []
    try:
        root = ET.fromstring(opml_path.read_text(encoding="utf-8", errors="replace"))
        for outline in root.findall(".//outline"):
            title = (outline.attrib.get("text") or outline.attrib.get("title") or "").strip()
            title_lower = title.lower()
            if any(token in title_lower for token in ("golf", "nhl", "hockey", "football", "soccer", "ai", "tech")):
                terms.append(title)
    except ET.ParseError:
        return []
    return terms[:10]


def _build_google_news_url(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote_plus(query)}&{GOOGLE_NEWS_LANG}"


def _category_sources(interests: dict[str, dict[str, list[str]]]) -> dict[str, list[tuple[str, str]]]:
    result: dict[str, list[tuple[str, str]]] = {}
    for category in ["hockey", "football", "golf", "tech_ai"]:
        keywords = interests.get("primary_topics", {}).get(category, [])
        if category == "tech_ai":
            keywords = interests.get("secondary_topics", {}).get("tech_ai", [])

        sources = list(CATEGORY_BASE_FEEDS.get(category, []))
        for keyword in keywords[:5]:
            sources.append((f"Google News: {keyword}", _build_google_news_url(keyword)))
        result[category] = sources
    return result


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


def _tag_name(tag: str) -> str:
    return tag.split("}")[-1]


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_summary_from_item(item: ET.Element) -> str:
    for tag in ("description", "summary", "encoded", "content"):
        for child in item.iter():
            name = _tag_name(child.tag).lower()
            if name.endswith(tag) and child.text:
                clean = _clean_text(child.text)
                if clean:
                    return clean[:420]
    return ""


def _extract_items(xml_text: str, source: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    root_name = _tag_name(root.tag)
    items: list[dict[str, Any]] = []

    if root_name == "feed":
        for entry in root.findall("{*}entry"):
            title = (entry.findtext("{*}title") or "Utan rubrik").strip()
            link = "#"
            for link_el in entry.findall("{*}link"):
                href = link_el.attrib.get("href")
                if href:
                    link = href
                    break
            pub_raw = entry.findtext("{*}published") or entry.findtext("{*}updated")
            pub_dt = _parse_date(pub_raw)
            summary = _clean_text(entry.findtext("{*}summary") or entry.findtext("{*}content"))[:420]
            items.append(
                {
                    "title": title,
                    "source": source,
                    "published": pub_dt,
                    "published_iso": pub_dt.isoformat(),
                    "link": link,
                    "summary": summary,
                }
            )
    else:
        channel = root.find(".//channel")
        if channel is None:
            return items
        for item in channel.findall("item"):
            title = (item.findtext("title") or "Utan rubrik").strip()
            link = (item.findtext("link") or "#").strip()
            pub_dt = _parse_date(item.findtext("pubDate"))
            summary = _extract_summary_from_item(item)
            items.append(
                {
                    "title": title,
                    "source": source,
                    "published": pub_dt,
                    "published_iso": pub_dt.isoformat(),
                    "link": link,
                    "summary": summary,
                }
            )
    return items


def _matches_interest(item: dict[str, Any], keywords: list[str]) -> bool:
    if not keywords:
        return True
    haystack = f"{item.get('title', '')} {item.get('summary', '')}".lower()
    return any(keyword.lower() in haystack for keyword in keywords)


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        key = item.get("link") or item.get("title", "")
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def fetch_news(
    max_per_category: int = 8,
    debug: bool = False,
    debug_dir: Path | None = None,
    interests_path: Path | None = None,
    opml_path: Path | None = None,
) -> dict[str, list[dict[str, Any]]]:
    opener = build_opener(ProxyHandler({}))
    interests = _load_interests(interests_path)
    opml_hints = _parse_opml_interest_hints(opml_path)
    if debug and opml_hints:
        print(f"[Nyheter][DEBUG] OPML-hints: {opml_hints}")

    category_sources = _category_sources(interests)
    result: dict[str, list[dict[str, Any]]] = {}

    for category_key in ["hockey", "football", "golf", "tech_ai"]:
        display_name = CATEGORY_LABELS[category_key]
        sources = category_sources.get(category_key, [])

        category_keywords = interests.get("primary_topics", {}).get(category_key, [])
        if category_key == "tech_ai":
            category_keywords = interests.get("secondary_topics", {}).get("tech_ai", [])
        if category_key in {"golf", "tech_ai"}:
            category_keywords = [*category_keywords, *opml_hints]

        print(f"[Nyheter/{display_name}] Källor: {[url for _, url in sources]}")
        collected: list[dict[str, Any]] = []

        for source_name, url in sources:
            request = Request(
                url,
                headers={
                    "User-Agent": "DailyBriefingBot/1.2 (+https://github.com/actions)",
                    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
                },
            )
            try:
                with opener.open(request, timeout=15) as response:
                    raw = response.read()
                xml_text = raw.decode("utf-8", errors="replace")
                source_items = _extract_items(xml_text, source_name)
                if category_keywords:
                    source_items = [item for item in source_items if _matches_interest(item, category_keywords)]
                collected.extend(source_items)
            except (URLError, TimeoutError, ET.ParseError) as exc:
                print(f"[Nyheter/{display_name}] VARNING: kunde inte läsa {source_name}: {exc}")
                continue

        collected = _dedupe(collected)
        collected.sort(key=lambda x: x["published"], reverse=True)
        result[display_name] = collected[:max_per_category]
        print(f"[Nyheter/{display_name}] OK: {len(result[display_name])} poster efter sortering.")

    if debug and debug_dir:
        (debug_dir / "parsed_news.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )

    return result
