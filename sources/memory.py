"""Retail RAM prices via the Best Buy Developer API — the legitimate path.

We do not scrape Amazon, Micro Center, or Newegg: they block automated traffic
(Micro Center returns 403, Newegg's robots.txt disallows crawling), it violates
their terms, and it would get our shared CI runners banned. Best Buy publishes
the same retail prices through a free, sanctioned JSON API, so we use that.

The source is inert until a key is set in monetize.json -> bestbuy_api_key
(free from developer.bestbuy.com). It emits the 25th-percentile $/GB for each
(generation, kit capacity) — e.g. DDR5 32GB — so one overpriced listing can't
move the number, mirroring how the GPU marketplace source works. RAM is priced
by the kit; we divide by total GB to make generations comparable."""

import json
import os
import re
import urllib.parse
import urllib.request

API = "https://api.bestbuy.com/v1/products"
UA = "FoundryBot/0.1 (pricing aggregator; gpudiff.com)"
PROVENANCE = "https://www.bestbuy.com/site/computer-cards-components/memory-ram/"
MIN_SAMPLE = 4

CAP = re.compile(r"\b(\d{1,3})\s?GB\b", re.I)
GEN = re.compile(r"\bDDR([345])\b", re.I)


def _key():
    # Read from an env var fed by a GitHub Actions secret — NEVER a committed
    # file, since this is a public repo and a key there would be scraped.
    return os.environ.get("BESTBUY_API_KEY", "").strip()


def _p25(values):
    values = sorted(values)
    return round(values[max(0, int(0.25 * (len(values) - 1)))], 4)


def _total_gb(name):
    """Total kit capacity in GB. 'DDR5 32GB (2 x 16GB)' -> 32 (the pack size,
    the first/largest figure), not the per-module 16."""
    caps = [int(m) for m in CAP.findall(name)]
    return max(caps) if caps else None


class MemorySource:
    name = "bestbuy-ram"
    cadence = "daily"  # retail RAM moves over days, and the free key is rate-limited

    def fetch(self, observed_at):
        key = _key()
        if not key:
            return []  # inert until the key exists — never errors the pipeline

        buckets = {}  # (gen, cap) -> [ $/GB, ... ]
        for gen in ("DDR5", "DDR4"):
            page = 1
            while page <= 5:  # cap the crawl; free key allows plenty for this
                query = (f'(search={gen}&search=desktop&search=memory&'
                         f'salePrice>0)')
                url = (f"{API}{query}?apiKey={urllib.parse.quote(key)}&format=json"
                       f"&show=name,salePrice&pageSize=100&page={page}")
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    payload = json.load(resp)
                products = payload.get("products", [])
                for p in products:
                    name, price = p.get("name", ""), p.get("salePrice")
                    if not isinstance(price, (int, float)) or price <= 0:
                        continue
                    if not GEN.search(name):
                        continue
                    gb = _total_gb(name)
                    if not gb or gb < 4 or gb > 256:
                        continue
                    per_gb = price / gb
                    if 0.5 <= per_gb <= 50:  # sanity band; drops mislabeled listings
                        buckets.setdefault((gen.lower(), gb), []).append(per_gb)
                if page >= payload.get("totalPages", 1):
                    break
                page += 1

        offers = []
        for (gen, gb), pool in sorted(buckets.items()):
            if len(pool) < MIN_SAMPLE:
                continue
            sku = f"{gen}-{gb}gb"
            offers.append({
                "id": f"bestbuy:{sku}:us:list",
                "provider": "bestbuy",
                "sku": sku,
                "price": _p25(pool),
                "unit": "usd_per_gb_ram",
                "pricing_type": "list",
                "region": "us",
                "attrs": {"generation": gen.upper(), "kit_gb": gb,
                          "sample_size": len(pool), "metric": "p25_retail_per_gb"},
                "provenance": {"url": PROVENANCE, "observed_at": observed_at},
                "fixture": False,
            })
        return offers
