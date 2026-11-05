from __future__ import annotations

import collections
import unittest

from semcrys_lite.core import (
    MAX_PADDED_EVENTS,
    OCC_HOMOPHONIC,
    OCC_UNIQUE,
    OCC_VISIBLE,
    PADDING_COUNT,
    PADDING_COUNT_AND_SIZE,
    PADDING_FIXED,
    PADDING_NONE,
    POSITION_CONCEAL,
    POSITION_PRESERVE,
    LiteHold,
    _decode_b64,
    _decode_body,
    _open_moving_legend,
    _position_index,
    _projection_subkeys,
    decode_bytes,
    deserialize_container,
    encode_bytes,
    rotate_protected_container,
)


KEY = b"0123456789abcdef0123456789abcdef"
NEW_KEY = b"fedcba9876543210fedcba9876543210"


class HomophonicProjection(unittest.TestCase):
    def test_balances_alias_frequency_and_round_trips(self):
        source = b"a" * 101 + b"b" * 13 + b"c" * 3
        container, _legend, moving, receipt = encode_bytes(
            source,
            occurrence_mode=OCC_HOMOPHONIC,
            alias_limit=7,
            key=KEY,
        )
        body = deserialize_container(container)
        events = body["body_b64"]
        self.assertIsInstance(events, str)
        restored, _ = decode_bytes(container, moving_legend=moving, key=KEY)
        self.assertEqual(restored, source)
        self.assertEqual(receipt["effective_instance_configuration"]["occurrence_mode"], OCC_HOMOPHONIC)

    def test_count_padding_exposes_only_bucket(self):
        source = b"abc" * 17
        container, _legend, moving, receipt = encode_bytes(
            source,
            occurrence_mode=OCC_HOMOPHONIC,
            alias_limit=4,
            key=KEY,
            padding_policy=PADDING_COUNT,
        )
        public = deserialize_container(container)
        self.assertEqual(public["event_count"], 64)
        self.assertIsNone(receipt["event_count"])
        self.assertIsNone(receipt["source_bytes"])
        self.assertEqual(receipt["public_event_count"], 64)
        self.assertEqual(receipt["receipt_visibility"], "PUBLIC_REDACTED")
        restored, _ = decode_bytes(container, moving_legend=moving, key=KEY)
        self.assertEqual(restored, source)

    def test_alias_namespace_is_not_monotonic_and_changes_per_encoding(self):
        source = b"a" * 101 + b"b" * 73 + b"c" * 41 + b"d" * 19
        first, _legend, first_moving, _receipt = encode_bytes(
            source, occurrence_mode=OCC_HOMOPHONIC, alias_limit=3, key=KEY,
        )
        second, _legend, second_moving, _receipt = encode_bytes(
            source, occurrence_mode=OCC_HOMOPHONIC, alias_limit=3, key=KEY,
        )
        first_public = deserialize_container(first)
        first_plaintext = _open_moving_legend(
            first_moving, key=KEY, binding=first_public["moving_legend_binding"]
        )
        mapping = sorted(
            (row["alias"], row["base"]) for row in first_plaintext["payload"]["alias_to_base"]
        )
        bases_in_public_alias_order = [base for _alias, base in mapping]
        self.assertNotEqual(bases_in_public_alias_order, sorted(bases_in_public_alias_order))
        self.assertNotEqual(_decode_body(first_public), _decode_body(deserialize_container(second)))

    def test_padding_is_fresh_and_interspersed(self):
        source = b"padding fixture" * 11
        first, _legend, first_moving, _receipt = encode_bytes(
            source, occurrence_mode=OCC_HOMOPHONIC, alias_limit=3, key=KEY,
            padding_policy=PADDING_COUNT,
        )
        second, _legend, _second_moving, _receipt = encode_bytes(
            source, occurrence_mode=OCC_HOMOPHONIC, alias_limit=3, key=KEY,
            padding_policy=PADDING_COUNT,
        )
        first_public = deserialize_container(first)
        second_public = deserialize_container(second)
        first_events = _decode_body(first_public)["events"]
        self.assertNotEqual(first_events, _decode_body(second_public)["events"])
        plaintext = _open_moving_legend(
            first_moving, key=KEY, binding=first_public["moving_legend_binding"]
        )
        payload = plaintext["payload"]
        self.assertEqual(payload["padding_layout"], "KEYED_FEISTEL_INTERSPERSED_V1")
        salt = _decode_b64(payload["projection_salt_b64"], "TEST")
        projection_root = _decode_b64(payload["projection_root_b64"], "TEST")
        position_key = _projection_subkeys(projection_root, salt)["position"]
        true_count = payload["true_event_count"]
        public_count = payload["public_event_count"]
        real_positions = {
            _position_index(index, public_count, position_key) for index in range(true_count)
        }
        filler_positions = set(range(public_count)) - real_positions
        self.assertNotEqual(filler_positions, set(range(true_count, public_count)))
        restored, _ = decode_bytes(first, moving_legend=first_moving, key=KEY)
        self.assertEqual(restored, source)

    def test_position_concealment_is_independent_of_padding(self):
        source = (b"alpha beta gamma delta " * 97) + b"omega"
        container, _legend, moving, receipt = encode_bytes(
            source,
            occurrence_mode=OCC_HOMOPHONIC,
            alias_limit=5,
            key=KEY,
            position_policy=POSITION_CONCEAL,
        )
        public = deserialize_container(container)
        plaintext = _open_moving_legend(
            moving, key=KEY, binding=public["moving_legend_binding"]
        )
        payload = plaintext["payload"]
        self.assertEqual(public["event_count"], len(source))
        self.assertEqual(public["padding_policy"], PADDING_NONE)
        self.assertEqual(public["position_policy"], POSITION_CONCEAL)
        self.assertEqual(payload["position_layout"], "KEYED_FEISTEL_PERMUTATION_V1")
        self.assertEqual(payload["padding_layout"], "NONE")
        self.assertEqual(
            receipt["effective_instance_configuration"]["position_policy"], POSITION_CONCEAL
        )
        restored, _ = decode_bytes(container, moving_legend=moving, key=KEY)
        self.assertEqual(restored, source)

    def test_preserved_position_remains_explicit(self):
        container, _legend, moving, _receipt = encode_bytes(
            b"position control" * 13,
            occurrence_mode=OCC_HOMOPHONIC,
            alias_limit=4,
            key=KEY,
            position_policy=POSITION_PRESERVE,
        )
        public = deserialize_container(container)
        plaintext = _open_moving_legend(
            moving, key=KEY, binding=public["moving_legend_binding"]
        )
        self.assertEqual(plaintext["payload"]["position_layout"], "NONE")
        self.assertEqual(public["verification"]["public_body_semantics"], "ALIASED_EVENT_ORDER")

    def test_position_concealment_refuses_nonaliased_modes(self):
        with self.assertRaises(LiteHold) as caught:
            encode_bytes(
                b"public", occurrence_mode=OCC_VISIBLE,
                position_policy=POSITION_CONCEAL,
            )
        self.assertEqual(caught.exception.code, "HELD_POSITION_REQUIRES_ALIASED_MODE")

    def test_padding_refuses_unprotected_mode(self):
        with self.assertRaises(LiteHold) as caught:
            encode_bytes(b"public", occurrence_mode=OCC_VISIBLE, padding_policy=PADDING_COUNT)
        self.assertEqual(caught.exception.code, "HELD_PADDING_REQUIRES_PROTECTED_MODE")


class UniquePaddingAndRotation(unittest.TestCase):
    def test_unique_mode_pads_count_and_sealed_plaintext(self):
        source = b"private payload" * 5
        container, _legend, moving, _receipt = encode_bytes(
            source,
            occurrence_mode=OCC_UNIQUE,
            key=KEY,
            padding_policy=PADDING_COUNT_AND_SIZE,
        )
        public = deserialize_container(container)
        self.assertGreaterEqual(public["event_count"], len(source))
        self.assertEqual(public["event_count"] & (public["event_count"] - 1), 0)
        self.assertGreater(moving["padded_plaintext_bytes"], 0)
        self.assertNotIn("content_plaintext_bytes", moving)
        restored, _ = decode_bytes(container, moving_legend=moving, key=KEY)
        self.assertEqual(restored, source)

    def test_padding_target_is_bounded(self):
        with self.assertRaisesRegex(LiteHold, "HELD_PADDING_TARGET_SIZE"):
            encode_bytes(
                b"bounded padding",
                occurrence_mode=OCC_HOMOPHONIC,
                alias_limit=2,
                key=KEY,
                padding_policy=PADDING_FIXED,
                padding_bucket=MAX_PADDED_EVENTS + 1,
            )

    def test_key_rotation_preserves_body_and_source(self):
        source = b"rotation fixture" * 20
        container, _legend, moving, _receipt = encode_bytes(
            source,
            occurrence_mode=OCC_HOMOPHONIC,
            alias_limit=3,
            key=KEY,
            padding_policy=PADDING_COUNT_AND_SIZE,
        )
        prior = deserialize_container(container)
        rotated, rotated_moving, rotation = rotate_protected_container(
            container, moving, old_key=KEY, new_key=NEW_KEY
        )
        after = deserialize_container(rotated)
        self.assertEqual(after["body_logical_sha256"], prior["body_logical_sha256"])
        self.assertEqual(after["body_carrier_sha256"], prior["body_carrier_sha256"])
        self.assertFalse(rotation["source_reencoded"])
        restored, _ = decode_bytes(rotated, moving_legend=rotated_moving, key=NEW_KEY)
        self.assertEqual(restored, source)
        with self.assertRaises(LiteHold):
            decode_bytes(rotated, moving_legend=rotated_moving, key=KEY)


if __name__ == "__main__":
    unittest.main()
