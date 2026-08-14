"""Static site + API builder.

Renders from the accumulated snapshots, the spec table, and the monetization
config. Core rule from the data model: a GPU *memory configuration* is an
identity — comparison and history only ever happen within a family
(h100-pcie-80gb and h100-nvl-94gb are different products). Cross-family
context comes from value lenses ($/GB-VRAM-hr) computed off nameplate specs,
never from raw price ranking."""

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
BASE_URL = "https://gpudiff.com"

CSS = """
:root { --bg:#ffffff; --ink:#16181d; --mut:#5c6470; --line:#e3e6ea; --card:#f6f7f9;
        --cut:#0a7d43; --raise:#b42324; --acc:#2451b3; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#121418; --ink:#e8eaef; --mut:#98a1ad; --line:#2a2e36; --card:#1a1d23;
          --cut:#4cc98a; --raise:#e58a8a; --acc:#8aa8ef; }
}
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
       font:15px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; }
.wrap { max-width:1000px; margin:0 auto; padding:28px 18px 64px; }
header.site { display:flex; flex-wrap:wrap; align-items:baseline; gap:10px 18px; margin-bottom:6px; }
.brand { font-size:22px; font-weight:700; letter-spacing:-.01em; text-decoration:none; color:var(--ink); }
.brand b { color:var(--acc); }
.tag { color:var(--mut); }
nav.site a { color:var(--mut); text-decoration:none; margin-right:14px; }
nav.site a:hover { color:var(--ink); }
.sub { border:1px solid var(--line); background:var(--card); border-radius:6px;
       padding:10px 14px; margin:18px 0; display:flex; flex-wrap:wrap; gap:8px 16px; align-items:center; }
.sub a { color:var(--acc); }
h1 { font-size:26px; margin:18px 0 6px; letter-spacing:-.01em; }
h2 { font-size:19px; margin:30px 0 8px; }
p { max-width:72ch; }
.mut { color:var(--mut); }
small.mut { display:block; margin-top:4px; }
table { border-collapse:collapse; width:100%; font-variant-numeric:tabular-nums; }
th { text-align:left; font-size:12px; text-transform:uppercase; letter-spacing:.06em;
     color:var(--mut); padding:8px 10px; border-bottom:1px solid var(--line); white-space:nowrap; }
td { padding:8px 10px; border-bottom:1px solid var(--line); vertical-align:middle; }
td.n, th.n { text-align:right; }
tr:hover td { background:var(--card); }
a { color:var(--acc); }
.chg { list-style:none; padding:0; margin:0; }
.chg li { padding:7px 0; border-bottom:1px solid var(--line); }
.chg time { color:var(--mut); margin-right:10px; font-variant-numeric:tabular-nums; }
.cut { color:var(--cut); font-weight:600; }
.raise { color:var(--raise); font-weight:600; }
.badge { font-size:11px; border:1px solid var(--line); border-radius:4px; padding:1px 6px;
         color:var(--mut); white-space:nowrap; }
.spark { vertical-align:middle; }
.tablewrap { overflow-x:auto; }
footer.site { margin-top:48px; padding-top:16px; border-top:1px solid var(--line);
              color:var(--mut); font-size:13px; }
footer.site a { color:var(--mut); }
.specbox { border:1px solid var(--line); background:var(--card); border-radius:6px;
           padding:12px 16px; margin:12px 0; display:flex; flex-wrap:wrap; gap:6px 26px; }
.specbox div b { display:block; font-size:12px; text-transform:uppercase; letter-spacing:.06em;
                 color:var(--mut); font-weight:600; }
input.em { padding:7px 10px; border:1px solid var(--line); border-radius:5px;
           background:var(--bg); color:var(--ink); min-width:210px; }
button.em { padding:7px 14px; border:1px solid var(--acc); border-radius:5px;
            background:var(--acc); color:#fff; cursor:pointer; }
"""


# ---------------------------------------------------------------- data layer

def _load(path, default):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else default


def load_specs():
    return _load(ROOT / "specs" / "gpus.json", {"families": {}})["families"]


def load_monetize():
    return _load(ROOT / "monetize.json", {})


def alias_index(specs):
    idx = {}
    for fam, spec in specs.items():
        idx[fam] = fam
        for a in spec.get("aliases", []):
            idx[a] = fam
    return idx


def family_of(sku, aliases):
    return aliases.get(sku, sku)


def load_history():
    """All snapshots -> {offer_id: [(date, price), ...]} sorted by date."""
    series = {}
    offers_dir = ROOT / "data" / "offers"
    if not offers_dir.exists():
        return series
    for snap in sorted(offers_dir.glob("*.json")):
        date = snap.stem
        for o in json.loads(snap.read_text()):
            series.setdefault(o["id"], []).append((date, o["price"]))
    return series


def group_families(offers, specs, aliases):
    """-> {family: {spec, offers[]}} — comparison only ever inside a family."""
    fams = {}
    for o in offers:
        fam = family_of(o["sku"], aliases)
        fams.setdefault(fam, {"spec": specs.get(fam), "offers": []})["offers"].append(o)
    for fam in fams.values():
        fam["offers"].sort(key=lambda o: o["price"])
    return fams


def fam_display(fam, entry):
    return entry["spec"]["display"] if entry.get("spec") else fam.replace("-", " ").upper()


# ------------------------------------------------------------------- pieces

def esc(s):
    return html.escape(str(s))


def outbound(offer, monetize):
    ref = (monetize.get("referral_links") or {}).get(offer["provider"], "")
    if ref:
        return ref, ' rel="sponsored noopener"'
    home = (monetize.get("provider_home") or {}).get(offer["provider"])
    return home or offer["provenance"]["url"], ' rel="noopener"'


def metric_badge(offer):
    metric = (offer.get("attrs") or {}).get("metric", "list")
    n = (offer.get("attrs") or {}).get("sample_size")
    label = {"list_price": "list", "p25_per_gpu_dph_verified": f"p25 ×{n}" if n else "p25"}.get(metric, "list")
    return f'<span class="badge" title="How this number is measured">{esc(label)}</span>'


def sparkline(points, width=120, height=26):
    if len(points) < 2:
        return f'<span class="mut" title="History accrues daily">since {esc(points[0][0])}</span>' if points else ""
    prices = [p for _, p in points]
    lo, hi = min(prices), max(prices)
    span = (hi - lo) or 1.0
    step = width / (len(points) - 1)
    coords = [(round(i * step, 1), round(height - 3 - (p - lo) / span * (height - 6), 1))
              for i, (_, p) in enumerate(points)]
    pts = " ".join(f"{x},{y}" for x, y in coords)
    lx, ly = coords[-1]
    color = "var(--cut)" if prices[-1] <= prices[0] else "var(--raise)"
    return (f'<svg class="spark" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
            f'role="img" aria-label="price history {lo} to {hi}">'
            f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.5"/>'
            f'<circle cx="{lx}" cy="{ly}" r="2.4" fill="{color}"/></svg>')


def chg_html(e, aliases):
    fam = family_of(e["id"].split(":")[1], aliases)
    cls = ""
    if e["kind"] == "price_change":
        cls = "cut" if e["new_price"] < e["old_price"] else "raise"
    return (f'<li><time>{esc(e["date"])}</time> '
            f'<a href="/gpu/{esc(fam)}.html" class="{cls}">{esc(e["summary"])}</a></li>')


def subscribe_block(monetize):
    user = monetize.get("buttondown_username", "")
    email = ""
    if user:
        email = (f'<form action="https://buttondown.com/api/emails/embed-subscribe/{esc(user)}" '
                 f'method="post" style="display:flex;gap:8px;flex-wrap:wrap">'
                 f'<input class="em" type="email" name="email" placeholder="you@work.gpu" required>'
                 f'<button class="em" type="submit">Get the weekly diff</button></form>')
    return (f'<div class="sub"><strong>Follow the diffs:</strong> '
            f'<a href="/rss.xml">RSS</a> <span class="mut">·</span> '
            f'<a href="/api/">Free API</a> <span class="mut">·</span> '
            f'<a href="{esc(monetize.get("sponsor_url", "#"))}">Sponsor this site</a> {email}</div>')


def page(title, body, monetize, desc="", jsonld=""):
    nav = ('<nav class="site"><a href="/">prices</a><a href="/changelog.html">changelog</a>'
           '<a href="/api/">api</a><a href="https://github.com/graemegilmourbates/gpudiff">source</a></nav>')
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc or title)}">
<link rel="alternate" type="application/rss+xml" title="gpudiff changelog" href="/rss.xml">
<style>{CSS}</style>{jsonld}
</head>
<body><div class="wrap">
<header class="site"><a class="brand" href="/">gpu<b>diff</b></a>
<span class="tag">the public record of change in GPU cloud pricing</span>{nav}</header>
{subscribe_block(monetize)}
{body}
<footer class="site">Every datum links its source and is versioned in
<a href="https://github.com/graemegilmourbates/gpudiff">public git history</a>.
Data: CC BY 4.0 — cite gpudiff.com. Nameplate specs are vendor claims, not measured
throughput. Vast prices are the 25th percentile of verified marketplace listings
(what a careful buyer actually gets); RunPod prices are list. Outbound provider
links may carry referral codes; they never affect the numbers.</footer>
</div></body></html>"""


# ------------------------------------------------------------------ renders

def render_index(fams, changelog, date, monetize):
    rows = []
    def sort_key(item):
        fam, entry = item
        spec = entry.get("spec") or {}
        return (-(spec.get("vram_gb") or 0), fam)
    for fam, entry in sorted(fams.items(), key=sort_key):
        spec = entry.get("spec") or {}
        best = entry["offers"][0]
        url, rel = outbound(best, monetize)
        vram = spec.get("vram_gb")
        per_gb = f"${best['price'] / vram:.3f}" if vram else "—"
        rows.append(
            f"<tr><td><a href='/gpu/{esc(fam)}.html'><strong>{esc(fam_display(fam, entry))}</strong></a></td>"
            f"<td class='n'>{vram or '—'}</td>"
            f"<td class='n'><strong>${best['price']:.2f}</strong>/hr</td>"
            f"<td>{esc(best['provider'])} · {esc(best.get('region', ''))} {metric_badge(best)}</td>"
            f"<td class='n'>{per_gb}</td>"
            f"<td class='n'>{len(entry['offers'])}</td>"
            f"<td><a href='{esc(url)}'{rel}>rent</a></td></tr>")
    recent = [e for e in changelog if e["kind"] == "price_change"][-15:]
    aliases = alias_index(load_specs())
    log = "\n".join(chg_html(e, aliases) for e in reversed(recent)) or \
          '<li class="mut">Tracking began today — diffs appear with the next price move.</li>'
    jsonld = ('<script type="application/ld+json">' + json.dumps({
        "@context": "https://schema.org", "@type": "Dataset",
        "name": "gpudiff — GPU cloud price changelog",
        "description": "Versioned GPU cloud pricing with provenance: current offers, price history, and a changelog of every change.",
        "url": BASE_URL, "license": "https://creativecommons.org/licenses/by/4.0/",
        "creator": {"@type": "Organization", "name": "gpudiff"},
        "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json",
                          "contentUrl": f"{BASE_URL}/api/v1/offers.json"}],
    }) + '</script>')
    body = f"""
<h1>What changed in GPU cloud pricing</h1>
<ul class="chg">{log}</ul>
<p><a href="/changelog.html">Full changelog →</a></p>
<h2>Cheapest current price by GPU</h2>
<p class="mut">Grouped by memory configuration — an H100 NVL 94GB and an H100 PCIe 80GB are
different products, so they never share a row. Prices refresh hourly; snapshot {esc(date)}.</p>
<div class="tablewrap"><table>
<thead><tr><th>GPU</th><th class="n">VRAM GB</th><th class="n">Best $/hr</th><th>Where</th>
<th class="n">$/GB·hr</th><th class="n">Offers</th><th></th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<small class="mut">$/GB·hr = hourly price per gigabyte of nameplate VRAM — a screening lens,
not a verdict; interconnect, cloud tier, and real throughput still matter.</small>"""
    return page("gpudiff — GPU cloud price changelog", body, monetize,
                "Live GPU cloud prices with history, provenance, and a changelog of every change. H100, H200, B200, A100, RTX 4090/5090 and more.",
                jsonld)


def render_family(fam, entry, history, changelog, monetize, aliases):
    spec = entry.get("spec")
    specbox = ""
    if spec:
        bw = f"{spec['mem_bw_gbs']} GB/s" if spec.get("mem_bw_gbs") else "—"
        specbox = (f'<div class="specbox">'
                   f'<div><b>VRAM</b>{spec["vram_gb"]} GB {esc(spec.get("mem_type", ""))}</div>'
                   f'<div><b>Memory bandwidth</b>{bw}</div>'
                   f'<div><b>Vendor</b>{esc(spec.get("vendor", ""))}</div>'
                   f'<div><b>Nameplate source</b><a href="{esc(spec["provenance"])}" rel="noopener">spec sheet</a></div>'
                   f'</div>')
    rows = []
    for o in entry["offers"]:
        url, rel = outbound(o, monetize)
        series = history.get(o["id"], [])
        rows.append(
            f"<tr><td>{esc(o['provider'])}</td><td>{esc(o.get('region', ''))}</td>"
            f"<td>{esc(o['pricing_type'])} {metric_badge(o)}</td>"
            f"<td class='n'><strong>${o['price']:.2f}</strong>/hr</td>"
            f"<td>{sparkline(series)}</td>"
            f"<td><a href='{esc(o['provenance']['url'])}' rel='noopener'>source</a></td>"
            f"<td><a href='{esc(url)}'{rel}>rent</a></td></tr>")
    fam_entries = [e for e in changelog
                   if family_of(e["id"].split(":")[1], aliases) == fam][-20:]
    log = "\n".join(chg_html(e, aliases) for e in reversed(fam_entries)) or \
          '<li class="mut">No recorded changes yet for this GPU.</li>'
    name = fam_display(fam, entry)
    body = f"""
<h1>{esc(name)} — cloud rental prices</h1>
{specbox}
<h2>Current offers</h2>
<div class="tablewrap"><table>
<thead><tr><th>Provider</th><th>Region / tier</th><th>Type</th><th class="n">$/hr</th>
<th>History</th><th>Provenance</th><th></th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<h2>Changelog</h2>
<ul class="chg">{log}</ul>
<p><a href="/api/v1/history/{esc(fam)}.json">History JSON for this GPU →</a></p>"""
    return page(f"{name} cloud price — gpudiff", body, monetize,
                f"Current {name} rental prices across clouds, with price history, provenance, and a changelog of every change.")


def render_changelog(changelog, monetize, aliases):
    by_date = {}
    for e in changelog:
        by_date.setdefault(e["date"], []).append(e)
    sections = []
    for date in sorted(by_date, reverse=True):
        items = "\n".join(chg_html(e, aliases) for e in by_date[date])
        sections.append(f"<h2>{esc(date)}</h2><ul class='chg'>{items}</ul>")
    body = "<h1>Changelog</h1>" + ("".join(sections) or
           "<p class='mut'>Tracking began today. The record grows with every price move.</p>")
    return page("Changelog — gpudiff", body, monetize,
                "Every recorded change in GPU cloud pricing, in order.")


def render_api_docs(monetize):
    body = f"""
<h1>Free API</h1>
<p>Static JSON on a CDN — no keys, no rate limits worth worrying about. Data is
<strong>CC BY 4.0</strong>: use it freely, cite <code>gpudiff.com</code>.</p>
<div class="tablewrap"><table>
<thead><tr><th>Endpoint</th><th>What it returns</th></tr></thead>
<tbody>
<tr><td><a href="/api/v1/offers.json">/api/v1/offers.json</a></td><td>All current offers with provenance</td></tr>
<tr><td><a href="/api/v1/families.json">/api/v1/families.json</a></td><td>Per-GPU summary: specs + cheapest current offer</td></tr>
<tr><td><a href="/api/v1/changelog.json">/api/v1/changelog.json</a></td><td>Every recorded change</td></tr>
<tr><td><a href="/api/v1/specs.json">/api/v1/specs.json</a></td><td>Nameplate spec table with vendor provenance</td></tr>
<tr><td>/api/v1/history/&lt;gpu&gt;.json</td><td>Per-offer price series for one GPU family</td></tr>
</tbody></table></div>
<p class="mut">Paths are versioned and stable. A keyed tier (webhooks, alerts,
bulk history, SLA) ships when demand shows up — watch the <a href="/rss.xml">feed</a>.</p>"""
    return page("API — gpudiff", body, monetize,
                "Free JSON API for GPU cloud prices, history, and the changelog. CC BY 4.0.")


def render_rss(changelog):
    items = []
    for e in [e for e in changelog if e["kind"] == "price_change"][-50:][::-1]:
        items.append(f"""<item>
<title>{esc(e['summary'])}</title>
<link>{BASE_URL}/changelog.html</link>
<guid isPermaLink="false">{esc(e['id'])}:{esc(e['date'])}</guid>
<pubDate>{esc(e['date'])}T00:00:00Z</pubDate>
</item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>gpudiff — GPU cloud price changelog</title>
<link>{BASE_URL}</link>
<description>Every recorded change in GPU cloud pricing.</description>
{''.join(items)}
</channel></rss>"""


# -------------------------------------------------------------------- build

def build_site(offers, changelog, date):
    specs = load_specs()
    aliases = alias_index(specs)
    monetize = load_monetize()
    history = load_history()
    fams = group_families(offers, specs, aliases)

    (SITE / "gpu").mkdir(parents=True, exist_ok=True)
    (SITE / "api" / "v1" / "history").mkdir(parents=True, exist_ok=True)

    (SITE / "index.html").write_text(render_index(fams, changelog, date, monetize))
    (SITE / "changelog.html").write_text(render_changelog(changelog, monetize, aliases))
    (SITE / "api" / "index.html").write_text(render_api_docs(monetize))
    (SITE / "rss.xml").write_text(render_rss(changelog))

    fam_summaries = []
    for fam, entry in fams.items():
        (SITE / "gpu" / f"{fam}.html").write_text(
            render_family(fam, entry, history, changelog, monetize, aliases))
        fam_hist = {o["id"]: history.get(o["id"], []) for o in entry["offers"]}
        (SITE / "api" / "v1" / "history" / f"{fam}.json").write_text(
            json.dumps({"family": fam, "series": fam_hist}, indent=2) + "\n")
        best = entry["offers"][0]
        spec = entry.get("spec") or {}
        fam_summaries.append({
            "family": fam, "display": fam_display(fam, entry),
            "vram_gb": spec.get("vram_gb"), "mem_bw_gbs": spec.get("mem_bw_gbs"),
            "best": {"price": best["price"], "provider": best["provider"],
                     "region": best.get("region"), "unit": best["unit"]},
            "offers": len(entry["offers"]),
        })

    api = SITE / "api" / "v1"
    (api / "offers.json").write_text(json.dumps(offers, indent=2) + "\n")
    (api / "changelog.json").write_text(json.dumps(changelog, indent=2) + "\n")
    (api / "specs.json").write_text(json.dumps(specs, indent=2) + "\n")
    (api / "families.json").write_text(json.dumps(fam_summaries, indent=2) + "\n")
    # Legacy aliases from the day-one URLs
    (SITE / "api" / "offers.json").write_text(json.dumps(offers, indent=2) + "\n")
    (SITE / "api" / "changelog.json").write_text(json.dumps(changelog, indent=2) + "\n")

    urls = [f"{BASE_URL}/", f"{BASE_URL}/changelog.html", f"{BASE_URL}/api/"] + \
           [f"{BASE_URL}/gpu/{fam}.html" for fam in sorted(fams)]
    (SITE / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
        "".join(f"<url><loc>{esc(u)}</loc></url>\n" for u in urls) + "</urlset>\n")
    (SITE / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n")

    return SITE / "index.html"
