from __future__ import annotations

import hashlib
import json
from typing import Any

from semcrys_lite.core import tokenize_text


class SemanticRefusal(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def root(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise SemanticRefusal(code)


def build_registry(entries: list[dict[str, Any]]) -> dict[str, Any]:
    _require(isinstance(entries, list), "HELD_SEMANTIC_ENTRIES")
    normalized = []
    seen_ids: set[int] = set()
    seen_keys: set[str] = set()
    for row in entries:
        _require(isinstance(row, dict), "HELD_SEMANTIC_ENTRY")
        identifier = row.get("integer_id")
        key = row.get("semantic_key")
        surface = row.get("surface")
        _require(isinstance(identifier, int) and identifier > 0, "HELD_SEMANTIC_INTEGER_ID")
        _require(isinstance(key, str) and key, "HELD_SEMANTIC_KEY")
        _require(isinstance(surface, str) and surface, "HELD_SEMANTIC_SURFACE")
        _require(identifier not in seen_ids, "HELD_SEMANTIC_INTEGER_DUPLICATE")
        _require(key not in seen_keys, "HELD_SEMANTIC_KEY_DUPLICATE")
        seen_ids.add(identifier)
        seen_keys.add(key)
        normalized.append({"integer_id": identifier, "semantic_key": key, "surface": surface})
    normalized.sort(key=lambda row: row["integer_id"])
    value = {
        "schema": "semcrys.semantic-key-registry.v0.1.candidate",
        "standing": "CALLER_ASSIGNED_NO_CANONICAL_IDENTITY_EFFECT",
        "entries": normalized,
        "entry_count": len(normalized)
    }
    value["registry_root"] = root(value)
    return value


def validate_registry(value: dict[str, Any]) -> str:
    _require(value.get("schema") == "semcrys.semantic-key-registry.v0.1.candidate", "HELD_SEMANTIC_REGISTRY_SCHEMA")
    claimed = value.get("registry_root")
    subject = dict(value)
    subject.pop("registry_root", None)
    _require(isinstance(claimed, str) and claimed == root(subject), "HELD_SEMANTIC_REGISTRY_ROOT")
    rebuilt = build_registry(value.get("entries"))
    _require(rebuilt["registry_root"] == claimed, "HELD_SEMANTIC_REGISTRY_CONTENT")
    return claimed


def integerize(data: bytes, registry: dict[str, Any], bindings: dict[str, str] | None = None) -> dict[str, Any]:
    registry_root = validate_registry(registry)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SemanticRefusal("HELD_SEMANTIC_SOURCE_NOT_UTF8") from error
    tokens = [token for _kind, token in tokenize_text(text)]
    bindings = bindings or {}
    _require(isinstance(bindings, dict), "HELD_OCCURRENCE_BINDINGS")
    by_key = {row["semantic_key"]: row for row in registry["entries"]}
    by_surface: dict[str, list[dict[str, Any]]] = {}
    for row in registry["entries"]:
        by_surface.setdefault(row["surface"], []).append(row)

    selected: list[dict[str, Any] | None] = []
    local_values: set[str] = set()
    explicit_count = 0
    for index, token in enumerate(tokens):
        requested = bindings.get(str(index))
        if requested is not None:
            row = by_key.get(requested)
            _require(row is not None and row["surface"] == token, "HELD_OCCURRENCE_BINDING_MISMATCH")
            selected.append(row)
            explicit_count += 1
        else:
            candidates = by_surface.get(token, [])
            row = candidates[0] if len(candidates) == 1 else None
            selected.append(row)
            if row is None:
                local_values.add(token)

    local_order = sorted(local_values)
    local_ids = {token: index + 1 for index, token in enumerate(local_order)}
    events = [[0, row["integer_id"]] if row is not None else [1, local_ids[token]] for token, row in zip(tokens, selected)]
    value = {
        "schema": "semcrys.semantic-integer-stream.v0.1.candidate",
        "standing": "CANDIDATE_ONLY_NO_CANONICAL_IDENTITY_EFFECT",
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "source_bytes": len(data),
        "registry_root": registry_root,
        "namespace_codes": {"0": "CALLER_ASSIGNED_SEMANTIC", "1": "DOCUMENT_LOCAL_LITERAL"},
        "local_legend": [{"integer_id": index + 1, "text": token} for index, token in enumerate(local_order)],
        "events": events,
        "event_count": len(events),
        "semantic_event_count": sum(1 for row in selected if row is not None),
        "explicit_occurrence_binding_count": explicit_count,
        "full_integer_coverage": True
    }
    value["stream_root"] = root(value)
    return value


def restore(stream: dict[str, Any], registry: dict[str, Any]) -> bytes:
    registry_root = validate_registry(registry)
    _require(stream.get("schema") == "semcrys.semantic-integer-stream.v0.1.candidate", "HELD_SEMANTIC_STREAM_SCHEMA")
    claimed = stream.get("stream_root")
    subject = dict(stream)
    subject.pop("stream_root", None)
    _require(isinstance(claimed, str) and claimed == root(subject), "HELD_SEMANTIC_STREAM_ROOT")
    _require(stream.get("registry_root") == registry_root, "HELD_SEMANTIC_REGISTRY_MISMATCH")
    semantic = {row["integer_id"]: row["surface"] for row in registry["entries"]}
    local = {row["integer_id"]: row["text"] for row in stream.get("local_legend", [])}
    tokens = []
    for event in stream.get("events", []):
        _require(isinstance(event, list) and len(event) == 2, "HELD_SEMANTIC_EVENT")
        namespace, identifier = event
        table = semantic if namespace == 0 else local if namespace == 1 else None
        _require(table is not None and identifier in table, "HELD_SEMANTIC_EVENT_REFERENCE")
        tokens.append(table[identifier])
    data = "".join(tokens).encode("utf-8")
    _require(hashlib.sha256(data).hexdigest() == stream.get("source_sha256"), "HELD_SEMANTIC_SOURCE_ROOT")
    return data
