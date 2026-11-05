"""Synchronization surface court.

R4. The four surfaces are read-only measurement, so the court checks three
things the single prior test did not: that each surface refuses in a typed way,
that the cross-dialect boundary holds in both directions, and that no surface
mutates its inputs.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from semcrys.synchronization import account_artifacts, composition_proposal, disclosure, ordering_projection
from streaming_app.core import Refusal, iter_units
from streaming_legend.core import LegendError
from streaming_legend.core import LegendReader, write_legend
from streaming_legend.crys_v2 import write_crys

SAMPLE = "we would like tea. we would like cake.\nwe would like a deterministic composition court.\n"
REPO = Path(__file__).resolve().parent.parent


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "sample.txt"
    source.write_text(SAMPLE, encoding="utf-8", newline="")
    units: list[str] = []
    for _kind, value in iter_units(source):
        if value not in units:
            units.append(value)
    legend = tmp_path / "sample.leg"
    write_legend(legend, units, entry_count=len(units), legend_id="sync-test",
                 unit_mode="TOKEN", parent_sha256=None)
    return source, legend


class Disclosure(unittest.TestCase):
    def test_coverage_and_counts_agree(self):
        with tempfile.TemporaryDirectory() as directory:
            source, legend = _fixture(Path(directory))
            measured = disclosure(source, legend)
            self.assertEqual(measured["coverage_fraction"], 1.0)
            self.assertEqual(
                measured["covered_events"] + measured["literal_events"],
                measured["event_count"],
            )
            self.assertEqual(measured["legend_entries"], LegendReader(legend).verify()["entry_count"])
            self.assertIn("disclosure_root", measured)

    def test_missing_legend_refuses(self):
        with tempfile.TemporaryDirectory() as directory:
            source, _legend = _fixture(Path(directory))
            with self.assertRaises((Refusal, OSError)):
                disclosure(source, Path(directory) / "absent.leg")

    def test_missing_source_refuses(self):
        with tempfile.TemporaryDirectory() as directory:
            _source, legend = _fixture(Path(directory))
            with self.assertRaises((Refusal, OSError)):
                disclosure(Path(directory) / "absent.txt", legend)


class OrderingProjection(unittest.TestCase):
    def test_projection_is_a_proposal_and_is_never_applied(self):
        with tempfile.TemporaryDirectory() as directory:
            source, legend = _fixture(Path(directory))
            before = legend.read_bytes()
            projected = ordering_projection(source, legend)
            self.assertEqual(projected["application_status"], "PROPOSAL_NOT_APPLIED")
            self.assertEqual(legend.read_bytes(), before)

    def test_projection_reports_a_bounded_savings_figure(self):
        with tempfile.TemporaryDirectory() as directory:
            source, legend = _fixture(Path(directory))
            projected = ordering_projection(source, legend)
            self.assertEqual(
                projected["projected_savings_bytes"],
                projected["packed_reference_bytes_before"] - projected["packed_reference_bytes_after"],
            )
            # NOTE: unlike composition_proposal, this surface carries no
            # claim-ceiling field declaring that the figure is packed-reference
            # only and ignores the outer codec. Recorded as an open finding
            # rather than repaired here, because adding the declaration is a
            # semantic change to a published surface.
            self.assertNotIn("claim_ceiling", projected)


class Composition(unittest.TestCase):
    def test_candidates_are_proposals_only(self):
        with tempfile.TemporaryDirectory() as directory:
            source, legend = _fixture(Path(directory))
            before = legend.read_bytes()
            proposal = composition_proposal(source, legend, minimum_count=2)
            self.assertEqual(proposal["application_status"], "PROPOSAL_NOT_APPLIED")
            self.assertEqual(legend.read_bytes(), before)

    def test_composition_declares_its_cost_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            source, legend = _fixture(Path(directory))
            proposal = composition_proposal(source, legend, minimum_count=2)
            self.assertIn("PACKED_REFERENCE_COST_ONLY", proposal["boundary"])
            self.assertIn("OUTER_CODEC_EFFECT_NOT_INFERRED", proposal["boundary"])

    def test_minimum_count_bounds_the_candidate_set(self):
        with tempfile.TemporaryDirectory() as directory:
            source, legend = _fixture(Path(directory))
            loose = composition_proposal(source, legend, minimum_count=2)
            strict = composition_proposal(source, legend, minimum_count=99)
            self.assertGreaterEqual(len(loose["candidates"]), len(strict["candidates"]))
            self.assertEqual(strict["candidates"], [])


class Accounting(unittest.TestCase):
    def _artifacts(self, tmp_path: Path):
        source, legend = _fixture(tmp_path)
        container = tmp_path / "sample.crys"
        # The accounting surface checks that the container corresponds to the
        # source, so the stub must carry the source's real decoded digest.
        write_crys(container, configuration={"schema": "semcrys.sync-test-configuration.v0.1"},
                   body=b"bounded-fixture", legend_stack=(), glyph_binding=None,
                   decoded_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        return source, legend, container

    def test_columns_use_actual_artifact_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            source, legend, container = self._artifacts(tmp_path)
            report = account_artifacts([source], [container], [legend])
            self.assertIn("NO_COUNTERFACTUAL_COMPRESSION", report["accounting_rule"])
            self.assertEqual(report["actual_legend_bytes"], legend.stat().st_size)
            row = report["curve"][0]
            self.assertEqual(row["warm_bytes"], container.stat().st_size)
            self.assertEqual(row["cold_bytes"], row["warm_bytes"] + report["actual_legend_bytes"])

    def test_mismatched_input_counts_refuse(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            source, legend, container = self._artifacts(tmp_path)
            with self.assertRaises(Refusal):
                account_artifacts([source, source], [container], [legend])

    def test_missing_container_refuses(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            source, legend, _container = self._artifacts(tmp_path)
            with self.assertRaises((Refusal, OSError)):
                account_artifacts([source], [tmp_path / "absent.crys"], [legend])


class ReadOnlyInvariant(unittest.TestCase):
    def test_no_surface_mutates_its_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            source, legend = _fixture(tmp_path)
            container = tmp_path / "sample.crys"
            write_crys(container, configuration={"schema": "semcrys.sync-test-configuration.v0.1"},
                       body=b"bounded-fixture", legend_stack=(), glyph_binding=None,
                       decoded_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
            before = {p: p.read_bytes() for p in (source, legend, container)}
            disclosure(source, legend)
            ordering_projection(source, legend)
            composition_proposal(source, legend, minimum_count=2)
            account_artifacts([source], [container], [legend])
            for path, data in before.items():
                self.assertEqual(path.read_bytes(), data, f"{path.name} was mutated")


class CrossDialectBoundary(unittest.TestCase):
    """The central claim of the synchronization: correspondence, not identity.

    Neither dialect may silently parse the other's artifacts.
    """

    def _lite_legend(self, tmp_path: Path) -> Path:
        lite_source = REPO / "src"
        script = (
            "import sys, pathlib;"
            f"sys.path.insert(0, {str(lite_source)!r});"
            "from semcrys_lite.core import build_word_legend, legend_bytes;"
            f"data = pathlib.Path({str(tmp_path / 'sample.txt')!r}).read_bytes();"
            f"pathlib.Path({str(tmp_path / 'lite.leg')!r}).write_bytes(legend_bytes(build_word_legend(data)))"
        )
        completed = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
        if completed.returncode != 0:
            self.skipTest("lite member unavailable in this layout")
        return tmp_path / "lite.leg"

    def test_full_refuses_a_lite_legend(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            source, _legend = _fixture(tmp_path)
            lite_legend = self._lite_legend(tmp_path)
            with self.assertRaises((Refusal, LegendError)) as context:
                disclosure(source, lite_legend)
            self.assertEqual(context.exception.args[0], "HELD_BAD_LEGEND_MAGIC")

    def test_lite_refuses_a_full_legend(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            _source, legend = _fixture(tmp_path)
            lite_source = REPO / "src"
            script = (
                "import sys, pathlib;"
                f"sys.path.insert(0, {str(lite_source)!r});"
                "from semcrys_lite.core import load_legend_bytes, LiteHold;"
                f"data = pathlib.Path({str(legend)!r}).read_bytes();"
                "\ntry:\n"
                "    load_legend_bytes(data); print('ACCEPTED')\n"
                "except LiteHold as hold: print(hold.code)\n"
                "except Exception as error: print(type(error).__name__)\n"
            )
            completed = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
            if completed.returncode != 0:
                self.skipTest("lite member unavailable in this layout")
            verdict = completed.stdout.strip()
            self.assertNotEqual(verdict, "ACCEPTED", "lite parsed a full legend")
            self.assertTrue(verdict.startswith("HELD_"), verdict)


class SizeStubFixture(unittest.TestCase):
    """R5: the accounting stub must declare that it is not decodable.

    The declaration lives in the configuration section, which is schema-open.
    The framed header is schema-closed and rejects unknown keys, which is why
    the marker is not carried there.
    """

    def test_stub_declares_its_kind_and_lives_outside_evidence(self):
        stub = REPO / "fixtures" / "accounting-size-stub.crys"
        if not stub.exists():
            self.skipTest("stub not present in this layout")
            return
        self.assertFalse((REPO / "evidence" / "sync-fixture.crys").exists(),
                         "a non-decodable stub must not sit in evidence/")
        blob = stub.read_bytes()
        self.assertIn(b"SIZE_STUB_NOT_DECODABLE", blob)

    def test_stub_refuses_to_decode(self):
        stub = REPO / "fixtures" / "accounting-size-stub.crys"
        if not stub.exists():
            self.skipTest("stub not present in this layout")
            return
        completed = subprocess.run(
            [sys.executable, "-m", "semcrys", "decode", str(stub), str(Path(tempfile.gettempdir()) / "stub.out")],
            cwd=REPO, capture_output=True, text=True,
            env={"PYTHONPATH": str(REPO / "src"), "PATH": str(Path(sys.executable).parent)},
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("HELD_CONFIGURATION_FIELDS", completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()


class ReleaseScopeDrift(unittest.TestCase):
    """R1 regression: scope drift must fail a test, not a user's first command."""

    def test_parser_command_count_equals_scope_record(self):
        import argparse
        from semcrys.cli import parser as build_parser
        from importlib.resources import files as package_files

        commands = []

        def visit(node, path):
            for action in node._actions:
                if isinstance(action, argparse._SubParsersAction):
                    for name, child in sorted(action.choices.items()):
                        visit(child, path + [name])
                    return
            commands.append(" ".join(path))

        visit(build_parser(), [])
        scope = json.loads(package_files("semcrys").joinpath("RELEASE_SCOPE.json").read_text(encoding="utf-8"))
        listed = [c for group in scope["command_groups"].values() for c in group]
        self.assertEqual(sorted(commands), sorted(listed))

    def test_capabilities_surface_does_not_refuse(self):
        from semcrys.capabilities import surface
        self.assertIn("commands", surface())
