"""Azure GPU VMs from the public Retail Prices API (no auth). Server-side SKU
filter keeps the response to one small page. Emits on-demand and spot rows per
family (Linux only, Low Priority excluded). Instance-bundled like AWS: price ÷
GPU count, flagged in attrs. Daily cadence — list prices move rarely."""

import json
import urllib.parse
import urllib.request

from .base import Source, make_id

API = "https://prices.azure.com/api/retail/prices"
UA = "FoundryBot/0.1 (pricing aggregator; gpudiff.com)"
PROVENANCE = "https://azure.microsoft.com/en-us/pricing/details/virtual-machines/linux/"
REGION = "eastus"

INSTANCES = {
    "Standard_ND96isr_H100_v5": ("h100-sxm-80gb", 8),
    "Standard_NC40ads_H100_v5": ("h100-nvl-94gb", 1),
    "Standard_ND96isr_H200_v5": ("h200-sxm-141gb", 8),
    "Standard_ND96amsr_A100_v4": ("a100-sxm4-80gb", 8),
    "Standard_NC24ads_A100_v4": ("a100-pcie-80gb", 1),
    "Standard_NC4as_T4_v3": ("t4-16gb", 1),
    "Standard_NV36ads_A10_v5": ("a10-24gb", 1),
}


class AzureSource(Source):
    name = "azure"
    cadence = "daily"

    def fetch(self, observed_at):
        sku_filter = " or ".join(f"armSkuName eq '{s}'" for s in INSTANCES)
        flt = (f"serviceName eq 'Virtual Machines' and priceType eq 'Consumption' "
               f"and armRegionName eq '{REGION}' and ({sku_filter})")
        url = API + "?" + urllib.parse.urlencode({"$filter": flt})

        items = []
        for _ in range(5):  # pagination guard; filtered result is ~1 page
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.load(resp)
            items.extend(payload.get("Items", []))
            url = payload.get("NextPageLink")
            if not url:
                break

        # (family, pricing_type) -> cheapest qualifying rate
        best = {}
        for it in items:
            sku = it.get("armSkuName")
            if sku not in INSTANCES:
                continue
            if "Windows" in (it.get("productName") or ""):
                continue
            meter = it.get("meterName") or ""
            if "Low Priority" in meter:
                continue
            if it.get("unitOfMeasure") != "1 Hour":
                continue
            price = it.get("retailPrice")
            if not isinstance(price, (int, float)) or price <= 0:
                continue
            family, ngpus = INSTANCES[sku]
            ptype = "spot" if "Spot" in meter else "on_demand"
            key = (family, ptype)
            per_gpu = price / ngpus
            cur = best.get(key)
            if cur is None or per_gpu < cur[0]:
                best[key] = (per_gpu, sku, ngpus, price)

        offers = []
        for (family, ptype), (per_gpu, sku, ngpus, price) in sorted(best.items()):
            offers.append({
                "id": make_id("azure", family, REGION, ptype),
                "provider": "azure",
                "sku": family,
                "price": round(per_gpu, 4),
                "unit": "usd_per_hour",
                "pricing_type": ptype,
                "region": REGION,
                "attrs": {
                    "instance_type": sku,
                    "gpus_per_instance": ngpus,
                    "instance_price": price,
                    "metric": "instance_list_per_gpu",
                },
                "provenance": {"url": PROVENANCE, "observed_at": observed_at},
                "fixture": False,
            })
        return offers
