from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from semcrys.seekable_metalegend import (
    MAGIC,
    SeekableMetalegendReader,
    build,
    inspect,
    restore,
    verify,
)
from streaming_app.core import Refusal
from streaming_legend.core import LegendReader, file_sha256, write_legend


class SeekableMetalegendTests(unittest.TestCase):
    def fixture(self, directory: Path, count: int = 145) -> Path:
        values = [f"constitutional-memory-{index // 9:04d}-{index:06d}".encode()
                  for index in range(count)]
        path = directory / "fixture.leg"
        write_legend(path, values, entry_count=len(values), legend_id="TEST-SEEKABLE",
                     unit_mode="TOKEN", index_stride=8)
        return path

    def test_exact_inverse_direct_lookup_and_full_verification(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            legend = self.fixture(directory)
            expected = LegendReader(legend)
            meta = directory / "fixture.mleg"
            built = build(legend, meta, block_entries=16, frame_blocks=2,
                          candidate_presets=(0, 1), require_smaller=False)
            self.assertEqual(built["status"], "PASS")
            self.assertEqual(meta.read_bytes()[:len(MAGIC)], MAGIC)
            view = inspect(meta)
            self.assertGreater(view["configuration"]["data_frames"], 1)
            reader = SeekableMetalegendReader(meta)
            for identifier in (1, 16, 17, 32, 33, expected.count):
                self.assertEqual(reader.get(identifier), expected.get(identifier))
            restored = directory / "restored.leg"
            self.assertTrue(restore(meta, restored)["exact_original_legend"])
            self.assertEqual(restored.read_bytes(), legend.read_bytes())
            self.assertEqual(file_sha256(restored), file_sha256(legend))
            self.assertEqual(verify(meta)["frames_verified"],
                             view["configuration"]["frame_count"])

    def test_root_verified_frame_and_full_cache(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            legend = self.fixture(directory)
            meta = directory / "fixture.mleg"
            build(legend, meta, block_entries=16, frame_blocks=2,
                  candidate_presets=(0,), require_smaller=False)
            cache = directory / "cache"
            first = SeekableMetalegendReader(meta, cache_root=cache)
            self.assertEqual(first.get(1), LegendReader(legend).get(1))
            self.assertEqual(first.receipt()["cache"]["stats"]["frame_writes"], 1)
            second = SeekableMetalegendReader(meta, cache_root=cache)
            self.assertEqual(second.get(2), LegendReader(legend).get(2))
            self.assertEqual(second.receipt()["cache"]["stats"]["frame_hits"], 1)
            full = second.prepare_full_cache()
            self.assertEqual(file_sha256(full), file_sha256(legend))
            third = SeekableMetalegendReader(meta, cache_root=cache)
            self.assertTrue(third.receipt()["full_legend_ready"])
            self.assertEqual(third.get(77), LegendReader(legend).get(77))
            self.assertEqual(third.receipt()["stats"]["full_legend_hits"], 1)
            full.write_bytes(b"corrupt")
            repaired = SeekableMetalegendReader(meta, cache_root=cache)
            repaired_path = repaired.prepare_full_cache()
            self.assertEqual(file_sha256(repaired_path), file_sha256(legend))

    def test_targeted_frame_corruption_is_refused(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            legend = self.fixture(directory)
            meta = directory / "fixture.mleg"
            build(legend, meta, block_entries=16, frame_blocks=2,
                  candidate_presets=(0,), require_smaller=False)
            raw = bytearray(meta.read_bytes())
            _, header_size = __import__("struct").Struct(">8sI").unpack(raw[:12])
            header = json.loads(raw[12:12 + header_size])
            row = header["directory"][1]
            raw[12 + header_size + row["offset"]] ^= 1
            meta.write_bytes(raw)
            with self.assertRaises(Refusal):
                SeekableMetalegendReader(meta).get(1)
            with self.assertRaises(Refusal):
                inspect(meta)

    def test_nesting_and_unprofitable_admission_are_refused(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            legend = self.fixture(directory, count=7)
            first = directory / "first.mleg"
            build(legend, first, block_entries=16, frame_blocks=1,
                  candidate_presets=(0,), require_smaller=False)
            with self.assertRaises(Refusal):
                build(first, directory / "nested.mleg", block_entries=16,
                      frame_blocks=1, candidate_presets=(0,), require_smaller=False)
            refused = directory / "refused.mleg"
            with self.assertRaises(Refusal):
                build(legend, refused, block_entries=16, frame_blocks=1,
                      candidate_presets=(0,), require_smaller=True)
            self.assertFalse(refused.exists())

    def test_canonical_metalegend_facade_defaults_seekable_and_group_aliases_remain(self):
        from semcrys import group_legend, metalegend
        from semcrys import meta_auxiliary, meta_bundle
        from semcrys import group_auxiliary, group_bundle

        self.assertEqual(group_legend.SCHEMA, "semcrys.metalegend-instance.v0.1")
        self.assertIs(meta_auxiliary.contract, group_auxiliary.contract)
        self.assertIs(meta_bundle.wrap, group_bundle.wrap)
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            legend = self.fixture(directory)
            output = directory / "default.mleg"
            metalegend.build(legend, output, block_entries=16, frame_blocks=2,
                             candidate_presets=(0,), require_smaller=False)
            self.assertEqual(output.read_bytes()[:len(MAGIC)], MAGIC)
            self.assertEqual(metalegend.inspect(output)["configuration"]["profile"],
                             "SEEKABLE_PREFIX_SUPERFRAMES_V1")


if __name__ == "__main__":
    unittest.main()
