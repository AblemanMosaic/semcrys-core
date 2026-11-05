"""Read-only GTK dossier, resolution, exposure and vocabulary adapters.

This module does not mutate source text, GTK, CSIL, legends, or relationship
state.  GTK bound-term identities and SemCrys local transport identifiers are
deliberately different types.

SPDX-License-Identifier: Apache-2.0
"""
from __future__ import annotations

import hashlib
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Sequence

from streaming_app.core import Refusal, iter_units, protect_outputs, _validate_lineage
from streaming_app.legend_context import VerifiedLegendContext
from streaming_legend.assembly import ExecutionLegendReader
from streaming_legend.core import canonical, file_sha256
from streaming_legend import scratch_io as sio


DOSSIER_SCHEMA = "hyperpedia.gtk-bound-term-dossier.v0.1.candidate"
SCHEMA_CONTRACT = "hyperpedia.gtk-schema-contract.v0.1.candidate"
DECISION_SCHEMA = "semcrys.gtk-resolution-decisions.v0.2"
REPORT_SCHEMA = "semcrys.gtk-analysis.v0.2"
VOCABULARY_SCHEMA = "semcrys.legend-vocabulary.v0.1"
MAX_JSON = 16 * 1024 * 1024
MAX_SOURCE = 64 * 1024 * 1024
MAX_DOSSIERS = 4096
MAX_UNITS = 1_000_000
MAX_ANNOTATIONS = 100_000
MAX_SURFACE_BYTES = 4096
TOKENIZER = "UNICODE_CATEGORY_LOSSLESS_V1"
ACCEPTED_PROVENANCE = ("CANDIDATE_BACKED", "REVIEWED")


def _rooted(value: dict, key: str) -> dict:
    return {**value, key: hashlib.sha256(canonical(value)).hexdigest()}


def _is_root(value) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _read_json(path: Path, limit: int = MAX_JSON) -> dict:
    try:
        with Path(path).open("rb") as handle:
            data = handle.read(limit + 1)
        if len(data) > limit:
            raise Refusal("HELD_GTK_JSON_LIMIT", str(path))
        def no_duplicates(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise Refusal("HELD_GTK_DUPLICATE_JSON_KEY", str(key))
                value[key] = item
            return value
        value = json.loads(data.decode("utf-8"), object_pairs_hook=no_duplicates)
        if type(value) is not dict:
            raise Refusal("HELD_GTK_JSON_OBJECT_REQUIRED", str(path))
        return value
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, Refusal):
            raise
        raise Refusal("HELD_GTK_JSON_INVALID", str(path)) from exc


def load_schema_contract(path: Path) -> dict:
    value = _read_json(path)
    required = {
        "schema", "contract_id", "predecessor_candidate_root", "standing", "claim_ceiling",
        "canonical_mutation", "authority_effect", "admission_effect", "ratification_effect",
        "release_effect", "identity_axes", "identity_invariants", "projection_coordinate",
        "polarities", "cell_states", "normalized_integer_tables", "text_projections",
        "zoom_registry_ref", "lpz_factor_registry_ref", "relation_type_registry_ref",
        "object_registry_ref", "proposal_contract_ref", "curation_crosswalk_ref", "evolution_rule",
    }
    if set(value) != required or value.get("schema") != SCHEMA_CONTRACT or value.get("standing") != "INFORMATION_ONLY":
        raise Refusal("HELD_GTK_SCHEMA_CONTRACT")
    if value.get("canonical_mutation") is not False or any(value.get(k) != "NONE" for k in ("authority_effect", "admission_effect", "ratification_effect", "release_effect")):
        raise Refusal("HELD_GTK_SCHEMA_AUTHORITY_BOUNDARY")
    axes = value.get("identity_axes")
    if type(axes) is not list or not {"bound_term_csil", "lexeme_csil", "sense_category_csil", "language_csil", "part_of_speech_csils"}.issubset(set(axes)):
        raise Refusal("HELD_GTK_SCHEMA_IDENTITY_AXES")
    return {"value": value, "sha256": file_sha256(Path(path))}


def _positive(value) -> bool:
    return type(value) is int and 0 < value <= (1 << 63) - 1


def _cell_glosses(cells: list) -> list[str]:
    result = []
    for cell in cells:
        if type(cell) is not dict or cell.get("zoom_family") != "RPZ" or cell.get("zoom_level") != 2 or cell.get("polarity") != "CATAPHATIC" or cell.get("cell_state") != "FILLED":
            continue
        payload = cell.get("payload")
        claim = payload.get("claim") if type(payload) is dict else None
        if type(claim) is not dict or claim.get("kind") != "DEFINITION":
            continue
        text = claim.get("definition_text") if type(claim) is dict else None
        if isinstance(text, str) and text and len(text.encode("utf-8")) <= MAX_SURFACE_BYTES:
            result.append(text)
    return result[:16]


def load_dossier(path: Path) -> dict:
    value = _read_json(path)
    if set(value) != {"schema", "dossier_id", "identity", "cells", "standing", "canonical_mutation", "authority_effect", "admission_effect", "ratification_effect", "dossier_root"}:
        raise Refusal("HELD_GTK_DOSSIER_FIELDS", str(path))
    if value["schema"] != DOSSIER_SCHEMA or value["standing"] != "INFORMATION_ONLY" or value["canonical_mutation"] is not False:
        raise Refusal("HELD_GTK_DOSSIER_STANDING", str(path))
    if any(value[k] != "NONE" for k in ("authority_effect", "admission_effect", "ratification_effect")):
        raise Refusal("HELD_GTK_DOSSIER_AUTHORITY_BOUNDARY", str(path))
    if not isinstance(value["dossier_id"], str) or not value["dossier_id"] or len(value["dossier_id"].encode("utf-8")) > 256:
        raise Refusal("HELD_GTK_DOSSIER_ID", str(path))
    expected = hashlib.sha256(canonical({k: v for k, v in value.items() if k != "dossier_root"})).hexdigest()
    if value["dossier_root"] != expected:
        raise Refusal("HELD_GTK_DOSSIER_ROOT", str(path))
    identity = value["identity"]
    keys = {"bound_term_csil", "lexeme_csil", "sense_category_csil", "language_csil", "part_of_speech_csils", "source_sense_csils", "rendering"}
    if type(identity) is not dict or set(identity) != keys:
        raise Refusal("HELD_GTK_DOSSIER_IDENTITY", str(path))
    if any(not _positive(identity[k]) for k in ("bound_term_csil", "lexeme_csil", "sense_category_csil", "language_csil")):
        raise Refusal("HELD_GTK_DOSSIER_IDENTITY", str(path))
    for key in ("part_of_speech_csils", "source_sense_csils"):
        rows = identity[key]
        if type(rows) is not list or not rows or len(rows) > 64 or any(not _positive(x) for x in rows) or rows != sorted(set(rows)):
            raise Refusal("HELD_GTK_DOSSIER_IDENTITY", key)
    rendering = identity["rendering"]
    if not isinstance(rendering, str) or ":" not in rendering or not rendering.split(":", 1)[0] or len(rendering.encode("utf-8")) > MAX_SURFACE_BYTES:
        raise Refusal("HELD_GTK_DOSSIER_RENDERING", str(path))
    cells = value["cells"]
    if type(cells) is not list or not cells or len(cells) > 4096:
        raise Refusal("HELD_GTK_DOSSIER_CELL_LIMIT", str(path))
    # Strict mode validates the common identity/provenance perimeter while
    # retaining schema-extensible cell payloads as opaque candidate evidence.
    for cell in cells:
        if type(cell) is not dict or cell.get("subject_csil") != identity["bound_term_csil"] or cell.get("standing") != "INFORMATION_ONLY":
            raise Refusal("HELD_GTK_DOSSIER_CELL_BINDING", str(path))
        if cell.get("cell_state") not in ("FILLED", "EMPTY_APPLICABLE", "NOT_APPLICABLE", "UNKNOWN"):
            raise Refusal("HELD_GTK_DOSSIER_CELL_STATE", str(path))
    surface = rendering.split(":", 1)[0].casefold()
    return {
        "path": Path(path), "file_sha256": file_sha256(Path(path)), "dossier_root": value["dossier_root"],
        "surface": surface, "bound_term_csil": identity["bound_term_csil"], "lexeme_csil": identity["lexeme_csil"],
        "sense_category_csil": identity["sense_category_csil"], "part_of_speech_csils": identity["part_of_speech_csils"],
        "rendering": rendering, "glosses": _cell_glosses(cells), "value": value,
    }


def load_dossiers(paths: Sequence[Path], *, schema_contract_sha256: str) -> dict:
    if not _is_root(schema_contract_sha256):
        raise Refusal("HELD_GTK_SCHEMA_CONTRACT_ROOT")
    if not paths or len(paths) > MAX_DOSSIERS:
        raise Refusal("HELD_GTK_DOSSIER_COUNT")
    rows = [load_dossier(Path(path)) for path in paths]
    roots = [row["dossier_root"] for row in rows]
    bound = [row["bound_term_csil"] for row in rows]
    if len(set(roots)) != len(roots) or len(set(bound)) != len(bound):
        raise Refusal("HELD_GTK_DOSSIER_DUPLICATE_IDENTITY")
    rows.sort(key=lambda row: (row["surface"], row["bound_term_csil"], row["dossier_root"]))
    for surface in {row["surface"] for row in rows}:
        lexemes = {row["lexeme_csil"] for row in rows if row["surface"] == surface}
        if len(lexemes) != 1:
            raise Refusal("HELD_GTK_SURFACE_LEXEME_CONFLICT", surface)
    public = [{k: row[k] for k in ("surface", "bound_term_csil", "dossier_root", "file_sha256")} for row in rows]
    dossier_set = _rooted({"schema": "semcrys.gtk-dossier-set.v0.2", "standing": "CANDIDATE_ONLY",
                           "gtk_schema_contract_sha256": schema_contract_sha256, "dossiers": public}, "dossier_set_root")
    by_surface = defaultdict(list)
    for row in rows:
        by_surface[row["surface"]].append(row)
    return {"rows": rows, "by_surface": dict(by_surface), "dossier_set": dossier_set}


def load_decisions(path: Path | None, *, source_sha256: str, dossier_set_root: str, dossiers: dict) -> dict:
    if path is None:
        return {"type_defaults": {}, "occurrence_overrides": {}, "decision_root": None}
    value = _read_json(Path(path))
    if set(value) != {"schema", "standing", "tokenizer", "source_sha256", "dossier_set_root", "type_defaults", "occurrence_overrides", "decision_root"} or value.get("schema") != DECISION_SCHEMA or value.get("standing") != "CANDIDATE_ONLY" or value.get("tokenizer") != TOKENIZER:
        raise Refusal("HELD_GTK_DECISION_SCHEMA")
    expected = _rooted({k: v for k, v in value.items() if k != "decision_root"}, "decision_root")
    if value != expected or value["dossier_set_root"] != dossier_set_root:
        raise Refusal("HELD_GTK_DECISION_BINDING")
    decision_source = value["source_sha256"]
    if decision_source is not None and (not _is_root(decision_source) or decision_source != source_sha256):
        raise Refusal("HELD_GTK_DECISION_SOURCE_BINDING")
    roots = {row["dossier_root"]: row for row in dossiers["rows"]}

    def validate(row, surface, occurrence=None):
        required = {"surface", "bound_term_csil", "dossier_root", "provenance"}
        if occurrence is not None:
            required.add("unit_index")
        if type(row) is not dict or set(row) != required or row.get("surface") != surface or row.get("provenance") not in ACCEPTED_PROVENANCE:
            raise Refusal("HELD_GTK_DECISION_ROW")
        if occurrence is not None and row.get("unit_index") != occurrence:
            raise Refusal("HELD_GTK_DECISION_ROW")
        dossier = roots.get(row.get("dossier_root"))
        if dossier is None or dossier["surface"] != surface or dossier["bound_term_csil"] != row.get("bound_term_csil"):
            raise Refusal("HELD_GTK_DECISION_DOSSIER_BINDING")
        return row

    defaults = value["type_defaults"]
    if type(defaults) is not list or len(defaults) > MAX_DOSSIERS:
        raise Refusal("HELD_GTK_DECISION_LIMIT")
    by_type = {}
    for row in defaults:
        surface = row.get("surface") if type(row) is dict else None
        if not isinstance(surface, str) or surface != surface.casefold() or surface in by_type:
            raise Refusal("HELD_GTK_DECISION_ORDER_OR_DUPLICATE")
        by_type[surface] = validate(row, surface)
    if [r["surface"] for r in defaults] != sorted(by_type):
        raise Refusal("HELD_GTK_DECISION_ORDER_OR_DUPLICATE")
    overrides = value["occurrence_overrides"]
    if type(overrides) is not list or len(overrides) > MAX_UNITS:
        raise Refusal("HELD_GTK_DECISION_LIMIT")
    by_occurrence = {}
    if overrides and decision_source is None:
        raise Refusal("HELD_GTK_OCCURRENCE_DECISIONS_REQUIRE_SOURCE_ROOT")
    last = -1
    for row in overrides:
        index = row.get("unit_index") if type(row) is dict else None
        surface = row.get("surface") if type(row) is dict else None
        if type(index) is not int or index <= last or not isinstance(surface, str) or surface != surface.casefold():
            raise Refusal("HELD_GTK_DECISION_ORDER_OR_DUPLICATE")
        by_occurrence[index] = validate(row, surface, index); last = index
    return {"type_defaults": by_type, "occurrence_overrides": by_occurrence, "decision_root": value["decision_root"]}


def _snapshot_source(source: Path, target: Path, limit: int, expected_root: str) -> None:
    size = 0; digest = hashlib.sha256()
    with source.open("rb") as incoming, sio.open_output(target, "wb") as outgoing:
        for block in iter(lambda: incoming.read(1024 * 1024), b""):
            size += len(block)
            if size > limit:
                raise Refusal("HELD_GTK_SOURCE_LIMIT")
            digest.update(block); outgoing.write(block)
    if digest.hexdigest() != expected_root:
        raise Refusal("HELD_GTK_SOURCE_CHANGED")


def _context_witness(receipt: dict) -> dict:
    """Project deterministic custody facts; exclude timing/cache observations."""
    stats = receipt["stats"]
    return _rooted({
        "schema": "semcrys.gtk-legend-context-witness.v0.1", "standing": "CANDIDATE_ONLY",
        "effective_configuration": receipt["effective_configuration"],
        "policy": receipt["policy"], "operation_sequence": receipt["operation_sequence"],
        "legend_roots": receipt["legend_roots"],
        "deterministic_stats": {key: stats[key] for key in ("full_validations", "lookup_builds", "snapshot_bytes")},
        "persistent_cache": False, "security_claim": "NONE",
    }, "witness_root")


def analyze(source: Path, *, schema_contract: Path, dossiers: Sequence[Path], decisions: Path | None = None,
            legends: Sequence[Path] = (), pathway: str = "NL", sense_binding: str = "NONE",
            unresolved: str = "HOLD", force_csil: str = "FLAG", annotate: bool = True,
            max_source_bytes: int = MAX_SOURCE, max_units: int = MAX_UNITS,
            max_annotations: int = MAX_ANNOTATIONS, max_legend_bytes: int = 1024 * 1024 * 1024) -> dict:
    if pathway not in ("NL", "GCNL") or sense_binding not in ("NONE", "SENSE_KEYED") or unresolved not in ("HOLD", "SPINE") or force_csil not in ("OFF", "FLAG", "HOLD"):
        raise Refusal("HELD_GTK_ANALYSIS_CONFIGURATION")
    if pathway == "GCNL" and sense_binding != "SENSE_KEYED":
        raise Refusal("HELD_GCNL_REQUIRES_SENSE_KEYED")
    if pathway == "NL" and sense_binding != "NONE":
        raise Refusal("HELD_NL_REQUIRES_SURFACE_BINDING")
    if any(type(v) is not int or v < 1 for v in (max_source_bytes, max_units, max_annotations, max_legend_bytes)):
        raise Refusal("HELD_GTK_ANALYSIS_LIMIT")
    source = Path(source)
    if source.stat().st_size > max_source_bytes:
        raise Refusal("HELD_GTK_SOURCE_LIMIT")
    before = file_sha256(source)
    contract = load_schema_contract(Path(schema_contract))
    loaded = load_dossiers(dossiers, schema_contract_sha256=contract["sha256"])
    decision = load_decisions(decisions, source_sha256=before, dossier_set_root=loaded["dossier_set"]["dossier_set_root"], dossiers=loaded)
    counts = Counter();annotations = [];clarification = {};legend_roots = []
    context_receipt = None
    with sio.TempDirectory(prefix="semcrys-gtk-analysis-") as name, VerifiedLegendContext(max_legend_bytes=max_legend_bytes) as context:
        snapshot = Path(name) / "source.bytes"
        _snapshot_source(source, snapshot, max_source_bytes, before)
        lookup = None
        if legends:
            rows = context.rows(legends)
            _validate_lineage([row["path"] for row in rows])
            lookup, _ = context.stack(legends)
            legend_roots = [row["sha256"] for row in rows]
        for unit_index, (kind, raw) in enumerate(iter_units(snapshot)):
            if unit_index >= max_units:
                raise Refusal("HELD_GTK_UNIT_LIMIT")
            counts["units_total"] += 1
            found = lookup.execute("SELECT id FROM lookup WHERE value=?", (raw,)).fetchone() if lookup else None
            wire_id = found[0] if found else None
            if legends:
                counts["wire_legend_units" if wire_id else "wire_literal_units"] += 1
                counts["wire_literal_source_bytes" if wire_id is None else "wire_legend_source_bytes"] += len(raw)
            state = "NONLEXICAL"
            selected = None
            candidates = []
            surface = None
            if kind == "unit":
                counts["lexical_units"] += 1
                try:
                    rendered = raw.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise Refusal("HELD_GTK_UNIT_UTF8") from exc
                surface = rendered.casefold()
                candidates = loaded["by_surface"].get(surface, [])
                if not candidates:
                    state = "UNKNOWN"; counts["lexical_unknown"] += 1
                elif len(candidates) == 1:
                    state = "RESOLVED_SINGLE_CANDIDATE"; selected = candidates[0]; counts["lexical_resolved"] += 1
                else:
                    chosen = decision["occurrence_overrides"].get(unit_index) or decision["type_defaults"].get(surface)
                    if chosen is not None:
                        selected = next(row for row in candidates if row["dossier_root"] == chosen["dossier_root"])
                        state = "RESOLVED_REVIEWED"; counts["lexical_resolved"] += 1
                    elif unresolved == "SPINE":
                        selected = min(candidates, key=lambda row: row["bound_term_csil"])
                        state = "SPINE_GUESS"; counts["lexical_spine_guesses"] += 1
                    else:
                        state = "POLYSEMOUS_UNRESOLVED"; counts["lexical_polysemous_unresolved"] += 1
                    if state in ("POLYSEMOUS_UNRESOLVED", "SPINE_GUESS") and surface not in clarification:
                        clarification[surface] = {
                            "surface": surface, "state": state,
                            "prompt": f"'{rendered}' is unresolved; select one candidate bound-term.",
                            "candidates": [{"bound_term_csil": row["bound_term_csil"], "dossier_root": row["dossier_root"],
                                            "rendering": row["rendering"], "glosses": row["glosses"]} for row in candidates],
                        }
                if state != "UNKNOWN":
                    counts["lexical_covered"] += 1
            if annotate:
                if len(annotations) >= max_annotations:
                    raise Refusal("HELD_GTK_ANNOTATION_LIMIT")
                annotations.append({
                    "unit_index": unit_index, "kind": kind, "unit_hex": raw.hex(), "surface": surface,
                    "resolution_state": state,
                    "selected_bound_term_csil": selected["bound_term_csil"] if selected else None,
                    "selected_dossier_root": selected["dossier_root"] if selected else None,
                    "candidate_count": len(candidates),
                    "wire_state": ("NOT_ASSESSED" if not legends else ("LEGEND_ID" if wire_id else "LITERAL")),
                    "local_transport_id": wire_id,
                })
        context.verify_used(); context_receipt = _context_witness(context.receipt()) if legends else None
    if file_sha256(source) != before:
        raise Refusal("HELD_GTK_SOURCE_CHANGED")
    if decision["occurrence_overrides"] and max(decision["occurrence_overrides"]) >= counts["units_total"]:
        raise Refusal("HELD_GTK_DECISION_OCCURRENCE_OUT_OF_RANGE")
    if force_csil == "HOLD" and counts["lexical_unknown"]:
        raise Refusal("HELD_CSIL_COVERAGE_INCOMPLETE", str(counts["lexical_unknown"]))
    if pathway == "GCNL" and unresolved == "HOLD" and counts["lexical_polysemous_unresolved"]:
        raise Refusal("HELD_SENSE_RESOLUTION_INCOMPLETE", str(counts["lexical_polysemous_unresolved"]))
    queue = [clarification[key] for key in sorted(clarification)]
    base = {
        "schema": REPORT_SCHEMA, "status": "PASS", "standing": "CANDIDATE_ONLY",
        "source_sha256": before, "gtk_schema_contract_sha256": contract["sha256"],
        "dossier_set_root": loaded["dossier_set"]["dossier_set_root"], "decision_root": decision["decision_root"],
        "configuration": {"pathway": pathway, "sense_binding": sense_binding, "sense_unresolved": unresolved,
                          "force_csil": force_csil, "annotate": annotate},
        "identity_boundary": {
            "gtk_bound_term": "CSIL_ADDRESSED_CANDIDATE_DOSSIER_IDENTITY",
            "local_transport_id": "LEGEND_ROOT_AND_ORDER_SCOPED_NOT_CANONICAL_CSIL",
            "model_token_id": "NOT_ASSIGNED_BY_THIS_ADAPTER",
        },
        "metrics": dict(sorted(counts.items())), "legend_roots": legend_roots, "legend_context_receipt": context_receipt,
        "clarification_queue": queue, "annotations": annotations,
        "source_mutated": False, "canonical_gtk_mutated": False, "correction_applied": False,
        "security_claim": "NONE",
    }
    return _rooted(base, "analysis_root")


def export_vocabulary(output: Path, *, legends: Sequence[Path], acknowledge_legend_disclosure: bool,
                      max_legend_bytes: int = 1024 * 1024 * 1024) -> dict:
    """Write a streaming, exact, local-id vocabulary and validate its inverse."""
    if not acknowledge_legend_disclosure:
        raise Refusal("HELD_VOCABULARY_DISCLOSES_LEGEND")
    if not legends:
        raise Refusal("HELD_VOCABULARY_LEGEND_REQUIRED")
    target = Path(output)
    protect_outputs([target], legends); target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = sio.mkstemp(prefix=target.name + ".", suffix=".pending", dir=target.parent)
    sio.close_fd(descriptor); pending = Path(name)
    try:
        with VerifiedLegendContext(max_legend_bytes=max_legend_bytes) as context:
            rows = context.rows(legends); _validate_lineage([row["path"] for row in rows]); context.stack(legends)
            readers = [context.reader(path) for path in legends]
            roots = [row["sha256"] for row in rows]; total = sum(reader.count for reader in readers)
            header = {
                "schema": VOCABULARY_SCHEMA, "standing": "CANDIDATE_ONLY", "legend_roots": roots,
                "entries": total, "id_base": 1,
                "identity": "LEGEND_ROOT_AND_ORDER_SCOPED_LOCAL_IDS_NOT_CANONICAL_CSIL",
                "custody_warning": "THIS_ARTIFACT_DISCLOSES_THE_SUPPLIED_LEGEND_VALUES",
            }
            digest = hashlib.sha256()
            with sio.open_output(pending, "wb") as handle:
                handle.write(canonical(header) + b"\n")
                stack_id = 0
                for ordinal, reader in enumerate(readers):
                    for local_id, value in reader.iter_values():
                        stack_id += 1
                        row = {"id": stack_id, "legend_ordinal": ordinal, "legend_local_id": local_id, "unit_hex": value.hex()}
                        raw = canonical(row) + b"\n"; handle.write(raw); digest.update(raw)
                footer = {"schema": "semcrys.legend-vocabulary-footer.v0.1", "entry_rows_sha256": digest.hexdigest(), "entries": stack_id}
                handle.write(canonical(footer) + b"\n")
            verify_vocabulary(pending, legends=legends, max_legend_bytes=max_legend_bytes)
            context.verify_used()
        sio.replace(pending, target)
    except BaseException:
        sio.unlink(pending, missing_ok=True)
        raise
    return {"schema": "semcrys.legend-vocabulary-result.v0.1", "status": "PASS", "standing": "CANDIDATE_ONLY",
            "output_sha256": file_sha256(target), "legend_roots": roots, "entries": total,
            "inverse_verified": True, "custody_warning": header["custody_warning"], "security_claim": "NONE"}


def _bounded_line(handle, limit: int, code: str) -> bytes:
    raw = handle.readline(limit + 1)
    if not raw or len(raw) > limit or not raw.endswith(b"\n"):
        raise Refusal(code)
    return raw


def verify_vocabulary(path: Path, *, legends: Sequence[Path], max_legend_bytes: int = 1024 * 1024 * 1024) -> dict:
    if not legends:
        raise Refusal("HELD_VOCABULARY_LEGEND_REQUIRED")
    with VerifiedLegendContext(max_legend_bytes=max_legend_bytes) as context:
        rows = context.rows(legends); _validate_lineage([row["path"] for row in rows]); context.stack(legends)
        readers = [context.reader(legend) for legend in legends]
        roots = [row["sha256"] for row in rows]; total = sum(reader.count for reader in readers)
        with Path(path).open("rb") as handle:
            try:
                raw_header = _bounded_line(handle, 1024 * 1024, "HELD_VOCABULARY_HEADER")
                header = json.loads(raw_header.decode("utf-8"))
            except (ValueError, UnicodeError) as exc:
                raise Refusal("HELD_VOCABULARY_HEADER") from exc
            if type(header) is not dict or raw_header != canonical(header) + b"\n" or header.get("schema") != VOCABULARY_SCHEMA or header.get("legend_roots") != roots or header.get("entries") != total:
                raise Refusal("HELD_VOCABULARY_HEADER")
            digest = hashlib.sha256(); stack_id = 0
            for ordinal, reader in enumerate(readers):
                for local_id, value in reader.iter_values():
                    raw = _bounded_line(handle, 2 * reader.max_value_bytes + 4096, "HELD_VOCABULARY_ROW")
                    try:
                        row = json.loads(raw.decode("utf-8"))
                    except (ValueError, UnicodeError) as exc:
                        raise Refusal("HELD_VOCABULARY_ROW") from exc
                    stack_id += 1
                    expected = {"id": stack_id, "legend_ordinal": ordinal, "legend_local_id": local_id, "unit_hex": value.hex()}
                    if row != expected or raw != canonical(row) + b"\n":
                        raise Refusal("HELD_VOCABULARY_INVERSE", str(stack_id))
                    digest.update(raw)
            try:
                raw_footer = _bounded_line(handle, 1024 * 1024, "HELD_VOCABULARY_FOOTER")
                footer = json.loads(raw_footer.decode("utf-8"))
            except (ValueError, UnicodeError) as exc:
                raise Refusal("HELD_VOCABULARY_FOOTER") from exc
            expected_footer = {"schema": "semcrys.legend-vocabulary-footer.v0.1", "entry_rows_sha256": digest.hexdigest(), "entries": stack_id}
            if footer != expected_footer or raw_footer != canonical(footer) + b"\n" or handle.read(1):
                raise Refusal("HELD_VOCABULARY_FOOTER")
        context.verify_used()
    return {"schema": "semcrys.legend-vocabulary-verification.v0.1", "status": "PASS", "standing": "CANDIDATE_ONLY",
            "vocabulary_sha256": file_sha256(Path(path)), "legend_roots": roots, "entries": total, "inverse_verified": True}


def capabilities() -> dict:
    return _rooted({
        "schema": "semcrys.gtk-adapter-capabilities.v0.1", "standing": "CANDIDATE_ONLY",
        "operations": ["ANALYZE_READ_ONLY", "EXPORT_EXPLICIT_VOCABULARY", "VERIFY_VOCABULARY"],
        "pathways": ["NL", "GCNL"], "sense_binding": ["NONE", "SENSE_KEYED"],
        "unresolved": {"HOLD": "FAIL_CLOSED", "SPINE": "EXPLICIT_GUESS_COUNTED_NOT_RESOLVED"},
        "force_csil": {"OFF": "SILENT_ANALYSIS_ONLY", "FLAG": "VISIBLE_REPORT", "HOLD": "REFUSE_UNKNOWN_LEXICAL_UNIT"},
        "normalization": "PROPOSAL_ONLY_NOT_PACKAGED_IN_THIS_BUILD; NO_SOURCE_MUTATION",
        "wire_exposure": "MEASURED_FROM_EXACT_LEGEND_STACK_NOT_INFERRED_FROM_GTK_COVERAGE",
        "custody": "SOURCE_SNAPSHOT_PLUS_EPHEMERAL_DISK_BACKED_VERIFIED_LEGEND_CONTEXT",
        "decision_scope": "TYPE_DEFAULTS_REUSABLE; OCCURRENCE_OVERRIDES_TOKENIZER_AND_SOURCE_BOUND",
        "identity": "GTK_BOUND_TERM_DISTINCT_FROM_LOCAL_TRANSPORT_ID_DISTINCT_FROM_MODEL_TOKEN_ID",
        "security_claim": "NONE", "canonical_mutation": False, "authority_effect": "NONE",
    }, "capability_root")
