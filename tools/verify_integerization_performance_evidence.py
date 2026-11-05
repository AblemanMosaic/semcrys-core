from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = "28d61392bfc27ffb1c283beb6dc3dbd78a6d22f2a60e6c76121f6b70cffaaecb"
ULTRA_ROOT = "4e837160f1d0f3ccf1d568e01592286dbe0d982f862f0191db1d570f7b36d6b4"
PROFITABLE = (671046, "e0d424b3aa7265bcbd4d8a60eb8da5f4655bbae02fc194d669e6eb0630d4a43c")
FULL = (724782, "c0d3e93008358f758530bb54572edbc004456159a452774d281a9b92e5cdffce")
FILES = {
    "INTEGERIZATION-BASELINE.json": "0ce5c074a01c3e7bb50a423de46712d52c8d4a8a2aaf00383dd809002c949914",
    "INTEGERIZATION-MMAP-BASELINE.json": "94e8959f563c598eea0eba3dd07665af151477f8afad89e3fe5e3281246ccf18",
    "INTEGERIZATION-RAM-BASELINE.json": "476d4b3e8dd67e743dc5252191ce0fa963dcbeecf329540134a6e4074304016d",
    "INTEGERIZATION-AUTO-PRE-NATIVE.json": "270b622a9eb068a215d4675478e6f6b60e3a9ade912808c712f3cff89f24aada",
    "INTEGERIZATION-AUTO-ABI2.json": "9e3d75fdd215be37ef58b10d1937169730bb49ec80119b4afdf8547a663c8749",
    "INTEGERIZATION-AUTO-PYTHON-BATCHED.json": "c8dde6dfe2ae72d9d85f7b3558a2a05bedeb1a252ab7df3d90cbea734cf22889",
    "INTEGERIZATION-CACHE-COLD.json": "1a551d6d6ec8420ec078fc7168c9148699233fbd2ca5e53622a3c5b6a8947c76",
    "INTEGERIZATION-CACHE-WARM.json": "f9eb3cd8f55b65ff0dc170d072156e6ec53407fdd445a43eeba2740794bedbb1",
    "FULL-INTEGERIZATION-CACHE-WARM-ABI2.json": "c4cd43b0e83b86a6af2f4de9f4b7978e56a8b8af3c0698f59f3b1a7bf83c50ec",
}


def canonical(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()


def main() -> int:
    records = {}
    for name, expected_root in FILES.items():
        value = json.loads((ROOT / "evidence" / name).read_text(encoding="utf-8"))
        claimed = value.pop("evidence_root", None)
        observed = hashlib.sha256(canonical(value)).hexdigest()
        if claimed != expected_root or observed != expected_root:
            raise RuntimeError("HELD_INTEGERIZATION_EVIDENCE_ROOT:" + name)
        value["evidence_root"] = claimed
        if value.get("source_sha256") != SOURCE_ROOT or value.get("ultra_root") != ULTRA_ROOT:
            raise RuntimeError("HELD_INTEGERIZATION_EVIDENCE_IDENTITY:" + name)
        expected_container = FULL if name.startswith("FULL-") else PROFITABLE
        if (value.get("container_bytes"), value.get("container_sha256")) != expected_container:
            raise RuntimeError("HELD_INTEGERIZATION_CONTAINER_IDENTITY:" + name)
        records[name] = value

    disk = records["INTEGERIZATION-BASELINE.json"]["phase_metrics"]["encode_with_postwrite_proof"]["wall_ns"]
    optimized = records["INTEGERIZATION-AUTO-ABI2.json"]["phase_metrics"]["encode_with_postwrite_proof"]["wall_ns"]
    cold = records["INTEGERIZATION-CACHE-COLD.json"]["phase_metrics"]["ultra_preparation"]["wall_ns"]
    warm = records["INTEGERIZATION-CACHE-WARM.json"]["phase_metrics"]["ultra_preparation"]["wall_ns"]
    python_batched = records["INTEGERIZATION-AUTO-PYTHON-BATCHED.json"]["phase_metrics"]["encode_with_postwrite_proof"]["wall_ns"]
    result = {
        "schema": "semcrys.integerization-performance-verification.v0.1",
        "status": "PASS",
        "records": len(records),
        "container_identity_preserved": True,
        "disk_to_optimized_encode_reduction_percent": round((1 - optimized / disk) * 100, 2),
        "cold_to_warm_preparation_reduction_percent": round((1 - warm / cold) * 100, 2),
        "native_increment_over_python_batched_percent": round((1 - optimized / python_batched) * 100, 2),
        "claim_boundary": "Single-host pinned-fixture evidence; timings are observations, not cross-corpus guarantees.",
        "authority_effect": "NONE",
    }
    result["verification_root"] = hashlib.sha256(canonical(result)).hexdigest()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
