"""SMHI weather utilities."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

SMHI_URL_TEMPLATE = (
    "https://opendata-download-metfcst.smhi.se/api/category/snow1g/version/1/"
    "geotype/point/lon/{lon}/lat/{lat}/data.json"
)
SMHI_FALLBACK_URL_TEMPLATE = (
    "https://opendata-download-metfcst.smhi.se/api/category/pmp3g/version/2/"
    "geotype/point/lon/{lon}/lat/{lat}/data.json"
)

WEATHER_SYMBOLS = {1: "Klart", 2: "Nästan klart", 3: "Växlande molnighet", 4: "Halvklart", 5: "Molnigt", 6: "Mulet", 7: "Dimma", 8: "Lätta regnskurar", 9: "Måttliga regnskurar", 10: "Kraftiga regnskurar", 11: "Åskväder", 12: "Lätta byar av snöblandat regn", 13: "Måttliga byar av snöblandat regn", 14: "Kraftiga byar av snöblandat regn", 15: "Lätta snöbyar", 16: "Måttliga snöbyar", 17: "Kraftiga snöbyar", 18: "Lätt regn", 19: "Måttligt regn", 20: "Kraftigt regn", 21: "Åska", 22: "Lätt snöblandat regn", 23: "Måttligt snöblandat regn", 24: "Kraftigt snöblandat regn", 25: "Lätt snöfall", 26: "Måttligt snöfall", 27: "Kraftigt snöfall"}


def _timeseries_param_map(timeseries: dict[str, Any]) -> dict[str, Any]:
    return {p.get("name"): p.get("values", [None])[0] for p in timeseries.get("parameters", [])}


def _format_coord(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def get_weather(
    lat: float,
    lon: float,
    location_name: str,
    timeout: int = 12,
    debug: bool = False,
    debug_dir: Path | None = None,
) -> dict[str, Any]:
    lat_str = _format_coord(lat)
    lon_str = _format_coord(lon)
    urls = [
        SMHI_URL_TEMPLATE.format(lat=lat_str, lon=lon_str),
        SMHI_FALLBACK_URL_TEMPLATE.format(lat=lat_str, lon=lon_str),
    ]
    opener = build_opener(ProxyHandler({}))
    payload: dict[str, Any] | None = None
    chosen_url = ""
    last_error: Exception | None = None

    for url in urls:
        chosen_url = url
        print(f"[SMHI] Anropar URL: {url}")
        request = Request(url, headers={"User-Agent": "DailyBriefingBot/1.1 (+https://github.com/actions)"})
        try:
            with opener.open(request, timeout=timeout) as response:
                status = getattr(response, "status", 200)
                content_type = response.headers.get("Content-Type", "okänd")
                raw = response.read()
            if debug:
                print(
                    f"[SMHI][DEBUG] status={status} content-type={content_type} bytes={len(raw)}"
                )
                preview = raw.decode("utf-8", errors="replace")[:300].replace("\n", " ")
                print(f"[SMHI][DEBUG] response preview: {preview}")
            payload = json.loads(raw.decode("utf-8"))
            if "json" not in content_type.lower():
                raise ValueError(f"SMHI svarade med oväntad content-type: {content_type}")
            if not isinstance(payload.get("timeSeries"), list) or not payload.get("timeSeries"):
                raise ValueError("SMHI JSON saknar timeSeries/prognosdata")
            if debug and debug_dir:
                (debug_dir / "smhi_response.json").write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            print(f"[SMHI] JSON verifierad från: {url}")
            break
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            print(f"[SMHI] FEL på URL {url}: {exc}")
            payload = None
            continue

    if payload is None:
        print(f"SMHI parse failed because {last_error}")
        if debug and debug_dir:
            (debug_dir / "smhi_response.json").write_text(
                json.dumps({"error": str(last_error), "url": chosen_url}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return {"location": location_name, "error": f"Kunde inte hämta väderdata: {last_error}"}

    now_utc = datetime.now(timezone.utc)
    time_series = payload.get("timeSeries", [])
    if debug:
        print(f"[SMHI][DEBUG] timeSeries count: {len(time_series)}")
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
        print("[SMHI] FEL: svar innehöll ingen prognosrad.")
        print("SMHI parse failed because timeSeries saknar användbar prognos")
        return {"location": location_name, "error": "SMHI svarade utan prognosdata."}

    param_map = _timeseries_param_map(selected)
    symbol = int(param_map.get("Wsymb2") or 0)
    weather = {
        "location": location_name,
        "temperature_c": param_map.get("t"),
        "wind_ms": param_map.get("ws"),
        "precip_mm_h": param_map.get("pmean"),
        "description": WEATHER_SYMBOLS.get(symbol, "Okänd"),
        "forecast_time_utc": selected.get("validTime"),
        "error": None,
    }
    print(
        "[SMHI] OK: "
        f"{location_name} {weather['temperature_c']}°C, "
        f"{weather['description']}, vind {weather['wind_ms']} m/s"
    )
    print("SMHI fetch OK")
    return weather
