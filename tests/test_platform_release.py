from __future__ import annotations

import io
import hashlib
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from build_release import source_path_excluded  # noqa: E402
from build_release_receipt import inventory  # noqa: E402
from build_reviewer_bundle import court_source, verifier_source  # noqa: E402
from run_publication_court import COURT_TEMP, run  # noqa: E402
from standalone_custody import canonical_source_root  # noqa: E402
from verify_release import bind_temp_environment, inspect_tar, safe_extract_tar  # noqa: E402


class LinuxArchiveSafety(unittest.TestCase):
    def make_tar(self, members):
        scratch = ROOT / "release-work" / "test-platform-release"
        scratch.mkdir(parents=True, exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir=scratch)
        path = Path(directory.name) / "candidate.tar.gz"
        with tarfile.open(path, "w:gz") as archive:
            for name, kind in members:
                info = tarfile.TarInfo(name)
                if kind == "file":
                    payload = b"payload"
                    info.size = len(payload)
                    archive.addfile(info, io.BytesIO(payload))
                elif kind == "dir":
                    info.type = tarfile.DIRTYPE
                    archive.addfile(info)
                else:
                    info.type = tarfile.SYMTYPE
                    info.linkname = "target"
                    archive.addfile(info)
        return directory, path

    def test_safe_single_root_extracts(self):
        custody, path = self.make_tar(
            [("semcrys-linux-x64", "dir"), ("semcrys-linux-x64/file", "file")]
        )
        self.addCleanup(custody.cleanup)
        scratch = ROOT / "release-work" / "test-platform-release"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as output:
            safe_extract_tar(path, Path(output))
            self.assertEqual(
                (Path(output) / "semcrys-linux-x64" / "file").read_bytes(),
                b"payload",
            )

    def test_parent_traversal_refuses(self):
        custody, path = self.make_tar([("semcrys-linux-x64/../escape", "file")])
        self.addCleanup(custody.cleanup)
        with self.assertRaisesRegex(RuntimeError, "UNSAFE_TAR_MEMBER"):
            inspect_tar(path)

    def test_link_refuses(self):
        custody, path = self.make_tar([("semcrys-linux-x64/link", "link")])
        self.addCleanup(custody.cleanup)
        with self.assertRaisesRegex(RuntimeError, "TAR_UNSAFE_TYPE"):
            inspect_tar(path)

    def test_duplicate_refuses(self):
        custody, path = self.make_tar(
            [("semcrys-linux-x64/file", "file"), ("semcrys-linux-x64/file", "file")]
        )
        self.addCleanup(custody.cleanup)
        with self.assertRaisesRegex(RuntimeError, "TAR_DUPLICATE_MEMBER"):
            inspect_tar(path)


class PlatformReleaseContract(unittest.TestCase):
    def test_release_receipt_inventory_can_isolate_core_boundary(self):
        scratch = ROOT / ".test-tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            (root / "core.bin").write_bytes(b"core")
            (root / "companion.json").write_bytes(b"companion")
            result = inventory(root, "0.1.0", names={"core.bin"})
            self.assertEqual([row["name"] for row in result["artifacts"]], ["core.bin"])

    def test_source_root_orders_by_canonical_repository_path(self):
        scratch = ROOT / ".test-tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            first = root / "Z-upper" / "alpha"
            second = root / "a-lower" / "Beta"
            first.parent.mkdir(parents=True)
            second.parent.mkdir(parents=True)
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            forward = canonical_source_root(root, [first, second])
            reverse = canonical_source_root(root, [second, first, first])
            self.assertEqual(forward, reverse)

    def test_release_assembler_refuses_stale_platform_source_root(self):
        from tools.build_release import load_court

        scratch = ROOT / ".test-tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            artifact = root / "standalone.bin"
            artifact.write_bytes(b"standalone")
            court = root / "court.json"
            court.write_text(json.dumps({
                "schema": "example.platform-court.v0.1",
                "status": "PASS",
                "builds": [{"sha256": hashlib.sha256(b"standalone").hexdigest()}],
                "toolchain": {"source_root": "stale"},
            }), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "PLATFORM_COURT_SOURCE_DRIFT"):
                load_court(
                    court,
                    "example.platform-court.v0.1",
                    artifact,
                    expected_source_root="current",
                )

    def test_contract_declares_both_standalones(self):
        contract = json.loads((ROOT / "RELEASE_CONTRACT.json").read_text(encoding="utf-8"))
        platforms = contract["standalone_delivery"]["platforms"]
        self.assertEqual(set(platforms), {"windows_x86_64", "linux_x86_64"})
        self.assertFalse(contract["standalone_delivery"]["external_python_installation"])

    def test_release_inputs_are_ignored(self):
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("release-inputs/", ignore)

    def test_source_release_excludes_court_scratch_and_bytecode(self):
        cases = (
            Path(".test-tmp") / "court" / "result.json",
            Path("tmpdmr567z9") / "candidate.tar.gz",
            Path("src") / "semcrys" / "__pycache__" / "cli.cpython-314.pyc",
            Path("src") / "semcrys" / "archive.pyo",
        )
        for relative in cases:
            with self.subTest(relative=relative):
                self.assertTrue(source_path_excluded(ROOT / relative, relative))

    def test_source_release_keeps_intentional_tmp_named_sources(self):
        relative = Path("docs") / "tmp-format.md"
        self.assertFalse(source_path_excluded(ROOT / relative, relative))

    def test_publication_court_owns_child_temp_directory(self):
        COURT_TEMP.mkdir(parents=True, exist_ok=True)
        check = run(
            [
                "-c",
                "import pathlib,tempfile; print(pathlib.Path(tempfile.gettempdir()).resolve())",
            ]
        )
        self.assertEqual(check["returncode"], 0)
        self.assertEqual(Path(check["stdout_tail"].strip()), COURT_TEMP.resolve())

    def test_release_verifier_binds_every_python_temp_variable(self):
        root = ROOT / "release-work" / "release-verification" / "child"
        environment = bind_temp_environment({"UNRELATED": "preserved"}, root)
        self.assertEqual(environment["UNRELATED"], "preserved")
        for name in ("TEMP", "TMP", "TMPDIR"):
            self.assertEqual(environment[name], str(root))

    def test_generated_reviewer_programs_compile(self):
        compile(verifier_source(), "verify_reviewer_bundle.py", "exec")
        compile(court_source(), "run_reviewer_court.py", "exec")


if __name__ == "__main__":
    unittest.main()
