"""Phase L.B gate: assembly tier.

Assemblies are a shared corpus asset. The gate therefore checks not only that
they round-trip, but that a legend fitted to one document folds a different
document, and that every way of supplying the wrong one refuses.
"""
from __future__ import annotations

import unittest

from semcrys_lite.core import (
    KIND_ASSEMBLY,
    PROFILE_WORD,
    PROFILE_WORD_ASSEMBLY,
    LiteHold,
    apply_assembly_legend,
    assembly_bytes,
    build_assembly_legend,
    build_word_legend,
    decode_bytes,
    encode_bytes,
    expand_assembly_events,
    load_assembly_bytes,
    validate_assembly_legend,
    _base_events,
)

CORPUS_A = (
    b"the quick brown fox jumps over the lazy dog. "
    b"the quick brown fox sleeps. the lazy dog barks. "
) * 12
CORPUS_B = (
    b"the quick brown fox waits. the lazy dog waits too. "
    b"the quick brown fox and the lazy dog rest. "
) * 12
UNRELATED = b"entirely different vocabulary appears here without overlap.\n" * 4


def _fit(source: bytes, legend=None):
    base = legend if legend is not None else build_word_legend(source)
    events, _ = _base_events(source, PROFILE_WORD, base)
    return base, build_assembly_legend([events], base)


class AssemblyConstruction(unittest.TestCase):
    def test_assembly_legend_shape(self):
        base, asm = _fit(CORPUS_A)
        self.assertEqual(asm["kind"], KIND_ASSEMBLY)
        self.assertEqual(asm["base_legend_root"], base["legend_root"])
        self.assertEqual(asm["first_assembly_id"], base["entry_count"] + 1)
        self.assertEqual(asm["relationship"], "WARM_RELATIONSHIP_ONLY")
        self.assertGreater(asm["entry_count"], 0)

    def test_rules_never_reference_forward(self):
        _base, asm = _fit(CORPUS_A)
        for row in asm["entries"]:
            self.assertLess(row["pair"][0], row["id"])
            self.assertLess(row["pair"][1], row["id"])

    def test_assembly_reduces_unit_count(self):
        base, asm = _fit(CORPUS_A)
        events, _ = _base_events(CORPUS_A, PROFILE_WORD, base)
        self.assertLess(len(apply_assembly_legend(events, asm)), len(events))

    def test_fit_is_deterministic(self):
        base, first = _fit(CORPUS_A)
        events, _ = _base_events(CORPUS_A, PROFILE_WORD, base)
        second = build_assembly_legend([events], base)
        self.assertEqual(first["assembly_root"], second["assembly_root"])

    def test_pairs_do_not_span_stream_boundaries(self):
        base = build_word_legend(b"aa bb cc dd\n")
        ids = {row["text"]: row["id"] for row in base["entries"]}
        left, _ = _base_events(b"aa bb", PROFILE_WORD, base)
        right, _ = _base_events(b"cc dd", PROFILE_WORD, base)
        asm = build_assembly_legend([left, right] * 8, base)
        # "bb" ends the first stream and "cc" starts the second, so no rule may
        # expand to that adjacency even though the streams are fitted together.
        forbidden = [ids["bb"], ids["cc"]]
        for row in asm["entries"]:
            expansion = expand_assembly_events([row["id"]], asm)
            for index in range(len(expansion) - 1):
                self.assertNotEqual(expansion[index:index + 2], forbidden)

    def test_empty_stream_yields_empty_assembly(self):
        base = build_word_legend(b"a b\n")
        self.assertEqual(build_assembly_legend([[]], base)["entry_count"], 0)

    def test_expansion_inverts_application(self):
        base, asm = _fit(CORPUS_A)
        events, _ = _base_events(CORPUS_A, PROFILE_WORD, base)
        self.assertEqual(expand_assembly_events(apply_assembly_legend(events, asm), asm), events)


class RoundTrip(unittest.TestCase):
    def test_assembly_profile_round_trips(self):
        base, asm = _fit(CORPUS_A)
        container, external, moving, _r = encode_bytes(
            CORPUS_A, profile=PROFILE_WORD_ASSEMBLY, legend=base, assembly=asm,
            legend_placement="EXTERNAL",
        )
        restored, _ = decode_bytes(container, legend=external or base, moving_legend=moving, assembly=asm)
        self.assertEqual(restored, CORPUS_A)

    def test_assembly_profile_round_trips_with_lzma(self):
        base, asm = _fit(CORPUS_A)
        container, _e, moving, _r = encode_bytes(
            CORPUS_A, profile=PROFILE_WORD_ASSEMBLY, legend=base, assembly=asm, outer_codec="LZMA",
        )
        restored, _ = decode_bytes(container, legend=base, moving_legend=moving, assembly=asm)
        self.assertEqual(restored, CORPUS_A)

    def test_serialisation_round_trips(self):
        _base, asm = _fit(CORPUS_A)
        self.assertEqual(load_assembly_bytes(assembly_bytes(asm))["assembly_root"], asm["assembly_root"])


class CrossDocumentTransfer(unittest.TestCase):
    """The load-bearing property: assemblies fitted to A must fold and decode B."""

    def setUp(self):
        self.base = build_word_legend(CORPUS_A + CORPUS_B)
        events_a, _ = _base_events(CORPUS_A, PROFILE_WORD, self.base)
        self.asm = build_assembly_legend([events_a], self.base)

    def test_document_b_decodes_under_a_fitted_assembly(self):
        container, _e, moving, _r = encode_bytes(
            CORPUS_B, profile=PROFILE_WORD_ASSEMBLY, legend=self.base, assembly=self.asm,
        )
        restored, _ = decode_bytes(container, legend=self.base, moving_legend=moving, assembly=self.asm)
        self.assertEqual(restored, CORPUS_B)

    def test_a_fitted_assembly_still_folds_b(self):
        plain, _ = _base_events(CORPUS_B, PROFILE_WORD, self.base)
        folded, _ = _base_events(CORPUS_B, PROFILE_WORD_ASSEMBLY, self.base, assembly=self.asm)
        self.assertLess(len(folded), len(plain))

    def test_assembly_root_is_recorded_on_both_sides(self):
        container, _e, moving, receipt = encode_bytes(
            CORPUS_B, profile=PROFILE_WORD_ASSEMBLY, legend=self.base, assembly=self.asm,
        )
        _restored, decode_receipt = decode_bytes(
            container, legend=self.base, moving_legend=moving, assembly=self.asm
        )
        root = self.asm["assembly_root"]
        self.assertEqual(receipt["effective_instance_configuration"]["assembly_legend_root"], root)
        self.assertEqual(decode_receipt["assembly_legend_root"], root)


class Refusals(unittest.TestCase):
    def setUp(self):
        self.base, self.asm = _fit(CORPUS_A)

    def _encoded(self):
        return encode_bytes(
            CORPUS_A, profile=PROFILE_WORD_ASSEMBLY, legend=self.base, assembly=self.asm,
        )

    def test_encode_without_assembly_refuses(self):
        with self.assertRaises(LiteHold) as ctx:
            encode_bytes(CORPUS_A, profile=PROFILE_WORD_ASSEMBLY, legend=self.base)
        self.assertEqual(ctx.exception.code, "HELD_ASSEMBLY_LEGEND_MISSING")

    def test_decode_without_assembly_refuses(self):
        container, _e, moving, _r = self._encoded()
        with self.assertRaises(LiteHold) as ctx:
            decode_bytes(container, legend=self.base, moving_legend=moving)
        self.assertEqual(ctx.exception.code, "HELD_ASSEMBLY_LEGEND_MISSING")

    def test_decode_with_wrong_assembly_refuses(self):
        container, _e, moving, _r = self._encoded()
        other_base, other_asm = _fit(CORPUS_B)
        with self.assertRaises(LiteHold) as ctx:
            decode_bytes(container, legend=self.base, moving_legend=moving, assembly=other_asm)
        self.assertIn(ctx.exception.code, {"HELD_ASSEMBLY_BASE_MISMATCH", "HELD_ASSEMBLY_LEGEND_MISMATCH"})

    def test_assembly_bound_to_a_different_base_refuses(self):
        other_base = build_word_legend(UNRELATED)
        with self.assertRaises(LiteHold) as ctx:
            validate_assembly_legend(self.asm, other_base)
        self.assertEqual(ctx.exception.code, "HELD_ASSEMBLY_BASE_MISMATCH")

    def test_non_assembly_profile_rejects_an_assembly(self):
        with self.assertRaises(LiteHold) as ctx:
            encode_bytes(CORPUS_A, profile=PROFILE_WORD, legend=self.base, assembly=self.asm)
        self.assertEqual(ctx.exception.code, "HELD_ASSEMBLY_LEGEND_FORBIDDEN")

    def test_byte_profile_rejects_an_assembly(self):
        with self.assertRaises(LiteHold) as ctx:
            encode_bytes(CORPUS_A, profile="L:BYTE_LOCAL_DENSE", assembly=self.asm)
        self.assertEqual(ctx.exception.code, "HELD_ASSEMBLY_LEGEND_FORBIDDEN")

    def test_supplying_an_assembly_to_a_plain_container_refuses(self):
        container, _e, moving, _r = encode_bytes(CORPUS_A, profile=PROFILE_WORD, legend=self.base)
        with self.assertRaises(LiteHold) as ctx:
            decode_bytes(container, legend=self.base, moving_legend=moving, assembly=self.asm)
        self.assertEqual(ctx.exception.code, "HELD_ASSEMBLY_LEGEND_UNEXPECTED")

    def test_tampered_assembly_root_refuses(self):
        tampered = dict(self.asm)
        tampered["entry_count"] = tampered["entry_count"] + 1
        with self.assertRaises(LiteHold) as ctx:
            validate_assembly_legend(tampered)
        self.assertEqual(ctx.exception.code, "HELD_ASSEMBLY_ROOT_MISMATCH")

    def test_forward_reference_refuses(self):
        broken = {k: v for k, v in self.asm.items() if k != "assembly_root"}
        broken["entries"] = [dict(row) for row in broken["entries"]]
        broken["entries"][0]["pair"] = [broken["entries"][0]["id"] + 5, 1]
        from semcrys_lite.core import rooted
        with self.assertRaises(LiteHold) as ctx:
            validate_assembly_legend(rooted(broken, "assembly_root"))
        self.assertEqual(ctx.exception.code, "HELD_ASSEMBLY_PAIR_FORWARD_REFERENCE")


class WarmRelationshipDeclaration(unittest.TestCase):
    def test_receipt_declares_warm_only_and_states_the_cold_penalty(self):
        base, asm = _fit(CORPUS_A)
        _c, _e, _m, receipt = encode_bytes(
            CORPUS_A, profile=PROFILE_WORD_ASSEMBLY, legend=base, assembly=asm,
        )
        block = receipt["assembly_relationship"]
        self.assertEqual(block["relationship"], "WARM_RELATIONSHIP_ONLY")
        self.assertGreater(block["assembly_legend_bytes"], 0)
        self.assertIn("PRE_SHARED", block["cold_penalty_note"])

    def test_plain_word_profile_has_no_assembly_block(self):
        base = build_word_legend(CORPUS_A)
        _c, _e, _m, receipt = encode_bytes(CORPUS_A, profile=PROFILE_WORD, legend=base)
        self.assertIsNone(receipt["assembly_relationship"])


if __name__ == "__main__":
    unittest.main()
