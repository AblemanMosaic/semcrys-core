"""Phase L.E gate: the ladder as one declared axis.

The invariant is about repetition structure leaving the public body, not about
byte size. The gate proves both: that repetition exposure falls monotonically,
and that byte size does not, so the two are never conflated.
"""
from __future__ import annotations

import unittest

from semcrys_lite.core import (
    LADDER_RUNGS,
    OCC_BOUNDED,
    OCC_HOMOPHONIC,
    OCC_UNIQUE,
    OCC_VISIBLE,
    PROFILE_WORD,
    PROFILE_WORD_ASSEMBLY,
    LiteHold,
    account_corpus,
    account_document,
    build_assembly_legend,
    build_word_legend,
    encode_bytes,
    ladder_position,
    ladder_report,
    ladder_rungs,
    _base_events,
)

SOURCE = (b"the quick brown fox jumps over the lazy dog and the fox rests. " * 60)
LEGEND = build_word_legend(SOURCE)
KEY = b"0123456789abcdef0123456789abcdef"


def _assembly():
    events, _ = _base_events(SOURCE, PROFILE_WORD, LEGEND)
    return build_assembly_legend([events], LEGEND)


class Registry(unittest.TestCase):
    def test_rungs_are_ordered_and_contiguous(self):
        steps = [rung["step"] for rung in LADDER_RUNGS]
        self.assertEqual(steps, list(range(len(LADDER_RUNGS))))

    def test_shareability_falls_as_the_ladder_is_climbed(self):
        flags = [rung["legend_is_shareable"] for rung in LADDER_RUNGS]
        self.assertEqual(flags, sorted(flags, reverse=True))

    def test_message_specific_rungs_require_sealing_and_a_key(self):
        for rung in LADDER_RUNGS:
            if rung["legend_is_message_specific"]:
                self.assertTrue(rung["requires_sealing"], rung["rung"])
                self.assertTrue(rung["requires_runtime_key"], rung["rung"])

    def test_top_rung_declares_the_legend_is_the_message(self):
        top = LADDER_RUNGS[-1]
        self.assertEqual(top["worked_artifact_carries"], "EVENT_COUNT_ONLY")
        self.assertFalse(top["legend_is_shareable"])
        self.assertIn("NEVER_BE_A_CORPUS_ASSET", top["note"])

    def test_registry_is_rooted_and_states_the_invariant(self):
        report = ladder_rungs()
        self.assertIn("ladder_root", report)
        self.assertIn("REPETITION_STRUCTURE", report["invariant"])


class Position(unittest.TestCase):
    def test_a_container_reports_its_rung(self):
        container, *_ = encode_bytes(
            SOURCE, profile=PROFILE_WORD, legend=LEGEND, legend_placement="EXTERNAL"
        )
        self.assertEqual(ladder_position(container)["rung"]["rung"], "L0_WORD_DIRECT")

    def test_assembly_container_reports_the_second_rung(self):
        assembly = _assembly()
        container, *_ = encode_bytes(
            SOURCE, profile=PROFILE_WORD_ASSEMBLY, legend=LEGEND,
            assembly=assembly, legend_placement="EXTERNAL",
        )
        self.assertEqual(ladder_position(container)["rung"]["rung"], "L1_WORD_ASSEMBLY")

    def test_unique_container_reports_the_top_rung(self):
        container, *_ = encode_bytes(
            SOURCE, profile=PROFILE_WORD, legend=LEGEND, legend_placement="EXTERNAL",
            occurrence_mode=OCC_UNIQUE, key=KEY,
        )
        position = ladder_position(container)
        self.assertEqual(position["rung"]["rung"], "L4_UNIQUE_ASCENDING")
        self.assertEqual(position["public_body_semantics"], "EVENT_COUNT_ONLY")


class MigrationInvariant(unittest.TestCase):
    def setUp(self):
        self.report = ladder_report(SOURCE, legend=LEGEND, assembly=_assembly(), key=KEY)

    def test_repetition_exposure_falls_monotonically(self):
        series = self.report["public_repetition_exposure_by_step"]
        self.assertEqual(series, sorted(series, reverse=True))
        self.assertTrue(self.report["invariant_holds_in_this_measurement"])

    def test_the_top_rung_exposes_no_repetition(self):
        top = [row for row in self.report["rows"] if row["rung"] == "L4_UNIQUE_ASCENDING"][0]
        self.assertEqual(top["public_max_repetition"], 0)
        self.assertFalse(top["public_repetition_visible"])

    def test_bounded_alias_caps_repetition_rather_than_removing_it(self):
        row = [r for r in self.report["rows"] if r["rung"] == "L2_BOUNDED_ALIAS"][0]
        self.assertGreater(row["public_max_repetition"], 0)
        self.assertLessEqual(row["public_max_repetition"], 2)

    def test_homophonic_rung_balances_aliases(self):
        row = [r for r in self.report["rows"] if r["rung"] == "L3_HOMOPHONIC_BALANCED"][0]
        self.assertLessEqual(row["public_max_repetition"], 2)

    def test_byte_size_is_reported_separately_and_is_not_monotonic(self):
        # Concealment costs bytes: this is the fact the size note exists for.
        self.assertFalse(self.report["byte_size_is_monotonic"])
        self.assertIn("CONCEALMENT_CAN_COST_BYTES", self.report["size_note"])

    def test_every_rung_round_trips_before_being_reported(self):
        self.assertTrue(all(
            row["status"] == "MEASURED" for row in self.report["rows"]
        ))

    def test_keyless_run_skips_the_sealed_rungs_rather_than_failing(self):
        report = ladder_report(SOURCE, legend=LEGEND)
        skipped = {row["rung"] for row in report["rows"] if row["status"] == "SKIPPED"}
        self.assertEqual(skipped, {"L2_BOUNDED_ALIAS", "L3_HOMOPHONIC_BALANCED", "L4_UNIQUE_ASCENDING"})


class AmortizationIsRefusedForMessageSpecificLegends(unittest.TestCase):
    """The structural point: only shareable rungs have a break-even at all."""

    def test_account_document_refuses_a_message_specific_mode(self):
        for mode in (OCC_BOUNDED, OCC_HOMOPHONIC, OCC_UNIQUE):
            with self.subTest(mode=mode):
                with self.assertRaises(LiteHold) as ctx:
                    account_document(SOURCE, legend=LEGEND, occurrence_mode=mode, key=KEY)
                self.assertEqual(ctx.exception.code, "HELD_ACCOUNTING_LEGEND_NOT_SHAREABLE")

    def test_account_corpus_refuses_a_message_specific_mode(self):
        with self.assertRaises(LiteHold) as ctx:
            account_corpus([SOURCE], legend=LEGEND, occurrence_mode=OCC_UNIQUE, key=KEY)
        self.assertEqual(ctx.exception.code, "HELD_ACCOUNTING_LEGEND_NOT_SHAREABLE")

    def test_shareable_modes_are_still_accounted(self):
        self.assertIn("columns", account_document(SOURCE, legend=LEGEND, occurrence_mode=OCC_VISIBLE))


if __name__ == "__main__":
    unittest.main()
