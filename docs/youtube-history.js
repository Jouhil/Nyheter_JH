(function () {
  const INDEX_PATH = 'data/youtube-history/index.json';
  const HISTORY_BASE = 'data/youtube-history';
  const ui = window.YouTubeBriefing || {};
  const THEME_KEY = 'briefing-theme-mode';

  const byId = (id) => document.getElementById(id);

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

      dayPayloads.forEach((payload) => {
        const dateValue = payload?.date || 'okänt-datum';
        const section = document.createElement('section');
        section.className = 'history-day-section';
        section.id = `day-${dateValue}`;

        const heading = document.createElement('h3');
        heading.className = 'history-day-heading';
        heading.textContent = dateValue;

        const videos = Array.isArray(payload?.videos) ? payload.videos : [];
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
