"""SaaS pricing changelog, v1: price-signature scans of vendor pricing pages.

We make no attempt to map plans — that's a per-vendor parser treadmill.
Instead: extract every USD amount embedded in the page ($2–$2000 band),
publish the entry (lowest) and top (highest) detected price per company, and
let the diff engine catch movement at either end. It's a page-level signal,
badged as such; the 40% delta gate quarantines promo-noise jumps for human
review. Companies whose pages fail to fetch or yield no amounts are simply
absent — missing beats wrong. Daily cadence; be polite to marketing sites."""

import re
import urllib.request

from .base import Source, make_id

UA = ("Mozilla/5.0 (compatible; FoundryBot/0.1; +https://gpudiff.com/methodology.html)")
AMOUNT = re.compile(r"\$(\d{1,3}(?:,\d{3})?(?:\.\d{1,2})?)")

WATCHLIST = {
    "notion": "https://www.notion.com/pricing",
    "slack": "https://slack.com/pricing",
    "figma": "https://www.figma.com/pricing/",
    "github": "https://github.com/pricing",
    "zoom": "https://www.zoom.com/en/pricing/",
    "dropbox": "https://www.dropbox.com/plans",
    "asana": "https://asana.com/pricing",
    "monday": "https://monday.com/pricing",
    "linear": "https://linear.app/pricing",
    "airtable": "https://airtable.com/pricing",
    "clickup": "https://clickup.com/pricing",
    "miro": "https://miro.com/pricing/",
    "zendesk": "https://www.zendesk.com/pricing/",
    "hubspot": "https://www.hubspot.com/pricing/crm",
    "mailchimp": "https://mailchimp.com/pricing/marketing/",
    "shopify": "https://www.shopify.com/pricing",
    "webflow": "https://webflow.com/pricing",
    "vercel": "https://vercel.com/pricing",
    "netlify": "https://www.netlify.com/pricing/",
    "1password": "https://1password.com/pricing",
    "canva": "https://www.canva.com/pricing/",
    "loom": "https://www.loom.com/pricing",
    "buffer": "https://buffer.com/pricing",
    "basecamp": "https://basecamp.com/pricing",
    "atlassian-jira": "https://www.atlassian.com/software/jira/pricing",
}


def _signature(html_text):
    amounts = set()
    for m in AMOUNT.finditer(html_text):
        try:
            v = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if 1 <= v <= 2000:
            amounts.add(round(v, 2))
    return sorted(amounts)


class SaasPagesSource(Source):
    name = "saaspages"
    cadence = "daily"

    @property
    def emits(self):
        return set(WATCHLIST)

    def fetch(self, observed_at):
        offers = []
        for company, url in WATCHLIST.items():
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=25) as resp:
                    html_text = resp.read(3_000_000).decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001 — bot walls, timeouts: company is absent today
                continue
            sig = _signature(html_text)
            # Quality gate: one lone amount is usually marketing noise ("save
            # $1,000"), and an entry price above $150 on this watchlist means
            # the scan latched onto junk. Drop the company rather than guess.
            if len(sig) < 2 or sig[0] > 150:
                continue
            points = [("pricing-entry", sig[0])]
            if len(sig) > 1:
                points.append(("pricing-top", sig[-1]))
            for sku, price in points:
                offers.append({
                    "id": make_id(company, sku, "global", "list"),
                    "provider": company,
                    "sku": sku,
                    "price": price,
                    "unit": "usd_per_unit",
                    "pricing_type": "list",
                    "region": "global",
                    "attrs": {
                        "price_points": sig,
                        "point_count": len(sig),
                        "metric": "page_scan",
                    },
                    "provenance": {"url": url, "observed_at": observed_at},
                    "fixture": False,
                })
        return offers
