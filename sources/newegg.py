"""Retail graphics-card and RAM prices from Newegg's public category listings —
no key required.

Newegg's robots.txt permits crawlers (the site-wide Disallow lines apply to
specific named bots, not `*`), and its category pages are server-rendered with
prices in the HTML, so a polite daily fetch of a couple of listing pages is the
same pattern as our SaaS pricing-page scans: public page, descriptive
user-agent, low frequency, aggregate statistics only, provenance link on every
number. We publish the 25th-percentile price per GPU model and per RAM kit size
so one marked-up listing can't move the number. Their markup can change
without notice; the health gate catches a silent zero."""

import re
import urllib.request

from .base import Source

UA = "Mozilla/5.0 (compatible; FoundryBot/0.1; +https://gpudiff.com/methodology.html)"
CATEGORIES = {
    # category id -> (kind, human URL for provenance)
    "100007709": ("gpu", "https://www.newegg.com/GPUs-Video-Graphics-Cards/SubCategory/ID-48"),
    "100007611": ("ram", "https://www.newegg.com/Desktop-Memory/SubCategory/ID-147"),
}
PAGES_PER_CATEGORY = 2   # ~60 listings each, polite
MIN_SAMPLE = 3

CELL = re.compile(r'class="item-cell"(.*?)(?=class="item-cell"|$)', re.S)
TITLE = re.compile(r'item-title"[^>]*>(.*?)</a>', re.S)
PRICE = re.compile(r'price-current"[^>]*>.*?\$<strong>([\d,]+)</strong><sup>\.?(\d{2})</sup>', re.S)
GPU_MODEL = re.compile(r"\b(RTX\s?\d{4}(?:\s?(?:Ti|SUPER|D))?|RX\s?\d{4}(?:\s?XTX|\s?XT)?|Arc\s?[AB]\d{3})\b", re.I)
GEN = re.compile(r"\bDDR([345])\b", re.I)
CAP = re.compile(r"\b(\d{1,3})\s?GB\b", re.I)


def _p25(values):
    values = sorted(values)
    return round(values[max(0, int(0.25 * (len(values) - 1)))], 2)


def _fetch(cat_id, page):
    url = f"https://www.newegg.com/p/pl?N={cat_id}&page={page}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read(3_000_000).decode("utf-8", errors="replace")


def _items(html):
    for cell in CELL.findall(html):
        t, p = TITLE.search(cell), PRICE.search(cell)
        if not t or not p:
            continue
        title = re.sub(r"<[^>]+>", "", t.group(1)).strip()
        price = float(p.group(1).replace(",", "") + "." + p.group(2))
        if title and price > 0:
            yield title, price


class NeweggSource(Source):
    name = "newegg"
    cadence = "daily"

    def fetch(self, observed_at):
        cards, ram = {}, {}
        for cat_id, (kind, prov) in CATEGORIES.items():
            for page in range(1, PAGES_PER_CATEGORY + 1):
                html = _fetch(cat_id, page)
                if "Are you a human" in html:
                    break  # bot challenge — stop politely, publish what we have
                for title, price in _items(html):
                    if kind == "gpu":
                        m = GPU_MODEL.search(title)
                        if m and 100 <= price <= 5000:
                            model = re.sub(r"\s+", " ", m.group(1)).upper().strip()
                            cards.setdefault(model, []).append(price)
                    else:
                        g = GEN.search(title)
                        caps = [int(c) for c in CAP.findall(title)]
                        gb = max(caps) if caps else None
                        if g and gb and 4 <= gb <= 256:
                            per_gb = price / gb
                            if 0.5 <= per_gb <= 50:
                                ram.setdefault((f"ddr{g.group(1)}", gb), []).append(per_gb)

        offers = []
        for model, pool in sorted(cards.items()):
            if len(pool) < MIN_SAMPLE:
                continue
            sku = re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-")
            offers.append({
                "id": f"newegg:{sku}:us:list", "provider": "newegg", "sku": sku,
                "price": _p25(pool), "unit": "usd_per_card", "pricing_type": "list",
                "region": "us",
                "attrs": {"model": model, "sample_size": len(pool), "metric": "p25_retail_card"},
                "provenance": {"url": CATEGORIES["100007709"][1], "observed_at": observed_at},
                "fixture": False,
            })
        for (gen, gb), pool in sorted(ram.items()):
            if len(pool) < MIN_SAMPLE:
                continue
            offers.append({
                "id": f"newegg:{gen}-{gb}gb:us:list", "provider": "newegg", "sku": f"{gen}-{gb}gb",
                "price": _p25(pool), "unit": "usd_per_gb_ram", "pricing_type": "list",
                "region": "us",
                "attrs": {"generation": gen.upper(), "kit_gb": gb, "sample_size": len(pool),
                          "metric": "p25_retail_per_gb"},
                "provenance": {"url": CATEGORIES["100007611"][1], "observed_at": observed_at},
                "fixture": False,
            })
        return offers
