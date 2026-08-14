"""Weekly analyst: gathers the four leading indicators (traffic, audience,
mentions, data velocity) into data/metrics/<date>.json plus a markdown report.
Everything here is public-endpoint or best-effort — no credentials. Referral
earnings are owner-reported in the monthly board issue (dashboards need their
login, which automation never touches)."""

import argparse
import datetime as dt
import json
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
METRICS = ROOT / "data" / "metrics"
UA = "FoundryBot/0.1 (analyst; gpudiff.com)"


def _get_json(url, timeout=20):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except Exception:  # noqa: BLE001 — every metric is best-effort
        return None


def goatcounter_total(code):
    """Public counter endpoint — requires 'public counter' enabled in the
    GoatCounter site settings; returns None until the owner flips it."""
    for path in ("TOTAL", urllib.parse.quote("/", safe="")):
        d = _get_json(f"https://{code}.goatcounter.com/counter/{path}.json")
        if d and d.get("count") is not None:
            return str(d["count"]).replace(" ", "")
    return None


def hn_mentions():
    hits, links = 0, []
    for q in ("gpudiff", "gpudiff.com"):
        d = _get_json(f"https://hn.algolia.com/api/v1/search?query=%22{q}%22&hitsPerPage=5")
        if not d:
            continue
        hits = max(hits, d.get("nbHits", 0))
        for h in d.get("hits", []):
            oid = h.get("objectID")
            if oid:
                links.append(f"https://news.ycombinator.com/item?id={oid}")
    return hits, sorted(set(links))[:5]


def repo_stats():
    d = _get_json("https://api.github.com/repos/graemegilmourbates/gpudiff")
    if not d:
        return {}
    return {"stars": d.get("stargazers_count"), "forks": d.get("forks_count"),
            "watchers": d.get("subscribers_count")}


def changelog_velocity(days=7):
    path = ROOT / "data" / "changelog.json"
    if not path.exists():
        return {"total": 0, "gpu": 0, "llm": 0, "saas": 0}
    cutoff = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    out = {"total": 0, "gpu": 0, "llm": 0, "saas": 0}
    for e in json.loads(path.read_text()):
        if e["date"] < cutoff:
            continue
        out["total"] += 1
        if e["id"].startswith("openrouter:"):
            out["llm"] += 1
        elif e["id"].split(":")[1].startswith("pricing-"):
            out["saas"] += 1
        else:
            out["gpu"] += 1
    return out


def run(write):
    today = dt.date.today().isoformat()
    health = {}
    hpath = ROOT / "data" / "health.json"
    if hpath.exists():
        health = json.loads(hpath.read_text())
    uniques = goatcounter_total("graemebates")
    hn_count, hn_links = hn_mentions()
    repo = repo_stats()
    velocity = changelog_velocity()

    metrics = {
        "date": today,
        "uniques_total": uniques,
        "hn_mentions": hn_count,
        "hn_links": hn_links,
        "repo": repo,
        "changelog_7d": velocity,
        "offers": health.get("valid"),
        "sources_healthy": health.get("healthy"),
    }

    lines = [
        f"# Analyst report — {today}",
        "",
        f"- **Site visits (GoatCounter total)**: {uniques if uniques is not None else 'n/a — enable *public counter* in GoatCounter settings (Settings → Public counter) or check the dashboard manually'}",
        f"- **HN mentions**: {hn_count}" + (f" ({', '.join(hn_links)})" if hn_links else ""),
        f"- **Repo**: {repo.get('stars', '?')}★ · {repo.get('forks', '?')} forks · {repo.get('watchers', '?')} watchers",
        f"- **Changelog velocity (7d)**: {velocity['total']} entries — {velocity['gpu']} gpu · {velocity['llm']} llm · {velocity['saas']} saas",
        f"- **Dataset**: {health.get('valid', '?')} offers · sources {'healthy' if health.get('healthy') else 'DEGRADED'}",
        "",
        "Owner-reported (monthly, in the board issue): referral signups & earnings (Vast, RunPod).",
        "Gate (day-90): 1,000 uniques/mo OR 150 subscribers OR $50 MRR.",
    ]
    report = "\n".join(lines) + "\n"

    if write:
        METRICS.mkdir(parents=True, exist_ok=True)
        (METRICS / f"{today}.json").write_text(json.dumps(metrics, indent=2) + "\n")
        (METRICS / "latest.md").write_text(report)
    print(report)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    raise SystemExit(run(args.write))


if __name__ == "__main__":
    main()
