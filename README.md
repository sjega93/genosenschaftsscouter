# Genosenschaftsscouter

Scrapes apartment listings from Swiss housing co-operative (Genossenschaft)
websites and writes them to a flat text file — one pipe-delimited line per
listing.

Co-ops frequently delegate their listings to a property manager or an external
listing widget, so the scraper crawls a limited number of pages from the given
URL (following links that look like "properties" / "vacancies") until it finds
a listing widget it knows.

## Supported listing widgets

- **newhome.ch** "Partner Trefferliste" (`sources/newhome.py`)
- **Flatfox** embeds (`sources/flatfox.py`)

## Requirements

- [uv](https://docs.astral.sh/uv/) — used as the Python manager (no `python`/`pip` needed)

## Setup

```bash
uv sync   # resolves the lockfile and creates .venv
```

Dependencies are pinned in `uv.lock`, declared in `pyproject.toml`.

## Usage

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
sources/
  common.py            # shared HTTP/fetch helpers
  newhome.py           # newhome.ch resolver
  flatfox.py           # Flatfox resolver
  __init__.py          # RESOLVERS registry
pyproject.toml / uv.lock
```

## Adding a new widget

1. Create `sources/<name>.py` implementing the resolver interface
   (`NAME`, `detect(soup, url)`, `fetch_all(source)`).
2. Register it in `sources/__init__.py` `RESOLVERS`.

## Notes

`pip-system-certs` is a declared dependency so HTTPS requests work on machines
behind TLS-intercepting proxies (e.g. Avast on Windows) that install their own
CA into the OS trust store.
