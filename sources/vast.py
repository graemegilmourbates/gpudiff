"""Vast.ai marketplace: public bundles search, no auth.

We publish, per GPU model, the 25th-percentile $/GPU-hour across verified,
rentable listings — what a careful buyer can actually get, rather than the
single cheapest listing, which is often a trap. Spot is the same statistic
over each listing's minimum bid.

Query shape matters here: the API caps a response at ~64 rows, so one broad
query spreads those rows across every model on the marketplace and routinely
leaves nothing above the sample floor (it returned zero offers on 2026-08-21
and failed the health gate). Querying one model at a time gives each model its
own 64-row budget, which is both far deeper and far more stable.
"""

import json
import urllib.parse
import urllib.request

from .base import Source, make_id, slug

API = "https://console.vast.ai/api/v0/bundles/"
UA = "FoundryBot/0.1 (pricing aggregator; gpudiff.com)"
PROVENANCE = "https://vast.ai/pricing"
MIN_SAMPLE = 5

# Reported VRAM wobbles by a few hundred MB between hosts (81559MB and 81920MB
# are both an 80GB card), so snap to the real product sizes.
STANDARD_GB = (8, 10, 11, 12, 16, 20, 24, 32, 40, 48, 64, 80, 94, 96, 141, 143, 180, 192, 288)


def _vram_gb(listing):
    raw = listing.get("gpu_ram")
    if not isinstance(raw, (int, float)) or raw <= 0:
        return None
    gb = raw / 1024
    nearest = min(STANDARD_GB, key=lambda s: abs(s - gb))
    return nearest if abs(nearest - gb) <= 4 else round(gb)

# Vast's exact gpu_name values. Models are skipped automatically when the
# marketplace is too thin for a trustworthy percentile, so listing one that is
# briefly unavailable costs nothing but a request.
MODELS = [
    "H100 SXM", "H100 PCIE", "H100 NVL", "H200", "H200 NVL", "B200",
    "A100 SXM4", "A100 PCIE", "RTX 4090", "RTX 5090", "RTX 3090",
    "RTX A6000", "L40S", "L4", "RTX PRO 6000 WS", "RTX PRO 6000 S",
    "RTX PRO 5000",
]


def _p25(values):
    values = sorted(values)
    return round(values[max(0, int(0.25 * (len(values) - 1)))], 4)


def _fetch_model(gpu_name):
    query = {"gpu_name": {"eq": gpu_name}, "verified": {"eq": True},
             "rentable": {"eq": True}, "limit": 500}
    url = API + "?q=" + urllib.parse.quote(json.dumps(query))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.load(resp).get("offers", [])


class VastSource(Source):
    name = "vast"

    def fetch(self, observed_at):
        offers, failures = [], []
        for gpu_name in MODELS:
            try:
                listings = _fetch_model(gpu_name)
            except Exception as exc:  # noqa: BLE001 — one model must not sink the source
                failures.append(f"{gpu_name}: {type(exc).__name__}")
                continue

            # A memory configuration is a product: Vast lists 40GB and 80GB
            # A100 SXM4 under one name, and averaging them would price a card
            # that does not exist.
            by_vram = {}
            for listing in listings:
                gb = _vram_gb(listing)
                if not gb:
                    continue
                n = listing.get("num_gpus") or 1
                price, bid = listing.get("dph_total"), listing.get("min_bid")
                pools = by_vram.setdefault(gb, {"on_demand": [], "spot": []})
                if isinstance(price, (int, float)) and price > 0:
                    pools["on_demand"].append(price / n)
                if isinstance(bid, (int, float)) and bid > 0:
                    pools["spot"].append(bid / n)

            for gb, pools in sorted(by_vram.items()):
                sku = slug(f"{gpu_name}-{gb}gb")
                for pricing_type, metric in (("on_demand", "p25_per_gpu_dph_verified"),
                                             ("spot", "p25_min_bid_per_gpu")):
                    pool = pools[pricing_type]
                    if len(pool) < MIN_SAMPLE:
                        continue
                    offers.append({
                        "id": make_id("vast", sku, "global", pricing_type),
                        "provider": "vast",
                        "sku": sku,
                        "price": _p25(pool),
                        "unit": "usd_per_hour",
                        "pricing_type": pricing_type,
                        "region": "global",
                        "attrs": {"gpu_model": gpu_name, "vram_gb": gb,
                                  "sample_size": len(pool), "metric": metric},
                        "provenance": {"url": PROVENANCE, "observed_at": observed_at},
                        "fixture": False,
                    })

        if failures and len(failures) == len(MODELS):
            raise RuntimeError("every Vast model query failed: " + "; ".join(failures[:3]))
        return offers
