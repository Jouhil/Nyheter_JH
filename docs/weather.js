(function () {
  const GOTHENBURG = { name: "Göteborg", lat: 57.7089, lon: 11.9746 };
  const LOCAL_WEATHER_PATH = "data/weather-goteborg.json";
  const API = (lat, lon) =>
    `https://api.open-meteo.com/v1/forecast?latitude=${lat.toFixed(4)}&longitude=${lon.toFixed(4)}&current=temperature_2m,wind_speed_10m,precipitation,weather_code&hourly=temperature_2m,precipitation,weather_code&daily=temperature_2m_max,temperature_2m_min,weather_code,precipitation_sum&forecast_days=7&timezone=UTC`;

  const SYMBOLS = {
    0: ["☀️", "Klart"], 1: ["🌤️", "Mest klart"], 2: ["⛅", "Delvis molnigt"], 3: ["☁️", "Mulet"],
    45: ["🌫️", "Dimma"], 48: ["🌫️", "Dimma"], 51: ["🌦️", "Lätt duggregn"], 53: ["🌦️", "Duggregn"],
    55: ["🌧️", "Tätt duggregn"], 61: ["🌦️", "Lätt regn"], 63: ["🌧️", "Regn"], 65: ["🌧️", "Kraftigt regn"],
    71: ["🌨️", "Lätt snö"], 73: ["❄️", "Snö"], 75: ["❄️", "Kraftig snö"], 80: ["🌧️", "Regnskurar"],
    81: ["🌧️", "Kraftiga regnskurar"], 82: ["⛈️", "Mycket kraftiga regnskurar"], 95: ["⛈️", "Åska"],
    96: ["⛈️", "Åska med hagel"], 99: ["⛈️", "Åska med hagel"],
  };

  const byId = (id) => document.getElementById(id);
  const safeNum = (value, digits = 1) => (value == null || Number.isNaN(Number(value)) ? "-" : Number(value).toFixed(digits));
  const fmtHour = (iso) => (iso ? new Date(iso).toLocaleTimeString("sv-SE", { hour: "2-digit", minute: "2-digit" }) : "--:--");
  const fmtDay = (iso) => (iso ? new Date(iso).toLocaleDateString("sv-SE", { weekday: "short" }) : "-");
  const fmtDateTime = (iso) => (iso ? new Date(iso).toLocaleString("sv-SE") : "-");

  function normalizeApiToWeatherJson(apiData, locationName) {
    const current = apiData?.current || {};
    const weatherCode = Number(current.weather_code ?? 0);
    return {
      location: locationName,
      current: {
        temperature: current.temperature_2m ?? null,
        wind_speed: current.wind_speed_10m ?? null,
        precipitation: current.precipitation ?? null,
        weather_code: weatherCode,
        description: (SYMBOLS[weatherCode] || ["⛅", "Okänd"])[1],
        forecast_time: current.time ?? null,
      },
      hourly_24: (apiData?.hourly?.time || []).slice(0, 24).map((time, idx) => ({
        time,
        temperature: apiData?.hourly?.temperature_2m?.[idx] ?? null,
        weather_code: apiData?.hourly?.weather_code?.[idx] ?? null,
        precipitation: apiData?.hourly?.precipitation?.[idx] ?? null,
      })),
      daily_7: (apiData?.daily?.time || []).slice(0, 7).map((date, idx) => ({
        date,
        temp_max: apiData?.daily?.temperature_2m_max?.[idx] ?? null,
        temp_min: apiData?.daily?.temperature_2m_min?.[idx] ?? null,
        weather_code: apiData?.daily?.weather_code?.[idx] ?? null,
        precipitation_sum: apiData?.daily?.precipitation_sum?.[idx] ?? null,
      })),
      error: null,
    };
  }

  function renderWeather(data) {
    const current = data?.current || {};
    const [icon, fallbackText] = SYMBOLS[Number(current.weather_code ?? 0)] || ["⛅", "Okänd"];

    byId("weather-location").textContent = data?.location || GOTHENBURG.name;
    byId("weather-temp").textContent = `${safeNum(current.temperature, 0)}°C`;
    byId("weather-desc").textContent = current.description || fallbackText;
    byId("weather-icon").textContent = icon;
    byId("weather-wind").textContent = `${safeNum(current.wind_speed)} m/s`;
    byId("weather-precip").textContent = `${safeNum(current.precipitation)} mm/h`;
    byId("weather-updated").textContent = fmtDateTime(current.forecast_time);

    const hourlyTarget = byId("weather-hourly");
    const points = Array.isArray(data?.hourly_24) ? data.hourly_24 : [];
    if (!points.length) {
      hourlyTarget.innerHTML = "<p class='muted'>Ingen timprognos tillgänglig.</p>";
    } else {
      hourlyTarget.innerHTML = points
        .map((row) => {
          const [hourIcon] = SYMBOLS[Number(row.weather_code ?? 0)] || ["⛅"];
          return `<article class="hour-card"><p>${fmtHour(row.time)}</p><div>${hourIcon}</div><strong>${safeNum(row.temperature, 0)}°</strong></article>`;
        })
        .join("");
    }

    const dailyTarget = byId("weather-daily");
    const days = Array.isArray(data?.daily_7) ? data.daily_7 : [];
    if (!days.length) {
      dailyTarget.innerHTML = "<p class='muted'>Ingen dygnsprognos tillgänglig.</p>";
    } else {
      dailyTarget.innerHTML = days
        .map((day) => {
          const [dayIcon] = SYMBOLS[Number(day.weather_code ?? 0)] || ["⛅"];
          return `<article class="day-card"><p>${fmtDay(day.date)}</p><div>${dayIcon}</div><strong>${safeNum(day.temp_max, 0)}° / ${safeNum(day.temp_min, 0)}°</strong></article>`;
        })
        .join("");
    }
  }

  function renderFallback(msg) {
    const app = byId("weather-app");
    const existing = app.querySelector(".weather-fallback");
    if (existing) existing.textContent = msg;
    else app.insertAdjacentHTML("afterbegin", `<p class="weather-fallback">${msg}</p>`);
  }

  async function fetchLocalWeather() {
    const res = await fetch(LOCAL_WEATHER_PATH, { cache: "no-store" });
    if (!res.ok) throw new Error(`Lokal väderfil saknas (${res.status})`);
    const data = await res.json();
    console.log("Weather JSON loaded:", data);
    renderWeather(data);
  }

  async function fetchGeoWeather(lat, lon) {
    const res = await fetch(API(lat, lon));
    if (!res.ok) throw new Error(`Open-Meteo svarade ${res.status}`);
    const apiData = await res.json();
    const data = normalizeApiToWeatherJson(apiData, "Din position");
    renderWeather(data);
  }

  function init() {
    fetchLocalWeather()
      .catch(() => {
        renderFallback("Kunde inte läsa lokal väderfil. Visar inbäddad fallback för Göteborg.");
      })
      .finally(() => {
        if (!navigator.geolocation) return;
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            fetchGeoWeather(pos.coords.latitude, pos.coords.longitude).catch(() => {
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
