"""AWS EC2 on-demand GPU instances, us-east-1, from the public no-auth bulk
pricing CSV (~300MB, streamed row-by-row — never loaded into memory).

AWS sells bundled instances, not GPUs: a p5.48xlarge is 8×H100 fused to CPUs,
RAM, and NVMe. We publish price ÷ GPU count as $/GPU-hr with an
"instance_list_per_gpu" metric badge and the instance type in attrs, so the
bundling is visible, never hidden. Whitelist below maps instance types to the
GPU family and count; smallest instance per family is used where sizes exist
to minimize bundling distortion. Daily cadence: this file is huge and these
prices move rarely."""

import csv
import io
import urllib.request

from .base import Source, make_id

URL = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/us-east-1/index.csv"
UA = "FoundryBot/0.1 (pricing aggregator; gpudiff.com)"
PROVENANCE = "https://aws.amazon.com/ec2/pricing/on-demand/"

INSTANCES = {
    "p5.48xlarge": ("h100-sxm-80gb", 8),
    "p5e.48xlarge": ("h200-sxm-141gb", 8),
    "p5en.48xlarge": ("h200-sxm-141gb", 8),
    "p6-b200.48xlarge": ("b200-180gb", 8),
    "p4d.24xlarge": ("a100-sxm4-40gb", 8),
    "p4de.24xlarge": ("a100-sxm4-80gb", 8),
    "g6e.xlarge": ("l40s-48gb", 1),
    "g6.xlarge": ("l4-24gb", 1),
    "g5.xlarge": ("a10g-24gb", 1),
    "g4dn.xlarge": ("t4-16gb", 1),
}


class AwsSource(Source):
    name = "aws"
    cadence = "daily"

    def fetch(self, observed_at):
        req = urllib.request.Request(URL, headers={"User-Agent": UA})
        best = {}  # instance type -> lowest qualifying on-demand price
        with urllib.request.urlopen(req, timeout=300) as resp:
            text = io.TextIOWrapper(resp, encoding="utf-8", newline="")
            reader = csv.reader(text)
            cols = None
            for row in reader:
                if cols is None:
                    if row and row[0] == "SKU" and "PricePerUnit" in row:
                        cols = {name.strip().lower(): i for i, name in enumerate(row)}
                    continue

                def get(key):
                    i = cols.get(key)
                    return row[i].strip() if i is not None and i < len(row) else ""

                itype = get("instance type")
                if itype not in INSTANCES:
                    continue
                if get("termtype") != "OnDemand" or get("unit") != "Hrs":
                    continue
                if get("currency") != "USD" or get("tenancy") != "Shared":
                    continue
                if get("operating system") != "Linux":
                    continue
                if get("pre installed s/w") not in ("", "NA"):
                    continue
                if get("capacitystatus") not in ("", "Used"):
                    continue
                loc = get("location")
                if loc and loc != "US East (N. Virginia)":
                    continue
                try:
                    price = float(get("priceperunit"))
                except ValueError:
                    continue
                if price <= 0:
                    continue
                if itype not in best or price < best[itype]:
                    best[itype] = price

        # Two instance types can carry the same GPU family (p5e/p5en → H200);
        # ids must be unique, so keep the cheapest per family.
        by_family = {}
        for itype, price in best.items():
            family, ngpus = INSTANCES[itype]
            per_gpu = price / ngpus
            cur = by_family.get(family)
            if cur is None or per_gpu < cur[1] / cur[2]:
                by_family[family] = (itype, price, ngpus)

        offers = []
        for family, (itype, price, ngpus) in sorted(by_family.items()):
            offers.append({
                "id": make_id("aws", family, "us-east-1", "on_demand"),
                "provider": "aws",
                "sku": family,
                "price": round(price / ngpus, 4),
                "unit": "usd_per_hour",
                "pricing_type": "on_demand",
                "region": "us-east-1",
                "attrs": {
                    "instance_type": itype,
                    "gpus_per_instance": ngpus,
                    "instance_price": price,
                    "metric": "instance_list_per_gpu",
                },
                "provenance": {"url": PROVENANCE, "observed_at": observed_at},
                "fixture": False,
            })
        return offers
