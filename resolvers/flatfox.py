"""
Resolver/parser for the Flatfox (flatfox.ch) listing widget, embedded by
many Swiss property managers, e.g.:

    <div data-embed="flatfox" data-uid="f7f60c82-..." data-lang="de"></div>
    <script src="https://flatfox.ch/public/client/embed.*.js" async></script>

Flatfox renders this widget client-side (React), but its applet page
(.../de/applet/<uid>/) is server-rendered just enough to expose a
`data-selection-pk` attribute, which identifies the listing set in
Flatfox's public JSON REST API (/api/v1/public-listing/). That API is
reachable directly with plain HTTP requests, so no browser automation is
needed despite the widget itself being JS-rendered.
"""

from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .common import fetch, USER_AGENT, TIMEOUT

NAME = "flatfox"

API_BASE = "https://flatfox.ch/api/v1/public-listing/"
PERIOD_BY_UNIT = {"monthly": "Monat", "weekly": "Woche", "daily": "Tag", "yearly": "Jahr"}

# Residential-only by default; apartments/houses, not parking/storage/commercial.
RESIDENTIAL_CATEGORIES = {"APARTMENT", "HOUSE"}


def _selection_pk_from(soup: BeautifulSoup):
    root = soup.select_one("[data-embedded-search]")
    if root is not None:
        pk = root.get("data-selection-pk")
        if pk:
            return pk
    return None


def detect(soup: BeautifulSoup, url: str):
    # Page is already the Flatfox applet shell (or similar) with the pk inline.
    pk = _selection_pk_from(soup)
    if pk:
        return {"selection_pk": pk}

    # Page embeds the widget via data-embed="flatfox" + data-uid.
    embed_div = soup.select_one('div[data-embed="flatfox"][data-uid]')
    if embed_div is not None:
        uid = embed_div["data-uid"]
        lang = embed_div.get("data-lang", "de")
        applet_url = f"https://flatfox.ch/{lang}/applet/{uid}/"
        try:
            applet_soup, _ = fetch(applet_url)
        except requests.RequestException:
            return None
        pk = _selection_pk_from(applet_soup)
        if pk:
            return {"selection_pk": pk}

    return None


def _format_price(item: dict) -> str:
    price = item.get("price_display")
    if price is None:
        return ""
    chf = f"CHF {price:,.0f}".replace(",", "'")
    period = PERIOD_BY_UNIT.get(item.get("price_unit"), "")
    return f"{chf}/{period}" if period else chf


def _format_size(item: dict) -> str:
    parts = []
    rooms = item.get("number_of_rooms")
    if rooms:
        parts.append(f"{rooms} Zimmer")
    size = item.get("surface_living")
    if size:
        parts.append(f"{size} m²")
    return ", ".join(parts)


def _format_availability(item: dict) -> str:
    if item.get("moving_date_type") == "imm":
        return "Verfügbar: sofort"
    date = item.get("moving_date")
    return f"Verfügbar: {date}" if date else ""


def fetch_all(source: dict, residential_only: bool = True) -> list:
    pk = source["selection_pk"]
    url = f"{API_BASE}?expand=cover_image&selection={pk}&limit=50"
    apartments = []

    headers = {"User-Agent": USER_AGENT, "Accept-Language": "de"}
    while url:
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()

        for item in data["results"]:
            if residential_only and item.get("object_category") not in RESIDENTIAL_CATEGORIES:
                continue
            apartments.append(
                {
                    "title": item.get("short_title", ""),
                    "subtitle": "",
                    "address": item.get("public_address", ""),
                    "price": _format_price(item),
                    "size": _format_size(item),
                    "availability": _format_availability(item),
                    "detail_url": urljoin("https://flatfox.ch", item.get("url", "")),
                }
            )

        url = data.get("next")

    return apartments
