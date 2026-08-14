"""RunPod: public GraphQL gpuTypes query, no auth. Two offers per GPU type —
secure cloud and community cloud list prices. Zero/absent prices are skipped."""

import json
import urllib.request

from .base import Source, make_id, slug

API = "https://api.runpod.io/graphql"
QUERY = ('{"query":"query { gpuTypes { id displayName memoryInGb securePrice communityPrice '
         'secureSpotPrice communitySpotPrice } }"}')
UA = "FoundryBot/0.1 (pricing aggregator prototype)"


class RunpodSource(Source):
    name = "runpod"

    def fetch(self, observed_at):
        req = urllib.request.Request(
            API,
            data=QUERY.encode(),
            headers={"User-Agent": UA, "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.load(resp)

        offers = []
        for gpu in (payload.get("data") or {}).get("gpuTypes") or []:
            display = gpu.get("displayName") or gpu.get("id")
            mem = gpu.get("memoryInGb")
            if not display:
                continue
            base = slug(display)
            # Memory config is identity — but don't double-suffix names that
            # already carry it ("A100 SXM 40GB" must not become ...-40gb-40gb).
            sku = base if (not mem or base.endswith(f"-{mem}gb")) else f"{base}-{mem}gb"
            for field, region, ptype in (("securePrice", "secure-cloud", "on_demand"),
                                         ("communityPrice", "community-cloud", "on_demand"),
                                         ("secureSpotPrice", "secure-cloud", "spot"),
                                         ("communitySpotPrice", "community-cloud", "spot")):
                price = gpu.get(field)
                if not isinstance(price, (int, float)) or price <= 0:
                    continue
                offers.append({
                    "id": make_id("runpod", sku, region, ptype),
                    "provider": "runpod",
                    "sku": sku,
                    "price": round(float(price), 4),
                    "unit": "usd_per_hour",
                    "pricing_type": ptype,
                    "region": region,
                    "attrs": {"gpu_model": display, "vram_gb": mem, "metric": "list_price"},
                    "provenance": {"url": "https://www.runpod.io/pricing", "observed_at": observed_at},
                    "fixture": False,
                })
        return offers
