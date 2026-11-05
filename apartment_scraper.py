#!/usr/bin/env python3
"""
Apartment listing scraper for Swiss housing co-op / landlord pages.

Supports pages that embed a known listing widget directly, or that link to
one through a reasonable number of intermediate "properties"/"vacancies"
pages (as co-ops often delegate listings to a property manager's site).

Currently supported widgets:
  - newhome.ch "Partner Trefferliste" (see sources/newhome.py)
  - Flatfox embed (see sources/flatfox.py)

Usage:
    python apartment_scraper.py <url> [-o OUTPUT]
"""

import argparse
import re
import sys
from urllib.parse import urljoin

import requests

from sources import RESOLVERS
from sources.common import fetch

MAX_PAGES_CRAWLED = 8
KEYWORD_RE = re.compile(
    r"liegenschaft|wohnung|immobil|mieten|vermiet|angebot|vacan|apartment|wohnraum",
    re.I,
)


def discover(start_url: str):
    """Breadth-first search from start_url for a page with a known listing
    widget, following links whose text suggests a properties/vacancies page."""
    visited = set()
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

        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            if text and KEYWORD_RE.search(text):
                link = urljoin(final_url, a["href"])
                if link not in visited:
                    queue.append(link)

    raise ValueError(
        f"No known listing widget found starting from {start_url} "
        f"(visited {len(visited)} page(s))."
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="URL of the apartment listing page (or a page linking to one)")
    parser.add_argument(
        "-o", "--output", default="apartments.txt", help="Output text file path"
    )
    args = parser.parse_args()

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

    print(f"Wrote {len(apartments)} apartment(s) to {args.output} (source: {resolver.NAME})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
