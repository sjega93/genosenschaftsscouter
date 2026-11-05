"""
Fallback resolver for sites that explicitly state they have no vacancies —
e.g. "Wohnungen: Alle vermietet", "keine freien Wohnungen",
"zurzeit keine Mietobjekte". Lets the scraper report "site states no flats"
instead of "unsupported" for co-ops that publish availability in plain text.

Not registered in RESOLVERS: discover() tries real listing resolvers on every
crawled page first, then falls back to this check on all visited pages, so an
incidental "alle vermietet" note can't shadow a real widget on another page.
"""

import re

from bs4 import BeautifulSoup

NAME = "empty"

# Phrases that unambiguously declare "nothing is available right now".
# Require a vacancy-related noun near the negation to avoid matching
# unrelated statements ("zurzeit keine Veranstaltungen").
NO_FLATS_RE = re.compile(
    r"alle\s+(wohnungen\s+|mietobjekte\s+)?vermietet"
    r"|keine[n]?\s+freien?\s+(wohnungen|mietobjekte|wohnungsangebote|inserate)"
    r"|keine[n]?\s+(wohnungen|mietobjekte|inserate)\s+(frei|verfügbar|zu\s+vermieten|zur\s+vermietung)"
    r"|(zur\s*zeit|zurzeit|aktuell|momentan|derzeit)\s+(gibt\s+es\s+)?keine[n]?"
    r"[^.]{0,40}(wohnung|mietobjekt|vermietung|angebot|inserat|liegenschaft)"
    r"|(tous|toutes?|tout)\s+(est\s+|sont\s+)?louée?s?"
    r"|pas\s+d['’]appartements?\s+(libres?|disponibles?)",
    re.I,
)


# If the "all rented" statement is preceded by parking-related wording,
# it's about parking spaces, not flats.
_PARKING_RE = re.compile(r"parkpl|stellplatz|garage|einstellhall|motorrad", re.I)


def detect_text(text: str) -> bool:
    for m in NO_FLATS_RE.finditer(text):
        context = text[max(0, m.start() - 40) : m.start()]
        if _PARKING_RE.search(context):
            continue
        return True
    return False


def detect(soup: BeautifulSoup, url: str):
    return {} if detect_text(soup.get_text(" ", strip=True)) else None


def fetch_all(source: dict) -> list:
    return []
