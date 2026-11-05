from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from semcrys.recursive_metalegend import build, inspect, restore, verify
from streaming_app.core import Refusal
from streaming_legend.core import file_sha256, write_legend


class RecursiveMetalegendTests(unittest.TestCase):
    def fixture(self, directory: Path) -> Path:
        values = [
            b"constitutional-archive-alpha",
            b"constitutional-archive-beta",
            b"constitutional-archive-gamma",
            b"constitutional-memory-alpha",
            b"constitutional-memory-beta",
            b"semantic-archive-alpha",
            b"semantic-archive-beta",
        ]
        path = directory / "fixture.leg"
        write_legend(path, values, entry_count=len(values), legend_id="TEST-RECURSIVE",
                     unit_mode="TOKEN", index_stride=3)
        return path

    def test_exact_inverse_and_full_verification(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            legend = self.fixture(directory)
            expected = legend.read_bytes()
            meta = directory / "fixture.mleg"
            built = build(legend, meta, block_entries=16, candidate_presets=(0, 6),
                          require_smaller=False)
            self.assertEqual(built["status"], "PASS")
            self.assertEqual(inspect(meta)["configuration"]["recursion_depth"], 1)
            restored = directory / "restored.leg"
            receipt = restore(meta, restored)
            self.assertTrue(receipt["exact_original_legend"])
            self.assertEqual(restored.read_bytes(), expected)
            self.assertEqual(file_sha256(restored), file_sha256(legend))
            self.assertTrue(verify(meta)["verified_without_retained_original_legend"])

    def test_corruption_is_refused(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            legend = self.fixture(directory)
            meta = directory / "fixture.mleg"
            build(legend, meta, block_entries=16, candidate_presets=(0,),
                  require_smaller=False)
            damaged = bytearray(meta.read_bytes())
            damaged[-1] ^= 1
            meta.write_bytes(damaged)
            with self.assertRaises(Refusal):
                inspect(meta)

    def test_recursive_nesting_is_refused(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            legend = self.fixture(directory)
            first = directory / "first.mleg"
            build(legend, first, block_entries=16, candidate_presets=(0,),
                  require_smaller=False)
            with self.assertRaises(Refusal):
                build(first, directory / "second.mleg", block_entries=16,
                      candidate_presets=(0,), require_smaller=False)

    def test_unprofitable_default_is_refused_without_output(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            legend = self.fixture(directory)
            output = directory / "expanded.mleg"
            with self.assertRaises(Refusal):
                build(legend, output, block_entries=16, candidate_presets=(0,))
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
