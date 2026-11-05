"""General exact-workload configuration court.

The court reuses one verified SemCrys cross-product measurement to adjudicate
multiple custody, reuse-horizon, and capability-constrained objectives. It does
not predict future corpora or claim a global optimum.
SPDX-License-Identifier: Apache-2.0
"""
from __future__ import annotations

import bz2
import hashlib
import json
import lzma
import time
from pathlib import Path

from streaming_app.core import Refusal, protect_outputs
from streaming_legend import scratch_io as sio
from streaming_legend.core import canonical, file_sha256

from .configuration_selection import load_library, load_selection, select


SCHEMA = "semcrys.configuration-court.v0.1"
CONTROL_CODECS = ("RAW", "BZ2_1", "BZ2_9", "LZMA2_XZ_0", "LZMA2_XZ_6", "LZMA2_XZ_9")
LANES = (
    "MIN_COMPLETE_DELIVERY",
    "MIN_SEMCRYS_DELIVERY",
    "MIN_INTEGERIZED_DELIVERY",
    "MIN_FULL_INTEGERIZATION_DELIVERY",
    "MIN_SHARED_LEGEND_DELIVERY",
)
MAX_HORIZONS = 16


def _rooted(value: dict, field: str) -> dict:
    return {**value, field: hashlib.sha256(canonical(value)).hexdigest()}


def _stream_copy(source: Path, output, digest=None, limit=None) -> int:
    total = 0
    with source.open("rb") as incoming:
        for block in iter(lambda: incoming.read(1024 * 1024), b""):
            total += len(block)
            if limit is not None and total > limit:
                raise Refusal("HELD_CONFIGURATION_SOURCE_BUDGET")
            output.write(block)
            if digest is not None:
                digest.update(block)
    return total


def _natural_control(source: Path, work: Path, codec: str, source_root: str) -> dict:
    started_wall = time.perf_counter_ns()
    started_cpu = time.process_time_ns()
    if codec == "RAW":
        container_bytes = source.stat().st_size
        container_root = source_root
    else:
        target = work / (codec.lower() + ".bin")
        if codec.startswith("BZ2_"):
            level = int(codec.rsplit("_", 1)[1])
            with bz2.open(target, "wb", compresslevel=level) as outgoing:
                _stream_copy(source, outgoing)
            opener = bz2.open
        else:
            preset = int(codec.rsplit("_", 1)[1])
            with lzma.open(target, "wb", format=lzma.FORMAT_XZ, preset=preset) as outgoing:
                _stream_copy(source, outgoing)
            opener = lzma.open
        container_bytes = target.stat().st_size
        container_root = file_sha256(target)
        restored = hashlib.sha256()
        restored_bytes = 0
        with opener(target, "rb") as incoming:
            for block in iter(lambda: incoming.read(1024 * 1024), b""):
                restored.update(block)
                restored_bytes += len(block)
        if restored.hexdigest() != source_root or restored_bytes != source.stat().st_size:
            raise Refusal("HELD_CONFIGURATION_COURT_CONTROL_INVERSE")
    return {
        "candidate_id": "NATURAL:" + codec,
        "family": "NATURAL_CONTROL",
        "codec": codec,
        "profile": None,
        "legend_policy": None,
        "legend_roots": [],
        "container_bytes": container_bytes,
        "container_sha256": container_root,
        "verification_wall_ns": time.perf_counter_ns() - started_wall,
        "verification_cpu_ns": time.process_time_ns() - started_cpu,
        "capabilities": ["EXACT_RECOVERY"],
    }


def _semcrys_candidate(row: dict) -> dict:
    recipe = row["recipe"]
    profile = recipe["profile"]
    capabilities = ["EXACT_RECOVERY", "SEMCRYS_CONTAINER"]
    if profile != "C:RAW_BYTES":
        capabilities.append("INTEGERIZED")
    if recipe["legend_policy"] == "TOTAL":
        capabilities.append("FULL_INTEGERIZATION")
    elif profile != "C:RAW_BYTES":
        capabilities.append("PROFITABLE_INTEGERIZATION")
    if recipe["legend_roots"]:
        capabilities.append("SHARED_LEGEND")
    return {
        "candidate_id": "SEMCRYS:" + recipe["candidate_id"],
        "family": "SEMCRYS",
        "codec": recipe["codec"],
        "profile": profile,
        "legend_policy": recipe["legend_policy"],
        "legend_roots": recipe["legend_roots"],
        "container_bytes": row["container_bytes"],
        "container_sha256": row["container_sha256"],
        "body_payload_bytes": row["body_payload_bytes"],
        "verification_wall_ns": row["verification_wall_ns"],
        "verification_cpu_ns": row["verification_cpu_ns"],
        "traced_python_peak_bytes": row["traced_python_peak_bytes"],
        "instrumentation": row["instrumentation"],
        "inverse_verification": row["inverse_verification"],
        "execution_metrics": row["execution_metrics"],
        "capabilities": sorted(capabilities),
    }


def _eligible(candidate: dict, lane: str) -> bool:
    capabilities = set(candidate["capabilities"])
    if lane == "MIN_COMPLETE_DELIVERY":
        return True
    if lane == "MIN_SEMCRYS_DELIVERY":
        return candidate["family"] == "SEMCRYS"
    if lane == "MIN_INTEGERIZED_DELIVERY":
        return "INTEGERIZED" in capabilities
    if lane == "MIN_FULL_INTEGERIZATION_DELIVERY":
        return "FULL_INTEGERIZATION" in capabilities
    if lane == "MIN_SHARED_LEGEND_DELIVERY":
        return "SHARED_LEGEND" in capabilities
    raise Refusal("HELD_CONFIGURATION_COURT_LANE")


def _adjudicate(candidates: list[dict], artifacts: dict[str, dict], accounting: str,
                receiver_roots: list[str], horizon: int) -> dict:
    receiver = set(receiver_roots)
    scored = []
    for candidate in candidates:
        roots = set(candidate["legend_roots"])
        missing = sorted(roots - receiver)
        if accounting == "WARM" and missing:
            continue
        acquisition = sum(artifacts[root]["bytes"] for root in missing)
        scored.append({
            **candidate,
            "acquisition_bytes": acquisition,
            "reuse_horizon": horizon,
            "score_bytes": candidate["container_bytes"] * horizon + acquisition,
        })
    winners = {}
    for lane in LANES:
        rows = [row for row in scored if _eligible(row, lane)]
        winner = min(rows, key=lambda row: (row["score_bytes"], row["candidate_id"])) if rows else None
        winners[lane] = None if winner is None else {
            key: winner[key] for key in (
                "candidate_id", "family", "codec", "profile", "legend_policy",
                "legend_roots", "capabilities", "container_bytes", "acquisition_bytes",
                "reuse_horizon", "score_bytes", "container_sha256"
            )
        }
    return {
        "accounting": accounting,
        "receiver_roots": sorted(receiver),
        "reuse_horizon": horizon,
        "available_candidates": len(scored),
        "winners": winners,
    }


def run(source, output, *, library_path, legends, semcrys_codecs=("NONE", "LZMA", "BZ2_9"),
        control_codecs=CONTROL_CODECS, horizons=(1, 2, 4, 8, 16, 32), receiver_roots=(),
        qualification_label="UNSPECIFIED_EXACT_WORKLOAD", max_source_bytes=64 * 1024 * 1024,
        max_legend_bytes=1024 * 1024 * 1024, progress=None, lookup_cache_root=None):
    """Measure one exact workload and publish a rooted multi-objective court."""
    source, output, library_path = Path(source), Path(output), Path(library_path)
    legends = [Path(path) for path in legends]
    protect_outputs([output], [source, library_path, *legends])
    if type(qualification_label) is not str or not qualification_label or len(qualification_label) > 128:
        raise Refusal("HELD_CONFIGURATION_COURT_LABEL")
    horizons = sorted(set(horizons))
    if not horizons or len(horizons) > MAX_HORIZONS or any(type(value) is not int or not 1 <= value <= 1024 for value in horizons):
        raise Refusal("HELD_CONFIGURATION_COURT_HORIZONS")
    controls = list(control_codecs)
    if not controls or len(controls) != len(set(controls)) or any(codec not in CONTROL_CODECS for codec in controls):
        raise Refusal("HELD_CONFIGURATION_COURT_CONTROLS")
    output.parent.mkdir(parents=True, exist_ok=True)
    with sio.TempDirectory(prefix="configuration-court-", dir=output.parent) as name:
        work = Path(name)
        frozen = work / "source"
        source_digest = hashlib.sha256()
        with sio.open_output(frozen, "wb") as outgoing:
            _stream_copy(source, outgoing, source_digest, max_source_bytes)
        measurement_path = work / "measurement.json"
        if progress:
            progress({"stage": "CONFIGURATION_COURT_MEASUREMENT_STARTED"})
        select(
            frozen,
            measurement_path,
            library_path=library_path,
            legends=legends,
            codecs=semcrys_codecs,
            accounting="COLD",
            receiver_roots=(),
            horizon=1,
            max_source_bytes=max_source_bytes,
            max_legend_bytes=max_legend_bytes,
            progress=progress,
            persistent_lookup_cache=lookup_cache_root,
        )
        library = load_library(library_path)
        selection, _winner = load_selection(measurement_path, library)
        ic = selection["instance_constitution"]
        candidates = [_semcrys_candidate(row) for row in selection["rows"] if row["status"] == "PASS"]
        if source_digest.hexdigest() != ic["source_sha256"] or frozen.stat().st_size != ic["source_bytes"]:
            raise Refusal("HELD_CONFIGURATION_COURT_SNAPSHOT")
        candidates.extend(_natural_control(frozen, work, codec, ic["source_sha256"]) for codec in controls)
        artifacts = {row["sha256"]: row for row in library["artifacts"]}
        receiver = sorted(receiver_roots)
        if len(receiver) != len(set(receiver)) or any(root not in artifacts for root in receiver):
            raise Refusal("HELD_CONFIGURATION_COURT_RECEIVER_ROOTS")
        scenarios = []
        for horizon in horizons:
            scenarios.append(_adjudicate(candidates, artifacts, "COLD", [], horizon))
            if receiver:
                scenarios.append(_adjudicate(candidates, artifacts, "WARM", receiver, horizon))
        candidate_rows = sorted(candidates, key=lambda row: row["candidate_id"])
        value = _rooted({
            "schema": SCHEMA,
            "standing": "BOUNDED_EXACT_WORKLOAD_EVIDENCE",
            "qualification_label": qualification_label,
            "source_sha256": ic["source_sha256"],
            "source_bytes": ic["source_bytes"],
            "library_root": library["library_root"],
            "measurement_selection_root": selection["selection_root"],
            "semcrys_codecs": list(semcrys_codecs),
            "control_codecs": controls,
            "horizons": horizons,
            "candidate_count": len(candidate_rows),
            "candidates": candidate_rows,
            "scenarios": scenarios,
            "objective": "MIN_TOTAL_DELIVERY_BYTES_AT_EXACT_REUSE_HORIZON_WITH_CAPABILITY_CONSTRAINTS",
            "selection_scope": "ENUMERATED_CANDIDATES_FOR_ONE_EXACT_SOURCE_AND_DECLARED_RECEIVER_STATE",
            "future_prediction": False,
            "global_optimality": False,
            "security_claim": "NONE",
            "authority_effect": "NONE",
        }, "court_root")
        sio.write_bytes(output, canonical(value))
    if progress:
        progress({"stage": "CONFIGURATION_COURT_COMPLETE", "court_root": value["court_root"]})
    return {
        "schema": "semcrys.configuration-court-result.v0.1",
        "status": "PASS",
        "standing": "CANDIDATE_ONLY",
        "court_root": value["court_root"],
        "output_sha256": file_sha256(output),
        "candidate_count": value["candidate_count"],
        "scenario_count": len(value["scenarios"]),
        "global_optimality": False,
        "authority_effect": "NONE",
    }


def load(path):
    path = Path(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    root = value.get("court_root")
    without = {key: item for key, item in value.items() if key != "court_root"}
    if value.get("schema") != SCHEMA or root != hashlib.sha256(canonical(without)).hexdigest():
        raise Refusal("HELD_CONFIGURATION_COURT_ROOT")
    if value.get("future_prediction") is not False or value.get("global_optimality") is not False:
        raise Refusal("HELD_CONFIGURATION_COURT_CLAIM")
    return value
