from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from semcrys_core.contract import (ULTRA_ASSET_NAME, ULTRA_BYTES, ULTRA_SHA256,
                                   capabilities, verify_self)
from semcrys_core.dispatch import DispatchRefusal, detect_bytes, inspect_path
from semcrys_core.semantic import SemanticRefusal, build_registry, integerize, restore
from semcrys_lite.core import encode_bytes
from semcrys.recursive_metalegend import MAGIC as WHOLE_METALEGEND_MAGIC
from semcrys.seekable_metalegend import MAGIC as SEEKABLE_METALEGEND_MAGIC
from streaming_legend.crys_v2 import MAGIC as FULL_MAGIC


ROOT = Path(__file__).resolve().parent.parent


class DistributionContract(unittest.TestCase):
    def test_capabilities_bind_all_critical_components(self):
        components = set(capabilities()["components"])
        self.assertIn("ULTRA_RECURSIVE_METALEGEND_ASSET", components)
        self.assertIn("GROUP_LEGENDS", components)
        self.assertIn("RECURSIVE_METALEGENDS", components)
        self.assertIn("FULL_INTEGERIZATION", components)
        self.assertIn("PROTECTED_MOVING_LEGENDS", components)

    def test_ultra_is_exactly_bound(self):
        asset_root = Path(os.environ.get("SEMCRYS_ULTRA_ASSET_ROOT", ROOT / "assets" / "legends"))
        path = asset_root / ULTRA_ASSET_NAME
        if not path.is_file():
            self.skipTest(f"{ULTRA_ASSET_NAME} is a separately mounted release asset")
        self.assertEqual(path.stat().st_size, ULTRA_BYTES)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), ULTRA_SHA256)
        self.assertEqual(verify_self(path.parent)["ultra_verification"], "PASS")

    def test_verify_self_reports_standing(self):
        self.assertEqual(verify_self()["standing"], "CANDIDATE_ONLY")

    def test_publication_decision_is_rooted_and_replacement_is_authorized(self):
        decision = json.loads((ROOT / "PUBLICATION_DECISION.json").read_text(encoding="utf-8"))
        claimed = decision.pop("decision_root")
        canonical = json.dumps(decision, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), claimed)
        self.assertEqual(decision["decision"], "AUTHORIZED_FOR_GITHUB_PUBLICATION")
        contract = json.loads((ROOT / "RELEASE_CONTRACT.json").read_text(encoding="utf-8"))
        self.assertTrue(contract["publication_authorized"])
        self.assertEqual(contract["publication_decision_root"], claimed)
        self.assertEqual(decision["predecessor_decision_root"],
                         "abe8551445328dc73aa00499b4a527db7d88dd6a656648817d315891e25fe53c")
        self.assertEqual(contract["verification_status"], "SELF_VERIFYING_EXTERNAL_REPLAY_PENDING")

    def test_exact_boundary_uses_portable_repository_paths(self):
        path = ROOT / "evidence" / "EXACT-ARTIFACT-BOUNDARY.json"
        if not path.is_file():
            self.skipTest("generated release boundary is not carried in the source archive")
        boundary = json.loads(path.read_text(encoding="utf-8"))
        for artifact in boundary["artifacts"]:
            source = Path(artifact["source_path"])
            self.assertFalse(source.is_absolute())
            self.assertEqual(source.parts[0], "dist")


class DialectDispatch(unittest.TestCase):
    def test_full_signature(self):
        self.assertEqual(detect_bytes(FULL_MAGIC + b"rest"), "FULL_CRYS_0_2")

    def test_recursive_metalegend_signature(self):
        self.assertEqual(detect_bytes(SEEKABLE_METALEGEND_MAGIC + b"rest"),
                         "SEEKABLE_METALEGEND_0_1")
        self.assertEqual(detect_bytes(WHOLE_METALEGEND_MAGIC + b"rest"),
                         "WHOLE_STREAM_METALEGEND_0_1")

    def test_metalegend_registry_disambiguates_group_legend(self):
        from semcrys.formats import registry
        model = registry()
        self.assertEqual(model["terminology"]["group_legend"],
                         "HORIZONTAL_EXACT_RECORD_POOL_ACROSS_ARTIFACTS")
        dialects = model["artifacts"]["recursive_metalegend"]["dialects"]
        self.assertEqual([row["schema"] for row in dialects], [
            "semcrys.seekable-metalegend.v0.1",
            "semcrys.recursive-metalegend.v0.1",
        ])

    def test_lite_binary_and_inspection(self):
        container, _legend, _moving, _receipt = encode_bytes(b"hello")
        self.assertEqual(detect_bytes(container), "LITE_CRYS_0_3_BINARY")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.crys"
            path.write_bytes(container)
            self.assertEqual(inspect_path(path)["dialect"], "LITE_CRYS_0_3_BINARY")

    def test_unknown_refuses(self):
        with self.assertRaises(DispatchRefusal):
            detect_bytes(b"not semcrys")


class SemanticIntegerization(unittest.TestCase):
    def setUp(self):
        self.registry = build_registry([
            {"integer_id": 101, "semantic_key": "example:greeting", "surface": "hello"},
            {"integer_id": 201, "semantic_key": "example:bank-financial", "surface": "bank"},
            {"integer_id": 202, "semantic_key": "example:bank-river", "surface": "bank"}
        ])

    def test_full_integer_coverage_and_roundtrip(self):
        source = b"hello bank!\n"
        stream = integerize(source, self.registry)
        self.assertTrue(stream["full_integer_coverage"])
        self.assertEqual(stream["event_count"], 5)
        self.assertEqual(restore(stream, self.registry), source)
        self.assertEqual(stream["semantic_event_count"], 1)

    def test_explicit_occurrence_binding_disambiguates(self):
        source = b"bank"
        stream = integerize(source, self.registry, {"0": "example:bank-river"})
        self.assertEqual(stream["events"], [[0, 202]])
        self.assertEqual(restore(stream, self.registry), source)

    def test_mismatched_binding_refuses(self):
        with self.assertRaises(SemanticRefusal):
            integerize(b"hello", self.registry, {"0": "example:bank-river"})


if __name__ == "__main__":
    unittest.main()

