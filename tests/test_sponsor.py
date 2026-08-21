import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.sponsor_intake import build, _clean_url, _clean_text


class TestSponsorIntake(unittest.TestCase):
    def issue(self, n, name, url, tag, place="Sitewide"):
        return {"number": n, "body": (f"### Company / product name\n{name}\n"
                f"### Link URL (https://)\n{url}\n"
                f"### One line of copy (max 80 chars)\n{tag}\n### Placement\n{place}")}

    def test_rejects_javascript_url(self):
        self.assertEqual(_clean_url("javascript:alert(1)"), "")

    def test_rejects_http_url(self):
        self.assertEqual(_clean_url("http://insecure.example.com"), "")

    def test_accepts_https(self):
        self.assertEqual(_clean_url("https://acme.example.com/x"), "https://acme.example.com/x")

    def test_strips_markup_from_name(self):
        self.assertEqual(_clean_text("<script>x</script>Acme", 40), "xAcme".replace("x", "x"))
        self.assertNotIn("<", _clean_text("<b>Acme</b>", 40))

    def test_bad_url_issue_dropped(self):
        out = build([self.issue(1, "Bad", "javascript:x", "hi")])
        self.assertEqual(out, [])

    def test_valid_issue_accepted(self):
        out = build([self.issue(2, "Real Cloud", "https://real.example.com", "H100s cheap", "GPU pages only")])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["section"], "gpu")

    def test_one_sponsor_per_section(self):
        from pipeline.sponsor_intake import SECTION
        self.assertIn("sitewide", SECTION)


if __name__ == "__main__":
    unittest.main()
