"""Vast.ai marketplace: public bundles search, no auth. We publish one offer
per GPU model: the 25th-percentile $/hr across verified, rentable, single-GPU
listings (p25 is what a careful buyer can actually get, and it's stable enough
to survive the 40% delta gate). Models with fewer than MIN_SAMPLE listings are
skipped — missing beats wrong."""

import json
import urllib.parse
import urllib.request

from .base import Source, make_id, slug

API = "https://console.vast.ai/api/v0/bundles/"
# No num_gpus filter: the endpoint returns ~64 rows regardless, so we widen the
# pool and normalize to per-GPU price (dph_total / num_gpus) instead.
QUERY = {"verified": {"eq": True}, "rentable": {"eq": True}, "limit": 500}
MIN_SAMPLE = 5
UA = "FoundryBot/0.1 (pricing aggregator prototype)"


def _p25(values):
    values = sorted(values)
    idx = max(0, int(0.25 * (len(values) - 1)))
    return round(values[idx], 4)


class VastSource(Source):
    name = "vast"

    def fetch(self, observed_at):
        url = API + "?q=" + urllib.parse.quote(json.dumps(QUERY))
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.load(resp)

        by_model, by_model_bid = {}, {}
        for listing in payload.get("offers", []):
            gpu = listing.get("gpu_name")
            price = listing.get("dph_total")
            bid = listing.get("min_bid")
            n = listing.get("num_gpus") or 1
            if not gpu:
                continue
            if isinstance(price, (int, float)) and price > 0:
                by_model.setdefault(gpu, []).append(price / n)
            if isinstance(bid, (int, float)) and bid > 0:
                by_model_bid.setdefault(gpu, []).append(bid / n)

        offers = []
        for ptype, pool, metric in (("on_demand", by_model, "p25_per_gpu_dph_verified"),
                                    ("spot", by_model_bid, "p25_min_bid_per_gpu")):
            for gpu, prices in sorted(pool.items()):
                if len(prices) < MIN_SAMPLE:
                    continue
                sku = slug(gpu)
                offers.append({
                    "id": make_id("vast", sku, "global", ptype),
                    "provider": "vast",
                    "sku": sku,
                    "price": _p25(prices),
                    "unit": "usd_per_hour",
                    "pricing_type": ptype,
                    "region": "global",
                    "attrs": {
                        "gpu_model": gpu,
                        "sample_size": len(prices),
                        "metric": metric,
                    },
                    "provenance": {"url": "https://vast.ai/pricing", "observed_at": observed_at},
                    "fixture": False,
                })
        return offers
