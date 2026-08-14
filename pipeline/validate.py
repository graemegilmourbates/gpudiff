"""Validation gates. Missing beats wrong: bad offers are dropped and reported,
never published. Price moves beyond DELTA_LIMIT vs the previous snapshot are
quarantined for human review."""

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "offer.schema.json"
DELTA_LIMIT = 0.40  # fractional price move that triggers quarantine


def _load(path):
    with open(path) as f:
        return json.load(f)


def check_offer(offer, schema):
    """Validate one offer against the schema subset we use. Returns list of errors."""
    errors = []
    props = schema["properties"]
    for field in schema["required"]:
        if field not in offer:
            errors.append(f"missing required field: {field}")
    if errors:
        return errors

    if not isinstance(offer["price"], (int, float)) or isinstance(offer["price"], bool):
        errors.append("price must be a number")
    elif not (0 < offer["price"] <= props["price"]["maximum"]):
        errors.append(f"price out of range: {offer['price']}")

    if offer["unit"] not in props["unit"]["enum"]:
        errors.append(f"unknown unit: {offer['unit']}")
    if offer["pricing_type"] not in props["pricing_type"]["enum"]:
        errors.append(f"unknown pricing_type: {offer['pricing_type']}")
    if not re.match(props["id"]["pattern"], offer["id"]):
        errors.append(f"malformed id: {offer['id']}")
    if not isinstance(offer["fixture"], bool):
        errors.append("fixture must be boolean")

    prov = offer.get("provenance")
    if not isinstance(prov, dict):
        errors.append("provenance must be an object")
    else:
        if not re.match(r"^https?://", str(prov.get("url", ""))):
            errors.append("provenance.url must be an http(s) URL")
        if not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", str(prov.get("observed_at", ""))):
            errors.append("provenance.observed_at must be ISO-8601")
    return errors


def split_offers(offers, previous_by_id, schema):
    """Partition offers into (valid, rejected, quarantined)."""
    valid, rejected, quarantined = [], [], []
    for offer in offers:
        errors = check_offer(offer, schema)
        if errors:
            rejected.append({"offer": offer, "errors": errors})
            continue
        prev = previous_by_id.get(offer["id"])
        if prev and prev["price"] > 0:
            delta = abs(offer["price"] - prev["price"]) / prev["price"]
            if delta > DELTA_LIMIT:
                quarantined.append({
                    "offer": offer,
                    "previous_price": prev["price"],
                    "delta_pct": round(delta * 100, 1),
                    "reason": f"price moved {round(delta * 100, 1)}% (> {int(DELTA_LIMIT * 100)}% limit)",
                })
                continue
        valid.append(offer)
    return valid, rejected, quarantined


def validate_snapshot(snapshot_path, previous_path=None):
    schema = _load(SCHEMA_PATH)
    offers = _load(snapshot_path)
    previous_by_id = {}
    if previous_path and Path(previous_path).exists():
        previous_by_id = {o["id"]: o for o in _load(previous_path)}
    return split_offers(offers, previous_by_id, schema)


def main():
    ap = argparse.ArgumentParser(description="Validate an offers snapshot")
    ap.add_argument("snapshot")
    ap.add_argument("--previous", default=None)
    args = ap.parse_args()

    valid, rejected, quarantined = validate_snapshot(args.snapshot, args.previous)
    print(f"valid={len(valid)} rejected={len(rejected)} quarantined={len(quarantined)}")
    for r in rejected:
        print(f"  REJECT {r['offer'].get('id', '<no id>')}: {'; '.join(r['errors'])}", file=sys.stderr)
    for q in quarantined:
        print(f"  QUARANTINE {q['offer']['id']}: {q['reason']}", file=sys.stderr)
    sys.exit(1 if rejected else 0)


if __name__ == "__main__":
    main()
