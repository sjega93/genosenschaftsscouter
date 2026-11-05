# Genosenschaftsscouter

Scrapes apartment listings from Swiss housing co-operative (Genossenschaft)
websites and writes them to a flat text file — one pipe-delimited line per
listing.

Co-ops frequently delegate their listings to a property manager or an external
listing widget, so the scraper crawls a limited number of pages from the given
URL (following links that look like "properties" / "vacancies") until it finds
a listing widget it knows.

## Supported listing widgets

- **newhome.ch** "Partner Trefferliste" (`resolvers/newhome.py`)
- **newhome.ch detail links** — co-op pages that render their own cards and link to newhome.ch detail pages (`resolvers/newhome_links.py`)
- **Flatfox** embeds (`resolvers/flatfox.py`)
- **Statamic/Nuxt sites** on the Geissenstein runway module — listings parsed from the embedded SSR payload (`resolvers/statamic.py`)

## Requirements

- [uv](https://docs.astral.sh/uv/) — used as the Python manager (no `python`/`pip` needed)

## Setup

```bash
uv sync   # resolves the lockfile and creates .venv
```

Dependencies are pinned in `uv.lock`, declared in `pyproject.toml`.

## Usage

Scan a single co-op site:

```bash
uv run apartment_scraper.py <url> [-o OUTPUT]
```

- `<url>` — a listing page, or any page that links to one (the scraper crawls
  up to 8 pages looking for a known widget)
- `-o OUTPUT` — output file path (default: `apartments.txt`)

Example:

```bash
uv run apartment_scraper.py https://example-genossenschaft.ch/wohnungen -o out.txt
```

Exit code is 1 when no widget is found or a network error occurs; errors go to
stderr.

### Scan all co-ops

Without a URL, the scraper scans every co-op in `coops.txt` concurrently
(8 workers) and writes one combined file:

```bash
uv run apartment_scraper.py -o apartments.txt
```

Each co-op that has listings gets a `# <url> (N flat(s), source: <resolver>)`
header line above its entries; per-site progress and failures go to stderr.

`coops.txt` is a snapshot of the co-op sites linked from
[genossenschaftsradar.ch](https://genossenschaftsradar.ch/genossenschaften)
— one URL per line, `#` comments. Edit it by hand or refresh it:

```bash
uv run apartment_scraper.py --update-coop-list
```

## Output format

One line per apartment, pipe-delimited:

```
title | subtitle | address | price | size | availability | detail_url
```

Example:

```
4-Zi-Wohnung 5. OG | Bächliwis 22, 8184 Bachenbülach | CHF 1’465/Monat | 72 m² | Bezug: 01.12.2026 | https://www.newhome.ch/...
```

Writes "No apartments currently listed." when the widget is found but empty.

## Project layout

```
apartment_scraper.py   # entry point: discovery crawl + output writer
coop_list.py           # default co-op URL list (coops.txt) + radar-page refresh
coops.txt              # ~160 Swiss co-op sites, one URL per line
resolvers/
  common.py            # shared HTTP/fetch helpers
  newhome.py           # newhome.ch Trefferliste resolver
  newhome_links.py     # pages linking to newhome.ch detail pages
  flatfox.py           # Flatfox resolver
  statamic.py          # Statamic/Nuxt SSR-payload resolver
  __init__.py          # RESOLVERS registry
pyproject.toml / uv.lock
```

## Adding a new widget

1. Create `resolvers/<name>.py` implementing the resolver interface
   (`NAME`, `detect(soup, url)`, `fetch_all(source)`).
2. Register it in `resolvers/__init__.py` `RESOLVERS`.

## Notes

`pip-system-certs` is a declared dependency so HTTPS requests work on machines
behind TLS-intercepting proxies (e.g. Avast on Windows) that install their own
CA into the OS trust store.
