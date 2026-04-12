"""SMHI weather utilities."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

SMHI_URL_TEMPLATE = (
    "https://opendata-download-metfcst.smhi.se/api/category/pmp3g/version/2/"
    "geotype/point/lon/{lon}/lat/{lat}/data.json"
)

WEATHER_SYMBOLS = {1: "Klart", 2: "Nästan klart", 3: "Växlande molnighet", 4: "Halvklart", 5: "Molnigt", 6: "Mulet", 7: "Dimma", 8: "Lätta regnskurar", 9: "Måttliga regnskurar", 10: "Kraftiga regnskurar", 11: "Åskväder", 12: "Lätta byar av snöblandat regn", 13: "Måttliga byar av snöblandat regn", 14: "Kraftiga byar av snöblandat regn", 15: "Lätta snöbyar", 16: "Måttliga snöbyar", 17: "Kraftiga snöbyar", 18: "Lätt regn", 19: "Måttligt regn", 20: "Kraftigt regn", 21: "Åska", 22: "Lätt snöblandat regn", 23: "Måttligt snöblandat regn", 24: "Kraftigt snöblandat regn", 25: "Lätt snöfall", 26: "Måttligt snöfall", 27: "Kraftigt snöfall"}


def _timeseries_param_map(timeseries: dict[str, Any]) -> dict[str, Any]:
    return {p.get("name"): p.get("values", [None])[0] for p in timeseries.get("parameters", [])}


def get_weather(lat: float, lon: float, location_name: str, timeout: int = 12) -> dict[str, Any]:
    url = SMHI_URL_TEMPLATE.format(lat=lat, lon=lon)
    try:
        with urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"location": location_name, "error": f"Kunde inte hämta väderdata: {exc}"}

    now_utc = datetime.now(timezone.utc)
    time_series = payload.get("timeSeries", [])
    selected = None
    for item in time_series:
        valid = item.get("validTime")
        if not valid:
            continue
        valid_dt = datetime.fromisoformat(valid.replace("Z", "+00:00"))
        if valid_dt >= now_utc:
            selected = item
            break
    if not selected and time_series:
        selected = time_series[0]
    if not selected:
        return {"location": location_name, "error": "SMHI svarade utan prognosdata."}

    param_map = _timeseries_param_map(selected)
    symbol = int(param_map.get("Wsymb2") or 0)
    return {
        "location": location_name,
        "temperature_c": param_map.get("t"),
        "wind_ms": param_map.get("ws"),
        "precip_mm_h": param_map.get("pmean"),
        "description": WEATHER_SYMBOLS.get(symbol, "Okänd"),
        "forecast_time_utc": selected.get("validTime"),
        "error": None,
    }
