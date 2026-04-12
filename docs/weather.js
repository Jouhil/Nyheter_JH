(function () {
  const GOTHENBURG = { name: "Göteborg", lat: 57.7089, lon: 11.9746 };
  const LOCAL_WEATHER_PATH = "data/weather-goteborg.json";
  const API = (lat, lon) =>
    `https://opendata-download-metfcst.smhi.se/api/category/pmp3g/version/2/geotype/point/lon/${lon}/lat/${lat}/data.json`;

  const SYMBOLS = {
    1: ["☀️", "Klart"], 2: ["🌤️", "Nästan klart"], 3: ["⛅", "Växlande molnighet"],
    4: ["🌥️", "Halvklart"], 5: ["☁️", "Molnigt"], 6: ["☁️", "Mulet"], 7: ["🌫️", "Dimma"],
    8: ["🌦️", "Lätta regnskurar"], 9: ["🌧️", "Regnskurar"], 10: ["⛈️", "Kraftiga regnskurar"],
    11: ["⛈️", "Åska"], 18: ["🌦️", "Lätt regn"], 19: ["🌧️", "Regn"], 20: ["🌧️", "Kraftigt regn"],
    21: ["⛈️", "Åska"], 22: ["🌨️", "Snöblandat regn"], 23: ["🌨️", "Snöblandat regn"],
    24: ["🌨️", "Kraftigt snöblandat regn"], 25: ["❄️", "Snöfall"], 26: ["❄️", "Snöfall"], 27: ["❄️", "Kraftigt snöfall"],
  };

  const byId = (id) => document.getElementById(id);
  const pick = (params, name) => (params.find((p) => p.name === name)?.values || [null])[0];
  const fmtHour = (iso) => new Date(iso).toLocaleTimeString("sv-SE", { hour: "2-digit", minute: "2-digit" });
  const fmtDay = (iso) => new Date(iso).toLocaleDateString("sv-SE", { weekday: "short" });
  const safeNum = (value, digits = 1) => (value == null || Number.isNaN(Number(value)) ? "-" : Number(value).toFixed(digits));
  const toIsoOrDash = (value) => (value ? new Date(value).toLocaleString("sv-SE") : "-");

  function renderNow(data, locationName) {
    const current = data.timeSeries?.[0];
    if (!current) throw new Error("Ingen aktuell prognosrad");

    const t = pick(current.parameters, "t");
    const ws = pick(current.parameters, "ws");
    const p = pick(current.parameters, "pmean");
    const symbol = pick(current.parameters, "Wsymb2");
    const [icon, text] = SYMBOLS[symbol] || ["⛅", "Okänd"];

    byId("weather-location").textContent = locationName;
    byId("weather-temp").textContent = `${Math.round(t)}°C`;
    byId("weather-desc").textContent = text;
    byId("weather-icon").textContent = icon;
    byId("weather-wind").textContent = `${ws ?? "-"} m/s`;
    byId("weather-precip").textContent = `${p ?? "-"} mm/h`;
    byId("weather-updated").textContent = new Date(current.validTime).toLocaleString("sv-SE");
  }

  function renderNowFromLocal(payload) {
    const current = payload?.current || {};
    byId("weather-location").textContent = payload?.location || GOTHENBURG.name;
    byId("weather-temp").textContent = `${safeNum(current.temperature_c, 0)}°C`;
    byId("weather-desc").textContent = current.description || "Ingen väderbeskrivning";
    byId("weather-wind").textContent = `${safeNum(current.wind_ms)} m/s`;
    byId("weather-precip").textContent = `${safeNum(current.precip_mm_h)} mm/h`;
    byId("weather-updated").textContent = toIsoOrDash(current.forecast_time_utc);
    const symbol = current.symbol;
    const [icon] = SYMBOLS[symbol] || ["⛅"];
    byId("weather-icon").textContent = icon;
  }

  function renderHourly(data) {
    const target = byId("weather-hourly");
    const points = (data.timeSeries || []).slice(0, 24);
    if (!points.length) {
      target.innerHTML = "<p class='muted'>Ingen timprognos tillgänglig.</p>";
      return;
    }
    target.innerHTML = points
      .map((row) => {
        const t = pick(row.parameters, "t");
        const symbol = pick(row.parameters, "Wsymb2");
        const [icon] = SYMBOLS[symbol] || ["⛅"];
        return `<article class="hour-card"><p>${fmtHour(row.validTime)}</p><div>${icon}</div><strong>${Math.round(t)}°</strong></article>`;
      })
      .join("");
  }

  function renderDaily(data) {
    const target = byId("weather-daily");
    const rows = data.timeSeries || [];
    const days = new Map();

    for (const row of rows) {
      const d = row.validTime.slice(0, 10);
      const temp = pick(row.parameters, "t");
      const symbol = pick(row.parameters, "Wsymb2");
      if (!days.has(d)) days.set(d, { min: temp, max: temp, symbol });
      else {
        const day = days.get(d);
        day.min = Math.min(day.min, temp);
        day.max = Math.max(day.max, temp);
      }
      if (days.size >= 7) break;
    }

    if (!days.size) {
      target.innerHTML = "<p class='muted'>Ingen dygnsprognos tillgänglig.</p>";
      return;
    }

    target.innerHTML = [...days.entries()]
      .map(([date, day]) => {
        const [icon] = SYMBOLS[day.symbol] || ["⛅"];
        return `<article class="day-card"><p>${fmtDay(date)}</p><div>${icon}</div><strong>${Math.round(day.max)}° / ${Math.round(day.min)}°</strong></article>`;
      })
      .join("");
  }

  function renderHourlyFromLocal(payload) {
    const target = byId("weather-hourly");
    const points = payload?.hourly_24 || [];
    if (!points.length) {
      target.innerHTML = "<p class='muted'>Ingen timprognos tillgänglig.</p>";
      return;
    }
    target.innerHTML = points
      .map((row) => {
        const [icon] = SYMBOLS[row.symbol] || ["⛅"];
        return `<article class="hour-card"><p>${fmtHour(row.valid_time)}</p><div>${icon}</div><strong>${safeNum(row.temperature_c, 0)}°</strong></article>`;
      })
      .join("");
  }

  function renderDailyFromLocal(payload) {
    const target = byId("weather-daily");
    const days = payload?.daily_7 || [];
    if (!days.length) {
      target.innerHTML = "<p class='muted'>Ingen dygnsprognos tillgänglig.</p>";
      return;
    }
    target.innerHTML = days
      .map((day) => {
        const [icon] = SYMBOLS[day.symbol] || ["⛅"];
        return `<article class="day-card"><p>${fmtDay(day.date)}</p><div>${icon}</div><strong>${safeNum(day.max_temp_c, 0)}° / ${safeNum(day.min_temp_c, 0)}°</strong></article>`;
      })
      .join("");
  }

  function renderFallback(msg) {
    const app = byId("weather-app");
    const existing = app.querySelector(".weather-fallback");
    if (existing) existing.textContent = msg;
    else app.insertAdjacentHTML("afterbegin", `<p class="weather-fallback">${msg}</p>`);
  }

  async function fetchWeather(lat, lon, name) {
    const res = await fetch(API(lat.toFixed(6), lon.toFixed(6)));
    if (!res.ok) throw new Error(`SMHI svarade ${res.status}`);
    const data = await res.json();
    renderNow(data, name);
    renderHourly(data);
    renderDaily(data);
  }

  async function fetchLocalWeather() {
    const res = await fetch(LOCAL_WEATHER_PATH, { cache: "no-store" });
    if (!res.ok) throw new Error(`Lokal väderfil saknas (${res.status})`);
    const payload = await res.json();
    renderNowFromLocal(payload);
    renderHourlyFromLocal(payload);
    renderDailyFromLocal(payload);
    return payload;
  }

  function fallbackFromHtml() {
    const raw = byId("weather-fallback-data")?.textContent;
    if (!raw) return;
    try {
      const data = JSON.parse(raw);
      byId("weather-location").textContent = data.location || GOTHENBURG.name;
      byId("weather-temp").textContent = data.temperature_c != null ? `${Math.round(data.temperature_c)}°C` : "-°C";
      byId("weather-desc").textContent = data.description || "Ingen väderbeskrivning";
      byId("weather-wind").textContent = `${data.wind_ms ?? "-"} m/s`;
      byId("weather-precip").textContent = `${data.precip_mm_h ?? "-"} mm/h`;
      byId("weather-updated").textContent = data.forecast_time_utc || "-";
      byId("weather-hourly").innerHTML = "<p class='muted'>Timprognos saknas lokalt.</p>";
      byId("weather-daily").innerHTML = "<p class='muted'>Dygnsprognos saknas lokalt.</p>";
    } catch {
      // ignore malformed fallback data
    }
  }

  function init() {
    fallbackFromHtml();
    fetchLocalWeather()
      .catch(() => {
        renderFallback("Kunde inte läsa lokal väderfil. Visar inbäddad fallback för Göteborg.");
      })
      .finally(() => {
        if (!navigator.geolocation) return;
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            fetchWeather(pos.coords.latitude, pos.coords.longitude, "Din position").catch(() => {
              renderFallback("Kunde inte hämta väder för din plats. Visar Göteborg-data.");
            });
          },
          () => {
            // best effort only; behåll Göteborg-data
          },
          { timeout: 8000, enableHighAccuracy: false, maximumAge: 300000 }
        );
      });
  }

  init();
})();
