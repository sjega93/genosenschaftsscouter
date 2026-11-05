"""
Resolver/parser for the newhome.ch "Partner Trefferliste" widget, used by
many Swiss housing co-ops to embed their current vacancies, e.g.:

    <div data-partner-url="https://www.newhome.ch/de/partner/792995.aspx"></div>
    <script src="https://www.newhome.ch/js/partner.loader.js"></script>

The widget's real listing page (.../partner/immobilien?pc=...) is classic
server-rendered ASP.NET HTML with plain-GET pagination, so no browser
automation is needed.
"""

import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .common import fetch

NAME = "newhome"


def _is_trefferliste(soup: BeautifulSoup) -> bool:
    return soup.select_one("div.object-list.partner-treffer-liste") is not None


def detect(soup: BeautifulSoup, url: str):
    if _is_trefferliste(soup):
        return {"listing_url": url}

    partner_div = soup.select_one("div[data-partner-url]")
    if partner_div is not None:
        partner_url = urljoin(url, partner_div["data-partner-url"])
        try:
            listing_soup, listing_url = fetch(partner_url)
        except requests.RequestException:
            return None
        if _is_trefferliste(listing_soup):
            return {"listing_url": listing_url}

    return None


def _extract_specifications(item) -> dict:
    specs = {}
    for block in item.select(".specifications > div"):
        label_el = block.find("small")
        value_el = block.select_one(".value, .price")
        if label_el is None or value_el is None:
            continue
        label = label_el.get_text(strip=True)
        value = value_el.get_text(strip=True)
        if label:
            specs[label] = value
    return specs


def _parse_items(soup: BeautifulSoup, base_url: str) -> list:
    apartments = []
    for item in soup.select("div.object-list .item"):
        title_el = item.select_one(".title .name")
        additional_title_el = item.select_one(".additional-title")
        address_el = item.select_one(".adress")
        link_el = item.select_one(".details a[href]")
        specs = _extract_specifications(item)

        price = next(
            (v for k, v in specs.items() if "miete" in k.lower() or "preis" in k.lower()),
            "",
        )
        size = next((v for k, v in specs.items() if "fläche" in k.lower()), "")
        move_in = next((v for k, v in specs.items() if "bezug" in k.lower()), "")

        apartments.append(
            {
                "title": title_el.get_text(strip=True) if title_el else "",
                "subtitle": (
                    additional_title_el.get_text(strip=True)
                    if additional_title_el
                    else ""
                ),
                "address": address_el.get_text(strip=True) if address_el else "",
                "price": f"{price}/Monat" if price else "",
                "size": size,
                "availability": f"Bezug: {move_in}" if move_in else "",
                "detail_url": urljoin(base_url, link_el["href"]) if link_el else "",
            }
        )
    return apartments


def _get_page_count(soup: BeautifulSoup) -> int:
    pager = soup.select_one("[id*='ucPager_lPageCount']")
    if pager is None:
        return 1
    match = re.search(r"von\s+(\d+)", pager.get_text(strip=True))
    return int(match.group(1)) if match else 1


def _get_next_page_url(soup: BeautifulSoup, current_page: int, base_url: str):
    next_page = current_page + 1
    for link in soup.select(".pagination a[href]"):
        if link.get_text(strip=True) == str(next_page):
            return urljoin(base_url, link["href"])
    return None


def fetch_all(source: dict) -> list:
    listing_url = source["listing_url"]
    soup, listing_url = fetch(listing_url)

    all_apartments = _parse_items(soup, listing_url)
    total_pages = _get_page_count(soup)

    page = 1
    current_soup = soup
    while page < total_pages:
        next_url = _get_next_page_url(current_soup, page, listing_url)
        if next_url is None:
            break
        current_soup, _ = fetch(next_url)
        all_apartments.extend(_parse_items(current_soup, listing_url))
        page += 1

    return all_apartments
