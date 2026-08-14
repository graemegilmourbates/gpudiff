"""RunPod: public GraphQL gpuTypes query, no auth. Two offers per GPU type —
secure cloud and community cloud list prices. Zero/absent prices are skipped."""

import json
import urllib.request

from .base import Source, make_id, slug

API = "https://api.runpod.io/graphql"
QUERY = '{"query":"query { gpuTypes { id displayName memoryInGb securePrice communityPrice } }"}'
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
            sku = slug(f"{display}-{mem}gb" if mem else display)
            for field, region in (("securePrice", "secure-cloud"), ("communityPrice", "community-cloud")):
                price = gpu.get(field)
                if not isinstance(price, (int, float)) or price <= 0:
                    continue
                offers.append({
                    "id": make_id("runpod", sku, region, "on_demand"),
                    "provider": "runpod",
                    "sku": sku,
                    "price": round(float(price), 4),
                    "unit": "usd_per_hour",
                    "pricing_type": "on_demand",
                    "region": region,
                    "attrs": {"gpu_model": display, "vram_gb": mem, "metric": "list_price"},
                    "provenance": {"url": "https://www.runpod.io/pricing", "observed_at": observed_at},
                    "fixture": False,
                })
        return offers
