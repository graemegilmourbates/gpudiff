"""Turn approved sponsor issues into live slots. Runs in CI.

A sponsor buys a slot (payment link), opens an issue from the template, and a
maintainer — or the auto-approve rule — adds the `sponsor-live` label once
payment is confirmed. This reads every `sponsor-live` issue via the GitHub API,
parses the template fields, sanitizes them hard (external, paid text goes onto
every page — it must never inject markup or a javascript: link), and writes
sponsors.json. The next refresh renders it.

No secrets: uses the Actions-provided GITHUB_TOKEN via `gh` through the
environment, or falls back to the public issues API (public repo)."""

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "graemegilmourbates/gpudiff"
SECTION = {"sitewide": "all", "gpu pages only": "gpu",
           "llm pages only": "llm", "saas pages only": "saas"}


def _fetch_issues():
    url = f"https://api.github.com/repos/{REPO}/issues?labels=sponsor-live&state=open&per_page=50"
    req = urllib.request.Request(url, headers={
        "User-Agent": "FoundryBot/0.1", "Accept": "application/vnd.github+json"})
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        req.add_header("Authorization", f"Bearer {tok}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _field(body, label):
    """Pull one value from the rendered issue-form markdown."""
    m = re.search(rf"###\s*{re.escape(label)}\s*\n+([^\n#]+)", body or "", re.I)
    return m.group(1).strip() if m else ""


def _clean_text(v, limit):
    v = re.sub(r"<[^>]*>", "", v)                 # no markup
    v = re.sub(r"[\r\n\t]+", " ", v).strip()
    return v[:limit]


def _clean_url(v):
    v = v.strip().split()[0] if v.strip() else ""
    return v if re.match(r"^https://[\w.-]+\.[a-z]{2,}(/\S*)?$", v, re.I) else ""


def build(issues):
    active = []
    for iss in issues:
        body = iss.get("body", "")
        name = _clean_text(_field(body, "Company / product name"), 40)
        url = _clean_url(_field(body, "Link URL (https://)"))
        tag = _clean_text(_field(body, "One line of copy (max 80 chars)"), 80)
        section = SECTION.get(_field(body, "Placement").strip().lower(), "all")
        if name and url and tag:
            active.append({"name": name, "url": url, "tagline": tag,
                           "section": section, "issue": iss.get("number")})
    return active


def main():
    cfg_path = ROOT / "sponsors.json"
    cfg = json.loads(cfg_path.read_text())
    try:
        issues = _fetch_issues()
    except Exception as exc:  # noqa: BLE001 — never wipe live slots on a fetch blip
        print(f"sponsor intake: fetch failed ({exc}); leaving sponsors.json unchanged", file=sys.stderr)
        return 0
    active = build(issues)
    # One sponsor per section: first approved wins, keeps it deterministic.
    seen, deduped = set(), []
    for sp in active:
        if sp["section"] in seen:
            continue
        seen.add(sp["section"])
        deduped.append(sp)
    cfg["active"] = deduped
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")
    print(f"sponsor intake: {len(deduped)} live slot(s): {[s['name'] for s in deduped]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
