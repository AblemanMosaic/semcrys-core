from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from semcrys.artifacts import build_legend
from streaming_app.legend_context import VerifiedLegendContext


class PersistentLookupCache(unittest.TestCase):
    def test_verified_cache_is_reused_and_corruption_rebuilds(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            source = root / "source.txt"
            legend = root / "shared.leg"
            cache = root / "cache"
            source.write_text("alpha beta gamma " * 512, encoding="utf-8")
            build_legend(source, legend, policy="TOTAL")

            with VerifiedLegendContext(lookup_backend="AUTO", persistent_lookup_cache=cache) as context:
                first = context.prepare(legend)
                first_receipt = context.receipt()
                expected_database_root = first["database_sha256"]
            self.assertEqual(first_receipt["stats"]["lookup_builds"], 1)
            self.assertEqual(first_receipt["stats"]["persistent_lookup_misses"], 1)

            with VerifiedLegendContext(lookup_backend="AUTO", persistent_lookup_cache=cache) as context:
                second = context.prepare(legend)
                second_receipt = context.receipt()
            self.assertEqual(second["database_sha256"], expected_database_root)
            self.assertEqual(second_receipt["stats"]["lookup_builds"], 0)
            self.assertEqual(second_receipt["stats"]["persistent_lookup_hits"], 1)

            database = next(cache.rglob("*.sqlite3"))
            data = bytearray(database.read_bytes())
            data[len(data) // 2] ^= 1
            database.write_bytes(data)
            with VerifiedLegendContext(lookup_backend="AUTO", persistent_lookup_cache=cache) as context:
                rebuilt = context.prepare(legend)
                rebuilt_receipt = context.receipt()
            self.assertEqual(rebuilt["database_sha256"], expected_database_root)
            self.assertEqual(rebuilt_receipt["stats"]["lookup_builds"], 1)
            self.assertEqual(rebuilt_receipt["stats"]["persistent_lookup_misses"], 1)


if __name__ == "__main__":
    unittest.main()
