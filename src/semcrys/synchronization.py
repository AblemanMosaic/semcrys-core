"""Shared event-model measurement surfaces for full SemCrys.

These functions observe and propose.  They never mutate a legend, container,
canonical CSIL/GTK state, or relationship state.
"""
from __future__ import annotations

import collections
import hashlib
import json
import lzma
from pathlib import Path
from typing import Iterable

from streaming_app.core import Refusal, iter_units
from streaming_legend.core import LegendReader, canonical, file_sha256
from streaming_legend.crys_v2 import inspect_crys

STANDING = "CANDIDATE_ONLY"


def _rooted(value: dict, field: str) -> dict:
    material = dict(value)
    material.pop(field, None)
    return {**material, field: hashlib.sha256(canonical(material)).hexdigest()}


def _width(value: int) -> int:
    if type(value) is not int or value < 0:
        raise Refusal("HELD_INVALID_EVENT_ID")
    width = 1
    while value >= 0x80:
        value >>= 7
        width += 1
    return width


def _legend_map(path: Path, max_entries: int) -> tuple[LegendReader, dict[bytes, int], dict[int, bytes]]:
    reader = LegendReader(path, max_entries=max_entries)
    reader.verify()
    by_id = dict(reader.iter_values())
    return reader, {value: identifier for identifier, value in by_id.items()}, by_id


def disclosure(source: Path, legend: Path, *, max_entries: int = 5_000_000) -> dict:
    """Measure what a source reveals through one exact full-SemCrys legend."""
    reader, mapping, _by_id = _legend_map(legend, max_entries)
    counts: collections.Counter[bytes] = collections.Counter()
    event_count = 0
    for _kind, value in iter_units(source):
        counts[value] += 1
        event_count += 1
    visible = sum(count for value, count in counts.items() if value in mapping)
    missing = sum(count for value, count in counts.items() if value not in mapping)
    ranked = sorted(
        ((mapping[value], count) for value, count in counts.items() if value in mapping),
        key=lambda row: (-row[1], row[0]),
    )
    result = {
        "schema": "semcrys.full-legend-disclosure.v0.1.candidate",
        "standing": STANDING,
        "source_sha256": file_sha256(source),
        "legend_sha256": file_sha256(legend),
        "legend_entries": reader.count,
        "event_count": event_count,
        "covered_events": visible,
        "literal_events": missing,
        "coverage_fraction": round(visible / event_count, 9) if event_count else 1.0,
        "distinct_referenced_ids": len(ranked),
        "top_reference_counts": [{"id": i, "count": n} for i, n in ranked[:32]],
        "claim": "OBSERVED_REFERENCE_FREQUENCY_ONLY",
        "security_claim": "NONE",
    }
    return _rooted(result, "disclosure_root")


def ordering_projection(source: Path, legend: Path, *, max_entries: int = 5_000_000) -> dict:
    """Propose an ID permutation; does not alter the rooted legend."""
    reader, mapping, by_id = _legend_map(legend, max_entries)
    counts: collections.Counter[int] = collections.Counter()
    for _kind, value in iter_units(source):
        identifier = mapping.get(value)
        if identifier is not None:
            counts[identifier] += 1
    ordered = sorted(range(1, reader.count + 1), key=lambda i: (-counts[i], by_id[i], i))
    rows = [{"old_id": old, "new_id": new, "observed_count": counts[old]} for new, old in enumerate(ordered, 1)]
    old_cost = sum(counts[i] * _width(i) for i in counts)
    new_by_old = {row["old_id"]: row["new_id"] for row in rows}
    new_cost = sum(counts[i] * _width(new_by_old[i]) for i in counts)
    result = {
        "schema": "semcrys.full-ordering-projection.v0.1.candidate",
        "standing": STANDING,
        "source_sha256": file_sha256(source),
        "legend_sha256": file_sha256(legend),
        "ordering": "FREQUENCY_THEN_LEXICAL_BYTES_THEN_OLD_ID",
        "rows": rows,
        "packed_reference_bytes_before": old_cost,
        "packed_reference_bytes_after": new_cost,
        "projected_savings_bytes": old_cost - new_cost,
        "application_status": "PROPOSAL_NOT_APPLIED",
        "security_claim": "NONE",
    }
    return _rooted(result, "projection_root")


def composition_proposal(source: Path, legend: Path, *, minimum_count: int = 3, max_entries: int = 5_000_000) -> dict:
    """Find adjacent reference pairs whose packed reuse can repay a definition."""
    if minimum_count < 2:
        raise Refusal("HELD_INVALID_MINIMUM_COUNT")
    reader, mapping, _by_id = _legend_map(legend, max_entries)
    pairs: collections.Counter[tuple[int, int]] = collections.Counter()
    previous = None
    for _kind, value in iter_units(source):
        current = mapping.get(value)
        if previous is not None and current is not None:
            pairs[(previous, current)] += 1
        previous = current
    next_id = reader.count + 1
    candidates = []
    for (left, right), count in sorted(pairs.items(), key=lambda row: (-row[1], row[0])):
        if count < minimum_count:
            continue
        expanded = count * (_width(left) + _width(right))
        folded = count * _width(next_id)
        definition = _width(left) + _width(right) + _width(next_id)
        savings = expanded - folded - definition
        if savings > 0:
            candidates.append({
                "candidate_id": next_id,
                "components": [left, right],
                "count": count,
                "definition_bytes": definition,
                "projected_net_savings_bytes": savings,
            })
            next_id += 1
    result = {
        "schema": "semcrys.full-composition-proposal.v0.1.candidate",
        "standing": STANDING,
        "source_sha256": file_sha256(source),
        "legend_sha256": file_sha256(legend),
        "minimum_count": minimum_count,
        "candidates": candidates,
        "candidate_count": len(candidates),
        "application_status": "PROPOSAL_NOT_APPLIED",
        "boundary": "PACKED_REFERENCE_COST_ONLY; OUTER_CODEC_EFFECT_NOT_INFERRED",
        "security_claim": "NONE",
    }
    return _rooted(result, "composition_root")


def account_artifacts(sources: Iterable[Path], containers: Iterable[Path], legends: Iterable[Path]) -> dict:
    """Root actual artifacts and show the observed warm/cold break-even curve."""
    source_paths, container_paths, legend_paths = list(sources), list(containers), list(legends)
    if not source_paths or len(source_paths) != len(container_paths):
        raise Refusal("HELD_ACCOUNTING_PAIR_COUNT")
    legend_rows = [{"path_name": p.name, "sha256": file_sha256(p), "bytes": p.stat().st_size} for p in legend_paths]
    legend_bytes = sum(row["bytes"] for row in legend_rows)
    cumulative_worked = cumulative_source = cumulative_xz = 0
    curve = []
    for index, (source, container) in enumerate(zip(source_paths, container_paths), 1):
        inspection = inspect_crys(container)
        if inspection["header"].get("decoded_sha256") != file_sha256(source):
            raise Refusal("HELD_ACCOUNTING_SOURCE_CONTAINER_MISMATCH")
        raw = source.read_bytes()
        cumulative_source += len(raw)
        cumulative_worked += container.stat().st_size
        cumulative_xz += len(lzma.compress(raw, format=lzma.FORMAT_XZ, preset=6))
        curve.append({
            "document_count": index,
            "warm_bytes": cumulative_worked,
            "cold_bytes": cumulative_worked + legend_bytes,
            "xz_source_bytes": cumulative_xz,
            "cold_beats_xz": cumulative_worked + legend_bytes < cumulative_xz,
        })
    first = next((row["document_count"] for row in curve if row["cold_beats_xz"]), None)
    result = {
        "schema": "semcrys.full-artifact-accounting.v0.1.candidate",
        "standing": STANDING,
        "documents": [
            {"source_sha256": file_sha256(s), "container_sha256": file_sha256(c), "source_bytes": s.stat().st_size, "container_bytes": c.stat().st_size}
            for s, c in zip(source_paths, container_paths)
        ],
        "legend_artifacts": legend_rows,
        "actual_legend_bytes": legend_bytes,
        "curve": curve,
        "observed_first_cold_break_even_document": first,
        "accounting_rule": "ACTUAL_TRANSPORTED_ARTIFACT_BYTES; NO_COUNTERFACTUAL_COMPRESSION",
        "security_claim": "NONE",
    }
    return _rooted(result, "accounting_root")
