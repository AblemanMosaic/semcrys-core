from __future__ import annotations

import argparse
import bz2
import hashlib
import json
import platform
import tempfile
import time
import tracemalloc
from pathlib import Path

from streaming_app.core import decode_file, encode_file
from semcrys.recursive_metalegend import restore as restore_metalegend
from streaming_app.legend_context import VerifiedLegendContext


ROOT = Path(__file__).resolve().parent.parent
CHUNK = 1024 * 1024


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(CHUNK):
            digest.update(block)
    return digest.hexdigest()


def timed(label: str, function):
    print(json.dumps({"stage": label, "state": "STARTED"}), flush=True)
    wall = time.perf_counter_ns()
    cpu = time.process_time_ns()
    value = function()
    result = {
        "wall_ns": time.perf_counter_ns() - wall,
        "cpu_ns": time.process_time_ns() - cpu,
    }
    print(json.dumps({"stage": label, "state": "COMPLETE", **result}), flush=True)
    return value, result


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure one exact SemCrys integerization pipeline.")
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ultra-asset", "--ultra-container", dest="ultra_asset", type=Path,
                        default=ROOT / "assets" / "legends" / "ULTRA_FAMILY.mleg")
    parser.add_argument("--profile", choices=("T:PRESHARED_TOKEN", "A:LONGITUDINAL_TOKEN_DELTA"), default="T:PRESHARED_TOKEN")
    parser.add_argument("--outer-codec", choices=("NONE", "LZMA", "BZ2_9"), default="LZMA")
    parser.add_argument("--lookup-backend", choices=("AUTO", "DISK", "MMAP", "RAM"), default="AUTO")
    parser.add_argument("--tracemalloc", action="store_true")
    parser.add_argument("--independent-redecode", action="store_true")
    parser.add_argument("--cache-root", type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    expected = manifest["fixture"]
    release = json.loads((ROOT / "RELEASE_CONTRACT.json").read_text(encoding="utf-8"))
    ultra = release["ultra"]
    if args.fixture.stat().st_size != expected["bytes"] or hash_file(args.fixture) != expected["sha256"]:
        raise RuntimeError("HELD_WIKIPEDIA_FIXTURE_IDENTITY")
    if args.ultra_asset.stat().st_size != ultra["asset_bytes"] or hash_file(args.ultra_asset) != ultra["asset_sha256"]:
        raise RuntimeError("HELD_WIKIPEDIA_ULTRA_ASSET_IDENTITY")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="semcrys-integerization-benchmark-", dir=args.output.parent) as name:
        work = Path(name)
        source = work / "source.xml"

        def expand_fixture():
            with bz2.open(args.fixture, "rb") as incoming, source.open("wb") as outgoing:
                while block := incoming.read(CHUNK):
                    outgoing.write(block)

        _, expansion = timed("EXPAND_FIXTURE", expand_fixture)
        if source.stat().st_size != expected["expanded_bytes"] or hash_file(source) != expected["expanded_sha256"]:
            raise RuntimeError("HELD_WIKIPEDIA_EXPANDED_IDENTITY")

        legend = work / "ultra.leg"
        restored, restoration = timed(
            "RESTORE_ULTRA",
            lambda: restore_metalegend(args.ultra_asset, legend),
        )
        if legend.stat().st_size != ultra["logical_legend_bytes"] or restored["source_legend_sha256"] != ultra["logical_legend_sha256"]:
            raise RuntimeError("HELD_WIKIPEDIA_ULTRA_LEGEND_IDENTITY")

        peak = None
        if args.tracemalloc:
            tracemalloc.start()
        try:
            context_started = time.perf_counter_ns()
            with VerifiedLegendContext(lookup_backend=args.lookup_backend,persistent_lookup_cache=args.cache_root) as context:
                _, preparation = timed("PREPARE_ULTRA", lambda: context.prepare(legend))
                container = work / "candidate.crys"
                realized, encoding = timed(
                    "ENCODE_WITH_POSTWRITE_PROOF",
                    lambda: encode_file(
                        source,
                        container,
                        profile=args.profile,
                        external_legends=[legend],
                        outer_codec=args.outer_codec,
                        legend_policy="TOTAL" if args.profile == "A:LONGITUDINAL_TOKEN_DELTA" else "PROFITABLE",
                        legend_context=context,
                    ),
                )
                independent = None
                if args.independent_redecode:
                    decoded = work / "independent.decoded"
                    inverse, independent = timed(
                        "INDEPENDENT_REDECODE",
                        lambda: decode_file(container, decoded, external_legends=[legend], legend_context=context),
                    )
                    if inverse["output_sha256"] != expected["expanded_sha256"] or hash_file(decoded) != expected["expanded_sha256"]:
                        raise RuntimeError("HELD_WIKIPEDIA_INDEPENDENT_INVERSE")
                context_receipt = context.receipt()
            context_wall_ns = time.perf_counter_ns() - context_started
            if args.tracemalloc:
                _, peak = tracemalloc.get_traced_memory()
        finally:
            if args.tracemalloc:
                tracemalloc.stop()

        result = {
            "schema": "semcrys.integerization-pipeline-benchmark.v0.1",
            "standing": "SINGLE_HOST_BOUNDED_MEASUREMENT",
            "source_sha256": expected["expanded_sha256"],
            "source_bytes": expected["expanded_bytes"],
            "ultra_root": ultra["logical_legend_sha256"],
            "profile": args.profile,
            "outer_codec": args.outer_codec,
            "lookup_backend": args.lookup_backend,
            "tracemalloc": args.tracemalloc,
            "independent_redecode": args.independent_redecode,
            "container_bytes": container.stat().st_size,
            "container_sha256": realized["output_sha256"],
            "phase_metrics": {
                "fixture_expansion": expansion,
                "ultra_restoration": restoration,
                "ultra_preparation": preparation,
                "encode_with_postwrite_proof": encoding,
                "independent_redecode": independent,
                "context_total_wall_ns": context_wall_ns,
                "traced_python_peak_bytes": peak,
            },
            "compiler_execution_metrics": realized.get("execution_metrics"),
            "context_receipt": context_receipt,
            "runtime": {
                "python": platform.python_version(),
                "implementation": platform.python_implementation(),
                "system": platform.system(),
                "machine": platform.machine(),
            },
            "claim_boundary": "One exact pinned fixture and configuration on one host; no cross-corpus or global throughput claim.",
            "authority_effect": "NONE",
        }
        encoded = json.dumps(result, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
        result["evidence_root"] = hashlib.sha256(encoded).hexdigest()
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({
        "status": "PASS",
        "evidence_root": result["evidence_root"],
        "container_bytes": result["container_bytes"],
        "encode_wall_ns": result["phase_metrics"]["encode_with_postwrite_proof"]["wall_ns"],
        "output": str(args.output),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
