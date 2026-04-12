(function () {
  const SAVE_LOCATION = { name: "Säve", lat: 57.7807, lon: 11.8704 };
  const GOTEBORG_LOCATION = { name: "Göteborg", lat: 57.7089, lon: 11.9746 };
  const LOCAL_WEATHER_PATH = "data/weather-goteborg.json";
  const API = (lat, lon) =>
    `https://api.open-meteo.com/v1/forecast?latitude=${lat.toFixed(4)}&longitude=${lon.toFixed(4)}&current=temperature_2m,apparent_temperature,wind_speed_10m,precipitation,weather_code&hourly=temperature_2m,wind_speed_10m,precipitation,weather_code&daily=temperature_2m_max,temperature_2m_min,weather_code,precipitation_sum,sunrise,sunset&forecast_days=10&timezone=UTC`;

  const WEATHER_CODE_MAP = [
    { test: (code) => code === 0, icon: "☀️", text: "Klart", mood: "clear" },
    { test: (code) => code === 1, icon: "🌤️", text: "Delvis molnigt", mood: "partly-cloudy" },
    { test: (code) => code === 2 || code === 3, icon: "☁️", text: "Molnigt", mood: "cloudy" },
    { test: (code) => code === 45 || code === 48, icon: "🌫️", text: "Dimma", mood: "fog" },
    { test: (code) => [51, 53, 55, 61, 63, 65, 80, 81, 82].includes(code), icon: "🌧️", text: "Regn", mood: "rain" },
    { test: (code) => [95, 96, 99].includes(code), icon: "⛈️", text: "Åska", mood: "rain" },
    { test: (code) => [71, 73, 75, 77, 85, 86].includes(code), icon: "❄️", text: "Snö", mood: "snow" },
  ];

  const byId = (id) => document.getElementById(id);
  const safeNum = (value, digits = 1) => (value == null || Number.isNaN(Number(value)) ? null : Number(value).toFixed(digits));
  const valueOrText = (v, suffix = "", fallback = "Ingen data") => (v == null || Number.isNaN(Number(v)) ? fallback : `${Number(v).toFixed(0)}${suffix}`);
  const fmtHour = (iso) => (iso ? new Date(iso).toLocaleTimeString("sv-SE", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Stockholm" }) : "Tid saknas");
  const fmtDay = (iso) => (iso ? new Date(iso).toLocaleDateString("sv-SE", { weekday: "short", timeZone: "Europe/Stockholm" }) : "Okänd dag");
  const fmtDateTime = (iso) => (iso ? new Date(iso).toLocaleString("sv-SE", { timeZone: "Europe/Stockholm" }) : "Okänd tid");

  const getWeatherSymbol = (code) => {
    const value = Number(code);
    return WEATHER_CODE_MAP.find((row) => row.test(value)) || { icon: "🌤️", text: "Växlande molnighet", mood: "partly-cloudy" };
  };

  function moodFromCurrent(current = {}) {
    const hourInStockholm = Number(new Date().toLocaleString("en-US", { hour: "2-digit", hour12: false, timeZone: "Europe/Stockholm" }));
    const isNight = hourInStockholm >= 21 || hourInStockholm <= 5;
    if (isNight) return "night";
    return getWeatherSymbol(current.weather_code).mood;
  }

  function applyMood(app, mood) {
    if (!app) return;
    const moodClasses = ["clear", "partly-cloudy", "cloudy", "rain", "fog", "snow", "night"];
    app.classList.remove(...moodClasses.map((name) => `weather-mood-${name}`));
    app.classList.add(`weather-mood-${mood}`);
  }

  function normalizeApiToWeatherJson(apiData, locationName) {
    const current = apiData?.current || {};
    const weatherCode = Number(current.weather_code ?? 0);
    const daily = (apiData?.daily?.time || []).slice(0, 10).map((date, idx) => ({
      date,
      temp_max: apiData?.daily?.temperature_2m_max?.[idx] ?? null,
      temp_min: apiData?.daily?.temperature_2m_min?.[idx] ?? null,
      weather_code: apiData?.daily?.weather_code?.[idx] ?? null,
      precipitation_sum: apiData?.daily?.precipitation_sum?.[idx] ?? null,
      sunrise: apiData?.daily?.sunrise?.[idx] ?? null,
      sunset: apiData?.daily?.sunset?.[idx] ?? null,
    }));

    return {
      location: locationName,
      current: {
        temperature: current.temperature_2m ?? null,
        feels_like: current.apparent_temperature ?? null,
        wind_speed: current.wind_speed_10m ?? null,
        precipitation: current.precipitation ?? null,
        weather_code: weatherCode,
        description: getWeatherSymbol(weatherCode).text,
        forecast_time: current.time ?? null,
        temp_min: daily[0]?.temp_min ?? null,
        temp_max: daily[0]?.temp_max ?? null,
      },
      hourly_24: (apiData?.hourly?.time || []).slice(0, 24).map((time, idx) => ({
        time,
        temperature: apiData?.hourly?.temperature_2m?.[idx] ?? null,
        weather_code: apiData?.hourly?.weather_code?.[idx] ?? null,
        precipitation: apiData?.hourly?.precipitation?.[idx] ?? null,
        wind_speed: apiData?.hourly?.wind_speed_10m?.[idx] ?? null,
      })),
      daily_10: daily,
      error: null,
    };
  }

  function renderWeather(data) {
    const app = byId("weather-app");
    const current = data?.current || {};
    const symbol = getWeatherSymbol(current.weather_code);

    applyMood(app, moodFromCurrent(current));

    byId("weather-location").textContent = data?.location || SAVE_LOCATION.name;
    byId("weather-temp").textContent = valueOrText(current.temperature, "°", "Temperatur saknas");
    byId("weather-desc").textContent = current.description || symbol.text;
    byId("weather-icon").textContent = symbol.icon;
    byId("weather-feels-like").textContent = valueOrText(current.feels_like, "°", "okänt");
    byId("weather-hilo").textContent = `${valueOrText(current.temp_max, "°", "okänt")} / ${valueOrText(current.temp_min, "°", "okänt")}`;
    byId("weather-wind").textContent = safeNum(current.wind_speed) ? `${safeNum(current.wind_speed)} m/s` : "Vinddata saknas";
    byId("weather-precip").textContent = safeNum(current.precipitation) ? `${safeNum(current.precipitation)} mm/h` : "Ingen nederbörd just nu";
    byId("weather-updated").textContent = fmtDateTime(current.forecast_time);

    const hourlyTarget = byId("weather-hourly");
    const now = Date.now();
    const points = (Array.isArray(data?.hourly_24) ? data.hourly_24 : [])
      .filter((row) => row?.time && new Date(row.time).getTime() >= now - 3600_000)
      .slice(0, 24);
    if (!points.length) {
      hourlyTarget.innerHTML = "<p class='muted'>Ingen timprognos tillgänglig.</p>";
    } else {
      hourlyTarget.innerHTML = points
        .map((row) => {
          const hourSymbol = getWeatherSymbol(row.weather_code);
          const precip = safeNum(row.precipitation);
          return `<article class="hour-card"><p class="hour-time">${fmtHour(row.time)}</p><div class="hour-icon">${hourSymbol.icon}</div><strong>${valueOrText(row.temperature, "°", "—")}</strong><small>${precip ? `${precip} mm nederbörd` : "Ingen nederbörd"}</small></article>`;
        })
        .join("");
    }

    const dailyTarget = byId("weather-daily");
    const days = Array.isArray(data?.daily_10) ? data.daily_10.slice(0, 7) : [];
    if (!days.length) {
      dailyTarget.innerHTML = "<p class='muted'>Ingen dygnsprognos tillgänglig.</p>";
      return;
    }

    const dailyMins = days.map((day) => Number(day.temp_min)).filter((n) => Number.isFinite(n));
    const dailyMaxes = days.map((day) => Number(day.temp_max)).filter((n) => Number.isFinite(n));
    const globalMin = dailyMins.length ? Math.min(...dailyMins) : 0;
    const globalMax = dailyMaxes.length ? Math.max(...dailyMaxes) : 1;
    const span = Math.max(1, globalMax - globalMin);

    dailyTarget.innerHTML = days
      .map((day) => {
        const daySymbol = getWeatherSymbol(day.weather_code);
        const min = Number.isFinite(Number(day.temp_min)) ? Number(day.temp_min) : globalMin;
        const max = Number.isFinite(Number(day.temp_max)) ? Number(day.temp_max) : min;
        const offset = ((min - globalMin) / span) * 100;
        const width = (Math.max(0.5, max - min) / span) * 100;
        return `<article class="day-row"><p>${fmtDay(day.date)}</p><div class="day-icon">${daySymbol.icon}</div><span class="day-min">${valueOrText(day.temp_min, "°", "—")}</span><div class="temp-track"><span class="temp-fill" style="left:${offset.toFixed(1)}%;width:${width.toFixed(1)}%"></span></div><span class="day-max">${valueOrText(day.temp_max, "°", "—")}</span></article>`;
      })
      .join("");
  }

  function renderFallback(msg) {
    const app = byId("weather-app");
    const existing = app.querySelector(".weather-fallback");
    if (existing) existing.textContent = msg;
    else app.insertAdjacentHTML("afterbegin", `<p class="weather-fallback">${msg}</p>`);
  }

  async function fetchWeatherForLocation(location) {
    const res = await fetch(API(location.lat, location.lon));
    if (!res.ok) throw new Error(`Open-Meteo svarade ${res.status}`);
    const apiData = await res.json();
    renderWeather(normalizeApiToWeatherJson(apiData, location.name));
  }

  async function fetchLocalWeather() {
    const res = await fetch(LOCAL_WEATHER_PATH, { cache: "no-store" });
    if (!res.ok) throw new Error(`Lokal väderfil saknas (${res.status})`);
    const data = await res.json();
    renderWeather(data);
  }

  async function loadWithFallbackLocations() {
    try {
      await fetchWeatherForLocation(SAVE_LOCATION);
      renderFallback("Geolocation nekades eller misslyckades. Visar Säve som fallback.");
      return;
    } catch (_) {
      try {
        await fetchWeatherForLocation(GOTEBORG_LOCATION);
        renderFallback("Säve saknas just nu. Visar Göteborg som fallback.");
      } catch (error) {
        renderFallback("Kunde inte hämta fallback-väder. Visar senaste lokala väderdata.");
      }
    }
  }

  function init() {
    fetchLocalWeather().catch(() => {
      renderFallback("Kunde inte läsa lokal väderfil. Hämtar live-väder i stället.");
    });

    if (!navigator.geolocation) {
      loadWithFallbackLocations();
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        fetchWeatherForLocation({ name: "Din position", lat: pos.coords.latitude, lon: pos.coords.longitude }).catch(() => {
          loadWithFallbackLocations();
        });
      },
      () => {
        loadWithFallbackLocations();
      },
      { timeout: 9000, enableHighAccuracy: false, maximumAge: 240000 }
    );
  }

  init();
})();
