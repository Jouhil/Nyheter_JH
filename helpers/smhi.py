"""Weather utilities backed by Open-Meteo."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

WEATHER_CODES = {
    0: "Klart",
    1: "Mest klart",
    2: "Delvis molnigt",
    3: "Mulet",
    45: "Dimma",
    48: "Dimma",
    51: "Lätt duggregn",
    53: "Duggregn",
    55: "Tätt duggregn",
    61: "Lätt regn",
    63: "Regn",
    65: "Kraftigt regn",
    71: "Lätt snö",
    73: "Snö",
    75: "Kraftig snö",
    80: "Regnskurar",
    81: "Kraftiga regnskurar",
    82: "Mycket kraftiga regnskurar",
    95: "Åska",
    96: "Åska med hagel",
    99: "Åska med hagel",
}


def _fmt(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _safe_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    return value if isinstance(value, list) else []


def _build_open_meteo_url(lat: float, lon: float) -> str:
    params = {
        "latitude": _fmt(lat),
        "longitude": _fmt(lon),
        "current": "temperature_2m,apparent_temperature,wind_speed_10m,precipitation,weather_code",
        "hourly": "temperature_2m,wind_speed_10m,precipitation,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,weather_code,precipitation_sum",
        "forecast_days": 10,
        "timezone": "UTC",
    }
    return f"{OPEN_METEO_URL}?{urlencode(params)}"


def _build_hourly(hourly: dict[str, Any], hours: int = 24) -> list[dict[str, Any]]:
    times = _safe_list(hourly, "time")[:hours]
    temps = _safe_list(hourly, "temperature_2m")[:hours]
    winds = _safe_list(hourly, "wind_speed_10m")[:hours]
    precip = _safe_list(hourly, "precipitation")[:hours]
    code = _safe_list(hourly, "weather_code")[:hours]

    rows: list[dict[str, Any]] = []
    for idx, valid_time in enumerate(times):
        weather_code = int(code[idx]) if idx < len(code) and code[idx] is not None else 0
        rows.append(
            {
                "time": valid_time,
                "temperature": temps[idx] if idx < len(temps) else None,
                "weather_code": weather_code,
                "precipitation": precip[idx] if idx < len(precip) else None,
                "wind_speed": winds[idx] if idx < len(winds) else None,
            }
        )
    return rows


def _build_daily(daily: dict[str, Any], days: int = 10) -> list[dict[str, Any]]:
    dates = _safe_list(daily, "time")[:days]
    max_t = _safe_list(daily, "temperature_2m_max")[:days]
    min_t = _safe_list(daily, "temperature_2m_min")[:days]
    code = _safe_list(daily, "weather_code")[:days]
    precip = _safe_list(daily, "precipitation_sum")[:days]

    rows: list[dict[str, Any]] = []
    for idx, date in enumerate(dates):
        weather_code = int(code[idx]) if idx < len(code) and code[idx] is not None else 0
        rows.append(
            {
                "date": date,
                "temp_max": max_t[idx] if idx < len(max_t) else None,
                "temp_min": min_t[idx] if idx < len(min_t) else None,
                "weather_code": weather_code,
                "precipitation_sum": precip[idx] if idx < len(precip) else None,
            }
        )
    return rows


def get_weather(
    lat: float,
    lon: float,
    location_name: str,
    timeout: int = 12,
    debug: bool = False,
    debug_dir: Path | None = None,
) -> dict[str, Any]:
    opener = build_opener(ProxyHandler({}))
    url = _build_open_meteo_url(lat, lon)
    print(f"[WEATHER] Anropar Open-Meteo: {url}")

    request = Request(url, headers={"User-Agent": "DailyBriefingBot/1.1 (+https://github.com/actions)"})
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read()
        payload = json.loads(raw.decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"location": location_name, "error": f"Kunde inte hämta väderdata: {exc}"}

    if debug and debug_dir:
        (debug_dir / "smhi_response.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    current = payload.get("current") or {}
    daily_rows = _build_daily(payload.get("daily") or {}, days=10)
    today = daily_rows[0] if daily_rows else {}
    code = int(current.get("weather_code") or 0)
    return {
        "location": location_name,
        "temperature_c": current.get("temperature_2m"),
        "feels_like_c": current.get("apparent_temperature"),
        "min_c": today.get("temp_min"),
        "max_c": today.get("temp_max"),
        "wind_ms": current.get("wind_speed_10m"),
        "precip_mm_h": current.get("precipitation"),
        "description": WEATHER_CODES.get(code, "Okänd"),
        "forecast_time_utc": current.get("time"),
        "weather_code": code,
        "hourly_24": _build_hourly(payload.get("hourly") or {}, hours=24),
        "daily_10": daily_rows,
        "error": None,
    }
