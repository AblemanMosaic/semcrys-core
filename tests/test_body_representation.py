"""Phase L.BV gate: packed varint body representation.

The logical body is the same events either way, so the logical digest must be
carrier-independent and both carriers must restore identically.
"""
from __future__ import annotations

import json
import unittest

from semcrys_lite.core import (
    deserialize_container,
    serialize_container,
    ENVELOPE_TEXT,
    BODY_JSON_EVENTS,
    BODY_PACKED_VARINT,
    PROFILE_LOCAL,
    PROFILE_WORD,
    LiteHold,
    _pack_varints,
    _unpack_varints,
    build_word_legend,
    decode_bytes,
    encode_bytes,
)

TEXT = (b"the cat sat on the mat and the cat sat again. " * 40)


class VarintCodec(unittest.TestCase):
    def test_round_trips_edge_values(self):
        values = [0, 1, 127, 128, 129, 16383, 16384, 2 ** 31, 2 ** 62]
        self.assertEqual(_unpack_varints(_pack_varints(values)), values)

    def test_empty(self):
        self.assertEqual(_unpack_varints(_pack_varints([])), [])

    def test_truncated_stream_refuses(self):
        with self.assertRaises(LiteHold) as ctx:
            _unpack_varints(b"\x80")
        self.assertEqual(ctx.exception.code, "HELD_BODY_VARINT_TRUNCATED")

    def test_overlong_stream_refuses(self):
        with self.assertRaises(LiteHold) as ctx:
            _unpack_varints(b"\x80" * 12 + b"\x01")
        self.assertEqual(ctx.exception.code, "HELD_BODY_VARINT_OVERLONG")

    def test_negative_refuses(self):
        with self.assertRaises(LiteHold) as ctx:
            _pack_varints([-1])
        self.assertEqual(ctx.exception.code, "HELD_BODY_VARINT_RANGE")


class CarrierEquivalence(unittest.TestCase):
    def setUp(self):
        self.legend = build_word_legend(TEXT)

    def _encode(self, representation, outer):
        return encode_bytes(
            TEXT, profile=PROFILE_WORD, legend=self.legend, legend_placement="EXTERNAL",
            outer_codec=outer, body_representation=representation,
        )

    def test_both_carriers_round_trip(self):
        for representation in (BODY_JSON_EVENTS, BODY_PACKED_VARINT):
            for outer in ("NONE", "LZMA"):
                with self.subTest(representation=representation, outer=outer):
                    container, _e, moving, _r = self._encode(representation, outer)
                    restored, _ = decode_bytes(container, legend=self.legend, moving_legend=moving)
                    self.assertEqual(restored, TEXT)

    def test_logical_digest_is_carrier_independent(self):
        digests = set()
        for representation in (BODY_JSON_EVENTS, BODY_PACKED_VARINT):
            for outer in ("NONE", "LZMA"):
                container, _e, _m, _r = self._encode(representation, outer)
                digests.add(deserialize_container(container)["body_logical_sha256"])
        self.assertEqual(len(digests), 1)

    def test_representation_is_recorded(self):
        container, _e, _m, receipt = self._encode(BODY_PACKED_VARINT, "LZMA")
        self.assertEqual(deserialize_container(container)["body_representation"], BODY_PACKED_VARINT)
        self.assertEqual(
            receipt["effective_instance_configuration"]["body_representation_effective"], BODY_PACKED_VARINT
        )

    def test_packed_is_smaller_than_json(self):
        for outer in ("NONE", "LZMA"):
            with self.subTest(outer=outer):
                self.assertLess(
                    len(self._encode(BODY_PACKED_VARINT, outer)[0]),
                    len(self._encode(BODY_JSON_EVENTS, outer)[0]),
                )

    def test_packed_is_the_default(self):
        container, _e, _m, _r = encode_bytes(
            TEXT, profile=PROFILE_WORD, legend=self.legend, legend_placement="EXTERNAL"
        )
        self.assertEqual(deserialize_container(container)["body_representation"], BODY_PACKED_VARINT)

    def test_byte_profile_supports_packed_too(self):
        container, external, moving, _r = encode_bytes(
            bytes(range(256)) * 8, profile=PROFILE_LOCAL, body_representation=BODY_PACKED_VARINT,
        )
        restored, _ = decode_bytes(container, legend=external, moving_legend=moving)
        self.assertEqual(restored, bytes(range(256)) * 8)


class Refusals(unittest.TestCase):
    def test_range_body_falls_back_to_json_and_declares_it(self):
        # FULL_UNIQUE produces a RANGE body with no events array. There is
        # nothing to pack, so the fallback is taken and recorded on both sides
        # rather than refused or applied silently.
        container, _e, _m, receipt = encode_bytes(
            TEXT, profile=PROFILE_WORD, legend=build_word_legend(TEXT),
            legend_placement="EXTERNAL", occurrence_mode="FULL_UNIQUE_MESSAGE_LEGEND",
            key=b"0123456789abcdef0123456789abcdef", body_representation=BODY_PACKED_VARINT,
        )
        self.assertEqual(deserialize_container(container)["body_representation"], BODY_JSON_EVENTS)
        config = receipt["effective_instance_configuration"]
        self.assertEqual(config["body_representation_requested"], BODY_PACKED_VARINT)
        self.assertEqual(config["body_representation_effective"], BODY_JSON_EVENTS)

    def test_unknown_representation_refuses(self):
        with self.assertRaises(LiteHold) as ctx:
            encode_bytes(TEXT, profile=PROFILE_WORD, body_representation="PROTOBUF")
        self.assertEqual(ctx.exception.code, "HELD_BODY_REPRESENTATION_UNSUPPORTED")

    def test_tampered_packed_carrier_refuses(self):
        legend = build_word_legend(TEXT)
        container, _e, _m, _r = encode_bytes(
            TEXT, profile=PROFILE_WORD, legend=legend, legend_placement="EXTERNAL",
            body_representation=BODY_PACKED_VARINT,
        )
        value = deserialize_container(container)
        first = value["body_b64"][0]
        value["body_b64"] = ("B" if first == "A" else "A") + value["body_b64"][1:]
        with self.assertRaises(LiteHold):
            decode_bytes(serialize_container(value, ENVELOPE_TEXT), legend=legend)


if __name__ == "__main__":
    unittest.main()
