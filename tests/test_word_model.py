"""Phase L.A gate: word unit model.

Scope is the unit model only. Assemblies, accounting columns, leak metrics and
the mode ladder are out of scope for this phase.
"""
from __future__ import annotations

import unittest

from semcrys_lite.core import (
    HYPHEN_COMPOSED,
    HYPHEN_SINGLE,
    KIND_BYTE,
    KIND_WORD,
    ORDER_FIRST_APPEARANCE,
    ORDER_FREQUENCY,
    PROFILE_LOCAL,
    PROFILE_WORD,
    LiteHold,
    build_legend,
    build_word_legend,
    decode_bytes,
    encode_bytes,
    tokenize_text,
)

ASCII = b"the cat sat on the mat and the cat sat again.\n"
UNICODE = "coeur na\u00effs \u00e9l\u00e8ve \u4f60\u597d \u4e16\u754c caf\u00e9 caf\u00e9 na\u00effs\n".encode("utf-8")
HYPHENS = (
    b"re-enter the well-known well-known state. "
    b"re-enter again. mother-in-law arrived; mother-in-law left.\n"
)
PATHOLOGICAL = b" ".join(f"unique{n}".encode() for n in range(500))
WHITESPACE = b"a\t\tb\r\n\r\n  c\n\n\nd  \te\n"


def _round_trip(data: bytes, **kwargs) -> bytes:
    container, external, moving, _receipt = encode_bytes(data, profile=PROFILE_WORD, **kwargs)
    restored, _ = decode_bytes(container, legend=external, moving_legend=moving)
    return restored


class TokenizerLossless(unittest.TestCase):
    def test_tokenization_is_lossless(self):
        for sample in (ASCII, UNICODE, HYPHENS, PATHOLOGICAL, WHITESPACE):
            text = sample.decode("utf-8")
            with self.subTest(sample=sample[:20]):
                self.assertEqual("".join(t for _k, t in tokenize_text(text)), text)

    def test_hyphenated_compound_is_one_token_before_resolution(self):
        kinds = [k for k, _t in tokenize_text("re-enter now")]
        self.assertEqual(kinds[0], "HYPHEN")

    def test_whitespace_runs_collapse_to_single_tokens(self):
        tokens = tokenize_text("a\t\tb")
        self.assertIn(("SPACE", "\t\t"), tokens)


class WordRoundTrip(unittest.TestCase):
    def test_ascii_round_trip(self):
        self.assertEqual(_round_trip(ASCII), ASCII)

    def test_unicode_round_trip(self):
        self.assertEqual(_round_trip(UNICODE), UNICODE)

    def test_hyphen_dense_round_trip(self):
        self.assertEqual(_round_trip(HYPHENS), HYPHENS)

    def test_pathological_all_unique_round_trip(self):
        self.assertEqual(_round_trip(PATHOLOGICAL), PATHOLOGICAL)

    def test_whitespace_round_trip(self):
        self.assertEqual(_round_trip(WHITESPACE), WHITESPACE)

    def test_empty_source_round_trip(self):
        self.assertEqual(_round_trip(b""), b"")

    def test_external_placement_round_trip(self):
        container, external, moving, _r = encode_bytes(
            ASCII, profile=PROFILE_WORD, legend_placement="EXTERNAL"
        )
        self.assertIsNotNone(external)
        restored, _ = decode_bytes(container, legend=external, moving_legend=moving)
        self.assertEqual(restored, ASCII)


class IdOrdering(unittest.TestCase):
    def test_frequency_order_gives_lowest_ids_to_most_frequent(self):
        legend = build_word_legend(ASCII, id_order=ORDER_FREQUENCY)
        first = legend["entries"][0]["text"]
        self.assertIn(first, {" ", "the"})

    def test_frequency_ties_use_lexical_order_not_first_appearance(self):
        left = build_word_legend(b"z a", id_order=ORDER_FREQUENCY)
        right = build_word_legend(b"a z", id_order=ORDER_FREQUENCY)
        left_words = [row["text"] for row in left["entries"] if row["text"] != " "]
        right_words = [row["text"] for row in right["entries"] if row["text"] != " "]
        self.assertEqual(left_words, ["a", "z"])
        self.assertEqual(right_words, ["a", "z"])

    def test_first_appearance_order_starts_with_first_token(self):
        legend = build_word_legend(ASCII, id_order=ORDER_FIRST_APPEARANCE)
        self.assertEqual(legend["entries"][0]["text"], "the")

    def test_both_orders_round_trip(self):
        for order in (ORDER_FREQUENCY, ORDER_FIRST_APPEARANCE):
            with self.subTest(order=order):
                self.assertEqual(_round_trip(ASCII, id_order=order), ASCII)

    def test_order_is_recorded_in_legend(self):
        self.assertEqual(
            build_word_legend(ASCII, id_order=ORDER_FIRST_APPEARANCE)["id_order"],
            ORDER_FIRST_APPEARANCE,
        )

    def test_unknown_order_refuses(self):
        with self.assertRaises(LiteHold) as ctx:
            build_word_legend(ASCII, id_order="ALPHABETICAL")
        self.assertEqual(ctx.exception.code, "HELD_LEGEND_ID_ORDER")


class HyphenResolution(unittest.TestCase):
    def test_every_compound_receives_a_recorded_decision(self):
        legend = build_word_legend(HYPHENS)
        compounds = {row["compound"] for row in legend["hyphen_decisions"]}
        self.assertEqual(compounds, {"re-enter", "well-known", "mother-in-law"})
        for row in legend["hyphen_decisions"]:
            self.assertIn(row["binding"], {HYPHEN_SINGLE, HYPHEN_COMPOSED})
            self.assertIn("single_cost_estimate", row)
            self.assertIn("composed_cost_estimate", row)

    def test_decision_is_the_cheaper_estimate(self):
        for row in build_word_legend(HYPHENS)["hyphen_decisions"]:
            expected = (
                HYPHEN_SINGLE
                if row["single_cost_estimate"] < row["composed_cost_estimate"]
                else HYPHEN_COMPOSED
            )
            self.assertEqual(row["binding"], expected)

    def test_composed_compound_is_absent_from_entries(self):
        legend = build_word_legend(HYPHENS)
        texts = {row["text"] for row in legend["entries"]}
        for row in legend["hyphen_decisions"]:
            if row["binding"] == HYPHEN_COMPOSED:
                self.assertNotIn(row["compound"], texts)
                for part in row["parts"]:
                    self.assertIn(part, texts)

    def test_single_compound_is_present_in_entries(self):
        legend = build_word_legend(HYPHENS)
        texts = {row["text"] for row in legend["entries"]}
        for row in legend["hyphen_decisions"]:
            if row["binding"] == HYPHEN_SINGLE:
                self.assertIn(row["compound"], texts)

    def test_both_branches_are_reachable(self):
        # A compound entry costs its payload once and one reference per use, so
        # it amortizes with frequency. Composition costs a reference per part
        # per use and amortizes not at all. Rare compounds therefore compose;
        # frequent ones earn their own entry.
        mixed = (
            b"the cat. " * 40
            + b"the-cat "          # rare -> COMPOSED
            + b"zx-qv " * 60       # frequent -> SINGLE
        )
        rows = build_word_legend(mixed)["hyphen_decisions"]
        bindings = {row["compound"]: row["binding"] for row in rows}
        self.assertEqual(bindings["the-cat"], HYPHEN_COMPOSED)
        self.assertEqual(bindings["zx-qv"], HYPHEN_SINGLE)
        self.assertEqual(_round_trip(mixed), mixed)

    def test_frequency_flips_the_binding_for_the_same_compound(self):
        rare = build_word_legend(b"the cat. " * 40 + b"the-cat ")
        often = build_word_legend(b"the cat. " * 40 + b"the-cat " * 25)
        pick = lambda leg: next(
            r["binding"] for r in leg["hyphen_decisions"] if r["compound"] == "the-cat"
        )
        self.assertEqual(pick(rare), HYPHEN_COMPOSED)
        self.assertEqual(pick(often), HYPHEN_SINGLE)

    def test_composition_is_charged_for_parts_it_must_admit(self):
        rows = build_word_legend(b"aa-bb " * 30 + b"plain words here\n")["hyphen_decisions"]
        row = next(r for r in rows if r["compound"] == "aa-bb")
        self.assertEqual(sorted(row["parts_admitted_by_composition"]), ["-", "aa", "bb"])


class Refusals(unittest.TestCase):
    def test_non_utf8_source_refuses(self):
        with self.assertRaises(LiteHold) as ctx:
            encode_bytes(b"\xff\xfe\x00binary", profile=PROFILE_WORD)
        self.assertEqual(ctx.exception.code, "HELD_SOURCE_NOT_UTF8")

    def test_incomplete_coverage_refuses(self):
        legend = build_word_legend(b"only these words\n")
        with self.assertRaises(LiteHold) as ctx:
            encode_bytes(b"only these words and more\n", profile=PROFILE_WORD, legend=legend)
        self.assertEqual(ctx.exception.code, "HELD_LEGEND_COVERAGE_INCOMPLETE")

    def test_byte_legend_rejected_by_word_profile(self):
        with self.assertRaises(LiteHold) as ctx:
            encode_bytes(ASCII, profile=PROFILE_WORD, legend=build_legend(ASCII))
        self.assertEqual(ctx.exception.code, "HELD_LEGEND_KIND_MISMATCH_FOR_PROFILE")

    def test_word_legend_rejected_by_byte_profile(self):
        with self.assertRaises(LiteHold) as ctx:
            encode_bytes(ASCII, profile=PROFILE_LOCAL, legend=build_word_legend(ASCII))
        self.assertEqual(ctx.exception.code, "HELD_LEGEND_KIND_MISMATCH_FOR_PROFILE")

    def test_word_legend_with_duplicate_text_refuses(self):
        legend = build_word_legend(ASCII)
        legend["entries"][1]["text"] = legend["entries"][0]["text"]
        with self.assertRaises(LiteHold):
            encode_bytes(ASCII, profile=PROFILE_WORD, legend=legend)


class ByteModelUnaffected(unittest.TestCase):
    def test_byte_legend_kind_unchanged(self):
        self.assertEqual(build_legend(ASCII)["kind"], KIND_BYTE)

    def test_word_legend_kind_is_distinct(self):
        self.assertEqual(build_word_legend(ASCII)["kind"], KIND_WORD)

    def test_byte_profile_still_round_trips_binary(self):
        blob = bytes(range(256)) * 4
        container, external, moving, _r = encode_bytes(blob, profile=PROFILE_LOCAL)
        restored, _ = decode_bytes(container, legend=external, moving_legend=moving)
        self.assertEqual(restored, blob)


class UnitReduction(unittest.TestCase):
    def test_word_events_are_fewer_than_bytes(self):
        _c, _e, _m, receipt = encode_bytes(ASCII * 20, profile=PROFILE_WORD)
        self.assertLess(receipt["event_count"], len(ASCII * 20))


if __name__ == "__main__":
    unittest.main()
