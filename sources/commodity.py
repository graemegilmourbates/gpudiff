"""Commodity chip prices via the US Bureau of Labor Statistics — no key, no
scraping, no paywall. BLS publishes producer price indexes monthly through a
public API. There is no DRAM-only series; the closest honest proxies are the
all-semiconductor index and the Integrated Circuit Packages line (memory chips
are integrated circuits). We label them exactly as BLS does and never call
them "DRAM spot" — the daily spot data lives behind TrendForce's paywall.

Emits one index-valued offer per series (unit ppi_index) plus the last twelve
monthly points in attrs so the page can show a trend immediately. Daily cadence
with carry-forward: one request a day is far under the 25/day anonymous limit."""

import json
import urllib.request
import datetime as dt

from .base import Source

API = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
UA = "FoundryBot/0.1 (pricing aggregator; gpudiff.com)"
PROVENANCE = "https://www.bls.gov/ppi/"
SERIES = {
    "PCU334413334413": ("semiconductors-ppi",
                        "PPI: Semiconductor & related device manufacturing (all)"),
    "PCU3344133344131": ("integrated-circuits-ppi",
                         "PPI: Semiconductor manufacturing — Integrated circuit packages"),
}


class CommoditySource(Source):
    name = "bls"
    cadence = "daily"

    def fetch(self, observed_at):
        year = dt.datetime.now(dt.timezone.utc).year
        body = json.dumps({"seriesid": list(SERIES), "startyear": str(year - 1),
                           "endyear": str(year)}).encode()
        req = urllib.request.Request(API, data=body, headers={
            "Content-Type": "application/json", "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=40) as resp:
            payload = json.load(resp)
        if payload.get("status") != "REQUEST_SUCCEEDED":
            raise RuntimeError(f"BLS: {payload.get('status')} {payload.get('message')}")

        offers = []
        for s in payload.get("Results", {}).get("series", []):
            sid = s.get("seriesID")
            if sid not in SERIES:
                continue
            rows = [r for r in s.get("data", []) if r.get("period", "").startswith("M")]
            if not rows:
                continue
            rows.sort(key=lambda r: (r["year"], r["period"]))  # oldest -> newest
            latest = rows[-1]
            try:
                value = float(latest["value"])
            except (TypeError, ValueError):
                continue
            if value <= 0:
                continue
            sku, title = SERIES[sid]
            recent = [[f"{r['year']}-{r['period'][1:]}", float(r["value"])]
                      for r in rows[-12:] if r.get("value") not in (None, "-")]
            offers.append({
                "id": f"bls:{sku}:us:list",
                "provider": "bls",
                "sku": sku,
                "price": round(value, 3),
                "unit": "ppi_index",
                "pricing_type": "list",
                "region": "us",
                "attrs": {"series_id": sid, "title": title,
                          "period": f"{latest['year']}-{latest['period'][1:]}",
                          "recent": recent, "metric": "bls_ppi_monthly"},
                "provenance": {"url": f"https://data.bls.gov/timeseries/{sid}",
                               "observed_at": observed_at},
                "fixture": False,
            })
        return offers
