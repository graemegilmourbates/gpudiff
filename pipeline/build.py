"""Static site + API builder. Renders site/ from the latest snapshot and the
changelog. Deliberately minimal: the real surface design is week-2 work; this
proves the data → surfaces step and gives CI something to deploy."""

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"


def _fmt_price(offer):
    unit = {"usd_per_hour": "/hr", "usd_per_month": "/mo", "usd_per_unit": ""}[offer["unit"]]
    return f"${offer['price']:.2f}{unit}"


def build_site(offers, changelog, date):
    (SITE / "api").mkdir(parents=True, exist_ok=True)
    (SITE / "api" / "offers.json").write_text(json.dumps(offers, indent=2) + "\n")
    (SITE / "api" / "changelog.json").write_text(json.dumps(changelog, indent=2) + "\n")

    rows = "\n".join(
        f"<tr><td>{html.escape(o['provider'])}</td><td>{html.escape(o['sku'])}</td>"
        f"<td>{html.escape(o.get('region', ''))}</td><td>{html.escape(o['pricing_type'])}</td>"
        f"<td class='num'>{_fmt_price(o)}</td>"
        f"<td><a href='{html.escape(o['provenance']['url'])}'>source</a></td></tr>"
        for o in sorted(offers, key=lambda o: (o["sku"], o["price"]))
    )
    recent = [e for e in changelog if e["kind"] == "price_change"][-20:]
    log_items = "\n".join(
        f"<li><time>{html.escape(e['date'])}</time> {html.escape(e['summary'])}</li>"
        for e in reversed(recent)
    ) or "<li>No price changes recorded yet.</li>"

    fixture_note = ""
    if any(o.get("fixture") for o in offers):
        fixture_note = "<p class='warn'>Fixture data — dev build, not production.</p>"

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GPU Price Changelog</title>
<style>
  body {{ font: 15px/1.5 system-ui, sans-serif; margin: 2rem auto; max-width: 900px; padding: 0 1rem; color: #1b2130; }}
  h1 {{ font-size: 1.6rem; }} h2 {{ font-size: 1.15rem; margin-top: 2rem; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ text-align: left; padding: .45rem .6rem; border-bottom: 1px solid #dcdfe7; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  time {{ color: #5b6478; font-variant-numeric: tabular-nums; margin-right: .5rem; }}
  .warn {{ background: #fff3cd; border: 1px solid #e0c96b; padding: .5rem .8rem; }}
  footer {{ margin-top: 3rem; color: #5b6478; font-size: .85rem; }}
</style>
</head>
<body>
<h1>GPU Price Changelog</h1>
<p>The public record of change in GPU cloud pricing. Snapshot: {html.escape(date)}.</p>
{fixture_note}
<h2>What changed</h2>
<ul>{log_items}</ul>
<h2>Current offers</h2>
<table>
<thead><tr><th>Provider</th><th>SKU</th><th>Region</th><th>Type</th><th class="num">Price</th><th>Provenance</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
<footer>Every datum links its source. API: <a href="api/offers.json">offers.json</a> · <a href="api/changelog.json">changelog.json</a></footer>
</body>
</html>
"""
    (SITE / "index.html").write_text(page)
    return SITE / "index.html"
