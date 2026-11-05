"""Phase L.ENV gate: dual envelope, binary default, text optional.

One logical container, two serializations. container_root must be identical in
both, and decode must accept either without being told which.
"""
from __future__ import annotations

import unittest

from semcrys_lite.core import (
    BODY_PACKED_VARINT,
    CONTAINER_MAGIC,
    ENVELOPE_BINARY,
    ENVELOPE_TEXT,
    PROFILE_LOCAL,
    PROFILE_WORD,
    LiteHold,
    build_word_legend,
    decode_bytes,
    deserialize_container,
    encode_bytes,
    explain_container,
    inspect_container,
    serialize_container,
)

TEXT = b"the cat sat on the mat and the cat sat again. " * 30


class EnvelopeEquivalence(unittest.TestCase):
    def setUp(self):
        self.legend = build_word_legend(TEXT)

    def _encode(self, envelope, **kwargs):
        return encode_bytes(
            TEXT, profile=PROFILE_WORD, legend=self.legend, legend_placement="EXTERNAL",
            envelope=envelope, **kwargs,
        )

    def test_both_envelopes_round_trip(self):
        for envelope in (ENVELOPE_BINARY, ENVELOPE_TEXT):
            for representation in ("JSON_EVENTS", BODY_PACKED_VARINT):
                for outer in ("NONE", "LZMA"):
                    with self.subTest(envelope=envelope, body=representation, outer=outer):
                        container, _e, moving, _r = self._encode(
                            envelope, body_representation=representation, outer_codec=outer
                        )
                        restored, _ = decode_bytes(container, legend=self.legend, moving_legend=moving)
                        self.assertEqual(restored, TEXT)

    def test_container_root_is_envelope_independent(self):
        roots = {
            deserialize_container(self._encode(envelope)[0])["container_root"]
            for envelope in (ENVELOPE_BINARY, ENVELOPE_TEXT)
        }
        self.assertEqual(len(roots), 1)

    def test_logical_container_is_identical_across_envelopes(self):
        binary = deserialize_container(self._encode(ENVELOPE_BINARY)[0])
        text = deserialize_container(self._encode(ENVELOPE_TEXT)[0])
        self.assertEqual(binary, text)

    def test_reserialising_between_envelopes_preserves_meaning(self):
        container, _e, _m, _r = self._encode(ENVELOPE_BINARY, body_representation=BODY_PACKED_VARINT, outer_codec="LZMA")
        as_text = serialize_container(deserialize_container(container), ENVELOPE_TEXT)
        self.assertEqual(
            decode_bytes(as_text, legend=self.legend)[0],
            decode_bytes(container, legend=self.legend)[0],
        )

    def test_binary_is_the_default(self):
        container, _e, _m, receipt = encode_bytes(
            TEXT, profile=PROFILE_WORD, legend=self.legend, legend_placement="EXTERNAL"
        )
        self.assertTrue(container.startswith(CONTAINER_MAGIC))
        self.assertEqual(receipt["effective_instance_configuration"]["envelope"], ENVELOPE_BINARY)

    def test_text_envelope_has_no_magic_and_stays_readable(self):
        container, _e, _m, _r = encode_bytes(b"abc", profile="L:BYTE_DIRECT", envelope=ENVELOPE_TEXT, body_representation="JSON_EVENTS")
        self.assertFalse(container.startswith(CONTAINER_MAGIC))
        self.assertIn('"events":[97,98,99]', container.decode("utf-8"))

    def test_binary_is_smaller_for_packed_bodies(self):
        common = dict(body_representation=BODY_PACKED_VARINT, outer_codec="LZMA")
        self.assertLess(
            len(self._encode(ENVELOPE_BINARY, **common)[0]),
            len(self._encode(ENVELOPE_TEXT, **common)[0]),
        )

    def test_inspect_and_explain_accept_either_envelope(self):
        for envelope in (ENVELOPE_BINARY, ENVELOPE_TEXT):
            with self.subTest(envelope=envelope):
                container, _e, _m, _r = self._encode(envelope)
                self.assertEqual(inspect_container(container)["profile"], PROFILE_WORD)
                self.assertIn("where_are_the_bytes", explain_container(container))

    def test_receipt_container_bytes_matches_the_serialized_artifact(self):
        for envelope in (ENVELOPE_BINARY, ENVELOPE_TEXT):
            with self.subTest(envelope=envelope):
                container, _e, _m, receipt = self._encode(envelope)
                self.assertEqual(receipt["container_bytes"], len(container))


class Refusals(unittest.TestCase):
    def test_unknown_envelope_refuses(self):
        with self.assertRaises(LiteHold) as ctx:
            encode_bytes(TEXT, profile=PROFILE_LOCAL, envelope="PROTOBUF")
        self.assertEqual(ctx.exception.code, "HELD_ENVELOPE_UNSUPPORTED")

    def test_truncated_binary_container_refuses(self):
        container, _e, _m, _r = encode_bytes(TEXT, profile=PROFILE_LOCAL, envelope=ENVELOPE_BINARY)
        with self.assertRaises(LiteHold) as ctx:
            decode_bytes(container[:-5])
        self.assertEqual(ctx.exception.code, "HELD_CONTAINER_BINARY_TRUNCATED")

    def test_magic_without_lengths_refuses(self):
        with self.assertRaises(LiteHold) as ctx:
            decode_bytes(CONTAINER_MAGIC)
        self.assertEqual(ctx.exception.code, "HELD_CONTAINER_BINARY_TRUNCATED")

    def test_binary_payload_tamper_refuses(self):
        legend = build_word_legend(TEXT)
        container, _e, _m, _r = encode_bytes(
            TEXT, profile=PROFILE_WORD, legend=legend, legend_placement="EXTERNAL",
            body_representation=BODY_PACKED_VARINT, outer_codec="LZMA", envelope=ENVELOPE_BINARY,
        )
        broken = bytearray(container)
        broken[-3] ^= 0xFF
        with self.assertRaises(LiteHold):
            decode_bytes(bytes(broken), legend=legend)


if __name__ == "__main__":
    unittest.main()
