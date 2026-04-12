"""HTML rendering utilities."""

from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo


def _format_sv_datetime(iso_value: str | None) -> str:
    if not iso_value:
        return "Okänt datum"
    dt = datetime.fromisoformat(iso_value)
    dt_se = dt.astimezone(ZoneInfo("Europe/Stockholm"))
    return dt_se.strftime("%Y-%m-%d %H:%M")


def _render_weather(weather: dict) -> str:
    if weather.get("error"):
        return f"<p class='muted'>{escape(weather['error'])}</p>"

    return f"""
    <div class="weather-grid">
      <div class="metric"><span>Plats</span><strong>{escape(weather['location'])}</strong></div>
      <div class="metric"><span>Temperatur</span><strong>{weather.get('temperature_c', '–')} °C</strong></div>
      <div class="metric"><span>Väder</span><strong>{escape(weather.get('description', 'Okänt'))}</strong></div>
      <div class="metric"><span>Vind</span><strong>{weather.get('wind_ms', '–')} m/s</strong></div>
      <div class="metric"><span>Nederbörd</span><strong>{weather.get('precip_mm_h', '–')} mm/h</strong></div>
      <div class="metric"><span>Prognostid (UTC)</span><strong>{escape(weather.get('forecast_time_utc', '–'))}</strong></div>
    </div>
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
        rows.append(
            "<li><a href='{link}' target='_blank' rel='noopener noreferrer'>{title}</a>"
            "<div class='meta'>{subtitle}</div>{summary}</li>".format(
                link=escape(item.get("link", "#")),
                title=escape(item.get("title", "Utan titel")),
                subtitle=subtitle,
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
    <section class="card">
      <h2>Väder idag</h2>
      {_render_weather(weather)}
    </section>

    <section class="card">
      <h2>Nya YouTube-videos</h2>
      {_render_list(videos, 'video')}
    </section>

    <section class="card">
      <h2>Dagens nyheter</h2>
      {''.join(news_sections)}
    </section>
  </main>
</body>
</html>
"""
