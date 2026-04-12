(function () {
  const STOCKHOLM_TZ = 'Europe/Stockholm';

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

  function createVideoCard(video) {
    const article = document.createElement('article');
    article.className = 'video-item';

    const anchorThumb = document.createElement('a');
    anchorThumb.href = video.url || '#';
    anchorThumb.target = '_blank';
    anchorThumb.rel = 'noopener noreferrer';
    anchorThumb.className = 'thumb-link';

    const img = document.createElement('img');
    img.className = 'video-thumb';
    img.loading = 'lazy';
    img.referrerPolicy = 'no-referrer';
    img.src = video.thumbnail || (video.video_id ? `https://i.ytimg.com/vi/${video.video_id}/hqdefault.jpg` : 'https://i.ytimg.com/vi_webp/default/hqdefault.webp');
    img.alt = `Thumbnail för ${video.title || 'YouTube-video'}`;
    anchorThumb.appendChild(img);

    const content = document.createElement('div');
    content.className = 'video-content';

    const title = document.createElement('a');
    title.className = 'video-title';
    title.href = video.url || '#';
    title.target = '_blank';
    title.rel = 'noopener noreferrer';
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
    openBtn.href = video.url || '#';
    openBtn.target = '_blank';
    openBtn.rel = 'noopener noreferrer';
    openBtn.textContent = 'Öppna i YouTube';
    links.appendChild(openBtn);

    content.append(title, meta, summary, links);
    article.append(anchorThumb, content);
    return article;
  }

  window.YouTubeBriefing = {
    STOCKHOLM_TZ,
    parsePublishedDate,
    formatStockholmDateTime,
    createVideoCard,
  };
})();
