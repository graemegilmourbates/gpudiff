"""Deterministic fixture sources for dev and CI. Prices drift with the date so
consecutive runs produce a realistic diff — which is what the pipeline exists
to detect. Clearly fake providers; fixture=True keeps them off production
surfaces."""

import hashlib

from .base import Source, make_id

_CATALOG = [
    # provider, sku, base price usd/hr, region, pricing_type
    ("examplecloud", "gx-100-80gb", 2.49, "us-east", "on_demand"),
    ("examplecloud", "gx-100-80gb", 1.62, "us-east", "spot"),
    ("examplecloud", "gx-200-141gb", 3.89, "us-east", "on_demand"),
    ("samplecompute", "gx-100-80gb", 2.19, "eu-west", "on_demand"),
    ("samplecompute", "rtx-demo-24gb", 0.34, "eu-west", "spot"),
    ("mocktensor", "gx-100-80gb", 1.99, "asia-1", "on_demand"),
]


def _drift(seed, base):
    """Deterministic ±6% price drift keyed on (date, offer). Same date → same
    prices; different date → small realistic moves."""
    h = int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16)
    factor = 0.94 + (h % 1201) / 10000.0  # 0.94 .. 1.06
    return round(base * factor, 2)


class FixtureSource(Source):
    name = "fixtures"

    def __init__(self, date):
        self.date = date  # YYYY-MM-DD drives the drift

    def fetch(self, observed_at):
        offers = []
        for provider, sku, base, region, ptype in _CATALOG:
            oid = make_id(provider, sku, region, ptype)
            # mocktensor delists on odd days: exercises added/removed diffs too
            day = int(self.date[-2:])
            if provider == "mocktensor" and day % 2 == 1:
                continue
            offers.append({
                "id": oid,
                "provider": provider,
                "sku": sku,
                "price": _drift(f"{self.date}:{oid}", base),
                "unit": "usd_per_hour",
                "pricing_type": ptype,
                "region": region,
                "attrs": {"gpu_model": sku.rsplit("-", 1)[0], "vram_gb": int(sku.rsplit("-", 1)[1].rstrip("gb"))},
                "provenance": {
                    "url": f"https://fixtures.invalid/{provider}/pricing",
                    "observed_at": observed_at,
                },
                "fixture": True,
            })
        return offers
