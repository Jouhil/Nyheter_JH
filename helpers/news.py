"""News feed collection helpers."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener

NEWS_FEEDS: dict[str, list[tuple[str, str]]] = {
    "AI": [
        ("MIT AI News", "https://news.mit.edu/rss/topic/artificial-intelligence2"),
        ("Hugging Face Blog", "https://huggingface.co/blog/feed.xml"),
        ("OpenAI News", "https://openai.com/news/rss.xml"),
    ],
    "Teknik": [
        ("The Verge", "https://www.theverge.com/rss/index.xml"),
        ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
        ("TechCrunch", "https://techcrunch.com/feed/"),
    ],
    "Sverige": [
        ("SVT Nyheter", "https://www.svt.se/nyheter/rss.xml"),
        ("Sveriges Radio Ekot", "https://api.sr.se/api/rss/program/83"),
        ("Omni", "https://rss.omni.se/"),
    ],
}


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


def _extract_items(xml_text: str, source: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    root_name = _tag_name(root.tag)
    items: list[dict[str, Any]] = []

    if root_name == "feed":
        for entry in root.findall("{*}entry"):
            title = entry.findtext("{*}title") or "Utan rubrik"
            link = "#"
            for link_el in entry.findall("{*}link"):
                href = link_el.attrib.get("href")
                if href:
                    link = href
                    break
            pub_raw = entry.findtext("{*}published") or entry.findtext("{*}updated")
            pub_dt = _parse_date(pub_raw)
            items.append({
                "title": title.strip(),
                "source": source,
                "published": pub_dt,
                "published_iso": pub_dt.isoformat(),
                "link": link,
            })
    else:
        channel = root.find(".//channel")
        if channel is None:
            return items
        for item in channel.findall("item"):
            title = (item.findtext("title") or "Utan rubrik").strip()
            link = (item.findtext("link") or "#").strip()
            pub_dt = _parse_date(item.findtext("pubDate"))
            items.append({
                "title": title,
                "source": source,
                "published": pub_dt,
                "published_iso": pub_dt.isoformat(),
                "link": link,
            })
    return items


def fetch_news(
    max_per_category: int = 8,
    debug: bool = False,
    debug_dir: Path | None = None,
) -> dict[str, list[dict[str, Any]]]:
    opener = build_opener(ProxyHandler({}))
    result: dict[str, list[dict[str, Any]]] = {}
    all_items: dict[str, list[dict[str, Any]]] = {}

    for category, sources in NEWS_FEEDS.items():
        print(f"[Nyheter/{category}] Källor: {[url for _, url in sources]}")
        collected: list[dict[str, Any]] = []

        for idx, (source_name, url) in enumerate(sources):
            request = Request(
                url,
                headers={
                    "User-Agent": "DailyBriefingBot/1.1 (+https://github.com/actions)",
                    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
                },
            )
            try:
                with opener.open(request, timeout=15) as response:
                    status = getattr(response, "status", 200)
                    content_type = response.headers.get("Content-Type", "okänd")
                    raw = response.read()
                xml_text = raw.decode("utf-8", errors="replace")
                source_items = _extract_items(xml_text, source_name)

                if debug:
                    first_title = source_items[0]["title"] if source_items else "-"
                    print(
                        f"[Nyheter/{category}][DEBUG] {source_name}: status={status} "
                        f"content-type={content_type} bytes={len(raw)} parsed={len(source_items)} "
                        f"första='{first_title}'"
                    )
                if debug and debug_dir and idx == 0:
                    file_name = f"news_{category.lower()}_sample.xml"
                    (debug_dir / file_name).write_text(xml_text, encoding="utf-8")

                if not source_items:
                    print(f"[Nyheter/{category}] VARNING: 0 poster från {source_name} ({url})")
                collected.extend(source_items)
            except (URLError, TimeoutError, ET.ParseError) as exc:
                print(f"[Nyheter/{category}] VARNING: kunde inte läsa {source_name}: {exc}")
                continue

        print(f"[Nyheter/{category}] Totalt före sortering: {len(collected)}")
        collected.sort(key=lambda x: x["published"], reverse=True)
        result[category] = collected[:max_per_category]
        all_items[category] = result[category]
        print(f"[Nyheter/{category}] OK: {len(result[category])} poster efter sortering.")

    if debug and debug_dir:
        ai_sample = debug_dir / "news_ai_sample.xml"
        if not ai_sample.exists():
            ai_sample.write_text("<!-- No AI news feed could be downloaded in this run -->", encoding="utf-8")
        (debug_dir / "parsed_news.json").write_text(
            json.dumps(all_items, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )

    return result
