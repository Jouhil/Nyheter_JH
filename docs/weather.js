(function () {
  const GOTHENBURG = { name: "Göteborg", lat: 57.7089, lon: 11.9746 };
  const LOCAL_WEATHER_PATH = "data/weather-goteborg.json";
  const API = (lat, lon) =>
    `https://api.open-meteo.com/v1/forecast?latitude=${lat.toFixed(4)}&longitude=${lon.toFixed(4)}&current=temperature_2m,wind_speed_10m,precipitation,weather_code,time&hourly=temperature_2m,wind_speed_10m,precipitation_probability,weather_code&daily=temperature_2m_max,temperature_2m_min,weather_code&forecast_days=7&timezone=UTC`;

  const SYMBOLS = {
    0: ["☀️", "Klart"], 1: ["🌤️", "Mest klart"], 2: ["⛅", "Delvis molnigt"], 3: ["☁️", "Mulet"],
    45: ["🌫️", "Dimma"], 48: ["🌫️", "Dimma"], 51: ["🌦️", "Lätt duggregn"], 53: ["🌦️", "Duggregn"],
    55: ["🌧️", "Tätt duggregn"], 61: ["🌦️", "Lätt regn"], 63: ["🌧️", "Regn"], 65: ["🌧️", "Kraftigt regn"],
    71: ["🌨️", "Lätt snö"], 73: ["❄️", "Snö"], 75: ["❄️", "Kraftig snö"], 80: ["🌧️", "Regnskurar"],
    81: ["🌧️", "Kraftiga regnskurar"], 82: ["⛈️", "Mycket kraftiga regnskurar"], 95: ["⛈️", "Åska"],
    96: ["⛈️", "Åska med hagel"], 99: ["⛈️", "Åska med hagel"],
  };

  const byId = (id) => document.getElementById(id);
  const fmtHour = (iso) => (iso ? new Date(iso).toLocaleTimeString("sv-SE", { hour: "2-digit", minute: "2-digit" }) : "--:--");
  const fmtDay = (iso) => (iso ? new Date(iso).toLocaleDateString("sv-SE", { weekday: "short" }) : "-" );
  const safeNum = (value, digits = 1) => (value == null || Number.isNaN(Number(value)) ? "-" : Number(value).toFixed(digits));
  const toIsoOrDash = (value) => (value ? new Date(value).toLocaleString("sv-SE") : "-");

  function renderNowFromApi(data, locationName) {
    const current = data.current || {};
    const code = Number(current.weather_code ?? 0);
    const [icon, text] = SYMBOLS[code] || ["⛅", "Okänd"];

    byId("weather-location").textContent = locationName;
    byId("weather-temp").textContent = `${safeNum(current.temperature_2m, 0)}°C`;
    byId("weather-desc").textContent = text;
    byId("weather-icon").textContent = icon;
    byId("weather-wind").textContent = `${safeNum(current.wind_speed_10m)} m/s`;
    byId("weather-precip").textContent = `${safeNum(current.precipitation)} mm/h`;
    byId("weather-updated").textContent = toIsoOrDash(current.time);
  }

  function renderNowFromLocal(payload) {
    const current = payload?.current || {};
    byId("weather-location").textContent = payload?.location || GOTHENBURG.name;
    byId("weather-temp").textContent = `${safeNum(current.temperature_c, 0)}°C`;
    byId("weather-desc").textContent = current.description || "Ingen väderbeskrivning";
    byId("weather-wind").textContent = `${safeNum(current.wind_ms)} m/s`;
    byId("weather-precip").textContent = `${safeNum(current.precip_mm_h)} mm/h`;
    byId("weather-updated").textContent = toIsoOrDash(current.forecast_time_utc);
    const [icon] = SYMBOLS[current.symbol] || ["⛅"];
    byId("weather-icon").textContent = icon;
  }

  function renderHourlyFromApi(data) {
    const target = byId("weather-hourly");
    const time = (data.hourly?.time || []).slice(0, 24);
    const temp = (data.hourly?.temperature_2m || []).slice(0, 24);
    const code = (data.hourly?.weather_code || []).slice(0, 24);

    if (!time.length) {
      target.innerHTML = "<p class='muted'>Ingen timprognos tillgänglig.</p>";
      return;
    }
    target.innerHTML = time
      .map((validTime, idx) => {
        const [icon] = SYMBOLS[Number(code[idx] ?? 0)] || ["⛅"];
        return `<article class="hour-card"><p>${fmtHour(validTime)}</p><div>${icon}</div><strong>${safeNum(temp[idx], 0)}°</strong></article>`;
      })
      .join("");
  }

  function renderDailyFromApi(data) {
    const target = byId("weather-daily");
    const days = (data.daily?.time || []).slice(0, 7);
    const max = (data.daily?.temperature_2m_max || []).slice(0, 7);
    const min = (data.daily?.temperature_2m_min || []).slice(0, 7);
    const code = (data.daily?.weather_code || []).slice(0, 7);

    if (!days.length) {
      target.innerHTML = "<p class='muted'>Ingen dygnsprognos tillgänglig.</p>";
      return;
    }

    target.innerHTML = days
      .map((day, idx) => {
        const [icon] = SYMBOLS[Number(code[idx] ?? 0)] || ["⛅"];
        return `<article class="day-card"><p>${fmtDay(day)}</p><div>${icon}</div><strong>${safeNum(max[idx], 0)}° / ${safeNum(min[idx], 0)}°</strong></article>`;
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
    const res = await fetch(API(lat, lon));
    if (!res.ok) throw new Error(`Open-Meteo svarade ${res.status}`);
    const data = await res.json();
    renderNowFromApi(data, name);
    renderHourlyFromApi(data);
    renderDailyFromApi(data);
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
            // behåll Göteborg-data
          },
          { timeout: 8000, enableHighAccuracy: false, maximumAge: 300000 }
        );
      });
  }

  init();
})();
