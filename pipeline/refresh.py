"""Orchestrator: one refresh run = fetch → validate → snapshot → diff → build.
This is what refresh.yml executes on cron.

Sources are isolated: one broken scraper never blocks the others. The run
publishes whatever validated (missing beats wrong), records per-source status
in data/health.json, and `python3 -m pipeline.refresh --check-health` lets CI
fail the job — after committing good data — so the sentinel pages humans."""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from .build import build_site
from .diffgen import append_changelog, diff_snapshots
from .validate import SCHEMA_PATH, _load, split_offers

ROOT = Path(__file__).resolve().parent.parent


def data_root(use_fixtures):
    return ROOT / "data" / "dev" if use_fixtures else ROOT / "data"


def previous_snapshot(offers_dir, before_date):
    if not offers_dir.exists():
        return None
    snaps = sorted(p for p in offers_dir.glob("*.json") if p.stem < before_date)
    return snaps[-1] if snaps else None


def gather(date, use_fixtures, observed_at, carry_pool=(), force_all=False):
    """Returns (offers, statuses): per-source isolation, failures recorded.

    Daily-cadence sources fetch on the 06:xx UTC run (or when absent from the
    carry pool); between fetches their previous offers are carried forward
    unchanged so hourly snapshots never drop them."""
    if use_fixtures:
        from sources.fixtures import FixtureSource
        registry = [FixtureSource(date)]
    else:
        from sources.aws import AwsSource
        from sources.azure import AzureSource
        from sources.commodity import CommoditySource
        from sources.memory import MemorySource
        from sources.openrouter import OpenRouterSource
        from sources.ramp import RampSource
        from sources.routers import RoutersSource
        from sources.runpod import RunpodSource
        from sources.saaspages import SaasPagesSource
        from sources.vast import VastSource
        registry = [VastSource(), RunpodSource(), AwsSource(), AzureSource(),
                    OpenRouterSource(), RoutersSource(), RampSource(), SaasPagesSource(),
                    CommoditySource()]
        # Retail RAM source registers only when its key is set, so its inert
        # empty result never trips the "0 offers = broken" health gate.
        mem = MemorySource()
        from sources.memory import _key
        if _key():
            registry.append(mem)

    hour = dt.datetime.now(dt.timezone.utc).hour
    offers, statuses = [], []
    for source in registry:
        cadence = getattr(source, "cadence", "hourly")
        emits = getattr(source, "emits", {source.name})
        present = any(o["provider"] in emits for o in carry_pool)
        due = force_all or cadence == "hourly" or hour == 6 or not present
        if not due:
            carried = [o for o in carry_pool if o["provider"] in emits]
            offers.extend(carried)
            statuses.append({"source": source.name, "ok": True,
                             "offers": len(carried), "carried": True})
            continue
        try:
            fetched = source.fetch(observed_at)
            offers.extend(fetched)
            # Zero offers is a silent failure, not a success — a scraper that
            # returns nothing is broken or the source changed shape.
            status = {"source": source.name, "ok": len(fetched) > 0, "offers": len(fetched)}
            if not fetched:
                status["error"] = "fetch succeeded but produced 0 offers"
            statuses.append(status)
        except Exception as exc:  # noqa: BLE001 — a source may fail any way it likes
            statuses.append({"source": source.name, "ok": False, "error": f"{type(exc).__name__}: {exc}"})
    return offers, statuses


def run(date, use_fixtures, force_all=False):
    now = dt.datetime.now(dt.timezone.utc)
    observed_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    base = data_root(use_fixtures)
    offers_dir = base / "offers"
    changelog_path = base / "changelog.json"

    prev_path = previous_snapshot(offers_dir, date)
    prev_offers = _load(prev_path) if prev_path else []
    # Carry pool for slow-cadence sources: today's snapshot if one exists
    # (keeps this morning's fetch), else the previous day's.
    today_path = offers_dir / f"{date}.json"
    carry_pool = _load(today_path) if today_path.exists() else prev_offers

    raw, statuses = gather(date, use_fixtures, observed_at, carry_pool, force_all)
    schema = _load(SCHEMA_PATH)
    valid, rejected, quarantined = split_offers(raw, {o["id"]: o for o in prev_offers}, schema)

    ok_sources = [s for s in statuses if s["ok"]]
    health = {
        "date": date, "observed_at": observed_at, "sources": statuses,
        "valid": len(valid), "rejected": len(rejected), "quarantined": len(quarantined),
        "healthy": bool(ok_sources) and not rejected and len(ok_sources) == len(statuses),
    }
    (base).mkdir(parents=True, exist_ok=True)
    (base / "health.json").write_text(json.dumps(health, indent=2) + "\n")

    for s in statuses:
        mark = "ok " if s["ok"] else "FAIL"
        detail = f"{s.get('offers', 0)} offers" if s["ok"] else s["error"]
        if s.get("carried"):
            detail += " (carried)"
        print(f"  source {s['source']}: {mark} {detail}")

    if not ok_sources or not valid:
        print("nothing publishable — leaving previous data in place", file=sys.stderr)
        return 1

    offers_dir.mkdir(parents=True, exist_ok=True)
    (offers_dir / f"{date}.json").write_text(json.dumps(valid, indent=2) + "\n")

    if quarantined:
        qdir = base / "quarantine"
        qdir.mkdir(parents=True, exist_ok=True)
        (qdir / f"{date}.json").write_text(json.dumps(quarantined, indent=2) + "\n")

    entries = diff_snapshots(prev_offers, valid, date) if prev_offers else []
    changelog = append_changelog(changelog_path, entries) if entries else (
        json.loads(changelog_path.read_text()) if changelog_path.exists() else []
    )

    index = build_site(valid, changelog, date)

    print(f"snapshot offers/{date}.json: valid={len(valid)} rejected={len(rejected)} "
          f"quarantined={len(quarantined)}")
    print(f"changelog entries today: {len(entries)}  (total {len(changelog)})")
    print(f"site built: {index.relative_to(ROOT)}")
    for r in rejected:
        print(f"  REJECT {r['offer'].get('id', '<no id>')}: {'; '.join(r['errors'])}", file=sys.stderr)
    return 0


def check_health(use_fixtures):
    path = data_root(use_fixtures) / "health.json"
    if not path.exists():
        print("no health.json — refresh has not run", file=sys.stderr)
        return 1
    health = json.loads(path.read_text())
    if health.get("healthy"):
        print("health: ok")
        return 0
    print(f"health: DEGRADED {json.dumps(health['sources'])}", file=sys.stderr)
    return 1


def main():
    ap = argparse.ArgumentParser(description="Run one full refresh")
    # UTC everywhere: observed_at is UTC, CI runs in UTC, and a local run must
    # not write a snapshot under yesterday's local date.
    ap.add_argument("--date", default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    ap.add_argument("--fixtures", action="store_true", help="use fixture sources (writes under data/dev/)")
    ap.add_argument("--all-sources", action="store_true", help="fetch every source regardless of cadence")
    ap.add_argument("--check-health", action="store_true", help="exit nonzero if last run was degraded")
    args = ap.parse_args()
    if args.check_health:
        sys.exit(check_health(args.fixtures))
    sys.exit(run(args.date, args.fixtures, args.all_sources))


if __name__ == "__main__":
    main()
