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


class TestRampParsing(unittest.TestCase):
    def test_naming_normalized_into_shared_namespace(self):
        from sources.ramp import normalize
        self.assertEqual(normalize("kimi-k2p6"), "kimi-k2.6")
        self.assertEqual(normalize("glm-5p2"), "glm-5.2")
        self.assertEqual(normalize("opus-5"), "claude-opus-5")
        self.assertEqual(normalize("fable-5"), "claude-fable-5")
        self.assertEqual(normalize("gpt-5.6-sol"), "gpt-5.6-sol")


if __name__ == "__main__":
    unittest.main()
