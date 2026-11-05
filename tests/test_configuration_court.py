from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from semcrys.artifacts import build_legend
from semcrys.configuration_court import load, run
from semcrys.configuration_selection import build_library


class ConfigurationCourt(unittest.TestCase):
    def test_multi_objective_cold_and_warm_adjudication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calibration = root / "calibration.txt"
            source = root / "source.txt"
            legend = root / "shared.leg"
            library = root / "library.json"
            output = root / "court.json"
            calibration.write_text("alpha beta gamma " * 128, encoding="utf-8")
            source.write_text("alpha beta delta " * 96, encoding="utf-8")
            built = build_legend(calibration, legend, policy="TOTAL")
            build_library(library, [("TEST", "DOMAIN", 0, legend)])
            result = run(
                source,
                output,
                library_path=library,
                legends=[legend],
                semcrys_codecs=("NONE", "LZMA"),
                control_codecs=("RAW", "BZ2_9", "LZMA2_XZ_6"),
                horizons=(1, 4),
                receiver_roots=[built["output_sha256"]],
                qualification_label="UNIT_TEST",
            )
            self.assertEqual(result["status"], "PASS")
            court = load(output)
            self.assertEqual(len(court["scenarios"]), 4)
            warm = next(row for row in court["scenarios"] if row["accounting"] == "WARM" and row["reuse_horizon"] == 1)
            full = warm["winners"]["MIN_FULL_INTEGERIZATION_DELIVERY"]
            self.assertIsNotNone(full)
            self.assertIn("FULL_INTEGERIZATION", full["capabilities"])
            self.assertEqual(full["acquisition_bytes"], 0)
            complete = warm["winners"]["MIN_COMPLETE_DELIVERY"]
            self.assertIn(complete["family"], {"NATURAL_CONTROL", "SEMCRYS"})


if __name__ == "__main__":
    unittest.main()
