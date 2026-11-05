from __future__ import annotations

import collections
import json
from typing import Any

from .core import (
    OCC_BOUNDED,
    OCC_PERMUTE,
    OCC_UNIQUE,
    OCC_VISIBLE,
    OUTER_LZMA,
    OUTER_NONE,
    PROFILE_DIRECT,
    STANDING,
    canonical_bytes,
    encode_bytes,
    inspect_container,
    rooted,
)


DEMO_PHRASE = b"the cat and the dog saw the cat. "
DEMO_SOURCE = (DEMO_PHRASE * 8).rstrip()
DEMO_KEY = b"SemCrys-Lite tutorial key only!!"


def _row(data: bytes, *, label: str, occurrence: str, outer: str, key: bytes | None = None, alias_limit: int = 1) -> dict[str, Any]:
    container, base, moving, receipt = encode_bytes(
        data,
        profile=PROFILE_DIRECT,
        occurrence_mode=occurrence,
        outer_codec=outer,
        key=key,
        alias_limit=alias_limit,
    )
    visible = inspect_container(container, include_body=True)
    body = visible["body"]
    events = body.get("events", []) if isinstance(body, dict) else []
    counts = collections.Counter(events)
    return {
        "label": label,
        "profile": PROFILE_DIRECT,
        "occurrence_mode": occurrence,
        "outer_codec": outer,
        "source_bytes": len(data),
        "container_bytes": len(container),
        "base_legend_bytes": len(canonical_bytes(base)) + 1 if base else 0,
        "moving_legend_bytes": len(canonical_bytes(moving)) + 1 if moving else 0,
        "public_body_kind": body.get("kind"),
        "public_distinct_event_ids": len(counts),
        "maximum_public_repetition": max(counts.values(), default=0),
        "public_equality_preserved": visible["verification"].get("public_equality_preserved"),
        "ordered_reconstruction_location": "PUBLIC_BODY" if moving is None else "SEALED_MOVING_LEGEND",
        "size_advisory": receipt["size_advisory"],
    }


def compare_bytes(data: bytes, *, key: bytes | None = None) -> dict[str, Any]:
    rows = [
        _row(data, label="TRANSPARENT_REFERENCE", occurrence=OCC_VISIBLE, outer=OUTER_NONE),
        _row(data, label="COMPACT_REFERENCE", occurrence=OCC_VISIBLE, outer=OUTER_LZMA),
    ]
    for label, mode, alias_limit in (
        ("KEYED_PERMUTATION", OCC_PERMUTE, 1),
        ("BOUNDED_ALIAS_2", OCC_BOUNDED, 2),
        ("FULL_UNIQUE", OCC_UNIQUE, 1),
    ):
        if key is None:
            rows.append({
                "label": label,
                "occurrence_mode": mode,
                "status": "HELD_KEY_REQUIRED_FOR_COMPARISON",
                "security_claim": "NONE",
            })
        else:
            rows.append(_row(data, label=label, occurrence=mode, outer=OUTER_NONE, key=key, alias_limit=alias_limit))
    return rooted({
        "schema": "semcrys-lite.configuration-comparison.v0.1.candidate",
        "standing": STANDING,
        "source_bytes": len(data),
        "rows": rows,
        "interpretation": {
            "transparent_reference": "DIRECT_JSON_IS_FOR_INSPECTION_NOT_MINIMUM_BYTES",
            "compact_reference": "LZMA_CHANGES_CARRIER_NOT_SEMANTIC_EVENT_MODEL",
            "concealment_rows": "MEASURED_PROJECTIONS_NOT_CONFIDENTIALITY_PROOF",
        },
        "security_claim": "NONE",
    }, "comparison_root")


def demo_report() -> dict[str, Any]:
    comparison = compare_bytes(DEMO_SOURCE, key=DEMO_KEY)
    return rooted({
        "schema": "semcrys-lite.guided-demonstration.v0.1.candidate",
        "standing": STANDING,
        "fixture": {
            "text_preview": DEMO_PHRASE.decode("ascii").rstrip(),
            "repeat_count": 8,
            "source_bytes": len(DEMO_SOURCE),
            "tutorial_key": "FIXED_NON_SECRET_DEMONSTRATION_FIXTURE_ONLY",
        },
        "lesson": [
            "BYTE_DIRECT maps each source byte to an integer event.",
            "JSON_DIRECT leaves those events visible so the transform can be audited.",
            "LZMA compresses the same logical event body without changing its meaning.",
            "KEYED_PERMUTATION changes labels but preserves equality and repetition.",
            "BOUNDED_ALIAS limits public repetition and moves recovery data into a sealed companion.",
            "FULL_UNIQUE leaves only event count in the public body and moves ordered reconstruction into the sealed companion.",
        ],
        "comparison": comparison,
        "questions": [
            "Which equality relationships remain public?",
            "Where did the information needed for exact reconstruction move?",
            "Which bytes are format overhead rather than source representation?",
            "Which result is a measurement and which would require an independent security court?",
        ],
        "security_claim": "NONE",
    }, "demonstration_root")


def demo_json() -> bytes:
    return canonical_bytes(demo_report()) + b"\n"


def comparison_json(data: bytes, *, key: bytes | None = None) -> bytes:
    return canonical_bytes(compare_bytes(data, key=key)) + b"\n"


def body_text(data: bytes) -> str:
    return json.dumps(inspect_container(data, include_body=True)["body"], ensure_ascii=False, sort_keys=True, indent=2)
