"""Diff engine: two snapshots in, changelog entries out. The diff IS the
product — the site table is just the latest snapshot rendered."""

import json
from pathlib import Path


def diff_snapshots(prev_offers, curr_offers, date):
    prev = {o["id"]: o for o in prev_offers}
    curr = {o["id"]: o for o in curr_offers}
    # A provider arriving or disappearing wholesale is our plumbing, not the
    # market: onboarding a source must not publish thousands of "added" rows,
    # and a source outage must never publish phantom delistings.
    prev_providers = {o["provider"] for o in prev_offers}
    curr_providers = {o["provider"] for o in curr_offers}
    entries = []

    for oid in sorted(curr.keys() - prev.keys()):
        o = curr[oid]
        if o["provider"] not in prev_providers:
            continue
        entries.append({
            "date": date, "kind": "added", "id": oid,
            "provider": o["provider"], "sku": o["sku"],
            "price": o["price"], "unit": o["unit"],
            "summary": f"{o['provider']} listed {o['sku']} at {o['price']} {o['unit']}",
        })

    for oid in sorted(prev.keys() - curr.keys()):
        o = prev[oid]
        if o["provider"] not in curr_providers:
            continue
        entries.append({
            "date": date, "kind": "removed", "id": oid,
            "provider": o["provider"], "sku": o["sku"],
            "summary": f"{o['provider']} delisted {o['sku']}",
        })

    for oid in sorted(curr.keys() & prev.keys()):
        old, new = prev[oid]["price"], curr[oid]["price"]
        if old != new:
            pct = round((new - old) / old * 100, 1)
            direction = "cut" if new < old else "raised"
            entries.append({
                "date": date, "kind": "price_change", "id": oid,
                "provider": curr[oid]["provider"], "sku": curr[oid]["sku"],
                "old_price": old, "new_price": new, "pct": pct,
                "summary": (f"{curr[oid]['provider']} {direction} {curr[oid]['sku']} "
                            f"{abs(pct)}%: {old} → {new} {curr[oid]['unit']}"),
            })
    return entries


CATALOG_LABEL = {"ramp": "Ramp Router"}


def diff_catalog(prev_items, curr_items, date):
    """Availability diffs: what a gateway started or stopped carrying. Same
    entry shape as price diffs so the changelog, feeds, and pages need no
    special cases."""
    prev = {(i["provider"], i["item"]) for i in prev_items}
    curr = {(i["provider"], i["item"]) for i in curr_items}
    prev_providers = {p for p, _ in prev}
    curr_providers = {p for p, _ in curr}
    entries = []
    for kind, verb, delta in (("added", "added", curr - prev), ("removed", "dropped", prev - curr)):
        for provider, item in sorted(delta):
            # Same rule as prices: a gateway appearing or vanishing is plumbing.
            if provider not in (prev_providers if kind == "added" else curr_providers):
                continue
            label = CATALOG_LABEL.get(provider, provider)
            entries.append({
                "date": date, "kind": kind, "id": f"{provider}:{item}:global:catalog",
                "provider": provider, "sku": item,
                "summary": f"{label} {verb} {item}",
            })
    return entries


def append_changelog(changelog_path, entries):
    path = Path(changelog_path)
    existing = json.loads(path.read_text()) if path.exists() else []
    # A rerun for the same date replaces that date's entries instead of duplicating.
    dates = {e["date"] for e in entries}
    existing = [e for e in existing if e["date"] not in dates]
    merged = existing + entries
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, indent=2) + "\n")
    return merged
