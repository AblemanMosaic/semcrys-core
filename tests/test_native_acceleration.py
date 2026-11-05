from __future__ import annotations

import os
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from semcrys_core.contract import capabilities
from semcrys_lite.core import (
    _apply_assembly_legend_python,
    _pack_varints,
    _pack_varints_python,
    _unpack_varints,
    _unpack_varints_python,
    apply_assembly_legend,
)
from semcrys_native import parse_packed_events, reset_metrics, runtime_status
from streaming_app.core import (
    Refusal,
    _encode_token_body,
    _parse_packed_events_python,
    _pack_varint_batch,
    _pack_varint_batch_python,
)


def require_native(test_case: unittest.TestCase) -> None:
    status = runtime_status()
    if not status["available"]:
        test_case.skipTest(f"optional native kernel unavailable: {status['reason']}")


class NativeContract(unittest.TestCase):
    def test_capability_contract_is_realization_independent(self):
        contract = capabilities()["native_acceleration"]
        self.assertEqual(contract["abi"], "SEMCRYS_NATIVE_BUFFER_ABI_2")
        self.assertTrue(contract["pure_python_fallback"])
        self.assertTrue(contract["container_bytes_invariant"])

    def test_hash_bound_kernel_is_available_on_build_host(self):
        require_native(self)
        status = runtime_status()
        self.assertTrue(status["available"], status)
        self.assertEqual(status["abi_version"], 2)
        self.assertEqual(len(status["binary_sha256"]), 64)
        self.assertEqual(len(status["build_root"]), 64)


class DifferentialVarints(unittest.TestCase):
    def setUp(self):
        reset_metrics()
        self.values = [0, 1, 127, 128, 16383, 16384, (1 << 32) - 1, (1 << 63) - 1]
        randomizer = random.Random(20261101)
        self.values.extend(randomizer.randrange(0, 1 << 48) for _ in range(10000))

    def test_native_pack_is_byte_identical(self):
        require_native(self)
        with mock.patch.dict(os.environ, {"SEMCRYS_NATIVE": "auto", "SEMCRYS_NATIVE_THRESHOLD": "1"}):
            observed = _pack_varints(self.values)
            status = runtime_status()
        self.assertEqual(observed, _pack_varints_python(self.values))
        self.assertEqual(status["metrics"]["pack_calls"], 1)

    def test_native_unpack_is_event_identical(self):
        require_native(self)
        packed = _pack_varints_python(self.values)
        with mock.patch.dict(os.environ, {"SEMCRYS_NATIVE": "auto", "SEMCRYS_NATIVE_THRESHOLD": "1"}):
            observed = _unpack_varints(packed)
            status = runtime_status()
        self.assertEqual(observed, _unpack_varints_python(packed))
        self.assertEqual(status["metrics"]["unpack_calls"], 1)

    def test_native_packed_parser_is_event_identical(self):
        require_native(self)
        data = _pack_varint_batch_python([1, 2, 127]) + b"\x00\x05hello" + _pack_varint_batch_python([128, 3])
        expected = _parse_packed_events_python(data)
        with mock.patch.dict(os.environ, {"SEMCRYS_NATIVE": "auto", "SEMCRYS_NATIVE_THRESHOLD": "1"}):
            observed = parse_packed_events(data, _parse_packed_events_python)
            status = runtime_status()
        self.assertEqual(list(observed[0]), list(expected[0]))
        self.assertEqual(list(observed[1]), list(expected[1]))
        self.assertEqual(status["metrics"]["parse_calls"], 1)
        self.assertEqual(status["metrics"]["parse_events"], 6)

    def test_native_packed_parser_preserves_malformed_refusal(self):
        require_native(self)
        with mock.patch.dict(os.environ, {"SEMCRYS_NATIVE": "auto", "SEMCRYS_NATIVE_THRESHOLD": "1"}):
            with self.assertRaisesRegex(Refusal, "HELD_NONCANONICAL_VARINT"):
                parse_packed_events(b"\x80\x00", _parse_packed_events_python)
            with self.assertRaisesRegex(Refusal, "HELD_TRUNCATED_LITERAL"):
                parse_packed_events(b"\x00\x05abc", _parse_packed_events_python)

    def test_off_policy_uses_reference_path(self):
        with mock.patch.dict(os.environ, {"SEMCRYS_NATIVE": "off", "SEMCRYS_NATIVE_THRESHOLD": "1"}):
            self.assertEqual(_pack_varints(self.values), _pack_varints_python(self.values))
            self.assertFalse(runtime_status()["selected"])

    def test_malformed_inputs_preserve_python_refusals(self):
        with mock.patch.dict(os.environ, {"SEMCRYS_NATIVE": "auto", "SEMCRYS_NATIVE_THRESHOLD": "1"}):
            with self.assertRaisesRegex(RuntimeError, "HELD_BODY_VARINT_OVERLONG"):
                _unpack_varints(b"\x80" * 200)
            with self.assertRaisesRegex(RuntimeError, "HELD_BODY_VARINT_RANGE"):
                _pack_varints([-1] * 200)

    def test_unknown_policy_and_threshold_refuse(self):
        with mock.patch.dict(os.environ, {"SEMCRYS_NATIVE": "mystery", "SEMCRYS_NATIVE_THRESHOLD": "1"}):
            with self.assertRaisesRegex(RuntimeError, "HELD_NATIVE_POLICY"):
                _pack_varints(self.values)

    def test_full_compiler_batch_is_byte_identical(self):
        require_native(self)
        values = self.values * 2
        with mock.patch.dict(os.environ, {"SEMCRYS_NATIVE": "auto", "SEMCRYS_NATIVE_THRESHOLD": "1"}):
            observed = _pack_varint_batch(values)
            status = runtime_status()
        self.assertEqual(observed, _pack_varint_batch_python(values))
        self.assertGreaterEqual(status["metrics"]["pack_calls"], 1)

    def test_full_compiler_short_runs_do_not_cross_native_boundary(self):
        reset_metrics()
        values = [1, 2, 127, 128] * 100
        with mock.patch.dict(os.environ, {"SEMCRYS_NATIVE": "auto", "SEMCRYS_NATIVE_THRESHOLD": "1"}):
            observed = _pack_varint_batch(values)
            status = runtime_status()
        self.assertEqual(observed, _pack_varint_batch_python(values))
        self.assertEqual(status["metrics"]["pack_calls"], 0)
        self.assertEqual(status["metrics"]["fallback_calls"], 0)

    def test_full_token_body_is_identical_with_native_disabled(self):
        require_native(self)
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            source = root / "source.txt"
            source.write_text("alpha beta " * 5000, encoding="utf-8")
            lookup = sqlite3.connect(root / "lookup.sqlite3")
            lookup.execute("CREATE TABLE lookup(value BLOB PRIMARY KEY, id INTEGER NOT NULL) WITHOUT ROWID")
            lookup.executemany(
                "INSERT INTO lookup(value,id) VALUES (?,?)",
                ((b"alpha", 1), (b"beta", 2), (b" ", 3)),
            )
            lookup.commit()
            reference = root / "reference.body"
            accelerated = root / "accelerated.body"
            with mock.patch.dict(os.environ, {"SEMCRYS_NATIVE": "off", "SEMCRYS_NATIVE_THRESHOLD": "1"}):
                expected_stats = _encode_token_body(source, reference, lookup, max_unit_bytes=4096)
            reset_metrics()
            with mock.patch.dict(os.environ, {"SEMCRYS_NATIVE": "auto", "SEMCRYS_NATIVE_THRESHOLD": "1"}):
                observed_stats = _encode_token_body(source, accelerated, lookup, max_unit_bytes=4096)
                status = runtime_status()
            lookup.close()
            self.assertEqual(accelerated.read_bytes(), reference.read_bytes())
            self.assertEqual(observed_stats, expected_stats)
            self.assertGreater(status["metrics"]["pack_values"], 10000)
        with mock.patch.dict(os.environ, {"SEMCRYS_NATIVE": "auto", "SEMCRYS_NATIVE_THRESHOLD": "zero"}):
            with self.assertRaisesRegex(RuntimeError, "HELD_NATIVE_THRESHOLD"):
                _pack_varints(self.values)


class DifferentialAssembly(unittest.TestCase):
    def test_native_fold_matches_reference_across_random_streams(self):
        require_native(self)
        randomizer = random.Random(4421)
        assembly = {
            "entries": [
                {"id": 9, "pair": [1, 2]},
                {"id": 10, "pair": [9, 3]},
                {"id": 11, "pair": [4, 4]},
            ]
        }
        for _ in range(25):
            events = [randomizer.randrange(1, 9) for _ in range(2000)]
            expected = _apply_assembly_legend_python(events, assembly)
            with mock.patch.dict(os.environ, {"SEMCRYS_NATIVE": "auto", "SEMCRYS_NATIVE_THRESHOLD": "1"}):
                self.assertEqual(apply_assembly_legend(events, assembly), expected)
        self.assertGreaterEqual(runtime_status()["metrics"]["fold_calls"], 25)


if __name__ == "__main__":
    unittest.main()
