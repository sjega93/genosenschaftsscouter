"""Default co-op URL list handling.

`coops.txt` is a snapshot of the co-op websites linked from
https://genossenschaftsradar.ch/genossenschaften — one URL per line,
comments start with '#'. `--update-coop-list` re-fetches that page and
regenerates the file.
"""

from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from resolvers.common import fetch

RADAR_URL = "https://genossenschaftsradar.ch/genossenschaften"
COOPS_FILE = Path(__file__).parent / "coops.txt"

# Hosts to exclude when extracting co-op sites from the radar page
# (the radar site itself, social/CDN/mail links).
_BLOCKLIST = (
    "genossenschaftsradar",
    "eepurl",
    "facebook",
    "instagram",
    "linkedin",
    "twitter",
    "x.com",
    "youtube",
    "whatsapp",
    "google",
    "schema.org",
    "w3.org",
    "fonts.",
    "cdn",
    "mailto",
)


def load_coop_urls() -> list:
    return [
        line.strip()
        for line in COOPS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def fetch_coop_urls() -> list:
    """External co-op site URLs linked on the radar page, deduped by host."""
    soup, _ = fetch(RADAR_URL)
    by_host = {}
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href.startswith("http"):
            continue
        host = urlparse(href).netloc.lower().removeprefix("www.")
        if not host or any(b in host for b in _BLOCKLIST):
            continue
        by_host.setdefault(host, href)
    return [by_host[h] for h in sorted(by_host)]


def save_coop_urls(urls: list):
    header = (
        "# Swiss housing co-operatives (from genossenschaftsradar.ch/genossenschaften)\n"
        "# Regenerate: uv run apartment_scraper.py --update-coop-list\n"
    )
    COOPS_FILE.write_text(header + "\n".join(urls) + "\n", encoding="utf-8")
