(function () {
  const YOUTUBE_DATA_PATH = 'data/youtube-latest.json';
  const WEATHER_DATA_PATH = 'data/weather-goteborg.json';
  const THEME_KEY = 'briefing-theme-mode';
  const youtubeUi = window.YouTubeBriefing || {};
  const STOCKHOLM_TZ = youtubeUi?.STOCKHOLM_TZ || 'Europe/Stockholm';

  const byId = (id) => document.getElementById(id);

  function parseISO(value) {
    if (!value) return null;
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function parsePublishedDate(video) {
    if (typeof youtubeUi.parsePublishedDate === 'function') {
      return youtubeUi.parsePublishedDate(video);
    }
    const unix = Number(video?.published_at_unix);
    if (Number.isFinite(unix) && unix > 0) return new Date((unix > 1e12 ? unix : unix * 1000));
    return parseISO(video?.published_at_utc);
  }

  function formatStockholmDateTime(date) {
    if (typeof youtubeUi.formatStockholmDateTime === 'function') {
      return youtubeUi.formatStockholmDateTime(date);
    }
    return new Intl.DateTimeFormat('sv-SE', {
      timeZone: STOCKHOLM_TZ,
      hour: '2-digit',
      minute: '2-digit',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(date);
  }

  function isLikelyShort(video) {
    const hardSignals = [];
    const url = String(video?.url || '').toLowerCase();
    if (url.includes('/shorts/')) {
      hardSignals.push('url_contains_/shorts/');
    }

    const rawDuration = video?.duration;
    const duration = rawDuration === null || rawDuration === undefined || rawDuration === ''
      ? Number.NaN
      : Number(rawDuration);
    if (Number.isFinite(duration) && duration > 0 && duration <= 60) {
      hardSignals.push('duration_<=_60s');
    }

    const title = String(video?.title || '').toLowerCase();
    if (/#shorts\b/.test(title)) {
      hardSignals.push('title_contains_#shorts');
    }
    if (/\bshorts\b/.test(title)) {
      hardSignals.push('title_contains_word_shorts');
    }

    return {
      isShort: hardSignals.length > 0,
      isCandidate: hardSignals.length > 0,
      signals: hardSignals,
      reason: hardSignals[0] || null,
    };
  }

  async function renderYoutubeLatest() {
    const root = byId('youtube-list');
    if (!root) return;

    try {
      const response = await fetch(YOUTUBE_DATA_PATH, { cache: 'no-store' });
      if (!response.ok) throw new Error(`Kunde inte läsa YouTube-data (${response.status})`);
      const payload = await response.json();
      const now = new Date();
      const lower = new Date(now.getTime() - 24 * 3600 * 1000);
      const allVideos = Array.isArray(payload?.videos) ? payload.videos : [];

      const parsedVideos = allVideos
        .map((video) => {
          const published = parsePublishedDate(video);
          return { ...video, _published: published };
        })
        .filter((video) => video._published && !Number.isNaN(video._published.getTime()));

      const removedByShortRules = [];
      const keptAfterShortFilter = [];
      parsedVideos.forEach((video) => {
        const shortDecision = isLikelyShort(video);
        video._shortDecision = shortDecision;
        if (shortDecision.isShort) {
          removedByShortRules.push(video);
        } else {
          keptAfterShortFilter.push(video);
        }
      });

      const videos = keptAfterShortFilter
        .filter((video) => video._published >= lower && video._published <= now)
        .sort((a, b) => b._published.getTime() - a._published.getTime());

      console.log('[YouTube debug] total videos in json:', allVideos.length);
      console.log('[YouTube debug] after hard shorts filter:', keptAfterShortFilter.length);
      console.log('[YouTube debug] after 24h filter:', videos.length);
      console.log('[YouTube debug] first 10 kept titles:', videos.slice(0, 10).map((v) => v.title || 'Utan titel'));
      console.log('[YouTube debug] first 10 removed titles with reason:', removedByShortRules.slice(0, 10).map((v) => ({
        title: v.title || 'Utan titel',
        reason: v?._shortDecision?.reason || 'unknown',
      })));

      const label = byId('youtube-range-label');
      if (label) {
        label.textContent = `Hämtade ${allVideos.length} totalt • ${keptAfterShortFilter.length} efter shorts-filter • ${videos.length} senaste 24h (${formatStockholmDateTime(lower)}–${formatStockholmDateTime(now)}, ${STOCKHOLM_TZ}).`;
      }

      if (!videos.length) {
        root.innerHTML = "<p class='muted'>Inga vanliga videos senaste 24h just nu.</p>";
        return;
      }

      root.innerHTML = '';
      const list = document.createElement('div');
      list.className = 'item-list';
      if (typeof youtubeUi.createVideoCard !== 'function') {
        root.innerHTML = "<p class='muted'>YouTube-kort kunde inte laddas (saknad helper).</p>";
        return;
      }
      videos.forEach((video) => list.appendChild(youtubeUi.createVideoCard(video)));
      root.appendChild(list);
    } catch (error) {
      root.innerHTML = `<p class='muted'>Kunde inte läsa YouTube-listan: ${error.message}</p>`;
    }
  }

  function isNightByClock(now) {
    const stockholmHour = Number(new Intl.DateTimeFormat('en-GB', {
      timeZone: STOCKHOLM_TZ,
      hour: '2-digit',
      hour12: false,
    }).format(now));
    return stockholmHour >= 20 || stockholmHour < 6;
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
  }

  function computeThemeMode(weatherData) {
    const mode = localStorage.getItem(THEME_KEY) || 'auto';
    if (mode === 'light' || mode === 'dark') return mode;

    const now = new Date();
    const today = (weatherData?.daily_10 || [])[0] || {};
    const sunset = parseISO(today.sunset);
    if (sunset) {
      return now >= sunset ? 'dark' : 'light';
    }
    return isNightByClock(now) ? 'dark' : 'light';
  }

  function ensureThemeToggle(weatherData) {
    const topbar = document.querySelector('.topbar');
    if (!topbar || byId('theme-toggle')) return;

    const button = document.createElement('button');
    button.id = 'theme-toggle';
    button.className = 'theme-toggle';
    const mode = localStorage.getItem(THEME_KEY) || 'auto';
    button.textContent = `Tema: ${mode}`;
    button.type = 'button';

    button.addEventListener('click', () => {
      const current = localStorage.getItem(THEME_KEY) || 'auto';
      const next = current === 'auto' ? 'light' : current === 'light' ? 'dark' : 'auto';
      localStorage.setItem(THEME_KEY, next);
      button.textContent = `Tema: ${next}`;
      applyTheme(computeThemeMode(weatherData));
    });

    topbar.appendChild(button);
  }

  async function initTheme() {
    let weatherData = null;
    try {
      const response = await fetch(WEATHER_DATA_PATH, { cache: 'no-store' });
      if (response.ok) weatherData = await response.json();
    } catch (_) {}

    applyTheme(computeThemeMode(weatherData));
    ensureThemeToggle(weatherData);
  }

  renderYoutubeLatest();
  initTheme();
})();
