from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from . import __version__

ULTRA_ASSET_NAME = "ULTRA_FAMILY.mleg"
ULTRA_SHA256 = "e39a0067bd1285f521ece7b401edd827e2cca851a10fed2cec5df2fcdfd93e9a"
ULTRA_BYTES = 23632901
ULTRA_LEGEND_SHA256 = "4e837160f1d0f3ccf1d568e01592286dbe0d982f862f0191db1d570f7b36d6b4"
ULTRA_LEGEND_BYTES = 54102082


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def capabilities() -> dict[str, Any]:
    value = {
        "schema": "semcrys.core-capabilities.v0.2",
        "standing": "PUBLICATION_CANDIDATE",
        "version": __version__,
        "dialects": ["FULL_CRYS_0_2", "LITE_CRYS_0_3_BINARY", "LITE_CRYS_0_3_TEXT", "SEEKABLE_METALEGEND_0_1", "WHOLE_STREAM_METALEGEND_0_1", "PROTECTED_ARTIFACT_0_1"],
        "components": ["FULL_COMPILER", "LITE_REFERENCE_CODEC", "ULTRA_RECURSIVE_METALEGEND_ASSET", "DELTA_AND_LONGITUDINAL_LEGENDS", "GROUP_LEGENDS", "RECURSIVE_METALEGENDS", "PROFITABLE_INTEGERIZATION", "FULL_INTEGERIZATION", "PROFITABLE_SEPARATOR_CONSOLIDATION", "CALLER_ASSIGNED_SEMANTIC_BINDINGS", "KEYED_PERMUTATION", "FREQUENCY_BALANCED_HOMOPHONIC_PROJECTION", "INDEPENDENT_KEYED_POSITION_PROJECTION", "METADATA_PADDING", "PROTECTED_MOVING_LEGENDS", "PROTECTED_ARTIFACT_ENVELOPES", "OPTIONAL_NATIVE_BUFFER_KERNEL"],
        "base_runtime_dependencies": [],
        "native_acceleration": {
            "abi": "SEMCRYS_NATIVE_BUFFER_ABI_2",
            "policy": ["AUTO", "OFF", "REQUIRED"],
            "accelerated_operations": ["PACK_U63_VARINT", "UNPACK_U63_VARINT", "PARSE_PACKED_TOKEN_EVENTS", "FOLD_ASSEMBLY_PAIRS"],
            "pure_python_fallback": True,
            "container_bytes_invariant": True,
        },
        "secure_profile_dependencies": ["cryptography>=42"],
        "security_claim": "BOUNDED_IMPLEMENTED_PROFILE_NO_PROTOCOL_SECURITY_PROOF",
        "canonical_semantic_identity_effect": "NONE",
        "authority_effect": "NONE"
    }
    value["capability_root"] = hashlib.sha256(canonical(value)).hexdigest()
    return value


def profiles() -> dict[str, Any]:
    value = {
        "schema": "semcrys.core-profile-catalogue.v0.2",
        "profiles": {
            "compression": "MEASURED_PROFITABLE_CONFIGURATION",
            "integerization": "FULL_TOKEN_EVENT_INTEGER_COVERAGE",
            "group-legend": "RELATED_MULTI_DOCUMENT_EXACT_RECORD_POOLING",
            "metalegend": "ONE_LEVEL_LOGICAL_LEGEND_RECURSION_WITH_EXACT_INVERSE",
            "secure-permutation": "RELABELS_IDS_EQUALITY_REMAINS_VISIBLE",
            "secure-bounded": "BOUNDED_PUBLIC_RECURRENCE_PROTECTED_MOVING_LEGEND",
            "secure-homophonic": "PER_ENCODING_ALIAS_NAMESPACE_WITH_KEYED_FREQUENCY_BALANCED_SCHEDULE",
            "homophonic": "FREQUENCY_PROJECTION_ORDER_AND_EXACT_LENGTH_VISIBLE",
            "homophonic-positional": "FREQUENCY_AND_KEYED_POSITION_PROJECTION_EXACT_LENGTH_VISIBLE",
            "maximum-concealment": "FULL_UNIQUE_PROTECTED_STATE_WITH_COUNT_AND_SEALED_STATE_PADDING",
            "secure-full-unique": "EVENT_COUNT_CLASS_PUBLIC_ORDERED_SEQUENCE_PROTECTED",
            "private-balanced": "HOMOPHONIC_ALIASES_WITH_INTERSPERSED_COUNT_AND_SEALED_STATE_PADDING",
            "private-maximum": "FULL_UNIQUE_PROTECTED_STATE_WITH_COUNT_AND_SEALED_STATE_PADDING",
            "protected-artifact": "AEAD_ENVELOPE_WITH_ENCRYPTED_EXACT_SOURCE_METADATA_FOR_GROUP_LEGENDS_INDEXES_BESPOKE_LEGENDS_AND_METALEGENDS"
        },
        "authority_effect": "NONE"
    }
    value["catalogue_root"] = hashlib.sha256(canonical(value)).hexdigest()
    return value


def verify_self(asset_root: Path | None = None) -> dict[str, Any]:
    from semcrys.integrity import verify_self as verify_full
    from semcrys_native import runtime_status
    full = verify_full()
    if asset_root is None and os.environ.get("SEMCRYS_ULTRA_ASSET_ROOT"):
        asset_root = Path(os.environ["SEMCRYS_ULTRA_ASSET_ROOT"])
    ultra = None
    if asset_root is not None:
        path = asset_root / ULTRA_ASSET_NAME
        if not path.is_file():
            raise RuntimeError("HELD_ULTRA_ASSET_MISSING")
        data_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if data_hash != ULTRA_SHA256 or path.stat().st_size != ULTRA_BYTES:
            raise RuntimeError("HELD_ULTRA_ASSET_ROOT")
        from semcrys.metalegend import inspect as inspect_metalegend
        viewed = inspect_metalegend(path)
        configuration = viewed["configuration"]
        if (configuration["source_legend_sha256"] != ULTRA_LEGEND_SHA256
                or configuration["source_legend_bytes"] != ULTRA_LEGEND_BYTES):
            raise RuntimeError("HELD_ULTRA_LOGICAL_LEGEND_ROOT")
        ultra = {"asset": ULTRA_ASSET_NAME, "format": "SEEKABLE_METALEGEND_V1",
                 "sha256": data_hash, "bytes": path.stat().st_size,
                 "logical_legend_sha256": ULTRA_LEGEND_SHA256,
                 "logical_legend_bytes": ULTRA_LEGEND_BYTES}
    result = {
        "schema": "semcrys.core-self-verification.v0.2",
        "status": "PASS",
        "standing": full["standing"],
        "version": __version__,
        "full_component": full,
        "ultra": ultra,
        "ultra_verification": "PASS" if ultra else "NOT_REQUESTED",
        "native_runtime": runtime_status(),
        "authority_effect": "NONE"
    }
    result["verification_root"] = hashlib.sha256(canonical(result)).hexdigest()
    return result
