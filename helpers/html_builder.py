"""HTML rendering utilities."""

from __future__ import annotations

import json
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo


def _format_sv_datetime(iso_value: str | None) -> str:
    if not iso_value:
        return "Okänt datum"
    dt = datetime.fromisoformat(iso_value)
    dt_se = dt.astimezone(ZoneInfo("Europe/Stockholm"))
    return dt_se.strftime("%Y-%m-%d %H:%M")


def _safe_num(value: float | int | None) -> str:
    if value is None:
        return "-"
    return f"{value:.1f}" if isinstance(value, float) else str(value)


def _render_weather(weather: dict) -> str:
    error = weather.get("error")
    location = weather.get("location") or "Göteborg"
    temperature_c = _safe_num(weather.get("temperature_c") or weather.get("temperature"))
    description = weather.get("description") or "Ingen väderbeskrivning"
    wind_ms = _safe_num(weather.get("wind_ms") or weather.get("wind"))
    precip_mm_h = _safe_num(weather.get("precip_mm_h") or weather.get("precipitation"))
    forecast_time_utc = weather.get("forecast_time_utc") or "-"

    if error:
        fallback = f"<p class='weather-fallback'>{escape(str(error))}. Visar fallback för Göteborg.</p>"
    else:
        fallback = ""

    weather_json = json.dumps(
        {
            "location": location,
            "temperature_c": weather.get("temperature_c"),
            "description": description,
            "wind_ms": weather.get("wind_ms"),
            "precip_mm_h": weather.get("precip_mm_h"),
            "forecast_time_utc": forecast_time_utc,
            "error": error,
        },
        ensure_ascii=False,
    )

    return f"""
    <section id="weather-app" class="weather-app" aria-live="polite">
      {fallback}
      <div class="weather-now-card">
        <div class="weather-now-top">
          <div>
            <p class="weather-label">Plats</p>
            <h3 id="weather-location">{escape(str(location))}</h3>
          </div>
          <div class="weather-icon" id="weather-icon" aria-hidden="true">⛅</div>
        </div>
        <div class="weather-temp" id="weather-temp">{temperature_c}°C</div>
        <p class="weather-desc" id="weather-desc">{escape(str(description))}</p>
        <div class="weather-grid">
          <div class="metric"><span>Vind</span><strong id="weather-wind">{wind_ms} m/s</strong></div>
          <div class="metric"><span>Nederbörd</span><strong id="weather-precip">{precip_mm_h} mm/h</strong></div>
          <div class="metric"><span>Prognostid</span><strong id="weather-updated">{escape(str(forecast_time_utc))}</strong></div>
        </div>
      </div>

      <h3 class="subheading">Närmaste 24 timmar</h3>
      <div class="hourly-scroll" id="weather-hourly">
        <p class="muted">Laddar timprognos...</p>
      </div>

      <h3 class="subheading">7-dagarsöversikt</h3>
      <div class="daily-grid" id="weather-daily">
        <p class="muted">Laddar dygnsprognos...</p>
      </div>
    </section>
    <script id="weather-fallback-data" type="application/json">{escape(weather_json)}</script>
    """


def _render_list(items: list[dict], item_type: str) -> str:
    if not items:
        return "<p class='muted'>Inga poster hittades just nu.</p>"

    rows = []
    for item in items:
        when = _format_sv_datetime(item.get("published_iso"))
        subtitle = (
            f"{escape(item['channel'])} • {when}"
            if item_type == "video"
            else f"{escape(item['source'])} • {when}"
        )
        if item_type == "video":
            cta = (
                "<div class='video-links'>"
                f"<a class='yt-open' href='{escape(item.get('link', '#'))}' target='_blank' rel='noopener noreferrer'>Öppna i YouTube</a>"
                + (
                    f"<a class='yt-alt' href='{escape(item.get('secondary_link', '#'))}' target='_blank' rel='noopener noreferrer'>Kortlänk</a>"
                    if item.get("secondary_link")
                    else ""
                )
                + "</div>"
            )
        else:
            cta = ""

        rows.append(
            "<li><a href='{link}' target='_blank' rel='noopener noreferrer'>{title}</a>"
            "<div class='meta'>{subtitle}</div>{cta}{summary}</li>".format(
                link=escape(item.get("link", "#")),
                title=escape(item.get("title", "Utan titel")),
                subtitle=subtitle,
                cta=cta,
                summary=(
                    f"<p class='summary'>{escape(item.get('summary', ''))}</p>"
                    if item_type == "video" and item.get("summary")
                    else ""
                ),
            )
        )

    return "<ul class='item-list'>" + "".join(rows) + "</ul>"


def build_html(
    *,
    generated_at_iso: str,
    weather: dict,
    videos: list[dict],
    news_by_category: dict[str, list[dict]],
) -> str:
    generated_local = _format_sv_datetime(generated_at_iso)
    today_local = datetime.now(ZoneInfo("Europe/Stockholm")).strftime("%A %d %B %Y")

    news_sections = []
    for category, items in news_by_category.items():
        news_sections.append(
            f"<section><h3>{escape(category)}</h3>{_render_list(items, 'news')}</section>"
        )

    return f"""<!doctype html>
<html lang="sv">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Daglig briefing</title>
  <link rel="stylesheet" href="style.css" />
</head>
<body>
  <header class="topbar">
    <div>
      <h1>Daglig briefing</h1>
      <p>{escape(today_local)}</p>
    </div>
    <div class="updated">Senast uppdaterad: {escape(generated_local)} (Europe/Stockholm)</div>
  </header>

  <main class="container">
    <section class="card weather-card">
      <h2>Väder idag</h2>
      {_render_weather(weather)}
    </section>

    <section class="card youtube-card">
      <h2>Nya YouTube-videos</h2>
      {_render_list(videos, 'video')}
    </section>

    <section class="card">
      <h2>Dagens nyheter</h2>
      {''.join(news_sections)}
    </section>
  </main>
  <script src="weather.js" defer></script>
</body>
</html>
"""
