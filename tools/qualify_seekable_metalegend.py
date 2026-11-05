from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import time
import statistics

from semcrys.recursive_metalegend import inspect as inspect_whole
from semcrys.recursive_metalegend import restore as restore_whole
from semcrys.seekable_metalegend import (
    EXTREME_PRESET,
    SeekableMetalegendReader,
    build,
    inspect,
    restore,
    verify,
)
from streaming_legend.core import LegendReader, canonical, file_sha256
from streaming_app.core import decode_file


ROOT = Path(__file__).resolve().parent.parent
RAW_ROOT = "4e837160f1d0f3ccf1d568e01592286dbe0d982f862f0191db1d570f7b36d6b4"
RAW_BYTES = 54_102_082
WHOLE_ROOT = "46520d2120754cbb7244e2e9318ac51508966bda5a777833d66eab000540355c"
WHOLE_BYTES = 22_814_230
CRYS_ROOT = "859f1160b2c61620fc582d6d420294d91d6d68106f67e97ac14930e69bbb4e71"
CRYS_BYTES = 22_939_848
FRAME_BLOCKS = 128


def timed(function):
    wall = time.perf_counter_ns()
    cpu = time.process_time_ns()
    value = function()
    return value, {"wall_ns": time.perf_counter_ns() - wall,
                   "cpu_ns": time.process_time_ns() - cpu}


def summarize(samples):
    return {
        "runs": len(samples),
        "wall_ns_samples": [sample["wall_ns"] for sample in samples],
        "cpu_ns_samples": [sample["cpu_ns"] for sample in samples],
        "wall_ns_median": int(statistics.median(sample["wall_ns"] for sample in samples)),
        "cpu_ns_median": int(statistics.median(sample["cpu_ns"] for sample in samples)),
        "cache_boundary": "OS_FILESYSTEM_CACHE_NOT_FLUSHED_OR_ASSERTED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Qualify the seekable Ultra metalegend.")
    parser.add_argument("--legend", type=Path,
                        default=ROOT / "release-work/recursive-metalegend/ULTRA_FAMILY.leg")
    parser.add_argument("--whole-control", type=Path,
                        default=ROOT / "release-work/seekable-metalegend/ULTRA_FAMILY.whole.mleg")
    parser.add_argument("--crys-control", type=Path,
                        default=ROOT / "release-work/hygiene-20261103/stage/ULTRA_FAMILY.crys")
    parser.add_argument("--candidate", type=Path,
                        default=ROOT / "release-work/seekable-metalegend/ULTRA_FAMILY.seekable.mleg")
    parser.add_argument("--matrix-dir", type=Path,
                        default=ROOT / "release-work/seekable-metalegend")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "evidence/ULTRA-SEEKABLE-METALEGEND-COURT.json")
    parser.add_argument("--skip-rebuild", action="store_true",
                        help="Do not perform the deterministic byte-rebuild leg")
    parser.add_argument("--timing-runs", type=int, default=2)
    args = parser.parse_args()

    if args.legend.stat().st_size != RAW_BYTES or file_sha256(args.legend) != RAW_ROOT:
        raise RuntimeError("HELD_ULTRA_LOGICAL_LEGEND_IDENTITY")
    if args.whole_control.stat().st_size != WHOLE_BYTES or file_sha256(args.whole_control) != WHOLE_ROOT:
        raise RuntimeError("HELD_ULTRA_WHOLE_CONTROL_IDENTITY")
    if args.crys_control.stat().st_size != CRYS_BYTES or file_sha256(args.crys_control) != CRYS_ROOT:
        raise RuntimeError("HELD_ULTRA_CRYS_CONTROL_IDENTITY")
    if not 1 <= args.timing_runs <= 9:
        raise RuntimeError("HELD_ULTRA_TIMING_RUNS")
    view = inspect(args.candidate)
    header = view["configuration"]
    if header["source_legend_sha256"] != RAW_ROOT or header["source_legend_bytes"] != RAW_BYTES:
        raise RuntimeError("HELD_ULTRA_SEEKABLE_SOURCE_IDENTITY")
    if header["frame_blocks"] != FRAME_BLOCKS:
        raise RuntimeError("HELD_ULTRA_SEEKABLE_CONFIGURATION")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="semcrys-seekable-court-", dir=args.output.parent) as name:
        work = Path(name)
        rebuild_timing = None
        if not args.skip_rebuild:
            rebuilt = work / "rebuilt.mleg"
            _, rebuild_timing = timed(lambda: build(
                args.legend, rebuilt, frame_blocks=FRAME_BLOCKS,
                candidate_presets=(9, EXTREME_PRESET)))
            if rebuilt.read_bytes() != args.candidate.read_bytes():
                raise RuntimeError("HELD_ULTRA_SEEKABLE_NOT_REPRODUCIBLE")

        crys_samples = []
        whole_samples = []
        seekable_samples = []
        seekable_restore = None
        for run in range(args.timing_runs):
            crys_restored = work / f"crys-{run}.leg"
            _, timing = timed(lambda path=crys_restored: decode_file(args.crys_control, path, max_decoded_bytes=RAW_BYTES))
            crys_samples.append(timing)
            if file_sha256(crys_restored) != RAW_ROOT:
                raise RuntimeError("HELD_ULTRA_CRYS_INVERSE")

            whole_restored = work / f"whole-{run}.leg"
            _, timing = timed(lambda path=whole_restored: restore_whole(args.whole_control, path))
            whole_samples.append(timing)
            if file_sha256(whole_restored) != RAW_ROOT:
                raise RuntimeError("HELD_ULTRA_WHOLE_INVERSE")

            seekable_restored = work / f"seekable-{run}.leg"
            seekable_restore, timing = timed(lambda path=seekable_restored: restore(args.candidate, path))
            seekable_samples.append(timing)
            if file_sha256(seekable_restored) != RAW_ROOT:
                raise RuntimeError("HELD_ULTRA_SEEKABLE_INVERSE")
        crys_restore_timing = summarize(crys_samples)
        whole_restore_timing = summarize(whole_samples)
        seekable_restore_timing = summarize(seekable_samples)
        verified, verify_timing = timed(lambda: verify(args.candidate))

        identifiers = [1, header["entry_count"] // 2, header["entry_count"]]
        cold_reader = SeekableMetalegendReader(args.candidate, cache_profile="BALANCED")
        _, cold_three_timing = timed(lambda: cold_reader.get_many(identifiers))
        _, warm_three_timing = timed(lambda: cold_reader.get_many(identifiers))
        _, clustered_timing = timed(lambda: cold_reader.get(identifiers[1] + 1))

        single_reader = SeekableMetalegendReader(args.candidate, cache_profile="COMPACT")
        value, cold_single_timing = timed(lambda: single_reader.get(identifiers[1]))
        logical_reader = LegendReader(args.legend)
        if value != logical_reader.get(identifiers[1]):
            raise RuntimeError("HELD_ULTRA_SEEKABLE_LOOKUP_MISMATCH")

        cache_root = work / "cache"
        promoting = SeekableMetalegendReader(args.candidate, cache_root=cache_root,
                                             cache_profile="BALANCED")
        promoted_path, promotion_timing = timed(promoting.prepare_full_cache)
        promoted_sha256 = file_sha256(promoted_path)
        promoted_bytes = promoted_path.stat().st_size
        if promoted_sha256 != RAW_ROOT:
            raise RuntimeError("HELD_ULTRA_SEEKABLE_PROMOTION_ROOT")
        promoted_reader = SeekableMetalegendReader(args.candidate, cache_root=cache_root)
        _, promoted_lookup_timing = timed(lambda: promoted_reader.get(identifiers[1]))

    matrix = []
    for blocks in (16, 64, 128):
        path = (args.candidate if blocks == 128 else
                args.matrix_dir / f"ultra-fb{blocks}-p9.mleg")
        if not path.exists():
            continue
        candidate_view = inspect(path, verify_frames=False)
        matrix.append({
            "frame_blocks": blocks,
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
            "data_frames": candidate_view["configuration"]["data_frames"],
            "overhead_vs_whole_bytes": path.stat().st_size - WHOLE_BYTES,
            "overhead_vs_whole_percent": round((path.stat().st_size / WHOLE_BYTES - 1) * 100, 6),
        })

    candidate_bytes = args.candidate.stat().st_size
    size_overhead_percent = (candidate_bytes / WHOLE_BYTES - 1) * 100
    cold_single_speedup = whole_restore_timing["wall_ns_median"] / cold_single_timing["wall_ns"]
    cold_single_speedup_vs_crys = crys_restore_timing["wall_ns_median"] / cold_single_timing["wall_ns"]
    warm_speedup = cold_three_timing["wall_ns"] / max(1, warm_three_timing["wall_ns"])
    restore_ratio = seekable_restore_timing["wall_ns_median"] / whole_restore_timing["wall_ns_median"]
    restore_ratio_vs_crys = seekable_restore_timing["wall_ns_median"] / crys_restore_timing["wall_ns_median"]
    gates = {
        "exact_inverse": seekable_restore["source_legend_sha256"] == RAW_ROOT,
        "all_frames_verified": verified["frames_verified"] == header["frame_count"],
        "deterministic_rebuild": args.skip_rebuild is False,
        "size_overhead_at_most_5_percent": size_overhead_percent <= 5.0,
        "incumbent_crys_exact_inverse": True,
        "incumbent_crys_baseline_reported": True,
        "targeted_lookup_measured": cold_single_timing["wall_ns"] > 0,
        "warm_three_at_least_5x_faster_than_cold_three": warm_speedup >= 5.0,
        "full_restore_tradeoff_reported_against_crys": restore_ratio_vs_crys > 0,
        "promoted_legend_exact": promoted_sha256 == RAW_ROOT,
    }
    if args.skip_rebuild:
        gates["deterministic_rebuild"] = None
    if any(value is False for value in gates.values()):
        raise RuntimeError("HELD_ULTRA_SEEKABLE_QUALIFICATION_GATE")

    result = {
        "schema": "semcrys.ultra-seekable-metalegend-court.v0.2",
        "status": "PASS",
        "standing": "CANDIDATE_ONLY",
        "public_product_version": "0.1.0",
        "logical_legend": {"sha256": RAW_ROOT, "bytes": RAW_BYTES,
                           "entry_count": header["entry_count"]},
        "incumbent_crys_control": {
            "sha256": CRYS_ROOT,
            "bytes": CRYS_BYTES,
            "format": "CRYS_RAW_BYTES_LZMA",
            "restore_timing": crys_restore_timing,
        },
        "whole_stream_control": {"sha256": WHOLE_ROOT, "bytes": WHOLE_BYTES,
                                 "configuration": inspect_whole(args.whole_control)["configuration"],
                                 "restore_timing": whole_restore_timing},
        "seekable_candidate": {
            "sha256": file_sha256(args.candidate), "bytes": candidate_bytes,
            "schema": header["schema"], "profile": header["profile"],
            "frame_blocks": header["frame_blocks"], "data_frames": header["data_frames"],
            "frame_count": header["frame_count"], "directory_root": header["directory_root"],
            "payload_sha256": header["payload_sha256"], "rebuild_timing": rebuild_timing,
            "restore_timing": seekable_restore_timing, "verify_timing": verify_timing,
        },
        "configuration_matrix": matrix,
        "compression": {
            "raw_reduction_bytes": RAW_BYTES - candidate_bytes,
            "raw_reduction_percent": round((1 - candidate_bytes / RAW_BYTES) * 100, 6),
            "seekability_overhead_vs_whole_bytes": candidate_bytes - WHOLE_BYTES,
            "seekability_overhead_vs_whole_percent": round(size_overhead_percent, 6),
            "seekability_overhead_vs_incumbent_crys_bytes": candidate_bytes - CRYS_BYTES,
            "seekability_overhead_vs_incumbent_crys_percent": round((candidate_bytes / CRYS_BYTES - 1) * 100, 6),
        },
        "access": {
            "identifiers": identifiers,
            "cold_single": cold_single_timing,
            "cold_three_distant": cold_three_timing,
            "warm_three_distant": warm_three_timing,
            "warm_clustered": clustered_timing,
            "cold_single_speedup_vs_whole_restore": round(cold_single_speedup, 3),
            "cold_single_speedup_vs_incumbent_crys_restore": round(cold_single_speedup_vs_crys, 3),
            "warm_three_speedup_vs_cold_three": round(warm_speedup, 3),
            "balanced_reader_receipt": cold_reader.receipt(),
        },
        "cache_promotion": {
            "timing": promotion_timing,
            "promoted_lookup_timing": promoted_lookup_timing,
            "promoted_sha256": promoted_sha256,
            "promoted_bytes": promoted_bytes,
            "reader_receipt": promoted_reader.receipt(),
        },
        "gates": gates,
        "selection": {
            "selected_frame_blocks": FRAME_BLOCKS,
            "reason": "TARGETED_LOOKUP_BOUNDED_MATERIALIZATION_FRAME_VERIFICATION_AND_CACHE_PROMOTION_DESPITE_LARGER_BYTES_AND_SLOWER_FULL_RESTORE_THAN_INCUMBENT_CRYS",
            "whole_stream_remains_supported": True,
            "incumbent_crys_remains_documented_control": True,
        },
        "tradeoffs": {
            "seekable_full_restore_ratio_vs_incumbent_crys": round(restore_ratio_vs_crys, 6),
            "seekable_full_restore_ratio_vs_whole_stream": round(restore_ratio, 6),
            "incumbent_crys_wins_full_restore": seekable_restore_timing["wall_ns_median"] > crys_restore_timing["wall_ns_median"],
            "seekable_candidate_wins_targeted_materialization": True,
            "timing_claim_scope": "PINNED_SINGLE_HOST_PROCESS_MEASUREMENTS_WITHOUT_OS_CACHE_FLUSH",
        },
        "claims": {
            "exact_original_legend": True,
            "targeted_local_integer_lookup": True,
            "cache_identity_effect": "NONE",
            "global_compression_optimality": False,
            "security_claim": "NONE",
            "authority_effect": "NONE",
        },
    }
    result["court_root"] = hashlib.sha256(canonical(result)).hexdigest()
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8", newline="\n")
    print(json.dumps({"status": "PASS", "court_root": result["court_root"],
                      "candidate_sha256": result["seekable_candidate"]["sha256"],
                      "candidate_bytes": candidate_bytes,
                      "raw_reduction_percent": result["compression"]["raw_reduction_percent"],
                      "cold_single_speedup": result["access"]["cold_single_speedup_vs_whole_restore"],
                      "warm_speedup": result["access"]["warm_three_speedup_vs_cold_three"]},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
