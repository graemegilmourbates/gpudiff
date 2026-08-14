import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.diffgen import diff_snapshots


def offer(oid, price, provider="examplecloud", sku="gx-100-80gb"):
    return {"id": oid, "provider": provider, "sku": sku, "price": price, "unit": "usd_per_hour"}


class TestDiff(unittest.TestCase):
    def test_price_change_detected_with_pct(self):
        entries = diff_snapshots([offer("a:b:c:d", 2.00)], [offer("a:b:c:d", 1.80)], "2026-08-14")
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e["kind"], "price_change")
        self.assertEqual(e["pct"], -10.0)
        self.assertIn("cut", e["summary"])

    def test_added_and_removed(self):
        entries = diff_snapshots(
            [offer("old:x:r:t", 1.0)],
            [offer("new:y:r:t", 2.0, provider="samplecompute")],
            "2026-08-14",
        )
        kinds = sorted(e["kind"] for e in entries)
        self.assertEqual(kinds, ["added", "removed"])

    def test_no_change_no_entries(self):
        entries = diff_snapshots([offer("a:b:c:d", 2.0)], [offer("a:b:c:d", 2.0)], "2026-08-14")
        self.assertEqual(entries, [])


if __name__ == "__main__":
    unittest.main()
