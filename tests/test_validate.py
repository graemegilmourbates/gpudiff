import json
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.validate import SCHEMA_PATH, check_offer, split_offers


def good_offer(**over):
    offer = {
        "id": "examplecloud:gx-100-80gb:us-east:on_demand",
        "provider": "examplecloud",
        "sku": "gx-100-80gb",
        "price": 2.49,
        "unit": "usd_per_hour",
        "pricing_type": "on_demand",
        "region": "us-east",
        "provenance": {"url": "https://fixtures.invalid/p", "observed_at": "2026-08-14T00:00:00Z"},
        "fixture": True,
    }
    offer.update(over)
    return offer


class TestValidate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text())

    def test_good_offer_passes(self):
        self.assertEqual(check_offer(good_offer(), self.schema), [])

    def test_zero_and_negative_price_rejected(self):
        self.assertTrue(check_offer(good_offer(price=0), self.schema))
        self.assertTrue(check_offer(good_offer(price=-1.5), self.schema))

    def test_missing_provenance_rejected(self):
        offer = good_offer()
        del offer["provenance"]
        self.assertTrue(check_offer(offer, self.schema))

    def test_non_url_provenance_rejected(self):
        offer = good_offer(provenance={"url": "ftp://x", "observed_at": "2026-08-14T00:00:00Z"})
        self.assertTrue(check_offer(offer, self.schema))

    def test_big_move_quarantined_not_published(self):
        prev = {good_offer()["id"]: good_offer(price=2.00)}
        valid, rejected, quarantined = split_offers([good_offer(price=3.00)], prev, self.schema)
        self.assertEqual(len(valid), 0)
        self.assertEqual(len(rejected), 0)
        self.assertEqual(len(quarantined), 1)
        self.assertEqual(quarantined[0]["delta_pct"], 50.0)

    def test_small_move_passes(self):
        prev = {good_offer()["id"]: good_offer(price=2.00)}
        valid, rejected, quarantined = split_offers([good_offer(price=2.30)], prev, self.schema)
        self.assertEqual(len(valid), 1)
        self.assertEqual(len(quarantined), 0)


if __name__ == "__main__":
    unittest.main()
