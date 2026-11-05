from __future__ import annotations

import unittest

from semcrys_lite.core import (
    PROFILE_WORD,
    PROFILE_WORD_AUTO_SPACE,
    PROFILE_WORD_IMPLICIT_SPACE,
    decode_bytes,
    encode_bytes,
)


class SeparatorConsolidationTests(unittest.TestCase):
    def test_single_spaces_between_words_are_implicit_and_exact(self):
        source = (b"alpha beta gamma delta " * 200).rstrip()
        explicit, _explicit_legend, _explicit_moving, explicit_receipt = encode_bytes(source, profile=PROFILE_WORD)
        compact, _legend, _moving, receipt = encode_bytes(source, profile=PROFILE_WORD_AUTO_SPACE)
        restored, _ = decode_bytes(compact)
        self.assertEqual(restored, source)
        self.assertLess(receipt["event_count"], explicit_receipt["event_count"])
        self.assertLess(len(compact), len(explicit))

    def test_auto_keeps_explicit_control_when_complete_delivery_is_smaller(self):
        source = b"alpha beta"
        explicit, *_ = encode_bytes(source, profile=PROFILE_WORD)
        selected, _legend, _moving, receipt = encode_bytes(source, profile=PROFILE_WORD_AUTO_SPACE)
        self.assertLessEqual(len(selected), len(explicit))
        self.assertEqual(
            receipt["separator_admission"]["selected_profile"],
            receipt["effective_instance_configuration"]["profile"],
        )

    def test_tabs_newlines_multiple_spaces_and_punctuation_remain_explicit(self):
        fixtures = (
            b"alpha  beta",
            b"alpha\tbeta",
            b"alpha\r\nbeta",
            b"alpha, beta",
            b"well-known phrase",
            "naive cafe resume".encode("utf-8"),
        )
        for source in fixtures:
            with self.subTest(source=source):
                compact, *_ = encode_bytes(source, profile=PROFILE_WORD_IMPLICIT_SPACE)
                restored, _ = decode_bytes(compact)
                self.assertEqual(restored, source)


if __name__ == "__main__":
    unittest.main()
