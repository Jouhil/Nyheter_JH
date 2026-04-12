# Daglig briefing med GitHub Actions + GitHub Pages

Den här lösningen bygger en **automatisk daglig briefing** som publiceras som statisk HTML via GitHub Pages.
Ingen dator behöver vara igång när den körs.

## Vad version 1.2 innehåller

- Väder från SMHI (standard: Stockholm)
- Senaste YouTube-videos från `youtube_prenumerationer.opml`
- Svensk videosammanfattning (ca 2 meningar) per YouTube-post
- Dagliga nyheter via öppna RSS-flöden (AI, teknik, Sverige)
- Statisk och mobilvänlig sida i `docs/index.html`
- Debug-läge (`DEBUG_BRIEFING=1`) med detaljerade hämtloggar och debugfiler
- Validering som failar bygget om resultatet blir för tomt

## Projektstruktur

```text
.
├─ .github/workflows/daily_briefing.yml
├─ debug/                              # skapas i debug-läge
├─ docs/
│  ├─ index.html
│  └─ style.css
├─ helpers/
│  ├─ feeds.py
│  ├─ html_builder.py
│  ├─ news.py
│  └─ smhi.py
├─ generate_briefing.py
├─ requirements.txt
└─ youtube_prenumerationer.opml
```

## Så fungerar flödet

1. GitHub Actions startar varje morgon (och kan köras manuellt).
2. `generate_briefing.py` hämtar:
   - väder från SMHI,
   - senaste YouTube-poster från OPML-feeds,
   - RSS-nyheter från öppna källor.
3. Scriptet validerar minimikrav:
   - minst ett vädervärde,
   - minst 5 YouTube-poster,
   - minst 3 nyhetsposter totalt.
4. Scriptet bygger `docs/index.html`.
5. Workflow committar uppdaterad `docs/index.html` tillbaka till repot.
6. GitHub Pages serverar innehållet från `docs/`.

## Köra lokalt

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
DEBUG_BRIEFING=1 python -u generate_briefing.py
```

## Debugläge

Sätt `DEBUG_BRIEFING=1` för att få:

- URL som testas
- HTTP-statuskod
- Content-Type
- Antal bytes
- Antal parsade poster
- Första 1–2 titlar
- Debugfiler i `debug/`

Exempel på debugfiler:

- `debug/smhi_response.json`
- `debug/youtube_feed_sample.xml`
- `debug/news_ai_sample.xml`
- `debug/parsed_youtube.json`
- `debug/parsed_news.json`

## GitHub Actions

Workflow-fil: `.github/workflows/daily_briefing.yml`

- `schedule`: kör varje dag 05:30 UTC
- `workflow_dispatch`: manuell körning via GitHub UI
- Skriver ut Python-version, arbetskatalog och fil-listning
- Kör `python -u generate_briefing.py` med `DEBUG_BRIEFING=1`
- Laddar upp `debug/` som artifact även när bygget misslyckas
- Committar `docs/index.html` om den ändrats och valideringen passerar

## Anpassning

### Byta plats för SMHI

I `generate_briefing.py`, uppdatera:

```python
LOCATION = {
    "name": "Stockholm",
    "lat": 59.3293,
    "lon": 18.0686,
}
```

### Byta/utöka nyhetskällor

Uppdatera `NEWS_FEEDS` i `helpers/news.py`.

### Byta YouTube-kanaler

Redigera `youtube_prenumerationer.opml`.
