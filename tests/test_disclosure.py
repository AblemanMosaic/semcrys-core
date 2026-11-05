"""Phase L.D gate: measured legend disclosure.

Three axes. Two are ordering artifacts and can be removed; one cannot. The
gate's job is to prove the metrics are measured against the source rather than
read off the declared id_order.
"""
from __future__ import annotations

import unittest

from semcrys_lite.core import (
    ORDER_FIRST_APPEARANCE,
    ORDER_FREQUENCY,
    ORDER_LEXICAL,
    PROFILE_WORD,
    LiteHold,
    build_legend,
    build_word_legend,
    decode_bytes,
    encode_bytes,
    legend_disclosure,
)

# A vocabulary large enough for a confident rank determination, with alphabetical
# order deliberately decorrelated from both usage frequency and order of first
# appearance. A fixture where the three coincide cannot distinguish the axes.
_ALPHABET = "abcdefghijklmnopqrstuvwxyz"
# A fixed permutation: the nth most frequent unit gets an arbitrary name, so
# alphabetical order carries no information about usage or first appearance.
_WORDS = [
    _ALPHABET[(index * 7 + 3) % 26] + _ALPHABET[(index * 11 + 5) % 26] + f"{index % 10}"
    for index in range(80)
]
assert len(set(_WORDS)) == 80, len(set(_WORDS))
SOURCE = " ".join(
    word for index, word in enumerate(_WORDS) for _ in range(max(1, 40 - index // 2))
).encode() + b"\n"


def _report(order, source=SOURCE):
    return legend_disclosure(build_word_legend(source, id_order=order), source)


class VocabularyAxis(unittest.TestCase):
    def test_every_ordering_exposes_the_whole_vocabulary(self):
        for order in (ORDER_FREQUENCY, ORDER_FIRST_APPEARANCE, ORDER_LEXICAL):
            with self.subTest(order=order):
                block = _report(order)["vocabulary_disclosure"]
                self.assertEqual(block["content_units_exposed_fraction"], 1.0)

    def test_entry_counts_partition_into_content_and_separators(self):
        block = _report(ORDER_LEXICAL)["vocabulary_disclosure"]
        self.assertEqual(
            block["total_entries"],
            block["content_unit_entries"] + block["separator_entries"],
        )

    def test_residual_after_the_best_ordering_is_vocabulary_only(self):
        self.assertEqual(_report(ORDER_LEXICAL)["residual_after_best_ordering"], "VOCABULARY_ONLY")


class OrderingAxes(unittest.TestCase):
    def test_first_appearance_order_leaks_introduction_exactly(self):
        block = _report(ORDER_FIRST_APPEARANCE)["introduction_order_disclosure"]
        self.assertEqual(block["rank_correlation"], 1.0)
        self.assertTrue(block["exact_first_appearance_order"])
        self.assertTrue(block["leaks"])

    def test_frequency_order_leaks_frequency_rank(self):
        self.assertTrue(_report(ORDER_FREQUENCY)["frequency_rank_disclosure"]["leaks"])

    def test_lexical_order_leaks_neither(self):
        report = _report(ORDER_LEXICAL)
        self.assertFalse(report["introduction_order_disclosure"]["leaks"])
        self.assertFalse(report["frequency_rank_disclosure"]["leaks"])

    def test_frequency_order_is_not_first_appearance_order(self):
        self.assertFalse(_report(ORDER_FREQUENCY)["introduction_order_disclosure"]["exact_first_appearance_order"])

    def test_the_two_ordering_axes_are_independent(self):
        first = _report(ORDER_FIRST_APPEARANCE)
        self.assertTrue(first["introduction_order_disclosure"]["leaks"])
        lexical = _report(ORDER_LEXICAL)
        self.assertFalse(lexical["introduction_order_disclosure"]["leaks"])
        self.assertFalse(lexical["frequency_rank_disclosure"]["leaks"])


class SampleAdequacy(unittest.TestCase):
    def test_small_vocabularies_are_flagged_as_inadequate(self):
        tiny = b"a b c d a b a\n" * 4
        report = legend_disclosure(build_word_legend(tiny), tiny)
        self.assertFalse(report["sample"]["sample_adequate_for_a_confident_determination"])

    def test_threshold_widens_when_the_vocabulary_is_small(self):
        tiny = b"a b c d a b a\n" * 4
        small = legend_disclosure(build_word_legend(tiny), tiny)
        large = _report(ORDER_LEXICAL)
        self.assertGreater(
            small["frequency_rank_disclosure"]["decision_threshold"],
            large["frequency_rank_disclosure"]["decision_threshold"],
        )

    def test_large_vocabulary_is_adequate(self):
        self.assertTrue(_report(ORDER_LEXICAL)["sample"]["sample_adequate_for_a_confident_determination"])


class MeasuredNotDeclared(unittest.TestCase):
    def test_correlations_require_the_source(self):
        legend = build_word_legend(SOURCE, id_order=ORDER_LEXICAL)
        without = legend_disclosure(legend)
        self.assertFalse(without["measured_against_source"])
        self.assertNotIn("introduction_order_disclosure", without)
        self.assertTrue(legend_disclosure(legend, SOURCE)["measured_against_source"])

    def test_a_false_declaration_does_not_change_the_measurement(self):
        honest = build_word_legend(SOURCE, id_order=ORDER_FIRST_APPEARANCE)
        lying = {key: value for key, value in honest.items() if key != "legend_root"}
        lying["id_order"] = ORDER_LEXICAL
        from semcrys_lite.core import rooted
        report = legend_disclosure(rooted(lying, "legend_root"), SOURCE)
        # The declaration says LEXICAL; the entries are still first-appearance.
        self.assertEqual(report["declared_id_order"], ORDER_LEXICAL)
        self.assertTrue(report["introduction_order_disclosure"]["leaks"])
        self.assertEqual(report["introduction_order_disclosure"]["rank_correlation"], 1.0)


class Refusals(unittest.TestCase):
    def test_byte_legend_refuses(self):
        with self.assertRaises(LiteHold) as ctx:
            legend_disclosure(build_legend(SOURCE))
        self.assertEqual(ctx.exception.code, "HELD_DISCLOSURE_LEGEND_KIND")

    def test_mismatched_source_refuses(self):
        legend = build_word_legend(b"only these words\n")
        with self.assertRaises(LiteHold) as ctx:
            legend_disclosure(legend, b"quite different words entirely\n")
        self.assertEqual(ctx.exception.code, "HELD_LEGEND_COVERAGE_INCOMPLETE")

    def test_unknown_order_refuses(self):
        with self.assertRaises(LiteHold) as ctx:
            build_word_legend(SOURCE, id_order="RANDOM")
        self.assertEqual(ctx.exception.code, "HELD_LEGEND_ID_ORDER")


class LexicalStillWorks(unittest.TestCase):
    def test_lexical_legends_round_trip(self):
        legend = build_word_legend(SOURCE, id_order=ORDER_LEXICAL)
        container, _e, moving, _r = encode_bytes(
            SOURCE, profile=PROFILE_WORD, legend=legend, legend_placement="EXTERNAL"
        )
        restored, _ = decode_bytes(container, legend=legend, moving_legend=moving)
        self.assertEqual(restored, SOURCE)

    def test_minimal_disclosure_costs_bytes(self):
        def warm(order):
            legend = build_word_legend(SOURCE, id_order=order)
            return len(encode_bytes(
                SOURCE, profile=PROFILE_WORD, legend=legend,
                legend_placement="EXTERNAL", outer_codec="LZMA",
            )[0])
        # Frequency ordering buys small ids for common units; lexical does not.
        self.assertGreaterEqual(warm(ORDER_LEXICAL), warm(ORDER_FREQUENCY))


if __name__ == "__main__":
    unittest.main()
