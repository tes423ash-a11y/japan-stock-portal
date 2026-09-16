from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from validate_market_freshness import validate_market_freshness


def report(jp_pct=98.3, us_pct=95.0, us_dominant="2026-09-15"):
    return {
        "marketSummary": {
            "JP": {
                "expectedSession": "2026-09-15",
                "dominantDate": "2026-09-15",
                "freshCoveragePct": jp_pct,
            },
            "US": {
                "expectedSession": "2026-09-15",
                "dominantDate": us_dominant,
                "freshCoveragePct": us_pct,
            },
        }
    }


class FreshnessValidationTests(unittest.TestCase):
    def test_accepts_both_markets_when_current(self):
        result = validate_market_freshness(report())
        self.assertEqual(result["US"]["freshCoveragePct"], 95.0)

    def test_rejects_high_total_coverage_with_stale_us_market(self):
        with self.assertRaisesRegex(ValueError, "US: expected=2026-09-15"):
            validate_market_freshness(report(us_pct=2.7, us_dominant="2026-09-14"))

    def test_rejects_missing_freshness_metadata(self):
        with self.assertRaisesRegex(ValueError, "US: freshness metadata missing"):
            validate_market_freshness({"marketSummary": {"JP": report()["marketSummary"]["JP"]}})


if __name__ == "__main__":
    unittest.main()
