from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import time

from semcrys_lite.core import _pack_varints, _unpack_varints, apply_assembly_legend
from semcrys_native import parse_packed_events, reset_metrics, runtime_status
from streaming_app.core import _pack_varint_batch_python, _parse_packed_events_python


def measure(function, repeats):
    samples = []
    result = None
    for _ in range(repeats):
        started = time.perf_counter()
        result = function()
        samples.append(time.perf_counter() - started)
    return result, statistics.median(samples), samples


def run_mode(mode, values, events, assembly, packed_events, repeats):
    os.environ["SEMCRYS_NATIVE"] = mode
    os.environ["SEMCRYS_NATIVE_THRESHOLD"] = "1"
    reset_metrics()
    packed, pack_seconds, pack_samples = measure(lambda: _pack_varints(values), repeats)
    restored, unpack_seconds, unpack_samples = measure(lambda: _unpack_varints(packed), repeats)
    folded, fold_seconds, fold_samples = measure(lambda: apply_assembly_legend(events, assembly), repeats)
    parsed, parse_seconds, parse_samples = measure(
        lambda: parse_packed_events(packed_events, _parse_packed_events_python), repeats
    )
    return {
        "mode": mode.upper(),
        "pack_seconds_median": pack_seconds,
        "unpack_seconds_median": unpack_seconds,
        "fold_seconds_median": fold_seconds,
        "parse_seconds_median": parse_seconds,
        "pack_samples": pack_samples,
        "unpack_samples": unpack_samples,
        "fold_samples": fold_samples,
        "parse_samples": parse_samples,
        "packed_sha256": __import__("hashlib").sha256(packed).hexdigest(),
        "unpack_exact": restored == values,
        "folded_events": len(folded),
        "runtime": runtime_status(),
        "parsed_events": len(parsed[0]),
    }, (packed, restored, folded, list(parsed[0]), list(parsed[1]))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=int, default=2_000_000)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    values = [index & 16383 for index in range(args.events)]
    events = [value for _ in range(args.events // 4) for value in (1, 2, 3, 4)]
    packed_events = _pack_varint_batch_python([value + 1 for value in values])
    assembly = {"entries": [{"id": 20001, "pair": [1, 2]}, {"id": 20002, "pair": [20001, 3]}]}
    reference, reference_outputs = run_mode("off", values, events, assembly, packed_events, args.repeats)
    native, native_outputs = run_mode("auto", values, events, assembly, packed_events, args.repeats)
    if reference_outputs != native_outputs:
        raise RuntimeError("NATIVE_DIFFERENTIAL_MISMATCH")
    result = {
        "schema": "semcrys.native-benchmark.v0.2",
        "status": "PASS",
        "events": args.events,
        "repeats": args.repeats,
        "reference": reference,
        "native": native,
        "speedup": {
            "pack": reference["pack_seconds_median"] / native["pack_seconds_median"],
            "unpack": reference["unpack_seconds_median"] / native["unpack_seconds_median"],
            "assembly_fold": reference["fold_seconds_median"] / native["fold_seconds_median"],
            "packed_event_parse": reference["parse_seconds_median"] / native["parse_seconds_median"],
        },
        "container_bytes_invariant": True,
        "authority_effect": "NONE",
    }
    result["benchmark_root"] = hashlib.sha256(
        json.dumps(result, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        from pathlib import Path
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
