from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent.parent


class ReleaseStatusConsistencyTests(unittest.TestCase):
    def test_replacement_is_authorized_across_public_surfaces(self):
        contract = json.loads((ROOT / "RELEASE_CONTRACT.json").read_text(encoding="utf-8"))
        decision = json.loads((ROOT / "PUBLICATION_DECISION.json").read_text(encoding="utf-8"))
        status = " ".join(
            (ROOT / "docs" / "RELEASE_CANDIDATE.md")
            .read_text(encoding="utf-8")
            .lower()
            .split()
        )
        release = (ROOT / "GITHUB_RELEASE.md").read_text(encoding="utf-8").lower()
        reproduction = (ROOT / "INDEPENDENT-REPRODUCTION.md").read_text(encoding="utf-8")
        self.assertTrue(contract["publication_authorized"])
        self.assertEqual(contract["standing"], "CANDIDATE_ONLY")
        self.assertEqual(decision["decision"], "AUTHORIZED_FOR_GITHUB_PUBLICATION")
        self.assertEqual(contract["publication_decision_root"], decision["decision_root"])
        self.assertIn("authorized for github publication", status)
        self.assertNotIn("companion independent evidence", release)
        self.assertIn("PENDING_SUCCESSOR_EXACT_ARTIFACT_REPLAY", reproduction)


if __name__ == "__main__":
    unittest.main()
