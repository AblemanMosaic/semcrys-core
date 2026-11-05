from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "benchmarks" / "wikipedia" / "SOURCE-MANIFEST.json"
EVIDENCE = ROOT / "evidence" / "WIKIPEDIA-BENCHMARK.json"


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    failures = []
    rooted = dict(evidence)
    claimed_root = rooted.pop("evidence_root", None)
    observed_root = hashlib.sha256(canonical(rooted)).hexdigest()
    if claimed_root != observed_root:
        failures.append("EVIDENCE_ROOT")
    manifest_root = hashlib.sha256(canonical(manifest)).hexdigest()
    if evidence.get("schema") != "semcrys.wikipedia-qualification.v0.2":
        failures.append("EVIDENCE_SCHEMA")
    if evidence.get("fixture_manifest_sha256") != manifest_root:
        failures.append("FIXTURE_MANIFEST_BINDING")
    if evidence.get("fixture") != manifest.get("fixture"):
        failures.append("FIXTURE_IDENTITY")
    if evidence.get("source_sha256") != manifest["fixture"].get("expanded_sha256"):
        failures.append("EXPANDED_SOURCE_IDENTITY")
    if evidence.get("source_bytes") != manifest["fixture"].get("expanded_bytes"):
        failures.append("EXPANDED_SOURCE_SIZE")
    if manifest["fixture"].get("redistributed") is not False:
        failures.append("CORPUS_REDISTRIBUTION_BOUNDARY")
    if evidence.get("standing") != "SINGLE_HOST_BOUNDED_CONFIGURATION_COURT_EVIDENCE":
        failures.append("EVIDENCE_STANDING")

    court = evidence.get("configuration_court", {})
    court_root = court.get("court_root")
    court_body = {key: value for key, value in court.items() if key != "court_root"}
    if court.get("schema") != "semcrys.configuration-court.v0.1" or court_root != hashlib.sha256(canonical(court_body)).hexdigest():
        failures.append("COURT_ROOT")
    if court.get("source_sha256") != evidence.get("source_sha256") or court.get("source_bytes") != evidence.get("source_bytes"):
        failures.append("COURT_SOURCE_BINDING")
    if court.get("future_prediction") is not False or court.get("global_optimality") is not False:
        failures.append("COURT_CLAIM_BOUNDARY")
    if court.get("candidate_count") != 18 or len(court.get("candidates", [])) != 18:
        failures.append("COURT_CANDIDATES")
    if court.get("horizons") != [1, 2, 4, 8, 16, 32] or len(court.get("scenarios", [])) != 12:
        failures.append("COURT_SCENARIOS")

    candidate_ids = {row.get("candidate_id") for row in court.get("candidates", [])}
    required_controls = {
        "NATURAL:RAW", "NATURAL:BZ2_1", "NATURAL:BZ2_9",
        "NATURAL:LZMA2_XZ_0", "NATURAL:LZMA2_XZ_6", "NATURAL:LZMA2_XZ_9",
    }
    if not required_controls.issubset(candidate_ids):
        failures.append("NATURAL_CONTROLS")

    for scenario in court.get("scenarios", []):
        winners = scenario.get("winners", {})
        if set(winners) != {
            "MIN_COMPLETE_DELIVERY", "MIN_SEMCRYS_DELIVERY", "MIN_INTEGERIZED_DELIVERY",
            "MIN_FULL_INTEGERIZATION_DELIVERY", "MIN_SHARED_LEGEND_DELIVERY",
        }:
            failures.append("LANE_SET")
            continue
        for lane, winner in winners.items():
            if winner is None or winner.get("candidate_id") not in candidate_ids:
                failures.append("LANE_WINNER_" + lane)
        full = winners.get("MIN_FULL_INTEGERIZATION_DELIVERY") or {}
        if "FULL_INTEGERIZATION" not in full.get("capabilities", []):
            failures.append("FULL_INTEGERIZATION_CONSTRAINT")
        if scenario.get("accounting") == "WARM":
            shared = winners.get("MIN_SHARED_LEGEND_DELIVERY") or {}
            if shared.get("acquisition_bytes") != 0:
                failures.append("WARM_ACQUISITION")

    headline = evidence.get("headline_scenarios", {})
    for name, accounting, horizon in (
        ("cold_horizon_1", "COLD", 1),
        ("warm_horizon_1", "WARM", 1),
        ("cold_horizon_32", "COLD", 32),
        ("warm_horizon_32", "WARM", 32),
    ):
        row = headline.get(name, {})
        if row.get("accounting") != accounting or row.get("reuse_horizon") != horizon:
            failures.append("HEADLINE_" + name.upper())

    result = {
        "schema": "semcrys.wikipedia-evidence-verification.v0.2",
        "status": "PASS" if not failures else "FAIL",
        "fixture_manifest_sha256": manifest_root,
        "evidence_root": observed_root,
        "court_root": court_root,
        "failures": sorted(set(failures)),
        "authority_effect": "NONE",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
