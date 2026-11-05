from __future__ import annotations

import hashlib
import json
from pathlib import Path

from streaming_legend.core import canonical, file_sha256


ROOT = Path(__file__).resolve().parent.parent


def require(condition: bool, code: str) -> None:
    if not condition:
        raise RuntimeError(code)


def main() -> int:
    evidence = json.loads((ROOT / "evidence/ULTRA-SEEKABLE-METALEGEND-COURT.json").read_text(encoding="utf-8"))
    contract = json.loads((ROOT / "RELEASE_CONTRACT.json").read_text(encoding="utf-8"))
    asset = ROOT / "assets/legends/ULTRA_FAMILY.mleg"
    claimed = evidence.pop("court_root")
    require(hashlib.sha256(canonical(evidence)).hexdigest() == claimed,
            "HELD_ULTRA_SEEKABLE_COURT_ROOT")
    require(evidence["schema"] == "semcrys.ultra-seekable-metalegend-court.v0.2"
            and evidence["status"] == "PASS", "HELD_ULTRA_SEEKABLE_COURT_STATUS")
    ultra = contract["ultra"]
    candidate = evidence["seekable_candidate"]
    logical = evidence["logical_legend"]
    require(asset.stat().st_size == candidate["bytes"] == ultra["asset_bytes"],
            "HELD_ULTRA_SEEKABLE_BYTES")
    require(file_sha256(asset) == candidate["sha256"] == ultra["asset_sha256"],
            "HELD_ULTRA_SEEKABLE_ASSET_ROOT")
    require(logical["bytes"] == ultra["logical_legend_bytes"]
            and logical["sha256"] == ultra["logical_legend_sha256"],
            "HELD_ULTRA_SEEKABLE_LOGICAL_ROOT")
    require(ultra["qualification_court_root"] == claimed,
            "HELD_ULTRA_SEEKABLE_CONTRACT_COURT_ROOT")
    compression = evidence["compression"]
    require(compression["raw_reduction_bytes"] == logical["bytes"] - candidate["bytes"],
            "HELD_ULTRA_SEEKABLE_REDUCTION")
    whole = evidence["whole_stream_control"]
    require(compression["seekability_overhead_vs_whole_bytes"]
            == candidate["bytes"] - whole["bytes"],
            "HELD_ULTRA_SEEKABLE_CONTROL_COMPARISON")
    incumbent = evidence["incumbent_crys_control"]
    require(incumbent["sha256"] == "859f1160b2c61620fc582d6d420294d91d6d68106f67e97ac14930e69bbb4e71"
            and incumbent["bytes"] == 22_939_848,
            "HELD_ULTRA_SEEKABLE_INCUMBENT_CONTROL")
    require(compression["seekability_overhead_vs_incumbent_crys_bytes"]
            == candidate["bytes"] - incumbent["bytes"],
            "HELD_ULTRA_SEEKABLE_INCUMBENT_COMPARISON")
    require(evidence["tradeoffs"]["incumbent_crys_wins_full_restore"] is True,
            "HELD_ULTRA_SEEKABLE_RESTORE_TRADEOFF")
    require(evidence["gates"] and all(value is True for value in evidence["gates"].values()),
            "HELD_ULTRA_SEEKABLE_GATES")
    require(evidence["selection"]["selected_frame_blocks"] == candidate["frame_blocks"],
            "HELD_ULTRA_SEEKABLE_SELECTION")
    require("DESPITE_LARGER_BYTES_AND_SLOWER_FULL_RESTORE_THAN_INCUMBENT_CRYS"
            in evidence["selection"]["reason"], "HELD_ULTRA_SEEKABLE_SELECTION_CLAIM")
    print(json.dumps({"status": "PASS", "court_root": claimed,
                      "asset_sha256": candidate["sha256"],
                      "logical_legend_sha256": logical["sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, KeyError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, sort_keys=True))
        raise SystemExit(1)
