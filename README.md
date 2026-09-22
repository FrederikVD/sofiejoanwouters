# sofiejoanwouters.com

Statische site van Sofie Joan Wouters. Eén bestand: `index.html`. De speellijst komt uit een Google Sheet (of, zolang die niet gekoppeld is, uit `speellijst.csv`).

## Bestanden

- `index.html`: de site (home + WAAR & WANNEER via `#waar`)
- `speellijst.csv`: de speellijst, zelfde kolommen als de Google Sheet
- `scripts/check.py`: leest de agenda's van de vijf gezelschappen en vergelijkt met de speellijst
- `.github/workflows/speellijst-check.yml`: draait dat script elke maandag en maakt een GitHub-issue met de nieuwe regels
- `CNAME`: het domein voor GitHub Pages

## Regels voor de weergave

- Schoolvoorstellingen: uren worden nooit getoond. Staat er `2x` of twee uren in de kolom `uur`, dan toont de site "schoolvoorstellingen" (meervoud), anders "schoolvoorstelling".
- Publieke voorstellingen (`tickets` of `premiere`): het uur wordt wel getoond, naast de ticketlink.
- Een dag met een schoolvoorstelling én een avondvoorstelling: twee regels in de sheet.

## Sheet koppelen

1. Google Sheet aanmaken, `speellijst.csv` importeren.
2. Bestand > Delen > Publiceren op het web > CSV, link kopiëren.
3. In `index.html`: `const SHEET_CSV_URL = "…";`
4. In GitHub: Settings > Secrets and variables > Actions > Variables > New variable: naam `SHEET_CSV_URL`, waarde die link. Zo vergelijkt de wekelijkse check met de sheet en niet met het csv-bestand.

## Wekelijkse check

Maandagochtend leest de Action de vijf agenda's. Nieuwe speelmomenten komen als issue binnen (GitHub mailt dat automatisch). Regels kopiëren, in de sheet plakken, status op `ok`. Manueel starten kan via Actions > Wekelijkse check speeldata > Run workflow.
