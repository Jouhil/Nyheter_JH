(function () {
  const ui = window.YouTubeBriefing || {};
  const THEME_KEY = 'briefing-theme-mode';

  const byId = (id) => document.getElementById(id);

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

  function renderHiddenChannels() {
    const root = byId('hidden-channels-root');
    if (!root) return;

    const readHiddenChannels = typeof ui.readHiddenChannels === 'function' ? ui.readHiddenChannels : () => [];
    const unhideChannel = typeof ui.unhideChannel === 'function' ? ui.unhideChannel : () => {};
    const clearHiddenChannels = typeof ui.clearHiddenChannels === 'function' ? ui.clearHiddenChannels : () => {};
    const hiddenChannels = readHiddenChannels();

    root.innerHTML = '';

    if (!hiddenChannels.length) {
      const empty = document.createElement('p');
      empty.className = 'muted';
      empty.textContent = 'Inga lokalt dolda kanaler.';
      root.appendChild(empty);
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
      resetBtn.addEventListener('click', () => {
        unhideChannel(channel);
        renderHiddenChannels();
      });

      li.append(label, resetBtn);
      list.appendChild(li);
    });

    const resetAllBtn = document.createElement('button');
    resetAllBtn.type = 'button';
    resetAllBtn.className = 'yt-reset-all';
    resetAllBtn.textContent = 'Återställ alla';
    resetAllBtn.addEventListener('click', () => {
      clearHiddenChannels();
      renderHiddenChannels();
    });

    root.append(list, resetAllBtn);
  }

  applyTheme();
  renderHiddenChannels();
})();
