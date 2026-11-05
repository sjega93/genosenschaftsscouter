"""
Resolver for Statamic/Nuxt sites built on the Geissenstein "runway"
real-estate module (used by several Swiss landlords/co-ops, e.g. ebg.lu).

These sites server-render their listing pages and embed the GraphQL result
in a devalue-flattened JSON array inside an inline <script> tag
(Nuxt SSR payload). Entries have __typename "runway_graphql_types_properties"
with fields like title, street, postal_code, city, rooms, surface, price,
available_from and property_uri — so no browser automation or extra requests
are needed; the listing data is already in the page.
"""

import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

NAME = "statamic"

TYPENAME = "runway_graphql_types_properties"
_DEWRAP = {
    "Reactive", "ShallowReactive", "Ref", "ShallowRef", "Readonly",
    "Set", "Map", "EmptyRef", "EmptyShallowRef",
}


def _unflatten(arr: list):
    """Resolve a devalue-flattened JSON array into plain Python objects."""
    def res(i):
        v = arr[i]
        if isinstance(v, list):
            if v and isinstance(v[0], str) and v[0] in _DEWRAP:
                if len(v) < 2:
                    return None
                inner = res(v[1])
                return set(inner) if v[0] == "Set" else inner
            return [res(x) for x in v]
        if isinstance(v, dict):
            return {k: res(x) for k, x in v.items()}
        return v
    return res(0)


def _payload_arrays(soup: BeautifulSoup) -> list:
    """Devalue arrays in inline scripts that contain property entries."""
    arrays = []
    for script in soup.find_all("script"):
        text = script.string or script.get_text()
        if not text or TYPENAME not in text:
            continue
        try:
            arr = json.loads(text.strip())
        except ValueError:
            continue
        if isinstance(arr, list):
            arrays.append(arr)
    return arrays


def _collect_properties(obj, found: list):
    if isinstance(obj, dict):
        if obj.get("__typename") == TYPENAME and "property_uri" in obj:
            found.append(obj)
            return
        for v in obj.values():
            _collect_properties(v, found)
    elif isinstance(obj, (list, set)):
        for v in obj:
            _collect_properties(v, found)


def _extract(soup: BeautifulSoup) -> list:
    properties = []
    for arr in _payload_arrays(soup):
        try:
            root = _unflatten(arr)
        except (IndexError, TypeError, KeyError):
            continue
        _collect_properties(root, properties)
    return properties


def detect(soup: BeautifulSoup, url: str):
    if _extract(soup):
        return {"soup": soup, "page_url": url}
    return None


def _fmt_date(value: str) -> str:
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", value or "")
    return f"{m.group(3)}.{m.group(2)}.{m.group(1)}" if m else ""


def _to_apartment(prop: dict, page_url: str) -> dict:
    address = ", ".join(
        p for p in (
            prop.get("street", ""),
            f"{prop.get('postal_code', '')} {prop.get('city', '')}".strip(),
        ) if p
    )

    price = ""
    if prop.get("price"):
        try:
            price = f"CHF {int(prop['price']):,}/Monat".replace(",", "'")
        except (TypeError, ValueError):
            price = f"CHF {prop['price']}/Monat"

    size = ", ".join(
        p for p in (
            f"{prop['rooms']} Zimmer" if prop.get("rooms") else "",
            f"{prop['surface']} m²" if prop.get("surface") else "",
        ) if p
    )

    available = _fmt_date(prop.get("available_from", ""))
    deadline = _fmt_date(prop.get("deadline", ""))

    return {
        "title": prop.get("title", ""),
        "subtitle": f"Bewerbungsfrist: {deadline}" if deadline else "",
        "address": address,
        "price": price,
        "size": size,
        "availability": f"Bezug: {available}" if available else "",
        "detail_url": urljoin(page_url, prop.get("property_uri", "")),
    }


def fetch_all(source: dict) -> list:
    page_url = source["page_url"]
    return [
        _to_apartment(prop, page_url) for prop in _extract(source["soup"])
    ]
