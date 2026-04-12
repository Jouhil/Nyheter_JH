(function () {
  const STOCKHOLM_TZ = 'Europe/Stockholm';
  const HIDDEN_CHANNELS_KEY = 'briefing-hidden-youtube-channels-v1';

  function parseISO(value) {
    if (!value) return null;
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function parsePublishedDate(video) {
    const unix = Number(video?.published_at_unix);
    if (Number.isFinite(unix) && unix > 0) {
      const unixMs = unix > 1e12 ? unix : unix * 1000;
      const unixDate = new Date(unixMs);
      if (!Number.isNaN(unixDate.getTime())) return unixDate;
    }
    return parseISO(video?.published_at_utc)
      || parseISO(video?.published_at)
      || parseISO(video?.published)
      || parseISO(video?.published_at_iso);
  }

  function formatStockholmDateTime(date) {
    return new Intl.DateTimeFormat('sv-SE', {
      timeZone: STOCKHOLM_TZ,
      hour: '2-digit',
      minute: '2-digit',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(date);
  }

  function buildVideoUrl(video) {
    const videoId = typeof video?.video_id === 'string' ? video.video_id.trim() : '';
    if (videoId) return `https://youtu.be/${videoId}`;
    return video?.url || '#';
  }

  async function copyToClipboard(text) {
    if (!text) return false;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch (_) {}

    const area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.position = 'absolute';
    area.style.left = '-9999px';
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(area);
    return ok;
  }

  function normalizeChannelName(value) {
    return String(value || '').trim();
  }

  function normalizeChannelKey(value) {
    return normalizeChannelName(value).toLocaleLowerCase('sv-SE');
  }

  function readHiddenChannels() {
    try {
      const raw = localStorage.getItem(HIDDEN_CHANNELS_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return [];
      const deduped = [];
      const seen = new Set();
      parsed.forEach((entry) => {
        const name = normalizeChannelName(entry);
        const key = normalizeChannelKey(name);
        if (!name || seen.has(key)) return;
        seen.add(key);
        deduped.push(name);
      });
      return deduped;
    } catch (_) {
      return [];
    }
  }

  function writeHiddenChannels(channels) {
    localStorage.setItem(HIDDEN_CHANNELS_KEY, JSON.stringify(channels));
  }

  function hideChannel(channelName) {
    const name = normalizeChannelName(channelName);
    if (!name) return;
    const channels = readHiddenChannels();
    const exists = channels.some((entry) => normalizeChannelKey(entry) === normalizeChannelKey(name));
    if (exists) return;
    channels.push(name);
    channels.sort((a, b) => a.localeCompare(b, 'sv-SE', { sensitivity: 'base' }));
    writeHiddenChannels(channels);
  }

  function unhideChannel(channelName) {
    const target = normalizeChannelKey(channelName);
    if (!target) return;
    const next = readHiddenChannels().filter((entry) => normalizeChannelKey(entry) !== target);
    writeHiddenChannels(next);
  }

  function clearHiddenChannels() {
    localStorage.removeItem(HIDDEN_CHANNELS_KEY);
  }

  function isChannelHidden(channelName, hiddenChannels) {
    const target = normalizeChannelKey(channelName);
    if (!target) return false;
    return hiddenChannels.some((entry) => normalizeChannelKey(entry) === target);
  }

  function createVideoCard(video, options = {}) {
    const onHideChannel = typeof options.onHideChannel === 'function' ? options.onHideChannel : null;
    const videoLink = buildVideoUrl(video);
    const article = document.createElement('article');
    article.className = 'video-item';

    const thumbWrap = document.createElement('div');
    thumbWrap.className = 'thumb-link';

    const img = document.createElement('img');
    img.className = 'video-thumb';
    img.loading = 'lazy';
    img.referrerPolicy = 'no-referrer';
    img.src = video.thumbnail || (video.video_id ? `https://i.ytimg.com/vi/${video.video_id}/hqdefault.jpg` : 'https://i.ytimg.com/vi_webp/default/hqdefault.webp');
    img.alt = `Thumbnail för ${video.title || 'video'}`;
    thumbWrap.appendChild(img);

    const content = document.createElement('div');
    content.className = 'video-content';

    const title = document.createElement('h3');
    title.className = 'video-title';
    title.textContent = video.title || 'Utan titel';

    const meta = document.createElement('div');
    meta.className = 'meta';
    const published = parsePublishedDate(video);
    meta.textContent = `${video.channel || 'Okänd kanal'} • ${published ? formatStockholmDateTime(published) : 'Okänd tid'}`;

    const summary = document.createElement('p');
    summary.className = 'summary';
    summary.textContent = video.summary || 'Sammanfattning saknas.';

    const links = document.createElement('div');
    links.className = 'video-links';
    const openBtn = document.createElement('a');
    openBtn.className = 'yt-open';
    openBtn.href = videoLink;
    openBtn.target = '_blank';
    openBtn.rel = 'noopener noreferrer';
    openBtn.referrerPolicy = 'no-referrer';
    openBtn.textContent = 'Öppna video';
    links.append(openBtn);

    const copyBtn = document.createElement('button');
    copyBtn.type = 'button';
    copyBtn.className = 'yt-copy';
    copyBtn.textContent = 'Kopiera länk';
    copyBtn.addEventListener('click', async () => {
      const ok = await copyToClipboard(videoLink);
      const original = copyBtn.textContent;
      copyBtn.textContent = ok ? 'Kopierad!' : 'Kunde inte kopiera';
      setTimeout(() => {
        copyBtn.textContent = original;
      }, 1200);
    });
    links.append(copyBtn);

    if (onHideChannel) {
      const hideBtn = document.createElement('button');
      hideBtn.type = 'button';
      hideBtn.className = 'yt-hide';
      hideBtn.textContent = 'Dölj kanal';
      hideBtn.addEventListener('click', () => {
        onHideChannel(video.channel || 'Okänd kanal');
      });
      links.append(hideBtn);
    }

    content.append(title, meta, summary, links);
    article.append(thumbWrap, content);
    return article;
  }

  window.YouTubeBriefing = {
    STOCKHOLM_TZ,
    HIDDEN_CHANNELS_KEY,
    parsePublishedDate,
    formatStockholmDateTime,
    readHiddenChannels,
    hideChannel,
    unhideChannel,
    clearHiddenChannels,
    isChannelHidden,
    createVideoCard,
  };
})();
