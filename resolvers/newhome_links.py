"""
Resolver for co-op sites that render their own listing cards server-side and
link each card out to a newhome.ch detail page — without embedding the
newhome "Partner Trefferliste" widget. Example: abl.ch /wohnen/wohnungsmarkt.

Detection: the page contains at least one anchor to a residential newhome.ch
detail URL (/immobilien/wohnung|haus/...detail/<id>).

Parsing: for each such anchor, the nearest ancestor containing a heading is
treated as the card; fields are then pulled from the card's text via regexes
(price, size, availability, PLZ-style address). This is deliberately generic
so it works for other sites using the same "cards linking to newhome detail"
pattern, not just abl.ch.
"""

import re

from bs4 import BeautifulSoup

NAME = "newhome_links"

DETAIL_RE = re.compile(
    r"newhome\.ch/[^?]*/immobilien/(?:wohnung|haus)/[^?]*detail/\d+"
)
AVAIL_RE = re.compile(
    r"(?:per|ab)\s+(\d{1,2}\.\s?\d{1,2}\.\s?\d{4}|sofort)", re.I
)
PRICE_RE = re.compile(r"CHF\s*[\d'’.,]+")
SIZE_RE = re.compile(r"\d+(?:[.,]\d+)?\s*m²")
# Swiss PLZ: 4 digits followed by a capitalized locality, e.g. "6003 Luzern"
ADDRESS_RE = re.compile(r"\b[1-9]\d{3}\s+[A-ZÄÖÜ]")
HEADINGS = ["h1", "h2", "h3", "h4", "h5"]


def detect(soup: BeautifulSoup, url: str):
    for a in soup.find_all("a", href=True):
        if DETAIL_RE.search(a["href"]):
            return {"soup": soup}
    return None


def _card_for(anchor):
    """Smallest ancestor of the anchor that contains a heading."""
    node = anchor.parent
    while node is not None and node.name != "body":
        if node.find(HEADINGS):
            return node
        node = node.parent
    return None


def _parse_card(card, detail_url: str) -> dict:
    text = card.get_text(" ", strip=True)

    heading = card.find(HEADINGS)
    title = heading.get_text(strip=True) if heading else ""

    availability = ""
    subtitle = ""
    avail_p = None
    for p in card.find_all("p"):
        t = p.get_text(" ", strip=True)
        if AVAIL_RE.search(t):
            avail_p = t
            break
    if avail_p is not None:
        m = AVAIL_RE.search(avail_p)
        availability = f"Bezug: {m.group(1)}"
        subtitle = AVAIL_RE.sub("", avail_p).strip(" -–,|")

    address = ""
    for p in card.find_all("p"):
        t = p.get_text(" ", strip=True)
        if AVAIL_RE.search(t):
            continue
        if ADDRESS_RE.search(t):
            address = t
            break

    price_m = PRICE_RE.search(text)
    size_m = SIZE_RE.search(text)
    size = re.sub(r"(\d)\s*m²", r"\1 m²", size_m.group(0)) if size_m else ""

    return {
        "title": title,
        "subtitle": subtitle,
        "address": address,
        "price": f"{price_m.group(0)}/Monat" if price_m else "",
        "size": size,
        "availability": availability,
        "detail_url": detail_url,
    }


def fetch_all(source: dict) -> list:
    soup = source["soup"]
    apartments = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not DETAIL_RE.search(href) or href in seen:
            continue
        card = _card_for(a)
        if card is None:
            continue
        seen.add(href)
        apartments.append(_parse_card(card, href))
    return apartments
