import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.diffgen import diff_catalog, diff_snapshots


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
        # Same provider on both sides: a listing genuinely came and another went.
        entries = diff_snapshots(
            [offer("old:x:r:t", 1.0), offer("keep:k:r:t", 5.0)],
            [offer("new:y:r:t", 2.0), offer("keep:k:r:t", 5.0)],
            "2026-08-14",
        )
        kinds = sorted(e["kind"] for e in entries)
        self.assertEqual(kinds, ["added", "removed"])

    def test_no_change_no_entries(self):
        entries = diff_snapshots([offer("a:b:c:d", 2.0)], [offer("a:b:c:d", 2.0)], "2026-08-14")
        self.assertEqual(entries, [])

    def test_new_provider_onboarding_is_not_news(self):
        prev = [offer("old:x:r:t", 1.0)]
        curr = prev + [offer("new:y:r:t", 2.0, provider="glama"),
                       offer("new:z:r:t", 3.0, provider="glama")]
        self.assertEqual(diff_snapshots(prev, curr, "2026-08-18"), [])

    def test_source_outage_never_publishes_delistings(self):
        prev = [offer("a:b:c:d", 1.0), offer("g:h:i:j", 2.0, provider="glama")]
        curr = [offer("a:b:c:d", 1.0)]  # glama failed this run
        self.assertEqual(diff_snapshots(prev, curr, "2026-08-18"), [])

    def test_known_provider_still_diffs_items(self):
        prev = [offer("a:b:c:d", 1.0), offer("a:gone:c:d", 2.0)]
        curr = [offer("a:b:c:d", 1.0), offer("a:fresh:c:d", 3.0)]
        kinds = sorted(e["kind"] for e in diff_snapshots(prev, curr, "2026-08-18"))
        self.assertEqual(kinds, ["added", "removed"])


class TestCatalogDiff(unittest.TestCase):
    def item(self, provider, name):
        return {"provider": provider, "item": name}

    def test_added_and_dropped(self):
        prev = [self.item("ramp", "kimi-k3"), self.item("ramp", "gpt-5.4")]
        curr = [self.item("ramp", "kimi-k3"), self.item("ramp", "claude-opus-5")]
        entries = diff_catalog(prev, curr, "2026-08-18")
        summaries = sorted(e["summary"] for e in entries)
        self.assertEqual(summaries, ["Ramp Router added claude-opus-5",
                                     "Ramp Router dropped gpt-5.4"])

    def test_new_gateway_is_not_news(self):
        prev = [self.item("ramp", "kimi-k3")]
        curr = prev + [self.item("othergw", "kimi-k3")]
        self.assertEqual(diff_catalog(prev, curr, "2026-08-18"), [])


if __name__ == "__main__":
    unittest.main()
