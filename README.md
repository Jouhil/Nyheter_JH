# Daglig briefing med GitHub Actions + GitHub Pages

Den här lösningen bygger en **automatisk daglig briefing** som publiceras som statisk HTML via GitHub Pages.
Ingen dator behöver vara igång när den körs.

## Vad version 1.1 innehåller

- Väder från SMHI (standard: Stockholm)
- Senaste YouTube-videos från `youtube_prenumerationer.opml`
- Svensk videosammanfattning (ca 2 meningar) per YouTube-post
- Dagliga nyheter via öppna RSS-flöden (AI, teknik, Sverige)
- Statisk och mobilvänlig sida i `docs/index.html`
- Automatisk uppdatering varje morgon via GitHub Actions

## Projektstruktur

```text
.
├─ .github/workflows/daily_briefing.yml
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
3. Scriptet bygger `docs/index.html`.
4. Workflow committar uppdaterad `docs/index.html` tillbaka till repot.
5. GitHub Pages serverar innehållet från `docs/`.

## Köra lokalt

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python generate_briefing.py
```

Öppna sedan `docs/index.html` i valfri webbläsare.

## GitHub Actions

Workflow-fil: `.github/workflows/daily_briefing.yml`

- `schedule`: kör varje dag 05:30 UTC
- `workflow_dispatch`: manuell körning via GitHub UI
- Installerar Python + dependencies
- Kör `python generate_briefing.py`
- Committar `docs/index.html` om den ändrats

## GitHub Pages (aktivering)

1. Gå till repo → **Settings** → **Pages**.
2. Under **Build and deployment**, välj:
   - **Source**: `Deploy from a branch`
   - **Branch**: `main` (eller din standard-branch)
   - **Folder**: `/docs`
3. Spara.
4. Efter första workflow-körningen publiceras sidan på din GitHub Pages-URL.

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

## Förslag för version 2

- **Google Calendar**
  - Lägg till kalender-sammanfattning per dag (t.ex. nästa 3 möten)
  - Rendera i egen sektion i HTML
- **Mejlutskick**
  - Lägg till jobb i workflow som skickar HTML eller sammanfattning via mail-API
- **Personliga ämnen/filter**
  - Lägg konfig i JSON/YAML för prioriterade kanaler och nyhetsämnen
  - Lägg in vikter/taggar och visa "Dagens fokus"

## Robusthet i lösningen

- HTTP-anrop använder Python standardbibliotek med tydlig timeout och egen User-Agent
- Proxy-bypass används i hämtningarna för att undvika 403 tunnel-fel i vissa miljöer
- Nätverksfel fångas så att hela bygget inte kraschar
- Trasiga feeds hoppas över istället för att stoppa processen
- Datum normaliseras och sorteras konsekvent
- OPML-parser hanterar dåliga tecken och har regex-fallback om XML är trasig
- Workflown loggar antal hittade OPML-feeds, videos, nyheter per kategori och SMHI-status
