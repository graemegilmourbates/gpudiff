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


def load_watchlist():
    return _load(ROOT / "specs" / "llm_watchlist.json", {"models": {}})["models"]


def canon_model(model_id):
    """Canonical model name shared across routers — mirrors sources/routers.py."""
    import re
    s = str(model_id).split("@")[0].strip().lower().split("/")[-1]
    return re.sub(r"[^a-z0-9.+-]+", "-", s).strip("-")


ROUTER_LABEL = {"openrouter": "OpenRouter", "requesty": "Requesty", "glama": "Glama",
                "novita": "Novita", "deepinfra": "DeepInfra", "ramp": "Ramp Router"}

# Gateway fees, quoted from each gateway's own docs. Token prices are only half
# the bill: two gateways can charge the same per token and still differ on what
# it costs to put money in.
ROUTER_FEES = {
    "openrouter": ("No markup on token prices (provider pass-through), but credit "
                   "purchases cost 5.5% via card ($0.80 minimum) or 5% via crypto; "
                   "BYOK usage above the monthly allowance is charged 5%.",
                   "https://openrouter.ai/docs/faq"),
    "ramp": ("Free through 2026 — no gateway fee, tokens billed at provider list "
             "price, first $26 of credit free.", "https://router.com/"),
}


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


def fam_vram(fam, entry):
    """VRAM fallback chain: spec table -> the slug itself (rtx-3070-8gb) ->
    provider-reported attrs. The GB is identity, so surface it wherever known."""
    spec = entry.get("spec") or {}
    if spec.get("vram_gb"):
        return spec["vram_gb"]
    import re
    m = re.search(r"-(\d+)gb$", fam)
    if m:
        return int(m.group(1))
    reported = [o.get("attrs", {}).get("vram_gb") for o in entry["offers"]]
    reported = [v for v in reported if isinstance(v, (int, float))]
    return int(max(reported)) if reported else None


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
    label = {"list_price": "list",
             "p25_per_gpu_dph_verified": f"p25 ×{n}" if n else "p25",
             "p25_min_bid_per_gpu": f"p25 bid ×{n}" if n else "p25 bid",
             "instance_list_per_gpu": "instance-bundled",
             "page_scan": "page scan",
             "openrouter_list": "list"}.get(metric, "list")
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


LLM_PROVIDERS = {"openrouter", "requesty", "glama", "novita", "deepinfra", "ramp"}


def chg_html(e, aliases):
    provider, sku = e["id"].split(":")[0], e["id"].split(":")[1]
    if provider in LLM_PROVIDERS:
        href = "/llm/"
    elif sku.startswith("pricing-"):
        href = "/saas/"
    else:
        href = f"/gpu/{esc(family_of(sku, aliases))}.html"
    cls = ""
    if e["kind"] == "price_change":
        cls = "cut" if e["new_price"] < e["old_price"] else "raise"
    return (f'<li><time>{esc(e["date"])}</time> '
            f'<a href="{href}" class="{cls}">{esc(e["summary"])}</a></li>')


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


def page(title, body, monetize, desc="", jsonld="", path="/"):
    nav = ('<nav class="site"><a href="/">gpus</a><a href="/llm/">llm apis</a>'
           '<a href="/saas/">saas</a><a href="/fit.html">fit</a>'
           '<a href="/changelog.html">changelog</a>'
           '<a href="/methodology.html">methodology</a>'
           '<a href="/api/">api</a><a href="https://github.com/graemegilmourbates/gpudiff">source</a></nav>')
    gc = monetize.get("goatcounter_code", "")
    analytics = (f'<script data-goatcounter="https://{esc(gc)}.goatcounter.com/count" '
                 f'async src="https://gc.zgo.at/count.js"></script>') if gc else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc or title)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc or title)}">
<meta property="og:url" content="{BASE_URL}{esc(path)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="gpudiff">
<meta name="twitter:card" content="summary">
<link rel="canonical" href="{BASE_URL}{esc(path)}">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="alternate" type="application/rss+xml" title="gpudiff changelog" href="/rss.xml">
<style>{CSS}</style>{jsonld}{analytics}
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
        return (-(fam_vram(fam, entry) or 0), fam)
    for fam, entry in sorted(fams.items(), key=sort_key):
        od = [o for o in entry["offers"] if o["pricing_type"] == "on_demand"]
        spot = [o for o in entry["offers"] if o["pricing_type"] == "spot"]
        best = od[0] if od else entry["offers"][0]
        url, rel = outbound(best, monetize)
        vram = fam_vram(fam, entry)
        per_gb = f"${best['price'] / vram:.3f}" if vram else "—"
        spot_cell = f"${spot[0]['price']:.2f}" if spot else "—"
        rows.append(
            f"<tr><td><a href='/gpu/{esc(fam)}.html'><strong>{esc(fam_display(fam, entry))}</strong></a></td>"
            f"<td class='n'>{vram or '—'}</td>"
            f"<td class='n'><strong>${best['price']:.2f}</strong>/hr</td>"
            f"<td>{esc(best['provider'])} · {esc(best.get('region', ''))} {metric_badge(best)}</td>"
            f"<td class='n'>{spot_cell}</td>"
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
<p class="mut">Now also tracking <a href="/llm/">LLM API prices per token</a> (beta).</p>
<h1>What changed in GPU cloud pricing</h1>
<ul class="chg">{log}</ul>
<p><a href="/changelog.html">Full changelog →</a></p>
<h2>Cheapest current price by GPU</h2>
<p class="mut">Grouped by memory configuration — an H100 NVL 94GB and an H100 PCIe 80GB are
different products, so they never share a row. Prices refresh hourly; snapshot {esc(date)}.
By provider: <a href="/provider/vast.html">Vast.ai</a> · <a href="/provider/runpod.html">RunPod</a> ·
<a href="/provider/aws.html">AWS</a> · <a href="/provider/azure.html">Azure</a>. Head-to-head:
<a href="/compare/h100-sxm-80gb-vs-h200-sxm-141gb.html">H100 vs H200</a> ·
<a href="/compare/a100-sxm4-80gb-vs-h100-sxm-80gb.html">A100 vs H100</a> ·
<a href="/compare/rtx-4090-24gb-vs-rtx-5090-32gb.html">4090 vs 5090</a>.</p>
<div class="tablewrap"><table>
<thead><tr><th>GPU</th><th class="n">VRAM GB</th><th class="n">On-demand $/hr</th><th>Where</th>
<th class="n">Spot from</th><th class="n">$/GB·hr</th><th class="n">Offers</th><th></th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<small class="mut">$/GB·hr = hourly price per gigabyte of nameplate VRAM — a screening lens,
not a verdict; interconnect, cloud tier, and real throughput still matter.</small>"""
    return page("GPU Cloud Pricing Compared — H100, H200, B200, A100, RTX 4090 rental prices, updated hourly | gpudiff",
                body, monetize,
                "Compare GPU cloud rental prices across Vast.ai, RunPod, AWS, and Azure — on-demand and spot, updated hourly, with price history and a changelog of every change.",
                jsonld)


def related_families(fam, entry, fams, n=6):
    """Nearest families by VRAM (the axis buyers actually shop along)."""
    v = fam_vram(fam, entry) or 0
    others = [(abs((fam_vram(f, e) or 0) - v), f, e) for f, e in fams.items() if f != fam]
    return [(f, e) for _, f, e in sorted(others, key=lambda t: (t[0], t[1]))[:n]]


def render_family(fam, entry, history, changelog, monetize, aliases, fams=None):
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
        stk = (o.get("attrs") or {}).get("stock")
        stock_note = f" <span class='mut'>· {esc(stk)} stock</span>" if stk else ""
        rows.append(
            f"<tr><td>{esc(o['provider'])}</td><td>{esc(o.get('region', ''))}</td>"
            f"<td>{esc(o['pricing_type'])} {metric_badge(o)}{stock_note}</td>"
            f"<td class='n'><strong>${o['price']:.2f}</strong>/hr</td>"
            f"<td>{sparkline(series)}</td>"
            f"<td><a href='{esc(o['provenance']['url'])}' rel='noopener'>source</a></td>"
            f"<td><a href='{esc(url)}'{rel}>rent</a></td></tr>")
    fam_entries = [e for e in changelog
                   if family_of(e["id"].split(":")[1], aliases) == fam][-20:]
    log = "\n".join(chg_html(e, aliases) for e in reversed(fam_entries)) or \
          '<li class="mut">No recorded changes yet for this GPU.</li>'
    name = fam_display(fam, entry)
    od = [o for o in entry["offers"] if o["pricing_type"] == "on_demand"]
    spot = [o for o in entry["offers"] if o["pricing_type"] == "spot"]
    best = od[0] if od else entry["offers"][0]
    providers = sorted({o["provider"] for o in entry["offers"]})
    n_prov = len(providers)
    hi = max(o["price"] for o in od) if od else best["price"]
    vram = fam_vram(fam, entry)

    # FAQ: written for the answer box, every number live from the snapshot.
    faqs = [
        (f"How much does an {name} cost to rent per hour?",
         f"As of the latest snapshot, {name} on-demand rental starts at ${best['price']:.2f}/hr "
         f"({best['provider']}, {best.get('region', 'global')}) and ranges up to ${hi:.2f}/hr across "
         f"{n_prov} tracked provider{'s' if n_prov != 1 else ''}. Prices refresh hourly."),
        (f"What is the cheapest {name} cloud provider right now?",
         f"{best['provider']} currently lists the lowest on-demand {name} price we track, at "
         f"${best['price']:.2f}/hr. Every number links to the page it was observed on."),
    ]
    if spot:
        faqs.append((f"Is there a cheaper spot or interruptible {name} price?",
                     f"Yes — spot/interruptible {name} capacity starts at ${spot[0]['price']:.2f}/hr "
                     f"({spot[0]['provider']}), versus ${best['price']:.2f}/hr on-demand. Spot can be "
                     f"reclaimed by the provider; use it for fault-tolerant work."))
    if vram:
        faqs.append((f"How much VRAM does the {name} have and what fits?",
                     f"{vram} GB. At fp16 that fits roughly a {int(vram / 2.4)}B-parameter model on a "
                     f"single GPU; use the fit calculator for other precisions."))
    faq_html = "".join(f"<h3>{esc(q)}</h3><p>{esc(a)}</p>" for q, a in faqs)
    faq_ld = ('<script type="application/ld+json">' + json.dumps({
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [{"@type": "Question", "name": q,
                        "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs],
    }) + '</script>')

    related = ""
    if fams:
        links = " · ".join(f'<a href="/gpu/{esc(f)}.html">{esc(fam_display(f, e))}</a>'
                           for f, e in related_families(fam, entry, fams))
        related = f"<h2>Similar GPUs by memory</h2><p>{links}</p>"

    prov_links = " · ".join(f'<a href="/provider/{esc(p)}.html">{esc(p)}</a>' for p in providers)
    body = f"""
<h1>{esc(name)} cloud rental price — {n_prov} provider{'s' if n_prov != 1 else ''} compared, updated hourly</h1>
<p class="mut">On-demand from <strong>${best['price']:.2f}/hr</strong>{f" · spot from ${spot[0]['price']:.2f}/hr" if spot else ""} · providers: {prov_links}</p>
{specbox}
<h2>Current offers</h2>
<div class="tablewrap"><table>
<thead><tr><th>Provider</th><th>Region / tier</th><th>Type</th><th class="n">$/hr</th>
<th>History</th><th>Provenance</th><th></th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<h2>Changelog</h2>
<ul class="chg">{log}</ul>
<p><a href="/api/v1/history/{esc(fam)}.json">History JSON for this GPU →</a> · <a href="/fit.html">Will my model fit?</a></p>
<h2>{esc(name)} pricing FAQ</h2>
{faq_html}
{related}"""
    return page(f"{name} Cloud Rental Price — from ${best['price']:.2f}/hr, {n_prov} providers compared | gpudiff",
                body, monetize,
                f"{name} cloud rental prices: on-demand from ${best['price']:.2f}/hr across {n_prov} providers, "
                f"spot prices, price history, and a changelog of every change. Updated hourly with provenance.",
                jsonld=faq_ld, path=f"/gpu/{fam}.html")


PROVIDER_BLURB = {
    "vast": ("Vast.ai", "a peer-to-peer GPU marketplace: many independent hosts, verified listings, "
             "on-demand and interruptible bids. Prices shown are the 25th percentile of verified "
             "listings per GPU — what a careful buyer can actually get."),
    "runpod": ("RunPod", "a GPU cloud with two tiers: Secure Cloud (data-center hosts) and Community "
               "Cloud (vetted third-party hosts, cheaper). Prices are RunPod's published list prices; "
               "we only show tiers with stock available."),
    "aws": ("AWS EC2", "the largest hyperscaler. GPUs come bundled into fixed instances (CPUs, RAM, "
            "storage attached); prices shown are on-demand Linux us-east-1 list ÷ GPU count."),
    "azure": ("Microsoft Azure", "a hyperscaler with GPU VM families (NC, ND). Prices are eastus "
              "consumption rates from the public Retail Prices API ÷ GPU count; spot rates included."),
}


def render_provider_page(provider, offers, fams, monetize, aliases):
    display, blurb = PROVIDER_BLURB.get(provider, (provider, "a tracked GPU cloud provider."))
    od = sorted([o for o in offers if o["pricing_type"] == "on_demand"], key=lambda o: o["price"])
    rows = []
    for o in od:
        fam = family_of(o["sku"], aliases)
        entry = fams.get(fam, {"spec": None, "offers": [o]})
        url, rel = outbound(o, monetize)
        rows.append(f"<tr><td><a href='/gpu/{esc(fam)}.html'><strong>{esc(fam_display(fam, entry))}</strong></a></td>"
                    f"<td>{esc(o.get('region', ''))} {metric_badge(o)}</td>"
                    f"<td class='n'><strong>${o['price']:.2f}</strong>/hr</td>"
                    f"<td><a href='{esc(url)}'{rel}>rent</a></td></tr>")
    cheapest = od[0] if od else None
    faqs = [(f"How much do {display} GPUs cost?",
             (f"{display} GPU pricing starts at ${cheapest['price']:.2f}/hr on-demand "
              f"({fam_display(family_of(cheapest['sku'], aliases), fams.get(family_of(cheapest['sku'], aliases), {'spec': None}))}) "
              f"across {len(od)} tracked configurations, updated hourly.") if cheapest else "No offers tracked right now."),
            (f"Is {display} cheaper than other GPU clouds?",
             f"It depends on the GPU — compare any card across every provider we track on its GPU page. "
             f"gpudiff records every price change, so you can also see whether {display} is trending up or down.")]
    faq_ld = ('<script type="application/ld+json">' + json.dumps({
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
                       for q, a in faqs]}) + '</script>')
    faq_html = "".join(f"<h3>{esc(q)}</h3><p>{esc(a)}</p>" for q, a in faqs)
    body = f"""
<h1>{esc(display)} GPU pricing — every tracked GPU, updated hourly</h1>
<p>{esc(display)} is {esc(blurb)}</p>
<div class="tablewrap"><table>
<thead><tr><th>GPU</th><th>Region / tier</th><th class="n">On-demand $/hr</th><th></th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<h2>{esc(display)} pricing FAQ</h2>
{faq_html}
<p class="mut">Other providers: {" · ".join(f'<a href="/provider/{esc(p)}.html">{esc(PROVIDER_BLURB.get(p, (p,))[0])}</a>' for p in PROVIDER_BLURB if p != provider)}</p>"""
    return page(f"{display} GPU Pricing ({len(od)} GPUs compared, updated hourly) | gpudiff", body, monetize,
                f"{display} GPU rental prices for every tracked GPU, with price history and a changelog of changes. Compare against other clouds.",
                jsonld=faq_ld, path=f"/provider/{provider}.html")


COMPARE_PAIRS = [
    ("h100-sxm-80gb", "h200-sxm-141gb"), ("h100-pcie-80gb", "h100-sxm-80gb"),
    ("a100-sxm4-80gb", "h100-sxm-80gb"), ("h100-sxm-80gb", "b200-180gb"),
    ("rtx-4090-24gb", "rtx-5090-32gb"), ("rtx-4090-24gb", "a100-pcie-80gb"),
    ("l40s-48gb", "a100-pcie-80gb"), ("h200-sxm-141gb", "b200-180gb"),
    ("mi300x-192gb", "h100-sxm-80gb"), ("rtx-pro-6000-96gb", "h100-pcie-80gb"),
]


def render_compare_page(a, b, fams, monetize):
    ea, eb = fams[a], fams[b]
    na, nb = fam_display(a, ea), fam_display(b, eb)
    def best(e):
        od = [o for o in e["offers"] if o["pricing_type"] == "on_demand"]
        return od[0] if od else e["offers"][0]
    ba, bb = best(ea), best(eb)
    va, vb = fam_vram(a, ea), fam_vram(b, eb)
    sa, sb = (ea.get("spec") or {}), (eb.get("spec") or {})
    def row(label, x, y):
        return f"<tr><td>{esc(label)}</td><td class='n'>{x}</td><td class='n'>{y}</td></tr>"
    ratio = bb["price"] / ba["price"] if ba["price"] else 0
    verdict = (f"{nb} currently costs {ratio:.1f}× the {na} at the cheapest on-demand price we track "
               f"(${bb['price']:.2f} vs ${ba['price']:.2f}/hr).") if ratio else ""
    body = f"""
<h1>{esc(na)} vs {esc(nb)}: cloud rental price comparison</h1>
<p>{esc(verdict)} Both numbers refresh hourly and link to their source.</p>
<div class="tablewrap"><table>
<thead><tr><th></th><th class="n"><a href="/gpu/{esc(a)}.html">{esc(na)}</a></th><th class="n"><a href="/gpu/{esc(b)}.html">{esc(nb)}</a></th></tr></thead>
<tbody>
{row("Cheapest on-demand $/hr", f"${ba['price']:.2f} ({esc(ba['provider'])})", f"${bb['price']:.2f} ({esc(bb['provider'])})")}
{row("VRAM", f"{va or '—'} GB", f"{vb or '—'} GB")}
{row("Memory bandwidth", f"{sa.get('mem_bw_gbs') or '—'} GB/s", f"{sb.get('mem_bw_gbs') or '—'} GB/s")}
{row("$ per GB VRAM per hour", f"${ba['price'] / va:.3f}" if va else "—", f"${bb['price'] / vb:.3f}" if vb else "—")}
{row("Providers tracked", len({o['provider'] for o in ea['offers']}), len({o['provider'] for o in eb['offers']}))}
</tbody></table></div>
<p class="mut">Nameplate specs are vendor claims, not measured throughput. See each GPU's page for
every offer, spot prices, and history. Other comparisons: {" · ".join(f'<a href="/compare/{x}-vs-{y}.html">{esc(fam_display(x, fams[x]))} vs {esc(fam_display(y, fams[y]))}</a>' for x, y in COMPARE_PAIRS if (x, y) != (a, b) and x in fams and y in fams)}</p>"""
    return page(f"{na} vs {nb} Price: Cloud Rental Cost Compared (hourly) | gpudiff", body, monetize,
                f"{na} vs {nb}: cheapest cloud rental prices, VRAM, bandwidth, and price-per-GB compared, updated hourly.",
                path=f"/compare/{a}-vs-{b}.html")


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
                "Every recorded change in GPU cloud pricing, in order.",
                path="/changelog.html")


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
bulk history, SLA) ships when demand shows up — watch the <a href="/rss.xml">feed</a>.</p>
<h2>Feeds &amp; badges</h2>
<p>RSS: <a href="/rss.xml">everything</a> · <a href="/gpu.xml">GPUs</a> ·
<a href="/llm/rss.xml">LLM APIs</a> · <a href="/saas/rss.xml">SaaS</a>.
Live price badges for your README: <a href="/badges.html">badges</a>.</p>"""
    return page("API — gpudiff", body, monetize,
                "Free JSON API for GPU cloud prices, history, and the changelog. CC BY 4.0.",
                path="/api/")


def llm_model_index(llm_offers):
    """canonical model -> {router -> {input, output, model_id, ctx}} — the join
    that makes one model one row no matter how each router spells it."""
    idx = {}
    for o in llm_offers:
        a = o.get("attrs") or {}
        canonical = a.get("canonical") or canon_model(a.get("model_id") or o["sku"])
        direction = a.get("direction") or ("output" if o["sku"].endswith("-output") else "input")
        r = idx.setdefault(canonical, {}).setdefault(
            o["provider"], {"model_id": a.get("model_id"), "ctx": a.get("context_length")})
        if r.get(direction) is None or o["price"] < r[direction]:
            r[direction] = o["price"]
            r[f"{direction}_id"] = o["id"]  # lets the model page draw its history
        if not r.get("ctx") and a.get("context_length"):
            r["ctx"] = a.get("context_length")
    return idx


def _price_cell(v):
    return f"${v:.2f}" if isinstance(v, (int, float)) else "—"


def _cheapest(routes, direction):
    vals = [(r[direction], name) for name, r in routes.items() if isinstance(r.get(direction), (int, float))]
    return min(vals) if vals else (None, None)


def _spread_of(routes):
    ins = [r["input"] for r in routes.values() if isinstance(r.get("input"), (int, float))]
    if len(ins) > 1 and min(ins):
        return max(ins) / min(ins)
    return None


def _model_link(canonical, label=None):
    return f"<a href='/llm/model/{esc(canonical)}.html'>{esc(label or canonical)}</a>"


def _model_row(canonical, routes, label=None, sub=None):
    lo_in, lo_router = _cheapest(routes, "input")
    lo_out, _ = _cheapest(routes, "output")
    sp = _spread_of(routes)
    name = f"<strong>{_model_link(canonical, label)}</strong>"
    if sub:
        name += f"<br><span class='mut'>{esc(sub)}</span>"
    return (f"<tr><td>{name}</td>"
            f"<td class='n'>{_price_cell(lo_in)}</td><td class='n'>{_price_cell(lo_out)}</td>"
            f"<td>{esc(ROUTER_LABEL.get(lo_router, lo_router or '—'))}</td>"
            f"<td class='n'>{f'{sp:.1f}×' if sp else '—'}</td>"
            f"<td class='n'>{len(routes)}</td></tr>")


TABLE_HEAD = ("<thead><tr><th>Model</th><th class='n'>$ in /MTok</th>"
              "<th class='n'>$ out /MTok</th><th>Cheapest via</th>"
              "<th class='n'>Spread</th><th class='n'>Gateways</th></tr></thead>")


def watchlist_routes(idx, meta, key):
    """Collapse a watchlist entry's aliases into one route table."""
    routes = {}
    for alias in meta.get("aliases", [key]):
        for router, r in (idx.get(alias) or {}).items():
            cur = routes.get(router)
            if cur is None or (isinstance(r.get("input"), (int, float))
                               and not isinstance(cur.get("input"), (int, float))) or (
                    isinstance(r.get("input"), (int, float))
                    and isinstance(cur.get("input"), (int, float))
                    and r["input"] < cur["input"]):
                routes[router] = r
    return routes


def render_llm_index(llm_offers, changelog, monetize):
    idx = llm_model_index(llm_offers)
    watchlist = load_watchlist()
    routers_live = sorted({o["provider"] for o in llm_offers})

    wl_rows = []
    for key, meta in watchlist.items():
        routes = watchlist_routes(idx, meta, key)
        if routes:
            wl_rows.append(_model_row(key, routes, meta.get("display"), meta.get("lab")))

    multi = {c: r for c, r in idx.items() if len(r) > 1}
    cat_rows = [_model_row(c, multi[c]) for c in sorted(multi)]

    recent = [e for e in changelog if entry_section(e) == "llm"][-15:]
    aliases = alias_index(load_specs())
    log = "\n".join(chg_html(e, aliases) for e in reversed(recent)) or \
          '<li class="mut">Tracking began today — diffs appear with the next price move.</li>'

    # Head-to-head links for the pairs people actually search for.
    pair_links = " · ".join(
        f'<a href="/llm/compare/{a}-vs-{b}.html">{esc(ROUTER_LABEL[a])} vs {esc(ROUTER_LABEL[b])}</a>'
        for a, b in COMPARE_ROUTER_PAIRS if a in routers_live and b in routers_live)

    body = f"""
<h1>LLM API pricing across {len(routers_live)} gateways <span class="badge">beta</span></h1>
<p class="mut">The same model costs different amounts depending on which gateway you buy it
through. We snapshot {", ".join(esc(ROUTER_LABEL.get(r, r)) for r in routers_live)} hourly,
normalize everything to USD per million tokens, and diff it. {len(idx)} models tracked,
{len(multi)} of them carried by more than one gateway. Click any model for its prices
everywhere plus its own changelog.</p>

<h2>What changed</h2>
<ul class="chg">{log}</ul>

<h2>Head to head</h2>
<p>{pair_links}</p>

<h2>Watchlist</h2>
<p class="mut">Flagship models. "Spread" is the most expensive gateway divided by the
cheapest — paying it is a silent tax on identical tokens.</p>
<div class="tablewrap"><table>{TABLE_HEAD}
<tbody>{''.join(wl_rows) or '<tr><td colspan="6" class="mut">No watchlist models priced yet.</td></tr>'}</tbody>
</table></div>

<h2>Every multi-gateway model</h2>
<p class="mut">Models sold by two or more gateways, so the comparison means something.
Single-gateway models are in the API.</p>
<div class="tablewrap"><table>{TABLE_HEAD}
<tbody>{''.join(cat_rows)}</tbody></table></div>
<p><a href="/api/v1/llm/watchlist.json">Watchlist JSON →</a> ·
<a href="/api/v1/llm/models.json">All models JSON →</a> ·
<a href="/llm/rss.xml">RSS</a></p>"""
    return page(f"LLM API Prices Compared Across {len(routers_live)} Gateways — per-token cost changelog | gpudiff",
                body, monetize,
                "Compare LLM API prices per million tokens across OpenRouter, Ramp Router, Requesty, Glama, "
                "Novita and DeepInfra, with per-model history and a changelog of every price change.",
                path="/llm/")


def render_llm_model(canonical, routes, history, entries, monetize, meta=None):
    """One model, every gateway that sells it, plus its own price history."""
    display = (meta or {}).get("display") or canonical
    lab = (meta or {}).get("lab")
    lo_in, lo_router = _cheapest(routes, "input")
    lo_out, lo_out_router = _cheapest(routes, "output")
    sp = _spread_of(routes)

    rows = []
    for rt, r in sorted(routes.items(),
                        key=lambda kv: kv[1].get("input") if isinstance(kv[1].get("input"), (int, float)) else 9e9):
        ctx = f"{r['ctx']:,}" if isinstance(r.get("ctx"), int) else "—"
        series = history.get(r.get("input_id"), [])
        fee = ROUTER_FEES.get(rt)
        fee_note = f" <span class='badge' title='{esc(fee[0])}'>fees</span>" if fee else ""
        rows.append(
            f"<tr><td><strong>{esc(ROUTER_LABEL.get(rt, rt))}</strong>{fee_note}</td>"
            f"<td class='n'>{_price_cell(r.get('input'))}</td>"
            f"<td class='n'>{_price_cell(r.get('output'))}</td>"
            f"<td class='n'>{ctx}</td>"
            f"<td>{sparkline(series)}</td>"
            f"<td><span class='mut'>{esc(r.get('model_id') or '')}</span></td></tr>")

    log = "\n".join(
        f"<li><time>{esc(e['date'])}</time> "
        f"<span class='{'cut' if e.get('new_price', 0) < e.get('old_price', 0) else 'raise'}'>"
        f"{esc(e['summary'])}</span></li>"
        if e["kind"] == "price_change" else
        f"<li><time>{esc(e['date'])}</time> {esc(e['summary'])}</li>"
        for e in reversed(entries[-25:])) or \
        '<li class="mut">No changes recorded for this model yet — history starts the day we first saw it.</li>'

    faqs = [
        (f"How much does {display} cost per million tokens?",
         f"The cheapest tracked gateway charges ${lo_in:.2f} per million input tokens and "
         f"${lo_out:.2f} per million output tokens"
         f"{f' ({ROUTER_LABEL.get(lo_router, lo_router)})' if lo_router else ''}. "
         f"Prices refresh hourly." if lo_in and lo_out else "No current price is published."),
        (f"Which gateway is cheapest for {display}?",
         f"{ROUTER_LABEL.get(lo_router, lo_router)} for input tokens and "
         f"{ROUTER_LABEL.get(lo_out_router, lo_out_router)} for output tokens, among the "
         f"{len(routes)} gateways we track." if lo_router else "Not currently sold by a tracked gateway."),
    ]
    if sp and sp > 1.01:
        faqs.append((f"Do {display} prices differ between gateways?",
                     f"Yes — the most expensive tracked gateway charges {sp:.1f}× the cheapest for "
                     f"input tokens. Identical model, identical tokens, different bill."))
    else:
        faqs.append((f"Do {display} prices differ between gateways?",
                     "No — every tracked gateway currently charges the same per-token price, so the "
                     "difference between them is fees and routing, not token cost."))
    faq_html = "".join(f"<h3>{esc(q)}</h3><p>{esc(a)}</p>" for q, a in faqs)
    faq_ld = ('<script type="application/ld+json">' + json.dumps({
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
                       for q, a in faqs]}) + '</script>')

    fee_rows = "".join(
        f"<li><strong>{esc(ROUTER_LABEL.get(rt, rt))}</strong>: {esc(ROUTER_FEES[rt][0])} "
        f"<a href='{esc(ROUTER_FEES[rt][1])}' rel='noopener'>source</a></li>"
        for rt in routes if rt in ROUTER_FEES)
    fees = f"<h2>Fees beyond the token price</h2><ul class='chg'>{fee_rows}</ul>" if fee_rows else ""

    body = f"""
<h1>{esc(display)} API price — {len(routes)} gateway{'s' if len(routes) != 1 else ''} compared</h1>
<p class="mut">{esc(lab + ' · ') if lab else ''}from <strong>{_price_cell(lo_in)}</strong> per
million input tokens{f' · {sp:.1f}× spread between gateways' if sp and sp > 1.01 else ' · same price on every gateway'}
· updated hourly</p>
<div class="tablewrap"><table>
<thead><tr><th>Gateway</th><th class="n">$ in /MTok</th><th class="n">$ out /MTok</th>
<th class="n">Context</th><th>Input price history</th><th>Model ID</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
{fees}
<h2>Changelog for {esc(display)}</h2>
<ul class="chg">{log}</ul>
<h2>{esc(display)} pricing FAQ</h2>
{faq_html}
<p class="mut"><a href="/llm/">← All LLM prices</a> · <a href="/api/v1/llm/models.json">API</a></p>"""
    return page(f"{display} API Price — {len(routes)} gateways compared, updated hourly | gpudiff",
                body, monetize,
                f"{display} API pricing per million tokens across {len(routes)} gateways, with price "
                f"history and a changelog of every change.",
                jsonld=faq_ld, path=f"/llm/model/{canonical}.html")


COMPARE_ROUTER_PAIRS = [
    ("ramp", "openrouter"), ("openrouter", "requesty"), ("openrouter", "glama"),
    ("openrouter", "novita"), ("openrouter", "deepinfra"), ("ramp", "requesty"),
    ("glama", "requesty"), ("novita", "deepinfra"),
]


def render_router_compare(a, b, idx, monetize):
    la, lb = ROUTER_LABEL.get(a, a), ROUTER_LABEL.get(b, b)
    shared = []
    for canonical, routes in idx.items():
        ra, rb = routes.get(a), routes.get(b)
        if not ra or not rb:
            continue
        ai, bi = ra.get("input"), rb.get("input")
        if isinstance(ai, (int, float)) and isinstance(bi, (int, float)):
            shared.append((canonical, ra, rb, ai, bi))
    shared.sort(key=lambda t: t[0])

    a_cheaper = sum(1 for _, _, _, ai, bi in shared if ai < bi)
    b_cheaper = sum(1 for _, _, _, ai, bi in shared if bi < ai)
    same = len(shared) - a_cheaper - b_cheaper

    rows = []
    for canonical, ra, rb, ai, bi in shared:
        delta = (bi - ai) / ai * 100 if ai else 0
        if abs(delta) < 0.01:
            verdict, cls = "same", "mut"
        elif delta > 0:
            verdict, cls = f"{la} −{abs(delta):.0f}%", "cut"
        else:
            verdict, cls = f"{lb} −{abs(delta):.0f}%", "cut"
        rows.append(
            f"<tr><td>{_model_link(canonical)}</td>"
            f"<td class='n'>{_price_cell(ai)}</td><td class='n'>{_price_cell(bi)}</td>"
            f"<td class='n'>{_price_cell(ra.get('output'))}</td>"
            f"<td class='n'>{_price_cell(rb.get('output'))}</td>"
            f"<td class='{cls}'>{esc(verdict)}</td></tr>")

    if same == len(shared) and shared:
        headline = (f"On token prices, {la} and {lb} are identical across all "
                    f"{len(shared)} models both sell — both pass provider list pricing straight "
                    f"through. The real difference is fees.")
    else:
        headline = (f"Across {len(shared)} models both gateways sell, {la} is cheaper on "
                    f"{a_cheaper}, {lb} on {b_cheaper}, and {same} are priced identically.")

    fee_rows = "".join(
        f"<li><strong>{esc(ROUTER_LABEL.get(rt, rt))}</strong>: {esc(ROUTER_FEES[rt][0])} "
        f"<a href='{esc(ROUTER_FEES[rt][1])}' rel='noopener'>source</a></li>"
        for rt in (a, b) if rt in ROUTER_FEES)
    fees = (f"<h2>Fees beyond the token price</h2><ul class='chg'>{fee_rows}</ul>"
            f"<p class='mut'>Quoted from each gateway's own documentation — we track published "
            f"token prices, not invoices, so treat fee terms as their claims, not our measurement.</p>"
            if fee_rows else "")

    # The question people actually ask is "which should I buy through", and the
    # answer needs both halves of the bill.
    bottom = ""
    if shared and a in ROUTER_FEES and b in ROUTER_FEES:
        token_winner = la if a_cheaper > b_cheaper else (lb if b_cheaper > a_cheaper else None)
        bottom = (
            f"<div class='callout'><p><strong>Bottom line.</strong> "
            f"{f'On token prices alone, {esc(token_winner)} wins more often — cheaper on ' if token_winner else 'Token prices are a wash: '}"
            f"{max(a_cheaper, b_cheaper)} of {len(shared)} shared models"
            f"{f', while {esc(lb if token_winner == la else la)} leads on {min(a_cheaper, b_cheaper)}' if token_winner else ''}, "
            f"and {same} are priced identically. On those identical models the token cost cannot "
            f"decide it, so the fee terms below do — which is where the two gateways genuinely "
            f"differ. Neither number is a quote: check your own volume and payment method.</p></div>")

    body = f"""
<h1>{esc(la)} vs {esc(lb)}: LLM API price comparison</h1>
<p>{esc(headline)} Input prices are USD per million tokens, refreshed hourly; every model
links to its full cross-gateway history.</p>
{bottom}
<div class="tablewrap"><table>
<thead><tr><th>Model</th><th class="n">{esc(la)} in</th><th class="n">{esc(lb)} in</th>
<th class="n">{esc(la)} out</th><th class="n">{esc(lb)} out</th><th>Cheaper</th></tr></thead>
<tbody>{''.join(rows) or '<tr><td colspan="6" class="mut">No overlapping models right now.</td></tr>'}</tbody>
</table></div>
{fees}
<p class="mut"><a href="/llm/">← All LLM prices</a></p>"""
    return page(f"{la} vs {lb} Pricing — {len(shared)} models compared per token | gpudiff",
                body, monetize,
                f"{la} vs {lb}: per-million-token API prices compared across {len(shared)} shared models, "
                f"plus the gateway fees each one charges. Updated hourly.",
                path=f"/llm/compare/{a}-vs-{b}.html")


def render_saas_index(saas_offers, changelog, monetize):
    companies = {}
    for o in saas_offers:
        c = companies.setdefault(o["provider"], {"url": o["provenance"]["url"],
                                                 "points": (o.get("attrs") or {}).get("point_count")})
        c[o["sku"]] = o["price"]
    rows = []
    for co, c in sorted(companies.items()):
        entry = f"${c['pricing-entry']:.0f}" if "pricing-entry" in c else "—"
        top = f"${c['pricing-top']:.0f}" if "pricing-top" in c else "—"
        rows.append(f"<tr><td><strong>{esc(co)}</strong></td>"
                    f"<td class='n'>{entry}</td><td class='n'>{top}</td>"
                    f"<td class='n'>{c.get('points') or '—'}</td>"
                    f"<td><a href='{esc(c['url'])}' rel='noopener'>pricing page</a></td></tr>")
    recent = [e for e in changelog if e["id"].split(":")[1].startswith("pricing-")][-15:]
    aliases = alias_index(load_specs())
    log = "\n".join(chg_html(e, aliases) for e in reversed(recent)) or \
          '<li class="mut">Tracking began today — entries appear when a pricing page moves.</li>'
    body = f"""
<h1>SaaS pricing changelog <span class="badge">beta</span></h1>
<p class="mut">Who raised prices this week. V1 method: we scan each vendor's public
pricing page daily and record the lowest and highest USD amounts present — a
page-level signal, not a plan-mapped price (see <a href="/methodology.html">methodology</a>).
{len(companies)} companies tracked. Amounts shown are as detected on the page.</p>
<h2>What changed</h2>
<ul class="chg">{log}</ul>
<h2>Current signals</h2>
<div class="tablewrap"><table>
<thead><tr><th>Company</th><th class="n">Entry price seen</th><th class="n">Top price seen</th><th class="n">Price points</th><th>Provenance</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<p><a href="/api/v1/saas/companies.json">Companies JSON →</a></p>"""
    return page("SaaS pricing changelog — gpudiff", body, monetize,
                "Daily scans of SaaS pricing pages: who raised prices, who cut them, with provenance.",
                path="/saas/")


FIT_JS = """
async function refit() {
  const fams = await (await fetch('/api/v1/families.json')).json();
  const b = parseFloat(document.getElementById('params').value) || 0;
  const bytes = parseFloat(document.getElementById('prec').value);
  const need = b * bytes * 1.2;
  document.getElementById('need').textContent = need ? need.toFixed(0) + ' GB (incl. 20% overhead)' : '—';
  const fit = fams.filter(f => f.vram_gb && f.vram_gb >= need && f.best)
                  .sort((a, z) => a.best.price - z.best.price);
  const rows = fit.map(f =>
    `<tr><td><a href="/gpu/${f.family}.html"><strong>${f.display}</strong></a></td>` +
    `<td class="n">${f.vram_gb}</td>` +
    `<td class="n"><strong>$${f.best.price.toFixed(2)}</strong>/hr</td>` +
    `<td>${f.best.provider} · ${f.best.region || ''}</td>` +
    `<td class="n">${f.spot_from ? '$' + f.spot_from.toFixed(2) : '—'}</td></tr>`).join('');
  document.getElementById('fitrows').innerHTML =
    rows || '<tr><td colspan="5" class="mut">Nothing fits on a single GPU at that size — shard across multiple GPUs or drop precision.</td></tr>';
}
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('params').addEventListener('input', refit);
  document.getElementById('prec').addEventListener('change', refit);
  document.querySelectorAll('[data-b]').forEach(btn => btn.addEventListener('click', () => {
    document.getElementById('params').value = btn.dataset.b; refit();
  }));
  refit();
});
"""


def render_fit_page(monetize):
    presets = "".join(f'<button class="em" data-b="{b}" type="button">{b}B</button>'
                      for b in (7, 13, 34, 70, 123, 405))
    body = f"""
<h1>What's the cheapest GPU that fits my model?</h1>
<p class="mut">Single-GPU fit: parameters × bytes-per-weight × 1.2 overhead, against
nameplate VRAM and live prices. Rough by design — KV cache scales with context,
and multi-GPU sharding changes everything. A screening tool, not a capacity plan.</p>
<div class="sub">
  <label>Model size (billions): <input class="em" id="params" type="number" value="70" min="0" step="1" style="min-width:90px"></label>
  {presets}
  <label>Precision:
    <select class="em" id="prec">
      <option value="2">fp16 / bf16 (2 B/param)</option>
      <option value="1">int8 (1 B/param)</option>
      <option value="0.5">int4 (0.5 B/param)</option>
    </select></label>
  <span>Needs: <strong id="need">—</strong></span>
</div>
<div class="tablewrap"><table>
<thead><tr><th>GPU</th><th class="n">VRAM GB</th><th class="n">On-demand $/hr</th><th>Where</th><th class="n">Spot from</th></tr></thead>
<tbody id="fitrows"></tbody></table></div>
<script>{FIT_JS}</script>"""
    return page("Cheapest GPU that fits — gpudiff", body, monetize,
                "Pick a model size and precision; see the cheapest cloud GPUs it actually fits on, at live prices.",
                path="/fit.html")


def render_digest_pages(monetize):
    """Render merged weekly digests (digests/*.md, committed by digest.yml)
    into dated site pages — the compounding content archive."""
    src = ROOT / "digests"
    out_dir = SITE / "digest"
    out_dir.mkdir(parents=True, exist_ok=True)
    stems = []
    for md in sorted(src.glob("*.md")) if src.exists() else []:
        lines_html = []
        for raw in md.read_text().splitlines():
            if raw.startswith("# "):
                lines_html.append(f"<h1>{esc(raw[2:])}</h1>")
            elif raw.startswith("- "):
                lines_html.append(f"<li>{esc(raw[2:])}</li>")
            elif raw.strip():
                lines_html.append(f"<p>{esc(raw)}</p>")
        body = "\n".join(lines_html).replace("<li>", "<ul class='chg'><li>", 1)
        if "<li>" in body:
            body += "</ul>"
        (out_dir / f"{md.stem}.html").write_text(
            page(f"Digest {md.stem} — gpudiff", body, monetize,
                 f"Weekly pricing digest for {md.stem}.", path=f"/digest/{md.stem}.html"))
        stems.append(md.stem)
    items = "\n".join(f'<li><a href="/digest/{s}.html">Week of {s}</a></li>' for s in reversed(stems)) \
            or '<li class="mut">First digest lands Monday.</li>'
    (out_dir / "index.html").write_text(
        page("Weekly digests — gpudiff", f"<h1>Weekly digests</h1><ul class='chg'>{items}</ul>",
             monetize, "The weekly what-changed digest archive.", path="/digest/"))
    return stems


def render_methodology(monetize):
    body = """
<h1>Methodology</h1>
<p>gpudiff records the price of renting GPUs in the cloud, hourly, with a
changelog of every move. Here is exactly how the numbers are made.</p>
<h2>Identity: a GPU memory configuration is a product</h2>
<p>An H100 PCIe 80GB, an H100 NVL 94GB, and an H100 SXM 80GB never share a row
or a page. Comparison and history only happen inside one of these families;
cross-family context comes from lenses like $/GB-VRAM-hr, clearly labeled as a
screening tool, not a verdict.</p>
<h2>Per-source metrics</h2>
<div class="tablewrap"><table>
<thead><tr><th>Provider</th><th>What we record</th><th>Cadence</th></tr></thead>
<tbody>
<tr><td>Vast.ai</td><td>25th percentile of verified marketplace listings, per GPU
(dph ÷ GPU count); models with fewer than 5 listings are skipped. Spot = p25 of
minimum bids. Marketplace listings vary in host quality — p25 is "what a careful
buyer can actually get," not the single cheapest outlier.</td><td>hourly</td></tr>
<tr><td>RunPod</td><td>Published list prices per GPU type, secure and community
cloud, on-demand and spot. Community tiers can be availability-limited.</td><td>hourly</td></tr>
<tr><td>AWS</td><td>On-demand Linux/shared list price of the smallest qualifying
instance per GPU family, us-east-1, divided by GPU count. AWS sells bundles
(CPUs + RAM attached), so rows are badged instance-bundled.</td><td>daily</td></tr>
<tr><td>Azure</td><td>Retail Prices API, eastus, Linux consumption rates ÷ GPU
count; on-demand and spot. Instance-bundled like AWS.</td><td>daily</td></tr>
<tr><td>OpenRouter (LLM)</td><td>Public model catalog; input and output prices
per million tokens, tracked as separate series per model. This is the resale
layer of LLM pricing; official provider list pages join as slower sources.</td><td>hourly</td></tr>
<tr><td>Requesty · Glama · Novita · DeepInfra (LLM)</td><td>Each router's public
catalog, normalized to USD per million tokens. A router often lists one model
several times (different upstream hosts or regions); we publish the cheapest
route per model and record how many were collapsed. Models are joined across
routers by canonical name — last path segment, region suffix stripped — so
<code>vertex/claude-sonnet-5@eu</code> and <code>anthropic/claude-sonnet-5</code>
are one row.</td><td>hourly</td></tr>
<tr><td>Ramp Router (LLM)</td><td>The published model table from Ramp's public docs:
input and output price per million tokens, context window. Ramp writes decimal
points as "p" (<code>kimi-k2p6</code>) and lists Anthropic models without the
<code>claude-</code> prefix (<code>opus-5</code>); both are normalized into the
shared namespace so one model is one row. Ramp states it bills at provider list
price with no gateway fee through 2026 — useful as a list-price reference, but
it is their published rate, not an invoice we have seen.</td><td>daily</td></tr>
<tr><td>SaaS pages</td><td>Page-level price signature: the set of USD amounts
($2–$2000) present on each vendor's public pricing page; we publish the lowest
and highest and diff those. Not plan-mapped — a movement signal with a
provenance link, not a quote. Companies whose pages block or yield nothing are
absent rather than guessed.</td><td>daily</td></tr>
</tbody></table></div>
<h2>Validation — missing beats wrong</h2>
<p>Every offer is schema-validated; anything failing is dropped and flagged,
never published. A price moving more than 40% in a day is quarantined for human
review instead of shipped. Every datum stores the URL it was observed at and
its timestamp, and every snapshot is committed to public git history — the
archive cannot be quietly rewritten.</p>
<h2>What we don't claim</h2>
<p>Specs shown are vendor nameplate figures with links to the spec sheet — not
measured throughput. Availability is not verified. Enterprise negotiated
pricing is invisible to everyone, including us.</p>
<h2>Money</h2>
<p>Outbound provider links may carry referral codes (disclosed, rel=sponsored).
They never influence which numbers are shown or how they're computed — the
pipeline is open source, so you can check.</p>"""
    return page("Methodology — gpudiff", body, monetize,
                "How gpudiff computes GPU cloud prices: per-source metrics, validation gates, provenance, and what we deliberately don't claim.",
                path="/methodology.html")


SECTION_OF = {"usd_per_mtok": "llm", "usd_per_unit": "saas"}


def entry_section(e):
    if e["id"].split(":")[0] in LLM_PROVIDERS:
        return "llm"
    if e["id"].split(":")[1].startswith("pricing-"):
        return "saas"
    return "gpu"


def render_rss(changelog, title, description, section=None):
    pool = [e for e in changelog if e["kind"] in ("price_change", "added")]
    if section:
        pool = [e for e in pool if entry_section(e) == section]
    items = []
    for e in pool[-50:][::-1]:
        items.append(f"""<item>
<title>{esc(e['summary'])}</title>
<link>{BASE_URL}/changelog.html</link>
<guid isPermaLink="false">{esc(e['id'])}:{esc(e['date'])}</guid>
<pubDate>{esc(e['date'])}T00:00:00Z</pubDate>
</item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>{esc(title)}</title>
<link>{BASE_URL}</link>
<description>{esc(description)}</description>
{''.join(items)}
</channel></rss>"""


# ------------------------------------------------------------------ favicon

FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
<rect width="32" height="32" rx="6" fill="#1A1D27"/>
<rect x="6" y="7" width="20" height="6" rx="2" fill="#3FBF7F"/>
<rect x="6" y="19" width="20" height="6" rx="2" fill="#E05252"/>
</svg>"""


def _favicon_px(x, y, size):
    """One pixel of the mark — a diff hunk: green added line over red removed
    line on the dark ground. RGBA."""
    bg, green, red = (26, 29, 39, 255), (63, 191, 127, 255), (224, 82, 82, 255)
    fx, fy = x / size, y / size
    if 0.19 <= fx <= 0.81 and 0.22 <= fy <= 0.41:
        return green
    if 0.19 <= fx <= 0.81 and 0.59 <= fy <= 0.78:
        return red
    return bg


def render_favicon_png(size):
    """The favicon as a real PNG, encoded by hand. Stdlib only (struct + zlib)."""
    import struct
    import zlib

    raw = b"".join(
        b"\x00" + b"".join(bytes(_favicon_px(x, y, size)) for x in range(size))
        for y in range(size)
    )

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


# ------------------------------------------------------------------- badges

BADGE_L_BG = "#35427E"
BADGE_R_BG = "#2F7D4F"


def render_badge(label, value):
    """Shields-style flat SVG with fixed colors — badges live on other
    people's pages, so no CSS variables, no theme dependence."""
    lw = round(len(label) * 6.4 + 14)
    vw = round(len(value) * 6.4 + 14)
    w = lw + vw
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="20" role="img" aria-label="{esc(label)}: {esc(value)}">
<linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient>
<clipPath id="r"><rect width="{w}" height="20" rx="3" fill="#fff"/></clipPath>
<g clip-path="url(#r)">
<rect width="{lw}" height="20" fill="{BADGE_L_BG}"/>
<rect x="{lw}" width="{vw}" height="20" fill="{BADGE_R_BG}"/>
<rect width="{w}" height="20" fill="url(#s)"/>
</g>
<g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
<text x="{lw / 2}" y="14">{esc(label)}</text>
<text x="{lw + vw / 2}" y="14">{esc(value)}</text>
</g>
</svg>"""


def render_badges_page(badge_rows, monetize):
    cards = []
    for fname, label, value, page_path in badge_rows:
        md = f"[![{label}: {value}](https://gpudiff.com/badge/{fname})](https://gpudiff.com{page_path})"
        cards.append(
            f"<tr><td><img src='/badge/{esc(fname)}' alt='{esc(label)}: {esc(value)}' height='20'></td>"
            f"<td><code style='font-size:12px'>{esc(md)}</code></td></tr>")
    body = f"""
<h1>Live badges</h1>
<p>Embed a live price in your README, blog, or docs. Badges regenerate with
every refresh, so the number stays current; the image is a plain SVG served
from this site — no scripts, no tracking.</p>
<div class="tablewrap"><table>
<thead><tr><th>Badge</th><th>Markdown</th></tr></thead>
<tbody>{''.join(cards)}</tbody></table></div>
<p class="mut">HTML variant: swap the Markdown for
<code>&lt;a href="…"&gt;&lt;img src="…svg"&gt;&lt;/a&gt;</code>. CC BY 4.0 — a link is the attribution.</p>"""
    return page("Badges — gpudiff", body, monetize,
                "Embeddable live GPU price badges: current prices in your README or blog, updated hourly.",
                path="/badges.html")


# -------------------------------------------------------------------- build

def build_site(offers, changelog, date):
    specs = load_specs()
    aliases = alias_index(specs)
    monetize = load_monetize()
    history = load_history()
    # Sections by unit: per-token = LLM, per-unit page scans = SaaS, rest = GPUs.
    llm_offers = [o for o in offers if o["unit"] == "usd_per_mtok"]
    saas_offers = [o for o in offers if o["unit"] == "usd_per_unit"]
    gpu_offers = [o for o in offers if o["unit"] not in ("usd_per_mtok", "usd_per_unit")]
    fams = group_families(gpu_offers, specs, aliases)

    (SITE / "gpu").mkdir(parents=True, exist_ok=True)
    (SITE / "llm").mkdir(parents=True, exist_ok=True)
    (SITE / "saas").mkdir(parents=True, exist_ok=True)
    (SITE / "api" / "v1" / "history").mkdir(parents=True, exist_ok=True)
    (SITE / "api" / "v1" / "llm").mkdir(parents=True, exist_ok=True)
    (SITE / "api" / "v1" / "saas").mkdir(parents=True, exist_ok=True)

    (SITE / "saas" / "index.html").write_text(render_saas_index(saas_offers, changelog, monetize))
    saas_companies = {}
    for o in saas_offers:
        c = saas_companies.setdefault(o["provider"], {"company": o["provider"],
                                                      "provenance": o["provenance"]["url"],
                                                      "price_points": (o.get("attrs") or {}).get("price_points")})
        c[o["sku"].replace("-", "_")] = o["price"]
    (SITE / "api" / "v1" / "saas" / "companies.json").write_text(
        json.dumps(sorted(saas_companies.values(), key=lambda c: c["company"]), indent=2) + "\n")

    (SITE / "llm" / "model").mkdir(parents=True, exist_ok=True)
    (SITE / "llm" / "compare").mkdir(parents=True, exist_ok=True)
    (SITE / "llm" / "index.html").write_text(
        render_llm_index(llm_offers, changelog, monetize))

    idx = llm_model_index(llm_offers)
    wl = load_watchlist()

    def model_record(canonical, routes, meta=None):
        ins = [r["input"] for r in routes.values() if isinstance(r.get("input"), (int, float))]
        rec = {
            "model": canonical, "unit": "usd_per_mtok",
            "gateways": {rt: {"input_per_mtok": r.get("input"), "output_per_mtok": r.get("output"),
                              "model_id": r.get("model_id"), "context_length": r.get("ctx")}
                         for rt, r in sorted(routes.items())},
            "cheapest_input_per_mtok": min(ins) if ins else None,
            "spread": round(max(ins) / min(ins), 2) if len(ins) > 1 and min(ins) else None,
            "url": f"{BASE_URL}/llm/model/{canonical}.html",
        }
        if meta:
            rec.update({"display": meta.get("display"), "lab": meta.get("lab")})
        return rec

    (SITE / "api" / "v1" / "llm" / "models.json").write_text(
        json.dumps([model_record(c, r) for c, r in sorted(idx.items())], indent=2) + "\n")

    # Per-model pages: every model sold by 2+ gateways, plus the whole watchlist.
    id_canon = {}
    for o in llm_offers:
        a = o.get("attrs") or {}
        id_canon[o["id"]] = a.get("canonical") or canon_model(a.get("model_id") or o["sku"])
    entries_by_model = {}
    for e in changelog:
        canonical = id_canon.get(e["id"])
        if canonical:
            entries_by_model.setdefault(canonical, []).append(e)

    wl_records, page_models = [], {c for c, r in idx.items() if len(r) > 1}
    for key, meta in wl.items():
        routes = watchlist_routes(idx, meta, key)
        if routes:
            wl_records.append(model_record(key, routes, meta))
            page_models.add(key)
            idx.setdefault(key, routes)
    (SITE / "api" / "v1" / "llm" / "watchlist.json").write_text(
        json.dumps(wl_records, indent=2) + "\n")

    for canonical in sorted(page_models):
        routes = idx.get(canonical) or {}
        if not routes:
            continue
        meta = wl.get(canonical)
        model_entries = entries_by_model.get(canonical, [])
        if meta:  # a watchlist entry may span several alias spellings
            for alias in meta.get("aliases", [canonical]):
                model_entries += entries_by_model.get(alias, []) if alias != canonical else []
            model_entries.sort(key=lambda e: e["date"])
        (SITE / "llm" / "model" / f"{canonical}.html").write_text(
            render_llm_model(canonical, routes, history, model_entries, monetize, meta))

    llm_pairs = []
    live_routers = {o["provider"] for o in llm_offers}
    for a, b in COMPARE_ROUTER_PAIRS:
        if a in live_routers and b in live_routers:
            (SITE / "llm" / "compare" / f"{a}-vs-{b}.html").write_text(
                render_router_compare(a, b, idx, monetize))
            llm_pairs.append((a, b))

    (SITE / "index.html").write_text(render_index(fams, changelog, date, monetize))
    (SITE / "changelog.html").write_text(render_changelog(changelog, monetize, aliases))
    (SITE / "methodology.html").write_text(render_methodology(monetize))
    (SITE / "fit.html").write_text(render_fit_page(monetize))
    digest_stems = render_digest_pages(monetize)
    (SITE / "api" / "index.html").write_text(render_api_docs(monetize))

    (SITE / "rss.xml").write_text(render_rss(
        changelog, "gpudiff — all price changes",
        "Every recorded change across GPU cloud, LLM API, and SaaS pricing."))
    (SITE / "gpu.xml").write_text(render_rss(
        changelog, "gpudiff — GPU cloud price changes",
        "Every recorded change in GPU cloud pricing.", section="gpu"))
    (SITE / "llm" / "rss.xml").write_text(render_rss(
        changelog, "gpudiff — LLM API price changes",
        "Every recorded LLM API price change and model listing.", section="llm"))
    (SITE / "saas" / "rss.xml").write_text(render_rss(
        changelog, "gpudiff — SaaS pricing changes",
        "Who raised prices this week: SaaS pricing page changes.", section="saas"))

    # Badges: one per GPU family plus section-level counters.
    (SITE / "badge").mkdir(parents=True, exist_ok=True)
    badge_rows = []
    n_models = len({(o.get("attrs") or {}).get("model_id") for o in llm_offers})
    n_saas = len({o["provider"] for o in saas_offers})
    overall = [("gpudiff.svg", "gpudiff", f"{len(offers)} prices · hourly diffs", "/"),
               ("llm.svg", "llm api prices", f"{n_models} models tracked", "/llm/"),
               ("saas.svg", "saas pricing", f"{n_saas} pages watched", "/saas/")]
    for fname, label, value, ppath in overall:
        (SITE / "badge" / fname).write_text(render_badge(label, value))
        badge_rows.append((fname, label, value, ppath))
    for fam, entry in sorted(fams.items()):
        od = [o for o in entry["offers"] if o["pricing_type"] == "on_demand"]
        if not od:
            continue
        label = fam_display(fam, entry)
        value = f"from ${od[0]['price']:.2f}/hr"
        fname = f"{fam}.svg"
        (SITE / "badge" / fname).write_text(render_badge(label, value))
        badge_rows.append((fname, label, value, f"/gpu/{fam}.html"))
    (SITE / "badges.html").write_text(render_badges_page(badge_rows, monetize))

    # IndexNow verification key file
    ik = monetize.get("indexnow_key", "")
    if ik:
        (SITE / f"{ik}.txt").write_text(ik + "\n")

    # Favicons: SVG for modern browsers, hand-encoded PNG for the rest, and a
    # /favicon.ico because Safari requests that path directly regardless of
    # link tags. Safari rejects PNG payloads inside 32px ICOs, so the ICO
    # carries a classic BMP: BITMAPINFOHEADER (doubled height), bottom-up
    # BGRA rows, then an all-zero AND mask.
    import struct as _struct
    size = 32
    rows = [b"".join(bytes((b, g, r, a)) for x in range(size)
                     for r, g, b, a in (_favicon_px(x, y, size),))
            for y in range(size)]
    xor = b"".join(reversed(rows))
    mask = (b"\x00" * ((size + 31) // 32 * 4)) * size
    dib = _struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0,
                       len(xor) + len(mask), 0, 0, 0, 0) + xor + mask
    ico = (_struct.pack("<HHH", 0, 1, 1)
           + _struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(dib), 22)
           + dib)
    (SITE / "favicon.svg").write_text(FAVICON_SVG)
    (SITE / "favicon.png").write_bytes(render_favicon_png(32))
    (SITE / "favicon.ico").write_bytes(ico)
    (SITE / "apple-touch-icon.png").write_bytes(render_favicon_png(180))

    # Provider + comparison pages (commercial-intent search surfaces).
    (SITE / "provider").mkdir(parents=True, exist_ok=True)
    (SITE / "compare").mkdir(parents=True, exist_ok=True)
    provider_names = sorted({o["provider"] for o in gpu_offers})
    for p in provider_names:
        (SITE / "provider" / f"{p}.html").write_text(
            render_provider_page(p, [o for o in gpu_offers if o["provider"] == p], fams, monetize, aliases))
    compare_built = []
    for a, b in COMPARE_PAIRS:
        if a in fams and b in fams:
            (SITE / "compare" / f"{a}-vs-{b}.html").write_text(render_compare_page(a, b, fams, monetize))
            compare_built.append((a, b))

    fam_summaries = []
    for fam, entry in fams.items():
        (SITE / "gpu" / f"{fam}.html").write_text(
            render_family(fam, entry, history, changelog, monetize, aliases, fams))
        fam_hist = {o["id"]: history.get(o["id"], []) for o in entry["offers"]}
        (SITE / "api" / "v1" / "history" / f"{fam}.json").write_text(
            json.dumps({"family": fam, "series": fam_hist}, indent=2) + "\n")
        od = [o for o in entry["offers"] if o["pricing_type"] == "on_demand"]
        spot = [o for o in entry["offers"] if o["pricing_type"] == "spot"]
        best = od[0] if od else entry["offers"][0]
        spec = entry.get("spec") or {}
        fam_summaries.append({
            "family": fam, "display": fam_display(fam, entry),
            "vram_gb": fam_vram(fam, entry), "mem_bw_gbs": spec.get("mem_bw_gbs"),
            "best": {"price": best["price"], "provider": best["provider"],
                     "region": best.get("region"), "unit": best["unit"]},
            "spot_from": spot[0]["price"] if spot else None,
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

    urls = [f"{BASE_URL}/", f"{BASE_URL}/llm/", f"{BASE_URL}/saas/", f"{BASE_URL}/fit.html",
            f"{BASE_URL}/changelog.html", f"{BASE_URL}/badges.html",
            f"{BASE_URL}/methodology.html", f"{BASE_URL}/api/", f"{BASE_URL}/digest/"] + \
           [f"{BASE_URL}/llm/model/{m}.html" for m in sorted(page_models)] + \
           [f"{BASE_URL}/llm/compare/{a}-vs-{b}.html" for a, b in llm_pairs] + \
           [f"{BASE_URL}/digest/{s}.html" for s in digest_stems] + \
           [f"{BASE_URL}/provider/{p}.html" for p in provider_names] + \
           [f"{BASE_URL}/compare/{a}-vs-{b}.html" for a, b in compare_built] + \
           [f"{BASE_URL}/gpu/{fam}.html" for fam in sorted(fams)]
    (SITE / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
        "".join(f"<url><loc>{esc(u)}</loc></url>\n" for u in urls) + "</urlset>\n")
    (SITE / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n")

    return SITE / "index.html"
