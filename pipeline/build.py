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
header.site { display:flex; flex-wrap:wrap; align-items:baseline; gap:4px 12px;
              margin-bottom:16px; border-bottom:1px solid var(--line); }
.brand { font-size:22px; font-weight:700; letter-spacing:-.01em; text-decoration:none; color:var(--ink); }
.brand b { color:var(--acc); }
.tag { color:var(--mut); font-size:13px; }
/* Nav is always its own full-width row that scrolls sideways when tight, so the
   header looks the same at every screen width instead of wrapping raggedly. */
nav.site { flex-basis:100%; display:flex; gap:2px; margin-top:8px;
           overflow-x:auto; white-space:nowrap; scrollbar-width:none; -webkit-overflow-scrolling:touch; }
nav.site::-webkit-scrollbar { display:none; }
nav.site a { color:var(--mut); text-decoration:none; padding:7px 11px; border-radius:6px 6px 0 0;
             font-size:14px; flex:0 0 auto; }
nav.site a:hover { color:var(--ink); background:var(--card); }
@media (max-width:600px){ .tag { display:none; } }
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
.cta { border-left:3px solid var(--cut); padding:6px 12px; background:var(--card); }
.vol { font-size:10.5px; letter-spacing:.03em; text-transform:uppercase; padding:1px 6px;
       border-radius:3px; border:1px solid currentColor; white-space:nowrap; }
.vol-low  { color:var(--cut); }
.vol-mid  { color:var(--gold, #9a7b1f); }
.vol-high { color:var(--raise); }
.vol-new  { color:var(--mut); }
.pick { border:1px solid var(--line); border-radius:8px; padding:16px 18px; margin:14px 0;
        background:var(--card); }
.pick h3 { margin:0 0 4px; } .pick .big { font-size:22px; font-weight:700; }
.pick .why { color:var(--mut); font-size:13.5px; margin-top:6px; }
.sponsor { display:flex; align-items:center; gap:10px; min-height:38px; margin:14px 0 4px;
           padding:8px 12px; border:1px solid var(--line); border-radius:6px;
           background:var(--card); font-size:13.5px; }
.sponsor a { color:var(--ink); text-decoration:none; }
.sponsor a:hover { text-decoration:underline; }
.sponsor-tag { font-size:10px; letter-spacing:.08em; text-transform:uppercase; color:var(--mut);
               border:1px solid var(--line); border-radius:3px; padding:2px 6px; white-space:nowrap;
               background:var(--bg); }
.sponsor-house a { color:var(--mut); }
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


def load_sponsors():
    return _load(ROOT / "sponsors.json", {"active": [], "contact_url": "#",
                                          "founding_rate_usd": 99})


def load_metrics():
    """Latest analyst snapshot, for the media kit's live audience numbers."""
    mdir = ROOT / "data" / "metrics"
    snaps = sorted(mdir.glob("*.json")) if mdir.exists() else []
    return json.loads(snaps[-1].read_text()) if snaps else {}


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


def gateway_link(router, monetize):
    """Outbound link to a gateway — the referral URL when we have one, else its
    home page. rel=sponsored whenever a code is attached."""
    ref = (monetize.get("referral_links") or {}).get(router, "")
    if ref:
        return ref, ' rel="sponsored noopener"'
    home = (monetize.get("provider_home") or {}).get(router) or ROUTER_FEES.get(router, ("", "#"))[1]
    return home or "#", ' rel="noopener"'


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


def volatility(series):
    """A plain-language stability read from a price history. Returns
    (label, css_class, detail). Honest about thin history: fewer than 3
    observations is 'new', never 'stable'."""
    pts = [p for _, p in (series or []) if isinstance(p, (int, float)) and p > 0]
    if len(pts) < 3:
        return ("new", "vol-new", f"{len(pts)} day(s) of history")
    lo, hi = min(pts), max(pts)
    swing = (hi / lo - 1) * 100 if lo else 0
    changes = sum(1 for a, b in zip(pts, pts[1:]) if a != b)
    if swing < 2:
        return ("stable", "vol-low", f"±{swing:.0f}% over {len(pts)} days")
    if swing < 15:
        return ("drifts", "vol-mid", f"±{swing:.0f}% over {len(pts)} days, {changes} move(s)")
    return ("volatile", "vol-high", f"{swing:.0f}% range over {len(pts)} days, {changes} move(s)")


def vol_badge(series):
    label, cls, detail = volatility(series)
    return f'<span class="vol {cls}" title="{esc(detail)}">{label}</span>'


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


def section_of_path(path):
    if path.startswith("/llm"):
        return "llm"
    if path.startswith("/saas"):
        return "saas"
    return "gpu"


def sponsor_slot(path):
    """One tasteful, labelled, first-party unit — or a house ad selling it.
    No third-party script, so ad blockers have nothing to block and the layout
    never shifts."""
    cfg = load_sponsors()
    section = section_of_path(path)
    for sp in cfg.get("active", []):
        if sp.get("section", "all") not in ("all", section):
            continue
        name = esc(sp.get("name", ""))
        return (f'<aside class="sponsor"><span class="sponsor-tag">Sponsored</span>'
                f'<a href="{esc(sp.get("url", "#"))}" rel="sponsored noopener" '
                f'data-goatcounter-click="sponsor-{name}">'
                f'<strong>{name}</strong> — {esc(sp.get("tagline", ""))}</a></aside>')
    return ('<aside class="sponsor sponsor-house"><span class="sponsor-tag">Sponsor slot</span>'
            '<a href="/sponsor.html" data-goatcounter-click="sponsor-house">'
            'This space is available — reach engineers comparing GPU and LLM prices →</a></aside>')


def page(title, body, monetize, desc="", jsonld="", path="/"):
    nav = ('<nav class="site"><a href="/">GPUs</a><a href="/llm/">LLM APIs</a>'
           '<a href="/rankings.html">rankings</a><a href="/movers.html">movers</a>'
           '<a href="/saas/">SaaS</a><a href="/memory.html">RAM</a><a href="/fit.html">fit</a>'
           '<a href="/changelog.html">changelog</a><a href="/methodology.html">methodology</a>'
           '<a href="/api/">API</a><a href="https://github.com/graemegilmourbates/gpudiff">source</a></nav>')
    gsc = monetize.get("google_site_verification", "")
    verify = f'<meta name="google-site-verification" content="{esc(gsc)}">' if gsc else ""
    gc = monetize.get("goatcounter_code", "")
    analytics = (f'<script data-goatcounter="https://{esc(gc)}.goatcounter.com/count" '
                 f'async src="https://gc.zgo.at/count.js"></script>') if gc else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc or title)}">{verify}
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
{sponsor_slot(path)}
{body}
<footer class="site">Every datum links its source and is versioned in
<a href="https://github.com/graemegilmourbates/gpudiff">public git history</a>.
Data: CC BY 4.0 — cite gpudiff.com. Nameplate specs are vendor claims, not measured
throughput. Vast prices are the 25th percentile of verified marketplace listings
(what a careful buyer actually gets); RunPod prices are list. Outbound provider
links may carry referral codes and sponsored units are labelled; neither ever
affects the numbers. <a href="/sponsor.html">Sponsor this site</a>.</footer>
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
<p><a href="/cheapest-gpu-cloud.html"><strong>Cheapest GPU cloud, ranked →</strong></a> · <a href="/movers.html">biggest moves this week</a> · <a href="/gpu-guide.html">where should I rent?</a></p>
<h1>What changed in GPU cloud pricing</h1>
<ul class="chg">{log}</ul>
<p><a href="/changelog.html">Full changelog →</a></p>
<h2>Cheapest current price by GPU</h2>
<p class="mut">Grouped by memory configuration — an H100 NVL 94GB and an H100 PCIe 80GB are
different products, so they never share a row. Prices refresh continually; snapshot {esc(date)}.
By provider: <a href="/provider/vast.html">Vast.ai</a> · <a href="/provider/runpod.html">RunPod</a> ·
<a href="/provider/aws.html">AWS</a> · <a href="/provider/azure.html">Azure</a>. Head-to-head:
<a href="/compare/h100-sxm-80gb-vs-h200-sxm-141gb.html">H100 vs H200</a> ·
<a href="/compare/a100-sxm4-80gb-vs-h100-sxm-80gb.html">A100 vs H100</a> ·
<a href="/compare/rtx-4090-24gb-vs-rtx-5090-32gb.html">4090 vs 5090</a>.</p>
<div class="tablewrap"><table>
<thead><tr><th>GPU</th><th class="n">VRAM GB</th><th class="n">On-demand $/hr</th><th>Where</th>
<th class="n">Spot from</th><th class="n">$/GB·hr</th><th class="n">Offers</th><th></th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<small class="mut">$/GB·hr = continually price per gigabyte of nameplate VRAM — a screening lens,
not a verdict; interconnect, cloud tier, and real throughput still matter.</small>"""
    return page("GPU Cloud Pricing Compared — H100, H200, B200, A100, RTX 4090 rental prices, updated continually | gpudiff",
                body, monetize,
                "Compare GPU cloud rental prices across Vast.ai, RunPod, AWS, and Azure — on-demand and spot, updated continually, with price history and a changelog of every change.",
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
         f"{n_prov} tracked provider{'s' if n_prov != 1 else ''}. Prices refresh continually."),
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

    prod_ld = ('<script type="application/ld+json">' + json.dumps({
        "@context": "https://schema.org", "@type": "Product",
        "name": f"{name} cloud GPU rental",
        "description": f"Hourly cloud rental prices for the {name} across {n_prov} providers.",
        "category": "Cloud GPU rental",
        "offers": {
            "@type": "AggregateOffer", "priceCurrency": "USD",
            "lowPrice": round(best["price"], 2),
            "highPrice": round(hi, 2),
            "offerCount": len(entry["offers"]),
            "availability": "https://schema.org/InStock",
        },
    }) + '</script>')
    crumb_ld = ('<script type="application/ld+json">' + json.dumps({
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "GPU prices", "item": BASE_URL + "/"},
            {"@type": "ListItem", "position": 2, "name": name, "item": f"{BASE_URL}/gpu/{fam}.html"},
        ],
    }) + '</script>')
    faq_ld = faq_ld + prod_ld + crumb_ld

    related = ""
    if fams:
        links = " · ".join(f'<a href="/gpu/{esc(f)}.html">{esc(fam_display(f, e))}</a>'
                           for f, e in related_families(fam, entry, fams))
        related = f"<h2>Similar GPUs by memory</h2><p>{links}</p>"

    prov_links = " · ".join(f'<a href="/provider/{esc(p)}.html">{esc(p)}</a>' for p in providers)
    body = f"""
<h1>{esc(name)} cloud rental price — {n_prov} provider{'s' if n_prov != 1 else ''} compared, updated continually</h1>
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
                f"spot prices, price history, and a changelog of every change. Updated continually with provenance.",
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
              f"across {len(od)} tracked configurations, updated continually.") if cheapest else "No offers tracked right now."),
            (f"Is {display} cheaper than other GPU clouds?",
             f"It depends on the GPU — compare any card across every provider we track on its GPU page. "
             f"gpudiff records every price change, so you can also see whether {display} is trending up or down.")]
    faq_ld = ('<script type="application/ld+json">' + json.dumps({
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
                       for q, a in faqs]}) + '</script>')
    faq_html = "".join(f"<h3>{esc(q)}</h3><p>{esc(a)}</p>" for q, a in faqs)
    body = f"""
<h1>{esc(display)} GPU pricing — every tracked GPU, updated continually</h1>
<p>{esc(display)} is {esc(blurb)}</p>
<div class="tablewrap"><table>
<thead><tr><th>GPU</th><th>Region / tier</th><th class="n">On-demand $/hr</th><th></th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<h2>{esc(display)} pricing FAQ</h2>
{faq_html}
<p class="mut">Other providers: {" · ".join(f'<a href="/provider/{esc(p)}.html">{esc(PROVIDER_BLURB.get(p, (p,))[0])}</a>' for p in PROVIDER_BLURB if p != provider)}</p>"""
    return page(f"{display} GPU Pricing ({len(od)} GPUs compared, updated continually) | gpudiff", body, monetize,
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
<p>{esc(verdict)} Both numbers refresh continually and link to their source.</p>
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
                f"{na} vs {nb}: cheapest cloud rental prices, VRAM, bandwidth, and price-per-GB compared, updated continually.",
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
    body = """
<h1>Free API</h1>
<p>Static JSON on a CDN — no keys, no sign-up, no rate limits worth worrying
about. Data is <strong>CC BY 4.0</strong>: use it freely, cite
<code>gpudiff.com</code>. Paths are versioned; <code>/api/v1/</code> endpoints
keep their shape.</p>

<h2>GPU cloud</h2>
<div class="tablewrap"><table>
<thead><tr><th>Endpoint</th><th>What it returns</th></tr></thead>
<tbody>
<tr><td><a href="/api/v1/offers.json">/api/v1/offers.json</a></td><td>Every current priced row across all three sections, with provenance</td></tr>
<tr><td><a href="/api/v1/families.json">/api/v1/families.json</a></td><td>Per-GPU summary: specs plus the cheapest current offer</td></tr>
<tr><td><a href="/api/v1/specs.json">/api/v1/specs.json</a></td><td>Nameplate GPU spec table with vendor provenance</td></tr>
<tr><td><a href="/api/v1/history/h100-sxm-80gb.json">/api/v1/history/&lt;gpu&gt;.json</a></td><td>Price series per offer for one GPU family</td></tr>
</tbody></table></div>

<h2>LLM APIs</h2>
<div class="tablewrap"><table>
<thead><tr><th>Endpoint</th><th>What it returns</th></tr></thead>
<tbody>
<tr><td><a href="/api/v1/llm/models.json">/api/v1/llm/models.json</a></td><td>Every tracked model: per-gateway input/output price per million tokens, context, spread</td></tr>
<tr><td><a href="/api/v1/llm/watchlist.json">/api/v1/llm/watchlist.json</a></td><td>Curated flagship models, same shape plus lab and display name</td></tr>
<tr><td><a href="/api/v1/llm/history/claude-opus-5.json">/api/v1/llm/history/&lt;model&gt;.json</a></td><td>Price series per gateway and direction for one model</td></tr>
</tbody></table></div>

<h2>SaaS pricing</h2>
<div class="tablewrap"><table>
<thead><tr><th>Endpoint</th><th>What it returns</th></tr></thead>
<tbody>
<tr><td><a href="/api/v1/saas/companies.json">/api/v1/saas/companies.json</a></td><td>Entry and top price detected on each tracked pricing page</td></tr>
</tbody></table></div>

<h2>Changes</h2>
<div class="tablewrap"><table>
<thead><tr><th>Endpoint</th><th>What it returns</th></tr></thead>
<tbody>
<tr><td><a href="/api/v1/changelog.json">/api/v1/changelog.json</a></td><td>Every recorded change across all sections, dated</td></tr>
</tbody></table></div>

<h2>Example</h2>
<pre><code>curl -s https://gpudiff.com/api/v1/llm/models.json \\
  | jq \'.[] | select(.model=="kimi-k3") | .gateways\'</code></pre>

<p class="mut">A keyed tier (webhooks, alerts, bulk history, an SLA) ships when
demand shows up — watch the <a href="/rss.xml">feed</a>. Building something with
this? Tell us in an <a href="https://github.com/graemegilmourbates/gpudiff/issues">issue</a>
and we will avoid breaking you.</p>

<h2>Feeds &amp; badges</h2>
<p>RSS: <a href="/rss.xml">everything</a> · <a href="/gpu.xml">GPUs</a> ·
<a href="/llm/rss.xml">LLM APIs</a> · <a href="/saas/rss.xml">SaaS</a>.
Live price badges for your README: <a href="/badges.html">badges</a>.</p>"""
    return page("Free API — GPU, LLM, and SaaS prices as JSON | gpudiff", body, monetize,
                "Free CC BY JSON API for GPU cloud prices, LLM API per-token prices, SaaS pricing, "
                "price history, and the full changelog. No key required.",
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
    via = esc(ROUTER_LABEL.get(lo_router, lo_router or "—"))
    if lo_router:
        url, rel = gateway_link(lo_router, load_monetize())
        via = f"<a href='{esc(url)}'{rel}>{via} →</a>"
    return (f"<tr><td>{name}</td>"
            f"<td class='n'>{_price_cell(lo_in)}</td><td class='n'>{_price_cell(lo_out)}</td>"
            f"<td>{via}</td>"
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
through. We snapshot {", ".join(esc(ROUTER_LABEL.get(r, r)) for r in routers_live)} continually,
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


def _cheapest_cta(router, price, spread, monetize):
    """The one-line answer a buyer came for, linked to the gateway that earns it."""
    if not router or price is None:
        return ""
    url, rel = gateway_link(router, monetize)
    saving = f" — {spread:.1f}× cheaper than the priciest gateway" if spread and spread > 1.05 else ""
    return (f'<p class="cta">Cheapest right now: <a href="{esc(url)}"{rel}>'
            f'<strong>{esc(ROUTER_LABEL.get(router, router))}</strong> at ${price:.2f}/MTok in</a>{saving}.</p>')


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
        url, rel = gateway_link(rt, monetize)
        rows.append(
            f"<tr><td><strong>{esc(ROUTER_LABEL.get(rt, rt))}</strong>{fee_note}</td>"
            f"<td class='n'>{_price_cell(r.get('input'))}</td>"
            f"<td class='n'>{_price_cell(r.get('output'))}</td>"
            f"<td class='n'>{ctx}</td>"
            f"<td>{sparkline(series)}</td>"
            f"<td><span class='mut'>{esc(r.get('model_id') or '')}</span></td>"
            f"<td><a href='{esc(url)}'{rel}>use</a></td></tr>")

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
         f"Prices refresh continually." if lo_in and lo_out else "No current price is published."),
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
{_cheapest_cta(lo_router, lo_in, sp, monetize)}
<p class="mut">{esc(lab + ' · ') if lab else ''}from <strong>{_price_cell(lo_in)}</strong> per
million input tokens{f' · {sp:.1f}× spread between gateways' if sp and sp > 1.01 else ' · same price on every gateway'}
· updated continually</p>
<div class="tablewrap"><table>
<thead><tr><th>Gateway</th><th class="n">$ in /MTok</th><th class="n">$ out /MTok</th>
<th class="n">Context</th><th>Input price history</th><th>Model ID</th><th></th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
{fees}
<h2>Changelog for {esc(display)}</h2>
<ul class="chg">{log}</ul>
<h2>{esc(display)} pricing FAQ</h2>
{faq_html}
<p class="mut"><a href="/llm/">← All LLM prices</a> · <a href="/api/v1/llm/models.json">API</a></p>"""
    return page(f"{display} API Price — {len(routes)} gateways compared, updated continually | gpudiff",
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
        winner = a if delta > 0.01 else (b if delta < -0.01 else None)
        if winner:
            wurl, wrel = gateway_link(winner, monetize)
            verdict_html = f"<a href='{esc(wurl)}'{wrel} class='{cls}'>{esc(verdict)} →</a>"
        else:
            verdict_html = f"<span class='{cls}'>{esc(verdict)}</span>"
        rows.append(
            f"<tr><td>{_model_link(canonical)}</td>"
            f"<td class='n'>{_price_cell(ai)}</td><td class='n'>{_price_cell(bi)}</td>"
            f"<td class='n'>{_price_cell(ra.get('output'))}</td>"
            f"<td class='n'>{_price_cell(rb.get('output'))}</td>"
            f"<td>{verdict_html}</td></tr>")

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
<p>{esc(headline)} Input prices are USD per million tokens, refreshed continually; every model
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
                f"plus the gateway fees each one charges. Updated continually.",
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


def render_sponsor_page(monetize, stats):
    cfg = load_sponsors()
    rate = cfg.get("monthly_price_usd", cfg.get("founding_rate_usd", 49))
    contact = cfg.get("contact_url", "#")
    buy = cfg.get("buy_url", "")
    metrics = load_metrics()
    visits = metrics.get("uniques_total")
    audience_row = (f"<tr><td>Visits to date</td><td class='n'>{esc(visits)}</td>"
                    f"<td class='mut'>counted by GoatCounter, cookieless</td></tr>"
                    if visits else
                    "<tr><td>Visits</td><td class='n'>early</td><td class='mut'>the site launched in "
                    "August 2026; ask and we will send the live dashboard</td></tr>")
    if buy:
        buy_line = f'<a href="{esc(buy)}"><strong>Buy a month \u2192</strong></a>'
    else:
        buy_line = f'Purchase (payment link coming \u2014 <a href="{esc(contact)}">enquire</a> meanwhile)'
    body = f"""
<h1>Sponsor gpudiff</h1>
<p>gpudiff is read by people deciding where to buy compute: engineers comparing
GPU rental prices across clouds, teams choosing an LLM gateway, and buyers
watching what software costs are doing. If you sell any of those, this is a
small, precisely-targeted audience.</p>

<h2>What the site is, in numbers</h2>
<div class="tablewrap"><table>
<tbody>
<tr><td>Prices tracked</td><td class="n">{stats['offers']:,}</td><td class="mut">refreshed continually</td></tr>
<tr><td>Providers and gateways</td><td class="n">{stats['providers']}</td><td class="mut">GPU clouds, LLM routers, SaaS vendors</td></tr>
<tr><td>GPU configurations</td><td class="n">{stats['families']}</td><td class="mut">memory config treated as a distinct product</td></tr>
<tr><td>LLM models</td><td class="n">{stats['models']:,}</td><td class="mut">priced per million tokens</td></tr>
<tr><td>Indexed pages</td><td class="n">{stats['pages']}</td><td class="mut">each one a specific buying question</td></tr>
<tr><td>Recorded changes</td><td class="n">{stats['changes']:,}</td><td class="mut">the archive competitors cannot backfill</td></tr>
{audience_row}
</tbody></table></div>
<p class="mut">Traffic is early and we will not pretend otherwise — the numbers
above are live and the analytics dashboard is shareable on request. A founding
sponsor is buying a low rate and a long run, not a big audience today.</p>

<h2>Self-serve — live within the hour</h2>
<p>Buy a month, tell us your one line, and the unit appears automatically. No
sales call, no contract, cancel anytime.</p>
<div class="tablewrap"><table>
<thead><tr><th>Placement</th><th>Where it appears</th><th class="n">Monthly</th></tr></thead>
<tbody>
<tr><td><strong>Sitewide</strong></td><td>The single sponsor unit on every page, near the top</td><td class="n">${rate}</td></tr>
<tr><td><strong>Section</strong></td><td>GPU, LLM, or SaaS pages only</td><td class="n">${int(rate * 0.7)}</td></tr>
</tbody></table></div>
<p><strong>How it works:</strong></p>
<ol>
<li>{buy_line}</li>
<li>Open a <a href="{esc(contact)}">sponsor issue</a> with your company, link, and one line of copy.</li>
<li>Once payment clears, your unit is live on the next continually build.</li>
</ol>
<p class="mut">Founding rate — locked until the site passes 10,000 monthly visits.
Below what a comparable dev-audience placement costs, deliberately, because a slot
that is always filled is worth more to us than a slot that is often empty.</p>

<h2>What the unit looks like</h2>
<aside class="sponsor"><span class="sponsor-tag">Sponsored</span>
<a href="#"><strong>Your company</strong> — one honest line about what you sell</a></aside>
<p class="mut">That is the whole format: our own HTML, a label, a link, and a
line of text. No image ads, no animation, no third-party script, nothing that
moves the page around as it loads.</p>

<h2>Rules we do not bend</h2>
<ul class="chg">
<li>Every sponsored link is labelled and carries <code>rel="sponsored"</code>.</li>
<li>Sponsorship never changes a price, a ranking, or which providers we track.
The pipeline is open source, so anyone can verify that.</li>
<li>No third-party ad scripts, no tracking pixels, no cookies. We will not sell
an audience we do not surveil.</li>
<li>We will decline a sponsor whose product we would not honestly list.</li>
</ul>

<h2>Get in touch</h2>
<p><a href="{esc(contact)}">Open a sponsorship enquiry →</a> — tell us the company,
the URL, which placement, and how many months. We will reply with current traffic
and a start date.</p>"""
    return page("Sponsor gpudiff — reach engineers comparing GPU and LLM prices", body, monetize,
                "Sponsor gpudiff: one labelled, first-party unit on a site read by engineers "
                "comparing GPU cloud and LLM API prices. No trackers, no third-party scripts.",
                path="/sponsor.html")


def render_gpu_guide(fams, history, monetize):
    """Where to rent: the single cheapest live option per common GPU need, with
    a volatility read so nobody is surprised by a swing. Highest buying intent
    on the site — so the referral links here matter most."""
    def cheapest_in(keys):
        cands = []
        for fam in keys:
            e = fams.get(fam)
            if not e:
                continue
            for o in e["offers"]:
                if o["pricing_type"] == "on_demand":
                    cands.append((o["price"], fam, e, o))
        return min(cands, default=None, key=lambda t: t[0])

    needs = [
        ("Cheapest 80GB-class card (large models, training)",
         ["h100-sxm-80gb", "h100-pcie-80gb", "a100-sxm4-80gb", "a100-pcie-80gb", "h100-nvl-94gb"]),
        ("Cheapest 24GB card (7B–13B inference, dev)",
         ["rtx-4090-24gb", "rtx-3090-24gb", "l4-24gb", "a10-24gb", "a10g-24gb"]),
        ("Cheapest 48GB card (fine-tuning, 34B inference)",
         ["l40s-48gb", "l40-48gb", "rtx-a6000-48gb", "rtx-pro-5000-48gb", "rtx-4090-48gb"]),
        ("Cheapest 141GB+ card (frontier, 70B+ single-GPU)",
         ["h200-sxm-141gb", "h200-nvl-143gb", "b200-180gb", "mi300x-192gb", "b300-288gb"]),
    ]
    cards = []
    for title, keys in needs:
        pick = cheapest_in(keys)
        if not pick:
            continue
        price, fam, e, o = pick
        url, rel = outbound(o, monetize)
        series = history.get(o["id"], [])
        cards.append(f"""<div class="pick">
<h3>{esc(title)}</h3>
<div class="big">{esc(fam_display(fam, e))} — ${price:.2f}/hr</div>
<div>on <strong>{esc(o['provider'])}</strong> ({esc(o.get('region',''))}) {vol_badge(series)}
 · <a href="{esc(url)}"{rel}>rent →</a> · <a href="/gpu/{esc(fam)}.html">all offers &amp; history</a></div>
<div class="why">Cheapest live on-demand price across everything we track for this need.
The volatility tag reflects the last week of prices — marketplace rates move; check before you commit to a long run.</div>
</div>""")
    body = f"""
<h1>Where to rent a GPU: the cheapest option right now</h1>
<p class="mut">One pick per common need — the lowest live on-demand price across every
provider we track, refreshed continually. The volatility tag warns when a price has been
moving, so a cheap number today is not a surprise bill tomorrow.</p>
{''.join(cards)}
<p class="mut">Want a specific card, spot prices, or the full history? Start from the
<a href="/">GPU price table</a>. Prices are marketplace/list rates, not quotes; see
<a href="/methodology.html">methodology</a>.</p>"""
    return page("Where to Rent a GPU — cheapest option per need, updated continually | gpudiff",
                body, monetize,
                "The cheapest live GPU cloud rental for each common need — 80GB, 24GB, 48GB, and frontier "
                "cards — with a volatility read on each, refreshed continually.",
                path="/gpu-guide.html")


def render_llm_guide(llm_offers, history, monetize):
    """Where to buy tokens: cheapest gateway per tier, with volatility."""
    idx = llm_model_index(llm_offers)
    wl = load_watchlist()

    def series_for(routes, router, direction):
        r = routes.get(router) or {}
        return history.get(r.get(f"{direction}_id"), [])

    tiers = [
        ("Cheapest frontier model (Claude / GPT / Gemini class)",
         ["claude-opus-5", "claude-sonnet-5", "gpt-5.6-sol", "gpt-5.6-terra", "gemini-3.1-pro"]),
        ("Cheapest strong open-weight model (Llama / Qwen / DeepSeek / GLM)",
         ["deepseek-v4-pro", "qwen3.8-max", "glm-5.2", "llama-4-maverick", "kimi-k3"]),
        ("Cheapest fast/cheap workhorse (flash-class)",
         ["gemini-3.7-flash", "deepseek-v4-flash", "gpt-5.6-luna"]),
    ]
    cards = []
    for title, keys in tiers:
        best = None
        for key in keys:
            meta = wl.get(key, {})
            routes = watchlist_routes(idx, meta, key) if meta else (idx.get(key) or {})
            lo_in, lo_router = _cheapest(routes, "input")
            if lo_in is None:
                continue
            if best is None or lo_in < best[0]:
                best = (lo_in, key, meta, routes, lo_router)
        if not best:
            continue
        lo_in, key, meta, routes, lo_router = best
        lo_out, _ = _cheapest(routes, "output")
        disp = meta.get("display", key)
        url, rel = gateway_link(lo_router, monetize)
        series = series_for(routes, lo_router, "input")
        cards.append(f"""<div class="pick">
<h3>{esc(title)}</h3>
<div class="big">{esc(disp)} — ${lo_in:.2f} in / ${lo_out:.2f} out per MTok</div>
<div>cheapest via <strong>{esc(ROUTER_LABEL.get(lo_router, lo_router))}</strong> {vol_badge(series)}
 · <a href="{esc(url)}"{rel}>use →</a> · <a href="/llm/model/{esc(key)}.html">all gateways &amp; history</a></div>
<div class="why">Lowest input price across the gateways we track for this tier. Frontier
models are usually identical across gateways (list passthrough); open-weight prices move,
so watch the volatility tag.</div>
</div>""")
    body = f"""
<h1>Where to buy LLM tokens: the cheapest gateway right now</h1>
<p class="mut">One pick per tier — the lowest live per-token price across six gateways,
refreshed continually, with a volatility read. Same model, wrong gateway, and you can pay
several times as much.</p>
{''.join(cards)}
<p class="mut">Full table, every model, and per-model history on the
<a href="/llm/">LLM prices page</a>. These are published list prices, not quotes;
see <a href="/methodology.html">methodology</a>.</p>"""
    return page("Where to Buy LLM Tokens — cheapest gateway per tier, updated continually | gpudiff",
                body, monetize,
                "The cheapest LLM API gateway for each tier — frontier, open-weight, and flash models — "
                "with a volatility read on each, refreshed continually across six gateways.",
                path="/llm-guide.html")


def render_gpu_guide_stub():
    pass


def render_movers(changelog, monetize, aliases):
    """The biggest price changes in the last 7 days, always current. Targets the
    high-intent 'gpu price drops this week' / 'llm price changes' searches, and
    regenerates every build so it is genuinely fresh, not a stale doorway."""
    import datetime
    cutoff = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    recent = [e for e in changelog if e["kind"] == "price_change" and e["date"] >= cutoff]
    def section_label(e):
        return {"gpu": "GPU", "llm": "LLM", "saas": "SaaS"}[entry_section(e)]
    def link(e):
        prov, sku = e["id"].split(":")[0], e["id"].split(":")[1]
        if prov in LLM_PROVIDERS:
            return f"/llm/model/{esc(canon_model((e.get('id').split(':')[1]) or ''))}.html"
        if sku.startswith("pricing-"):
            return "/saas/"
        return f"/gpu/{esc(family_of(sku, aliases))}.html"
    drops = sorted([e for e in recent if e.get("pct", 0) < 0], key=lambda e: e["pct"])[:20]
    rises = sorted([e for e in recent if e.get("pct", 0) > 0], key=lambda e: -e["pct"])[:20]
    def rows(items, cls):
        return "".join(
            f"<tr><td><span class='badge'>{section_label(e)}</span></td>"
            f"<td class='n {cls}'>{e['pct']:+.0f}%</td>"
            f"<td><a href='{link(e)}'>{esc(e['summary'])}</a></td>"
            f"<td class='mut n'>{esc(e['date'])}</td></tr>" for e in items) or             "<tr><td colspan='4' class='mut'>Quiet week — no moves in this direction.</td></tr>"
    body = f"""
<h1>Biggest AI compute price changes this week</h1>
<p class="mut">The largest moves across GPU cloud, LLM API, and SaaS pricing in the last
seven days, refreshed continually from our public archive. {len(recent)} recorded changes in
the window.</p>
<h2>Biggest price drops</h2>
<div class="tablewrap"><table>
<thead><tr><th>Where</th><th class="n">Change</th><th>What</th><th class="n">Date</th></tr></thead>
<tbody>{rows(drops, 'cut')}</tbody></table></div>
<h2>Biggest price rises</h2>
<div class="tablewrap"><table>
<thead><tr><th>Where</th><th class="n">Change</th><th>What</th><th class="n">Date</th></tr></thead>
<tbody>{rows(rises, 'raise')}</tbody></table></div>
<p class="mut">Every change links its source and is versioned in
<a href="https://github.com/graemegilmourbates/gpudiff">public git</a>. Follow moves as
they happen: <a href="/rss.xml">RSS</a> · <a href="/api/v1/changelog.json">API</a>.
See also <a href="/gpu-guide.html">where to rent a GPU</a> and
<a href="/llm-guide.html">where to buy tokens</a>.</p>"""
    return page("Biggest AI Compute Price Changes This Week — GPU, LLM & SaaS | gpudiff",
                body, monetize,
                "The biggest GPU cloud, LLM API, and SaaS price drops and rises in the last seven days, "
                "refreshed continually with provenance.",
                path="/movers.html")


def rank_providers(item_to_prices, min_comparable=3):
    """Fair, intuitive value ranking. item_to_prices maps an item (a GPU family
    or an LLM model) to {provider: that provider's cheapest price for it}.

    Only items two or more providers offer are scored — you cannot be "cheaper"
    than nobody. For each item we find the lowest price and give every provider
    within 0.5% of it a co-win (so identical frontier prices don't hand an
    arbitrary provider the trophy). Each provider's headline number is the
    MEDIAN premium over the cheapest across the items it offers — median, not
    mean, so one wildly-priced outlier can't sink an otherwise cheap provider —
    and providers are ranked by that, then by how often they are cheapest."""
    from collections import defaultdict
    import statistics
    st = defaultdict(lambda: {"wins": 0, "comparable": 0, "premiums": []})
    for _, prices in item_to_prices.items():
        if len(prices) < 2:
            continue
        cheapest = min(prices.values())
        if cheapest <= 0:
            continue
        for prov, price in prices.items():
            st[prov]["comparable"] += 1
            st[prov]["premiums"].append(price / cheapest)
            if price <= cheapest * 1.005:
                st[prov]["wins"] += 1
    rows = []
    for prov, d in st.items():
        if not d["premiums"]:
            continue
        rows.append({
            "provider": prov, "wins": d["wins"], "comparable": d["comparable"],
            "win_rate": d["wins"] / d["comparable"],
            "median_premium": statistics.median(d["premiums"]),
        })
    ranked = sorted([r for r in rows if r["comparable"] >= min_comparable],
                    key=lambda r: (round(r["median_premium"], 3), -r["win_rate"]))
    thin = sorted([r for r in rows if r["comparable"] < min_comparable],
                  key=lambda r: -r["comparable"])
    return ranked, thin


def _rank_table(ranked, thin, label_fn, link_fn, unit="offers"):
    def typical(r):
        pct = (r["median_premium"] - 1) * 100
        return "usually cheapest" if pct < 1 else f"+{pct:.0f}% typical"
    body = []
    for i, r in enumerate(ranked, 1):
        url, rel = link_fn(r["provider"])
        medal = {1: "\U0001F947", 2: "\U0001F948", 3: "\U0001F949"}.get(i, str(i))
        cls = "cut" if r["median_premium"] < 1.01 else ("raise" if r["median_premium"] > 1.25 else "")
        body.append(
            f"<tr><td class='n'><strong>{medal}</strong></td>"
            f"<td><strong>{esc(label_fn(r['provider']))}</strong></td>"
            f"<td class='n {cls}'>{typical(r)}</td>"
            f"<td class='n'>{r['wins']} of {r['comparable']} "
            f"<span class='mut'>({r['win_rate'] * 100:.0f}%)</span></td>"
            f"<td><a href='{esc(url)}'{rel}>visit \u2192</a></td></tr>")
    for r in thin:
        url, rel = link_fn(r["provider"])
        body.append(
            f"<tr><td class='n mut'>\u2014</td>"
            f"<td>{esc(label_fn(r['provider']))} <span class='mut'>(too few shared {unit})</span></td>"
            f"<td class='n mut'>\u2014</td>"
            f"<td class='n mut'>{r['comparable']} shared</td>"
            f"<td><a href='{esc(url)}'{rel}>visit \u2192</a></td></tr>")
    return ("<div class='tablewrap'><table><thead><tr><th class='n'>Rank</th><th>Provider</th>"
            f"<th class='n'>Typical price</th><th class='n'>Cheapest on</th>"
            "<th></th></tr></thead><tbody>" + "".join(body) + "</tbody></table></div>")


def render_gpu_ranking(fams, monetize):
    item_to_prices = {}
    for fam, e in fams.items():
        od = [o for o in e["offers"] if o["pricing_type"] == "on_demand"]
        by_prov = {}
        for o in od:
            by_prov[o["provider"]] = min(o["price"], by_prov.get(o["provider"], o["price"]))
        if by_prov:
            item_to_prices[fam] = by_prov
    ranked, thin = rank_providers(item_to_prices)
    label = lambda p: PROVIDER_BLURB.get(p, (p,))[0]
    link = lambda p: outbound({"provider": p, "provenance": {"url": "#"}}, monetize)
    verdict = ""
    if ranked:
        w = ranked[0]
        verdict = (f'<p class="cta"><strong>Cheapest GPU cloud right now: '
                   f'{esc(label(w["provider"]))}</strong> \u2014 the lowest price on '
                   f'{w["wins"]} of {w["comparable"]} comparable GPUs '
                   f'({w["win_rate"] * 100:.0f}%).</p>')
    body = f"""
<h1>Cheapest GPU cloud provider, ranked</h1>
<p class="mut">Which cloud is actually cheapest for renting GPUs? We rank every provider we
track by how its prices compare on the GPUs it shares with others — on-demand, updated continually.
A provider is only scored on cards at least one competitor also offers, so nobody wins by
only listing cheap hardware.</p>
{verdict}
{_rank_table(ranked, thin, label, link)}
<h2>How this ranking works</h2>
<p>For every GPU sold by two or more providers we find the lowest price, then measure how
much more each provider charges. <strong>"Typical price"</strong> is the median of those
premiums across the GPUs a provider offers — median, so one oddly-priced card can't skew it.
<strong>"Cheapest on"</strong> counts the GPUs where a provider matches the lowest price
(ties share the win). We rank on <strong>published on-demand price only</strong> — not speed,
reliability, or support (<a href="/methodology.html">methodology</a>). Provider links may
carry a referral code; the ranking is computed from prices and is unaffected.</p>
<p class="mut">Looking for one specific card? <a href="/gpu-guide.html">Where to rent a GPU →</a>
· Buying tokens instead? <a href="/cheapest-llm-api.html">Cheapest LLM API →</a></p>"""
    return page("Cheapest GPU Cloud Provider — RunPod, Vast, AWS, Azure ranked by price | gpudiff",
                body, monetize,
                "The cheapest GPU cloud provider, ranked by real on-demand prices across the GPUs "
                "each one offers. Updated continually, compared like-for-like.",
                path="/cheapest-gpu-cloud.html")


def render_llm_ranking(llm_offers, monetize):
    idx = llm_model_index(llm_offers)
    item_to_prices = {}
    for canonical, routes in idx.items():
        by_g = {g: r["input"] for g, r in routes.items() if isinstance(r.get("input"), (int, float))}
        if by_g:
            item_to_prices[canonical] = by_g
    ranked, thin = rank_providers(item_to_prices)
    label = lambda g: ROUTER_LABEL.get(g, g)
    link = lambda g: gateway_link(g, monetize)
    verdict = ""
    if ranked:
        w = ranked[0]
        verdict = (f'<p class="cta"><strong>Cheapest LLM gateway right now: '
                   f'{esc(label(w["provider"]))}</strong> \u2014 the lowest input price on '
                   f'{w["wins"]} of {w["comparable"]} shared models '
                   f'({w["win_rate"] * 100:.0f}%).</p>')
    body = f"""
<h1>Cheapest LLM API gateway, ranked</h1>
<p class="mut">Six gateways resell the same models at different prices. We rank them by input
price across the models they share, updated continually. Frontier models are usually identical
everywhere (gateways pass list pricing through), so the ranking is decided by open-weight
models — where the gap can be large.</p>
{verdict}
{_rank_table(ranked, thin, label, link)}
<h2>How this ranking works</h2>
<p>For every model sold by two or more gateways we find the lowest input price, then measure
each gateway's premium over it. <strong>"Typical price"</strong> is the median of those
premiums across the models a gateway carries — median, so a handful of wildly-priced models
can't skew the result, which is why a gateway that is cheapest most of the time reads as
"usually cheapest" even if its average is dragged up by outliers. <strong>"Cheapest on"</strong>
counts models where a gateway matches the lowest price (identical frontier prices are shared
wins). We rank on <strong>published per-token input price only</strong> — not latency,
throughput, or uptime (<a href="/methodology.html">methodology</a>). Gateway links may carry a
referral code; the ranking is computed from prices and is unaffected.</p>
<p class="mut"><a href="/llm-guide.html">Where to buy tokens by tier →</a> ·
<a href="/cheapest-gpu-cloud.html">Cheapest GPU cloud →</a></p>"""
    return page("Cheapest LLM API Gateway — OpenRouter, Ramp, Novita & more ranked by price | gpudiff",
                body, monetize,
                "The cheapest LLM API gateway, ranked by real per-token prices across the models "
                "each one offers. OpenRouter, Ramp Router, Requesty, Glama, Novita, DeepInfra.",
                path="/cheapest-llm-api.html")


def render_rankings_hub(fams, llm_offers, monetize):
    body = """
<h1>Price rankings: the cheapest GPU cloud and LLM API</h1>
<p class="mut">Not "which option for this need" (that is the <a href="/gpu-guide.html">guides</a>)
— this ranks the <em>providers themselves</em> by how cheap they are across everything they
offer, compared like-for-like and updated continually.</p>
<div class="pick"><h3><a href="/cheapest-gpu-cloud.html">Cheapest GPU cloud provider →</a></h3>
<div class="why">RunPod, Vast.ai, AWS, and Azure ranked by real on-demand prices across the
GPUs they share.</div></div>
<div class="pick"><h3><a href="/cheapest-llm-api.html">Cheapest LLM API gateway →</a></h3>
<div class="why">OpenRouter, Ramp Router, Requesty, Glama, Novita, and DeepInfra ranked by
per-token price across the models they share.</div></div>"""
    return page("Cheapest GPU Cloud & LLM API — price rankings | gpudiff", body, monetize,
                "Price rankings for AI compute: the cheapest GPU cloud provider and the cheapest "
                "LLM API gateway, compared like-for-like and updated continually.",
                path="/rankings.html")


def render_memory(memory_offers, changelog, monetize, aliases):
    by = {}
    for o in memory_offers:
        by.setdefault(o["attrs"]["generation"], []).append(o)
    rows = []
    for gen in sorted(by, reverse=True):
        for o in sorted(by[gen], key=lambda o: o["attrs"]["kit_gb"]):
            rows.append(
                f"<tr><td><strong>{esc(gen)}</strong></td>"
                f"<td class='n'>{o['attrs']['kit_gb']} GB</td>"
                f"<td class='n'><strong>${o['price']:.2f}</strong>/GB</td>"
                f"<td class='n'>${o['price'] * o['attrs']['kit_gb']:.0f}</td>"
                f"<td class='mut n'>p25 \u00d7{o['attrs']['sample_size']}</td></tr>")
    recent = [e for e in changelog if entry_section(e) == "memory"][-15:]
    log = "\n".join(chg_html(e, aliases) for e in reversed(recent)) or \
          '<li class="mut">Price history begins once tracking is live.</li>'
    if rows:
        table = ("<div class='tablewrap'><table><thead><tr><th>Type</th><th class='n'>Kit</th>"
                 "<th class='n'>$/GB</th><th class='n'>Kit price</th><th class='n'>Sample</th>"
                 "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")
        intro = ("Retail DDR5 and DDR4 memory prices, per gigabyte, from Best Buy's public "
                 "catalog \u2014 the 25th-percentile price across current listings for each kit "
                 "size, so one overpriced SKU can't skew it. Refreshed daily.")
    else:
        table = ('<p class="mut">Tracking is scaffolded and waiting on a data key. RAM prices '
                 'appear here on the next build once it is connected.</p>')
        intro = ("Retail DRAM prices swing sharply \u2014 exactly what a price changelog should "
                 "capture. We source them from Best Buy's sanctioned public API rather than "
                 "scraping retailers that block automated traffic.")
    body = f"""
<h1>RAM price tracker <span class="badge">beta</span></h1>
<p class="mut">{intro}</p>
<h2>What changed</h2>
<ul class="chg">{log}</ul>
<h2>Current $/GB by memory type</h2>
{table}
<p class="mut">Prices are US retail list from a public catalog, not spot/contract commodity
prices (those live behind paywalls like TrendForce). See <a href="/methodology.html">methodology</a>.</p>"""
    return page("RAM Price Tracker \u2014 DDR5 & DDR4 $/GB, updated daily | gpudiff", body, monetize,
                "Retail DDR5 and DDR4 RAM prices per gigabyte, tracked daily with a changelog of every "
                "change. Sourced from a public catalog API, not scraped.",
                path="/memory.html")


def render_methodology(monetize):
    body = """
<h1>Methodology</h1>
<p>gpudiff records the price of renting GPUs in the cloud, continually, with a
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
buyer can actually get," not the single cheapest outlier.</td><td>continually</td></tr>
<tr><td>RunPod</td><td>Published list prices per GPU type, secure and community
cloud, on-demand and spot. Community tiers can be availability-limited.</td><td>continually</td></tr>
<tr><td>AWS</td><td>On-demand Linux/shared list price of the smallest qualifying
instance per GPU family, us-east-1, divided by GPU count. AWS sells bundles
(CPUs + RAM attached), so rows are badged instance-bundled.</td><td>daily</td></tr>
<tr><td>Azure</td><td>Retail Prices API, eastus, Linux consumption rates ÷ GPU
count; on-demand and spot. Instance-bundled like AWS.</td><td>daily</td></tr>
<tr><td>OpenRouter (LLM)</td><td>Public model catalog; input and output prices
per million tokens, tracked as separate series per model. This is the resale
layer of LLM pricing; official provider list pages join as slower sources.</td><td>continually</td></tr>
<tr><td>Requesty · Glama · Novita · DeepInfra (LLM)</td><td>Each router's public
catalog, normalized to USD per million tokens. A router often lists one model
several times (different upstream hosts or regions); we publish the cheapest
route per model and record how many were collapsed. Models are joined across
routers by canonical name — last path segment, region suffix stripped — so
<code>vertex/claude-sonnet-5@eu</code> and <code>anthropic/claude-sonnet-5</code>
are one row.</td><td>continually</td></tr>
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
The site also sells a single first-party <a href="/sponsor.html">sponsor unit</a>,
always labelled, served from our own HTML with no third-party script or tracker.
Neither influences which numbers are shown, how they are computed, or which
providers we track — the pipeline is open source, so you can check.</p>"""
    return page("Methodology — gpudiff", body, monetize,
                "How gpudiff computes GPU cloud prices: per-source metrics, validation gates, provenance, and what we deliberately don't claim.",
                path="/methodology.html")


SECTION_OF = {"usd_per_mtok": "llm", "usd_per_unit": "saas"}


def entry_section(e):
    if e["id"].split(":")[0] in LLM_PROVIDERS:
        return "llm"
    if e["id"].split(":")[0] == "bestbuy":
        return "memory"
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
                "Embeddable live GPU price badges: current prices in your README or blog, updated continually.",
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
    memory_offers = [o for o in offers if o["unit"] == "usd_per_gb_ram"]
    gpu_offers = [o for o in offers if o["unit"] not in ("usd_per_mtok", "usd_per_unit", "usd_per_gb_ram")]
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
    (SITE / "api" / "v1" / "llm" / "history").mkdir(parents=True, exist_ok=True)
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

        # Per-model price series, one entry per gateway and direction — the
        # question only our archive can answer: how has this model priced?
        series = {}
        for rt, r in routes.items():
            for direction in ("input", "output"):
                oid = r.get(f"{direction}_id")
                if oid and history.get(oid):
                    series[f"{rt}:{direction}"] = history[oid]
        (SITE / "api" / "v1" / "llm" / "history" / f"{canonical}.json").write_text(
            json.dumps({"model": canonical, "unit": "usd_per_mtok", "series": series},
                       indent=2) + "\n")

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
    (SITE / "gpu-guide.html").write_text(render_gpu_guide(fams, history, monetize))
    (SITE / "llm-guide.html").write_text(render_llm_guide(llm_offers, history, monetize))
    (SITE / "movers.html").write_text(render_movers(changelog, monetize, aliases))
    (SITE / "memory.html").write_text(render_memory(memory_offers, changelog, monetize, aliases))
    (SITE / "rankings.html").write_text(render_rankings_hub(fams, llm_offers, monetize))
    (SITE / "cheapest-gpu-cloud.html").write_text(render_gpu_ranking(fams, monetize))
    (SITE / "cheapest-llm-api.html").write_text(render_llm_ranking(llm_offers, monetize))
    sponsor_stats = {
        "offers": len(offers),
        "providers": len({o["provider"] for o in offers}),
        "families": len(fams),
        "models": len(llm_model_index(llm_offers)),
        "changes": len(changelog),
        "pages": 0,  # filled after the sitemap is known
    }
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
    overall = [("gpudiff.svg", "gpudiff", f"{len(offers)} prices · continually diffs", "/"),
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

    urls = [f"{BASE_URL}/", f"{BASE_URL}/rankings.html", f"{BASE_URL}/cheapest-gpu-cloud.html",
            f"{BASE_URL}/cheapest-llm-api.html", f"{BASE_URL}/movers.html", f"{BASE_URL}/memory.html",
            f"{BASE_URL}/gpu-guide.html", f"{BASE_URL}/llm-guide.html",
            f"{BASE_URL}/llm/", f"{BASE_URL}/saas/", f"{BASE_URL}/fit.html",
            f"{BASE_URL}/changelog.html", f"{BASE_URL}/badges.html",
            f"{BASE_URL}/methodology.html", f"{BASE_URL}/api/", f"{BASE_URL}/digest/",
            f"{BASE_URL}/sponsor.html"] + \
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
    sponsor_stats["pages"] = len(urls)
    (SITE / "sponsor.html").write_text(render_sponsor_page(monetize, sponsor_stats))
    (SITE / "llms.txt").write_text(f"""# gpudiff

> The public record of change in AI compute and software pricing: GPU cloud
> rental prices (Vast.ai, RunPod, AWS, Azure), LLM API per-token prices across
> six gateways (OpenRouter, Ramp Router, Requesty, Glama, Novita, DeepInfra),
> and SaaS pricing pages — snapshotted continually, validated, diffed, and archived
> in public git with a provenance URL on every number. CC BY 4.0: cite gpudiff.com.

Current snapshot: {esc(date)} · {len(offers):,} prices · {len(fams)} GPU configurations ·
{len(llm_model_index(llm_offers)):,} LLM models · {len(changelog):,} recorded changes.

## Answering price questions
- Cheapest current price per GPU: {BASE_URL}/api/v1/families.json
- Every offer with provenance: {BASE_URL}/api/v1/offers.json
- LLM per-token prices by gateway: {BASE_URL}/api/v1/llm/models.json
- Per-GPU history: {BASE_URL}/api/v1/history/<gpu>.json (e.g. h100-sxm-80gb)
- Per-model history: {BASE_URL}/api/v1/llm/history/<model>.json (e.g. claude-opus-5)
- Every recorded change: {BASE_URL}/api/v1/changelog.json

## Pages
- GPU prices: {BASE_URL}/
- LLM API prices: {BASE_URL}/llm/
- Per-GPU pages: {BASE_URL}/gpu/<gpu>.html
- Per-model pages: {BASE_URL}/llm/model/<model>.html
- Gateway head-to-heads: {BASE_URL}/llm/compare/<a>-vs-<b>.html
- Methodology and what we do not claim: {BASE_URL}/methodology.html

Marketplace prices (Vast) are the 25th percentile of verified listings; hyperscaler
prices are on-demand list divided by GPU count; nameplate specs are vendor claims,
not measured throughput.
""")
    (SITE / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n")

    return SITE / "index.html"
