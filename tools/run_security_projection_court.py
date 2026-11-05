from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
from pathlib import Path

from semcrys.protected_artifact import ProtectedArtifactHold, inspect_bytes, protect_bytes, unprotect_bytes
from semcrys_lite.core import (
    OCC_HOMOPHONIC,
    OCC_UNIQUE,
    PADDING_COUNT,
    PADDING_COUNT_AND_SIZE,
    POSITION_CONCEAL,
    _decode_b64,
    _decode_body,
    _open_moving_legend,
    _position_index,
    _projection_subkeys,
    canonical_bytes,
    decode_bytes,
    deserialize_container,
    encode_bytes,
    rotate_protected_container,
)


ROOT = Path(__file__).resolve().parent.parent
KEY = b"semcrys-security-court-key-0001!"
NEW_KEY = b"semcrys-security-court-key-0002!"


def rooted(value, field):
    result = dict(value)
    result[field] = hashlib.sha256(canonical_bytes(result)).hexdigest()
    return result


def rank_correlation(pairs: list[tuple[int, int]]) -> float:
    if len(pairs) < 2:
        return 0.0
    def ranks(values: list[int]) -> list[float]:
        ordered = sorted(enumerate(values), key=lambda row: row[1])
        result = [0.0] * len(values)
        cursor = 0
        while cursor < len(ordered):
            end = cursor + 1
            while end < len(ordered) and ordered[end][1] == ordered[cursor][1]:
                end += 1
            rank = (cursor + end - 1) / 2.0
            for index in range(cursor, end):
                result[ordered[index][0]] = rank
            cursor = end
        return result
    left = ranks([row[0] for row in pairs])
    right = ranks([row[1] for row in pairs])
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    left_scale = sum((a - left_mean) ** 2 for a in left) ** 0.5
    right_scale = sum((b - right_mean) ** 2 for b in right) ** 0.5
    return numerator / (left_scale * right_scale) if left_scale and right_scale else 0.0


def context_mutual_information(values: list[int], context_width: int) -> float:
    if len(values) <= context_width:
        return 0.0
    pairs = [(tuple(values[index - context_width:index]), values[index])
             for index in range(context_width, len(values))]
    joint = collections.Counter(pairs)
    left = collections.Counter(row[0] for row in pairs)
    right = collections.Counter(row[1] for row in pairs)
    total = len(pairs)
    return sum(
        (count / total) * math.log2((count * total) / (left[context] * right[value]))
        for (context, value), count in joint.items()
    )


def deterministic_permutation(values: list[int], round_index: int) -> list[int]:
    return [
        value for _index, value in sorted(
            enumerate(values),
            key=lambda row: hashlib.sha256(
                b"semcrys-security-null-v1\x00"
                + round_index.to_bytes(2, "big")
                + row[0].to_bytes(8, "big")
            ).digest(),
        )
    ]


def null_upper_bound(values: list[int], context_width: int) -> float:
    return max(
        context_mutual_information(deterministic_permutation(values, round_index), context_width)
        for round_index in range(16)
    ) + 0.01


def public_base_sequence(container: bytes, moving: dict, key: bytes) -> tuple[list[int], dict]:
    public = deserialize_container(container)
    private = _open_moving_legend(moving, key=key, binding=public["moving_legend_binding"])["payload"]
    mapping = {row["alias"]: row["base"] for row in private["alias_to_base"]}
    return [mapping[value] for value in _decode_body(public)["events"]], private


def main() -> int:
    parser = argparse.ArgumentParser(description="Run bounded SemCrys security-projection qualification.")
    parser.add_argument("--output", type=Path, default=ROOT / "evidence/SECURITY-PROJECTION-COURT.json")
    args = parser.parse_args()

    source = bytes(range(20)) * 1000
    container, _legend, moving, receipt = encode_bytes(
        source,
        occurrence_mode=OCC_HOMOPHONIC,
        alias_limit=8,
        key=KEY,
    )
    public = deserialize_container(container)
    body = _decode_body(public)
    plaintext_moving = _open_moving_legend(moving, key=KEY, binding=public["moving_legend_binding"])
    mapping = {row["alias"]: row["base"] for row in plaintext_moving["payload"]["alias_to_base"]}
    alias_base_correlation = rank_correlation(sorted(mapping.items()))
    correlation_limit = max(0.03, 4.0 / math.sqrt(max(1, len(mapping) - 1)))
    by_base = collections.defaultdict(list)
    public_counts = collections.Counter(body["events"])
    for alias, base in mapping.items():
        by_base[base].append(public_counts[alias])
    balance_spread = max((max(counts) - min(counts) for counts in by_base.values()), default=0)
    restored, _ = decode_bytes(container, moving_legend=moving, key=KEY)

    control_sequence, _control_private = public_base_sequence(container, moving, KEY)
    positional, _pos_legend, positional_moving, positional_receipt = encode_bytes(
        source,
        occurrence_mode=OCC_HOMOPHONIC,
        alias_limit=8,
        key=KEY,
        position_policy=POSITION_CONCEAL,
    )
    positional_sequence, positional_private = public_base_sequence(
        positional, positional_moving, KEY
    )
    positional_restored, _ = decode_bytes(
        positional, moving_legend=positional_moving, key=KEY
    )
    control_bigram_mi = context_mutual_information(control_sequence, 1)
    positional_bigram_mi = context_mutual_information(positional_sequence, 1)
    positional_trigram_mi = context_mutual_information(positional_sequence, 2)
    positional_bigram_null = null_upper_bound(positional_sequence, 1)
    positional_trigram_null = null_upper_bound(positional_sequence, 2)

    count_classes = []
    for size in (73, 94):
        candidate, _external, candidate_moving, _receipt = encode_bytes(
            b"x" * size,
            occurrence_mode=OCC_UNIQUE,
            key=KEY,
            padding_policy=PADDING_COUNT,
        )
        viewed = deserialize_container(candidate)
        recovered, _ = decode_bytes(candidate, moving_legend=candidate_moving, key=KEY)
        count_classes.append({"source_bytes": size, "public_event_count": viewed["event_count"],
                              "exact_inverse": recovered == b"x" * size})

    first, _e1, first_moving, first_receipt = encode_bytes(
        source, occurrence_mode=OCC_HOMOPHONIC, alias_limit=8, key=KEY,
        padding_policy=PADDING_COUNT_AND_SIZE,
    )
    second, _e2, second_moving, _r2 = encode_bytes(
        source, occurrence_mode=OCC_HOMOPHONIC, alias_limit=8, key=KEY,
        padding_policy=PADDING_COUNT_AND_SIZE,
    )
    rotated, rotated_moving, rotation = rotate_protected_container(
        first, first_moving, old_key=KEY, new_key=NEW_KEY
    )
    rotated_source, _ = decode_bytes(rotated, moving_legend=rotated_moving, key=NEW_KEY)
    first_public = deserialize_container(first)
    second_public = deserialize_container(second)
    first_body = _decode_body(first_public)
    second_body = _decode_body(second_public)
    first_private = _open_moving_legend(
        first_moving, key=KEY, binding=first_public["moving_legend_binding"]
    )["payload"]
    projection_salt = _decode_b64(first_private["projection_salt_b64"], "COURT_PROJECTION_SALT")
    projection_root = _decode_b64(first_private["projection_root_b64"], "COURT_PROJECTION_ROOT")
    position_key = _projection_subkeys(projection_root, projection_salt)["position"]
    true_count = first_private["true_event_count"]
    public_count = first_private["public_event_count"]
    real_positions = {_position_index(index, public_count, position_key) for index in range(true_count)}
    filler_positions = set(range(public_count)) - real_positions
    tail_positions = set(range(true_count, public_count))
    first_mapping = {row["alias"]: row["base"] for row in first_private["alias_to_base"]}
    padded_sequence = [first_mapping[value] for value in first_body["events"]]
    padded_bigram_mi = context_mutual_information(padded_sequence, 1)
    padded_bigram_null = null_upper_bound(padded_sequence, 1)

    artifact = b"group-legend-fixture" * 128
    envelope, protected_receipt = protect_bytes(artifact, key=KEY, role="GROUP_LEGEND_ARCHIVE")
    protected_inspection = inspect_bytes(envelope)
    second_envelope, _ = protect_bytes(artifact, key=KEY, role="GROUP_LEGEND_ARCHIVE")
    second_inspection = inspect_bytes(second_envelope)
    artifact_inverse, _ = unprotect_bytes(envelope, key=KEY)
    tampered = bytearray(envelope)
    tampered[-1] ^= 1
    tamper_refused = False
    try:
        unprotect_bytes(bytes(tampered), key=KEY)
    except ProtectedArtifactHold:
        tamper_refused = True

    gates = {
        "homophonic_exact_inverse": restored == source,
        "homophonic_alias_max_at_most_declared_limit": max(public_counts.values(), default=0) <= 8,
        "homophonic_per_base_frequency_spread_at_most_one": balance_spread <= 1,
        "alias_identifier_base_rank_correlation_within_sample_adjusted_four_sigma": abs(alias_base_correlation) < correlation_limit,
        "position_only_exact_inverse": positional_restored == source,
        "position_only_preserves_exact_public_length": positional_receipt["public_event_count"] == len(source),
        "position_only_layout_is_explicit": positional_private["position_layout"] == "KEYED_FEISTEL_PERMUTATION_V1",
        "ordered_control_has_detectable_bigram_structure": control_bigram_mi > positional_bigram_null * 4,
        "position_only_bigram_mi_within_deterministic_null_bound": positional_bigram_mi <= positional_bigram_null,
        "position_only_trigram_mi_within_deterministic_null_bound": positional_trigram_mi <= positional_trigram_null,
        "padded_position_bigram_mi_within_deterministic_null_bound": padded_bigram_mi <= padded_bigram_null,
        "count_bucket_hides_distinction_within_class": count_classes[0]["public_event_count"] == count_classes[1]["public_event_count"] == 128,
        "count_bucket_exact_inverse": all(row["exact_inverse"] for row in count_classes),
        "same_plaintext_public_container_randomized": first != second,
        "same_plaintext_public_event_body_randomized": first_body["events"] != second_body["events"],
        "same_plaintext_protected_state_randomized": first_moving["sealed_legend_root"] != second_moving["sealed_legend_root"],
        "padding_filler_not_appended_as_tail": bool(filler_positions) and filler_positions != tail_positions,
        "protected_receipt_redacts_exact_source_metrics": protected_receipt["source_sha256"] is None and protected_receipt["source_bytes"] is None,
        "lite_receipt_redacts_exact_source_metrics": first_receipt["event_count"] is None and first_receipt["source_bytes"] is None,
        "sealed_moving_header_hides_unpadded_plaintext_size": "content_plaintext_bytes" not in first_moving,
        "protected_header_hides_source_length_and_digest": "source_bytes" not in protected_inspection and "source_sha256" not in protected_inspection,
        "same_key_protected_artifacts_have_unlinkable_key_identifiers": protected_inspection["key_identifier"] != second_inspection["key_identifier"],
        "key_rotation_does_not_reencode_source": rotation["source_reencoded"] is False,
        "key_rotation_exact_inverse": rotated_source == source,
        "protected_group_artifact_exact_inverse": artifact_inverse == artifact,
        "protected_group_artifact_tamper_refused": tamper_refused,
    }
    result = {
        "schema": "semcrys.security-projection-court.v0.1",
        "status": "PASS" if all(gates.values()) else "FAIL",
        "standing": "BUILDER_QUALIFICATION_NOT_INDEPENDENT_CRYPTOANALYSIS",
        "homophonic": {
            "source_events": len(source),
            "public_events": receipt["public_event_count"],
            "aliases": len(public_counts),
            "maximum_public_alias_frequency": max(public_counts.values(), default=0),
            "maximum_within_base_frequency_spread": balance_spread,
            "alias_count": len(mapping),
            "rank_correlation_gate": "ABS_LT_MAX_0_03_OR_FOUR_OVER_SQRT_N_MINUS_ONE",
            "alias_identifier_base_rank_correlation_class": (
                "WITHIN_SAMPLE_ADJUSTED_FOUR_SIGMA"
                if abs(alias_base_correlation) < correlation_limit
                else "OUTSIDE_SAMPLE_ADJUSTED_FOUR_SIGMA"
            ),
            "position_and_cooccurrence_concealed": False,
        },
        "position_projection": {
            "independent_of_padding": True,
            "exact_length_still_visible_without_padding": True,
            "fixture": "TWENTY_SYMBOL_ORDERED_CYCLE_20000_EVENTS",
            "bigram_gate": "CANDIDATE_MI_AT_OR_BELOW_MAX_OF_16_DETERMINISTIC_NULLS_PLUS_0_01_BITS",
            "trigram_gate": "CANDIDATE_MI_AT_OR_BELOW_MAX_OF_16_DETERMINISTIC_NULLS_PLUS_0_01_BITS",
            "measured_claim": "ORDER_AND_COOCCURRENCE_WITHIN_TESTED_FIXTURE_AND_ATTACK_METRICS",
        },
        "metadata_padding": {"count_classes": count_classes, "length_class_still_visible": True},
        "protected_artifact": {
            "role": protected_receipt["role"],
            "source_metadata_public": False,
            "envelope_bytes": protected_receipt["envelope_bytes"],
        },
        "gates": gates,
        "claim_boundary": {
            "security_claim": "NONE",
            "formal_security_proof": False,
            "independent_cryptanalysis": False,
            "traffic_analysis_resistance": False,
            "compression_side_channel_resistance": False,
            "position_claim_scope": "TESTED_FIXTURE_METRICS_NOT_UNIVERSAL_CONCEALMENT_PROOF",
        },
        "authority_effect": "NONE",
    }
    result = rooted(result, "court_root")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": result["status"], "court_root": result["court_root"], "gates": gates}, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
