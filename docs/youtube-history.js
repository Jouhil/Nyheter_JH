(function () {
  const INDEX_PATH = 'data/youtube-history/index.json';
  const HISTORY_BASE = 'data/youtube-history';
  const ui = window.YouTubeBriefing || {};
  const THEME_KEY = 'briefing-theme-mode';

  const byId = (id) => document.getElementById(id);

  function renderHiddenChannelsPanel({ root, hiddenChannels, onResetOne, onResetAll }) {
    let panel = byId('history-hidden-panel');
    if (!panel) {
      panel = document.createElement('section');
      panel.id = 'history-hidden-panel';
      panel.className = 'youtube-hidden-panel';
      root.parentNode?.insertBefore(panel, root);
    }

    panel.innerHTML = '';
    const heading = document.createElement('h3');
    heading.className = 'youtube-hidden-title';
    heading.textContent = 'Visa dolda kanaler (lokalt)';
    panel.appendChild(heading);

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

  function createDateAnchor(dateValue) {
    const a = document.createElement('a');
    a.className = 'history-date-anchor';
    a.href = `#day-${dateValue}`;
    a.textContent = dateValue;
    return a;
  }

  async function fetchJson(path) {
    const response = await fetch(path, { cache: 'no-store' });
    if (!response.ok) {
      throw new Error(`Kunde inte läsa ${path} (${response.status})`);
    }
    return response.json();
  }

  async function renderHistory() {
    const datesRoot = byId('history-date-list');
    const daysRoot = byId('history-days');
    if (!datesRoot || !daysRoot) return;

    try {
      const indexPayload = await fetchJson(INDEX_PATH);
      const dates = Array.isArray(indexPayload?.dates) ? indexPayload.dates : [];
      if (!dates.length) {
        datesRoot.innerHTML = "<p class='muted'>Ingen historik finns ännu.</p>";
        daysRoot.innerHTML = "<p class='muted'>Ingen historik finns ännu.</p>";
        return;
      }

      datesRoot.innerHTML = '';
      const nav = document.createElement('div');
      nav.className = 'history-date-nav';
      dates.forEach((dateValue) => nav.appendChild(createDateAnchor(dateValue)));
      datesRoot.appendChild(nav);

      daysRoot.innerHTML = '';
      const dayPayloads = await Promise.all(dates.map((dateValue) => fetchJson(`${HISTORY_BASE}/${dateValue}.json`)));

      const readHiddenChannels = typeof ui.readHiddenChannels === 'function' ? ui.readHiddenChannels : () => [];
      const isChannelHidden = typeof ui.isChannelHidden === 'function' ? ui.isChannelHidden : () => false;
      const unhideChannel = typeof ui.unhideChannel === 'function' ? ui.unhideChannel : () => {};
      const clearHiddenChannels = typeof ui.clearHiddenChannels === 'function' ? ui.clearHiddenChannels : () => {};
      const hiddenChannels = readHiddenChannels();

      renderHiddenChannelsPanel({
        root: daysRoot,
        hiddenChannels,
        onResetOne: (channel) => {
          unhideChannel(channel);
          renderHistory();
        },
        onResetAll: () => {
          clearHiddenChannels();
          renderHistory();
        },
      });

      dayPayloads.forEach((payload) => {
        const dateValue = payload?.date || 'okänt-datum';
        const section = document.createElement('section');
        section.className = 'history-day-section';
        section.id = `day-${dateValue}`;

        const heading = document.createElement('h3');
        heading.className = 'history-day-heading';
        heading.textContent = dateValue;

        const videos = (Array.isArray(payload?.videos) ? payload.videos : [])
          .filter((video) => !isChannelHidden(video.channel, hiddenChannels));
        section.appendChild(heading);

        if (!videos.length) {
          const empty = document.createElement('p');
          empty.className = 'muted';
          empty.textContent = 'Inga vanliga YouTube-videor sparades denna dag.';
          section.appendChild(empty);
        } else if (typeof ui.createVideoCard === 'function') {
          const list = document.createElement('div');
          list.className = 'item-list';
          videos.forEach((video) => list.appendChild(ui.createVideoCard(video)));
          section.appendChild(list);
        }

        daysRoot.appendChild(section);
      });
    } catch (error) {
      datesRoot.innerHTML = `<p class='muted'>Kunde inte läsa datumlistan: ${error.message}</p>`;
      daysRoot.innerHTML = `<p class='muted'>Kunde inte läsa historikfiler: ${error.message}</p>`;
    }
  }

  function applyTheme() {
    const mode = localStorage.getItem(THEME_KEY) || 'auto';
    let theme = mode;
    if (mode === 'auto') {
      const hour = Number(new Intl.DateTimeFormat('en-GB', {
        timeZone: 'Europe/Stockholm',
        hour: '2-digit',
        hour12: false,
      }).format(new Date()));
      theme = (hour >= 20 || hour < 6) ? 'dark' : 'light';
    }
    document.documentElement.setAttribute('data-theme', theme);
  }

  applyTheme();
  renderHistory();
})();
