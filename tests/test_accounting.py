"""Phase L.C gate: four-column accounting and corpus amortization.

The columns are claims, so the gate checks arithmetic consistency, that a round
trip is verified before any number is published, and that self-fitted results
cannot be mistaken for transfer results.
"""
from __future__ import annotations

import lzma
import unittest

from semcrys_lite.core import (
    FIT_EXTERNAL,
    FIT_SELF,
    PROFILE_WORD,
    LiteHold,
    account_corpus,
    account_document,
    build_assembly_legend,
    build_word_legend,
    legend_bytes,
    _base_events,
)

A = (b"the quick brown fox jumps over the lazy dog. the fox sleeps. " * 30)
B = (b"the quick brown fox waits. the lazy dog waits too and rests. " * 30)
C = (b"the lazy dog jumps and the quick fox rests over the dog. " * 30)
SHARED = build_word_legend(A + B + C)


class Columns(unittest.TestCase):
    def setUp(self):
        self.report = account_document(B, legend=SHARED)

    def test_columns_are_arithmetically_consistent(self):
        columns = self.report["columns"]
        self.assertEqual(
            columns["col3_both_bytes"],
            columns["col1_worked_document_bytes"] + columns["col2_shared_legend_bytes"],
        )

    def test_legend_breakdown_sums_to_column_two(self):
        breakdown = self.report["legend_breakdown"]
        self.assertEqual(
            breakdown["base_legend_bytes"] + breakdown["assembly_legend_bytes"],
            self.report["columns"]["col2_shared_legend_bytes"],
        )

    def test_cold_accounting_uses_actual_canonical_legend_bytes(self):
        self.assertEqual(
            self.report["legend_breakdown"]["base_legend_bytes"],
            len(legend_bytes(SHARED)),
        )
        self.assertIn(
            "ACTUAL_CANONICAL_LEGEND_ARTIFACT_BYTES",
            self.report["legend_accounting_note"],
        )

    def test_ratios_match_the_columns(self):
        columns, ratios, source = self.report["columns"], self.report["ratios"], self.report["source_bytes"]
        self.assertAlmostEqual(ratios["warm"], columns["col1_worked_document_bytes"] / source, places=5)
        self.assertAlmostEqual(ratios["cold"], columns["col3_both_bytes"] / source, places=5)
        self.assertAlmostEqual(ratios["xz"], columns["col4_xz_source_bytes"] / source, places=5)

    def test_column_four_is_really_xz_on_the_source(self):
        self.assertEqual(
            self.report["columns"]["col4_xz_source_bytes"],
            len(lzma.compress(B, format=lzma.FORMAT_XZ, preset=6)),
        )

    def test_verdict_agrees_with_the_columns(self):
        columns, verdict = self.report["columns"], self.report["verdict"]
        self.assertEqual(
            verdict["warm_beats_xz"],
            columns["col1_worked_document_bytes"] < columns["col4_xz_source_bytes"],
        )
        self.assertEqual(
            verdict["warm_delta_bytes"],
            columns["col4_xz_source_bytes"] - columns["col1_worked_document_bytes"],
        )

    def test_configuration_is_published_with_the_numbers(self):
        config = self.report["effective_instance_configuration"]
        self.assertEqual(config["base_legend_root"], SHARED["legend_root"])
        self.assertIn("body_representation_effective", config)
        self.assertIn("envelope", config)


class RoundTripPrecondition(unittest.TestCase):
    def test_numbers_are_only_published_after_a_verified_round_trip(self):
        wrong = build_word_legend(b"totally unrelated vocabulary here\n")
        with self.assertRaises(LiteHold):
            account_document(B, legend=wrong)


class FitProvenance(unittest.TestCase):
    def test_self_fitted_is_labelled_as_an_upper_bound(self):
        report = account_document(A, legend=build_word_legend(A), fit_provenance=FIT_SELF)
        self.assertEqual(report["fit_provenance"], FIT_SELF)
        self.assertIn("UPPER_BOUND", report["claim_ceiling"])

    def test_external_fit_is_labelled_as_a_transfer_result(self):
        self.assertIn("NOT_FITTED_TO", account_document(B, legend=SHARED)["claim_ceiling"])

    def test_unknown_provenance_refuses(self):
        with self.assertRaises(LiteHold) as ctx:
            account_document(B, legend=SHARED, fit_provenance="PROBABLY_FINE")
        self.assertEqual(ctx.exception.code, "HELD_FIT_PROVENANCE")


class WithAssemblies(unittest.TestCase):
    def setUp(self):
        events, _ = _base_events(A, PROFILE_WORD, SHARED)
        self.assembly = build_assembly_legend([events], SHARED)

    def test_assembly_cost_appears_in_column_two(self):
        report = account_document(B, legend=SHARED, assembly=self.assembly)
        self.assertGreater(report["legend_breakdown"]["assembly_legend_bytes"], 0)
        self.assertEqual(
            report["columns"]["col2_shared_legend_bytes"],
            report["legend_breakdown"]["base_legend_bytes"]
            + report["legend_breakdown"]["assembly_legend_bytes"],
        )

    def test_assembly_run_still_round_trips_before_publishing(self):
        self.assertEqual(
            account_document(B, legend=SHARED, assembly=self.assembly)["source_bytes"], len(B)
        )


class Corpus(unittest.TestCase):
    def setUp(self):
        self.report = account_corpus([A, B, C], legend=SHARED)

    def test_curve_has_one_row_per_document(self):
        self.assertEqual(len(self.report["amortization_curve"]), 3)
        self.assertEqual([r["documents"] for r in self.report["amortization_curve"]], [1, 2, 3])

    def test_cumulative_totals_are_monotonic(self):
        rows = self.report["amortization_curve"]
        for earlier, later in zip(rows, rows[1:]):
            self.assertLess(earlier["cumulative_semcrys_bytes"], later["cumulative_semcrys_bytes"])
            self.assertLess(earlier["cumulative_xz_bytes"], later["cumulative_xz_bytes"])

    def test_first_row_includes_the_whole_shared_legend(self):
        first = self.report["amortization_curve"][0]
        self.assertGreater(first["cumulative_semcrys_bytes"], self.report["shared_legend_bytes"])

    def test_break_even_is_consistent_with_the_curve(self):
        report = self.report
        if report["break_even_found_within_set"]:
            index = report["break_even_documents"]
            row = report["amortization_curve"][index - 1]
            self.assertLess(row["cumulative_semcrys_bytes"], row["cumulative_xz_bytes"])
            for earlier in report["amortization_curve"][: index - 1]:
                self.assertGreaterEqual(
                    earlier["cumulative_semcrys_bytes"], earlier["cumulative_xz_bytes"]
                )
        else:
            for row in report["amortization_curve"]:
                self.assertGreaterEqual(row["cumulative_semcrys_bytes"], row["cumulative_xz_bytes"])

    def test_break_even_is_not_extrapolated_beyond_the_set(self):
        report = account_corpus([A], legend=SHARED)
        if not report["break_even_found_within_set"]:
            self.assertIsNone(report["break_even_documents"])

    def test_empty_corpus_refuses(self):
        with self.assertRaises(LiteHold) as ctx:
            account_corpus([], legend=SHARED)
        self.assertEqual(ctx.exception.code, "HELD_CORPUS_EMPTY")


if __name__ == "__main__":
    unittest.main()
