from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from build_publication_asset_index import build_index, canonical, write_sidecar  # noqa: E402
from verify_publication_asset_index import verify  # noqa: E402


class PublicationAssetIndex(unittest.TestCase):
    def fixture(self):
        scratch = ROOT / "release-work" / "test-publication-asset-index"
        scratch.mkdir(parents=True, exist_ok=True)
        custody = tempfile.TemporaryDirectory(dir=scratch)
        root = Path(custody.name)
        dist = root / "dist"
        reviewers = root / "reviewers"
        dist.mkdir()
        reviewers.mkdir()
        payload = dist / "payload.pyz"
        payload.write_bytes(b"payload")
        write_sidecar(payload)
        manifest = {
            "schema": "semcrys.release-manifest.v0.2",
            "version": "0.1.0",
            "artifacts": [
                {
                    "path": payload.name,
                    "role": "STDLIB_ZIPAPP",
                    "bytes": payload.stat().st_size,
                    "sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
                }
            ],
        }
        manifest["manifest_root"] = hashlib.sha256(canonical(manifest)).hexdigest()
        manifest_path = dist / "RELEASE-MANIFEST.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        write_sidecar(manifest_path)
        bundle = dist / "semcrys-core-0.1.0-offline-bundle.zip"
        bundle.write_bytes(b"bundle")
        write_sidecar(bundle)
        reviewer = reviewers / "SemCrys-Core-0.1.0-REVIEWER-R1.zip"
        reviewer.write_bytes(b"review")
        write_sidecar(reviewer)
        (reviewers / "SemCrys-Core-0.1.0-REVIEWER-R1.boundary.json").write_text(
            "{}", encoding="utf-8"
        )
        return custody, dist, reviewers

    def test_index_closes_all_declared_publication_groups(self):
        custody, dist, reviewers = self.fixture()
        self.addCleanup(custody.cleanup)
        output, _, index = build_index(dist, reviewers)
        result = verify(output)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["indexed_assets"], 11)
        self.assertEqual(
            {group["group"] for group in index["asset_groups"]},
            {
                "release_control",
                "manifest_bound_payloads",
                "offline_custody_bundle",
                "reviewer_companion_evidence",
            },
        )

    def test_tampered_companion_refuses(self):
        custody, dist, reviewers = self.fixture()
        self.addCleanup(custody.cleanup)
        output, _, _ = build_index(dist, reviewers)
        (dist / "SemCrys-Core-0.1.0-REVIEWER-R1.zip").write_bytes(b"tampered")
        with self.assertRaisesRegex(RuntimeError, "ASSET_(SIZE|HASH)"):
            verify(output)

    def test_incomplete_reviewer_envelope_refuses(self):
        custody, dist, reviewers = self.fixture()
        self.addCleanup(custody.cleanup)
        (reviewers / "SemCrys-Core-0.1.0-REVIEWER-R1.boundary.json").unlink()
        with self.assertRaisesRegex(RuntimeError, "REVIEWER_ENVELOPE_INCOMPLETE"):
            build_index(dist, reviewers)


if __name__ == "__main__":
    unittest.main()
