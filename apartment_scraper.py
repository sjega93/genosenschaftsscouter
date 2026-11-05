#!/usr/bin/env python3
"""
Apartment listing scraper for Swiss housing co-op / landlord pages.

Supports pages that embed a known listing widget directly, or that link to
one through a reasonable number of intermediate "properties"/"vacancies"
pages (as co-ops often delegate listings to a property manager's site).

Currently supported widgets:
  - newhome.ch "Partner Trefferliste" (see resolvers/newhome.py)
  - Flatfox embed (see resolvers/flatfox.py)

Usage:
    uv run apartment_scraper.py [<url>] [-o OUTPUT]
    uv run apartment_scraper.py --update-coop-list

Without <url>, all co-ops in coops.txt are scanned concurrently
(see coop_list.py / --update-coop-list).
"""

import argparse
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

import requests

import coop_list
from resolvers import RESOLVERS, empty
from resolvers.common import fetch

MAX_WORKERS = 8

MAX_PAGES_CRAWLED = 8
KEYWORD_RE = re.compile(
    r"liegenschaft|wohnung|immobil|mieten|vermiet|angebot|vacan|apartment|wohnraum",
    re.I,
)


def discover(start_url: str):
    """Breadth-first search from start_url for a page with a known listing
    widget, following links whose text suggests a properties/vacancies page."""
    visited = set()
    visited_texts = []
    queue = [start_url]

    while queue and len(visited) < MAX_PAGES_CRAWLED:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        try:
            soup, final_url = fetch(url)
        except requests.RequestException:
            continue

        for resolver in RESOLVERS:
            result = resolver.detect(soup, final_url)
            if result is not None:
                return resolver, result

        visited_texts.append(soup.get_text(" ", strip=True))

        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            if text and KEYWORD_RE.search(text):
                link = urljoin(final_url, a["href"])
                if link not in visited:
                    queue.append(link)

    # Fallback: the site may plainly state it has no vacancies even though
    # no known listing widget was found.
    if any(empty.detect_text(text) for text in visited_texts):
        return empty, {}

    raise ValueError(
        f"unsupported site — no known listing pattern matched "
        f"(visited {len(visited)} page(s) from {start_url})"
    )


def format_line(apartment: dict) -> str:
    fields = [
        apartment.get("title", ""),
        apartment.get("subtitle", ""),
        apartment.get("address", ""),
        apartment.get("price", ""),
        apartment.get("size", ""),
        apartment.get("availability", ""),
        apartment.get("detail_url", ""),
    ]
    return " | ".join(f for f in fields if f)


def scrape_one(url: str):
    """Discover the listing widget for url and return (resolver_name, apartments)."""
    resolver, source = discover(url)
    return resolver.NAME, resolver.fetch_all(source)


def _run_all(urls: list, output_path: str) -> int:
    results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(scrape_one, url): url for url in urls}
        for done, future in enumerate(as_completed(futures), 1):
            url = futures[future]
            try:
                name, apartments = future.result()
                results[url] = (name, apartments)
                status = (
                    f"{len(apartments)} flat(s) via {name}"
                    if apartments
                    else (
                        "site states: no flats available"
                        if name == empty.NAME
                        else f"supported via {name} — no flats listed"
                    )
                )
            except ValueError as exc:
                status = f"unsupported: {exc}"
            except requests.RequestException as exc:
                status = f"unreachable: {exc}"
            print(f"[{done}/{len(urls)}] {url}: {status}", file=sys.stderr)

    total = 0
    hits = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for url in urls:
            result = results.get(url)
            if not result or not result[1]:
                continue
            name, apartments = result
            f.write(f"# {url} ({len(apartments)} flat(s), source: {name})\n")
            for apartment in apartments:
                f.write(format_line(apartment) + "\n")
            total += len(apartments)
            hits += 1

    if total == 0:
        print("No apartments currently listed on any co-op site.")
    print(f"Wrote {total} apartment(s) from {hits} co-op(s) to {output_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "url",
        nargs="?",
        help="URL of the apartment listing page (or a page linking to one). "
        "If omitted, all co-ops in coops.txt are scanned.",
    )
    parser.add_argument(
        "-o", "--output", default="apartments.txt", help="Output text file path"
    )
    parser.add_argument(
        "--update-coop-list",
        action="store_true",
        help="re-fetch the co-op list from genossenschaftsradar.ch and exit",
    )
    args = parser.parse_args()

    if args.update_coop_list:
        urls = coop_list.fetch_coop_urls()
        coop_list.save_coop_urls(urls)
        print(f"Wrote {len(urls)} co-op URL(s) to {coop_list.COOPS_FILE}")
        return 0

    if not args.url:
        return _run_all(coop_list.load_coop_urls(), args.output)

    try:
        resolver, source = discover(args.url)
        apartments = resolver.fetch_all(source)
    except (requests.RequestException, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    with open(args.output, "w", encoding="utf-8") as f:
        if not apartments:
            f.write("No apartments currently listed.\n")
        else:
            for apartment in apartments:
                f.write(format_line(apartment) + "\n")

    if not apartments:
        if resolver.NAME == empty.NAME:
            print("The site states it has no apartments available right now.")
        else:
            print(f"Site supported via {resolver.NAME}, but no apartments are currently listed.")
    else:
        print(f"Wrote {len(apartments)} apartment(s) to {args.output} (source: {resolver.NAME})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
