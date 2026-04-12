(function () {
  const YOUTUBE_DATA_PATH = 'data/youtube-latest.json';
  const WEATHER_DATA_PATH = 'data/weather-goteborg.json';
  const THEME_KEY = 'briefing-theme-mode';
  const youtubeUi = window.YouTubeBriefing || {};
  const STOCKHOLM_TZ = youtubeUi?.STOCKHOLM_TZ || 'Europe/Stockholm';

  const byId = (id) => document.getElementById(id);

  function renderHiddenChannelsPanel({ root, hiddenChannels, onResetOne, onResetAll }) {
    let panel = byId('youtube-hidden-panel');
    if (!panel) {
      panel = document.createElement('section');
      panel.id = 'youtube-hidden-panel';
      panel.className = 'youtube-hidden-panel';
      root.parentNode?.insertBefore(panel, root);
    }

    panel.innerHTML = '';
    const heading = document.createElement('h3');
    heading.className = 'youtube-hidden-title';
    heading.textContent = 'Visa dolda kanaler (lokalt)';
    panel.appendChild(heading);

    const help = document.createElement('p');
    help.className = 'muted youtube-hidden-help';
    help.textContent = 'Döljer endast i denna browser via localStorage. Inga filer i repot ändras.';
    panel.appendChild(help);

    if (!hiddenChannels.length) {
      const empty = document.createElement('p');
      empty.className = 'muted';
      empty.textContent = 'Inga lokalt dolda kanaler.';
      panel.appendChild(empty);
      return;
    }

    const list = document.createElement('ul');
    list.className = 'youtube-hidden-list';
    hiddenChannels.forEach((channel) => {
      const li = document.createElement('li');
      li.className = 'youtube-hidden-item';
      const label = document.createElement('span');
      label.textContent = channel;
      const resetBtn = document.createElement('button');
      resetBtn.type = 'button';
      resetBtn.className = 'yt-reset';
      resetBtn.textContent = 'Återställ';
      resetBtn.addEventListener('click', () => onResetOne(channel));
      li.append(label, resetBtn);
      list.appendChild(li);
    });
    panel.appendChild(list);

    const resetAllBtn = document.createElement('button');
    resetAllBtn.type = 'button';
    resetAllBtn.className = 'yt-reset-all';
    resetAllBtn.textContent = 'Återställ alla';
    resetAllBtn.addEventListener('click', onResetAll);
    panel.appendChild(resetAllBtn);
  }

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
    const softSignals = [];
    const url = String(video?.url || '').toLowerCase();
    if (url.includes('/shorts/')) {
      hardSignals.push('url_contains_/shorts/');
    }

    const rawDuration = video?.duration;
    const duration = rawDuration === null || rawDuration === undefined || rawDuration === ''
      ? Number.NaN
      : Number(rawDuration);
    if (Number.isFinite(duration) && duration > 0 && duration <= 70) {
      hardSignals.push('duration_<=_70s');
    }

    const title = String(video?.title || '').toLowerCase();
    if (/#shorts\b/.test(title)) {
      hardSignals.push('title_contains_#shorts');
    }
    if (/\bshorts\b/.test(title)) {
      hardSignals.push('title_contains_word_shorts');
    }

    const rawSignals = Array.isArray(video?.raw_short_signals) ? video.raw_short_signals : [];
    const hardSignalKeys = new Set([
      'url_contains_/shorts/',
      'title_contains_#shorts',
      'title_contains_word_shorts',
      'duration_<=_70s',
      'source_contains_short_hashtag',
    ]);
    const backendHard = rawSignals.filter((signal) => hardSignalKeys.has(String(signal)));
    if (backendHard.length) {
      hardSignals.push(`backend_hard:${backendHard[0]}`);
    }

    const summarySourceText = String(video?.summary_source_text || '');
    const combinedText = `${video?.title || ''} ${video?.summary || ''} ${summarySourceText}`.toLowerCase();
    const textLength = Number(video?.text_length);
    const thumbWidth = Number(video?.thumbnail_width);
    const thumbHeight = Number(video?.thumbnail_height);

    if (video?.is_short_candidate) softSignals.push('is_short_candidate');
    if (rawSignals.some((signal) => String(signal).includes('title_or_text_short_hint'))) {
      softSignals.push('title_or_text_short_hint');
    }
    if (rawSignals.some((signal) => String(signal).includes('feed_metadata_short_hint'))) {
      softSignals.push('feed_metadata_short_hint');
    }
    if (/#(?:shorts|ytshorts)\b/.test(combinedText)) {
      softSignals.push('hashtags_in_text');
    }
    if (Number.isFinite(textLength) && textLength > 0 && textLength <= 80) {
      softSignals.push('very_short_source_text');
    }
    if (
      /[\u{1F300}-\u{1FAFF}]/u.test(summarySourceText)
      || /(?:follow|subscribe|watch till the end|link in bio|part\s*\d+)/i.test(summarySourceText)
    ) {
      softSignals.push('emoji_or_social_caption_style');
    }
    if (
      Number.isFinite(thumbWidth)
      && Number.isFinite(thumbHeight)
      && thumbWidth > 0
      && thumbHeight > 0
      && thumbHeight > thumbWidth
    ) {
      softSignals.push('portrait_thumbnail');
    }

    const softScore = new Set(softSignals).size;
    const hardMatch = hardSignals.length > 0;
    const softMatch = !hardMatch && softScore >= 2;

    return {
      isShort: hardMatch || softMatch,
      isCandidate: hardMatch || softScore > 0,
      hardSignals: Array.from(new Set(hardSignals)),
      softSignals: Array.from(new Set(softSignals)),
      softScore,
      reason: hardMatch ? `hard:${hardSignals[0]}` : softMatch ? `soft_score:${softScore}` : null,
      reasonType: hardMatch ? 'hard' : softMatch ? 'soft' : null,
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

      const removedByHardShortRules = [];
      const removedBySoftShortRules = [];
      const keptAfterShortFilter = [];
      parsedVideos.forEach((video) => {
        const shortDecision = isLikelyShort(video);
        video._shortDecision = shortDecision;
        if (shortDecision.isShort) {
          if (shortDecision.reasonType === 'hard') {
            removedByHardShortRules.push(video);
          } else {
            removedBySoftShortRules.push(video);
          }
        } else {
          keptAfterShortFilter.push(video);
        }
      });

      const videos24h = keptAfterShortFilter
        .filter((video) => video._published >= lower && video._published <= now)
        .sort((a, b) => b._published.getTime() - a._published.getTime());

      const readHiddenChannels = typeof youtubeUi.readHiddenChannels === 'function'
        ? youtubeUi.readHiddenChannels
        : () => [];
      const isChannelHidden = typeof youtubeUi.isChannelHidden === 'function'
        ? youtubeUi.isChannelHidden
        : () => false;
      const hideChannel = typeof youtubeUi.hideChannel === 'function'
        ? youtubeUi.hideChannel
        : () => {};
      const unhideChannel = typeof youtubeUi.unhideChannel === 'function'
        ? youtubeUi.unhideChannel
        : () => {};
      const clearHiddenChannels = typeof youtubeUi.clearHiddenChannels === 'function'
        ? youtubeUi.clearHiddenChannels
        : () => {};
      const hiddenChannels = readHiddenChannels();
      const videos = videos24h.filter((video) => !isChannelHidden(video.channel, hiddenChannels));
      const hiddenByLocal = videos24h.length - videos.length;

      console.log('[YouTube debug] total videos in json:', allVideos.length);
      console.log('[YouTube debug] removed by hard short rules:', removedByHardShortRules.length);
      console.log('[YouTube debug] removed by soft score rules:', removedBySoftShortRules.length);
      console.log('[YouTube debug] kept after short filter:', keptAfterShortFilter.length);
      console.log('[YouTube debug] after 24h filter:', videos.length);
      console.log('[YouTube debug] first 15 removed titles with reason:', [...removedByHardShortRules, ...removedBySoftShortRules].slice(0, 15).map((v) => ({
        title: v.title || 'Utan titel',
        reason: v?._shortDecision?.reason || 'unknown',
        hardSignals: v?._shortDecision?.hardSignals || [],
        softSignals: v?._shortDecision?.softSignals || [],
        softScore: v?._shortDecision?.softScore || 0,
      })));
      console.log('[YouTube debug] hidden by local channel rules:', hiddenByLocal);
      console.log('[YouTube debug] first 15 kept titles:', videos.slice(0, 15).map((v) => v.title || 'Utan titel'));

      const label = byId('youtube-range-label');
      if (label) {
        label.textContent = `Hämtade ${allVideos.length} totalt • ${removedByHardShortRules.length} borttagna som tydliga shorts • ${removedBySoftShortRules.length} borttagna som short-liknande • ${keptAfterShortFilter.length} kvar efter shorts-filter • ${videos24h.length} senaste 24h • ${hiddenByLocal} lokalt dolda via kanal • ${videos.length} visas (${formatStockholmDateTime(lower)}–${formatStockholmDateTime(now)}, ${STOCKHOLM_TZ}).`;
      }

      const rerender = () => renderYoutubeLatest();
      renderHiddenChannelsPanel({
        root,
        hiddenChannels,
        onResetOne: (channel) => {
          unhideChannel(channel);
          rerender();
        },
        onResetAll: () => {
          clearHiddenChannels();
          rerender();
        },
      });

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
      videos.forEach((video) => {
        list.appendChild(youtubeUi.createVideoCard(video, {
          onHideChannel: (channel) => {
            hideChannel(channel);
            rerender();
          },
        }));
      });
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
