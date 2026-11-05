from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from semcrys import standard_archive
from semcrys_core.semantic import build_registry


ROOT = Path(__file__).resolve().parent.parent


class StandardArchiveTests(unittest.TestCase):
    def fixture(self, root: Path) -> Path:
        source = root / "project"
        (source / "empty").mkdir(parents=True)
        (source / "notes").mkdir()
        (source / "README.txt").write_text("hello bank\nhello bank\n", encoding="utf-8", newline="\n")
        (source / "notes" / "raw.bin").write_bytes(bytes(range(64)))
        return source

    def test_pack_list_verify_unpack_and_determinism(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as name:
            root = Path(name); source = self.fixture(root)
            first = root / "first.crys"; second = root / "second.crys"
            registry = build_registry([
                {"integer_id": 7, "semantic_key": "example:greeting", "surface": "hello"},
                {"integer_id": 8, "semantic_key": "example:bank", "surface": "bank"},
            ])
            result = standard_archive.pack([source], first, registry=registry)
            self.assertEqual(result["status"], "PASS")
            self.assertTrue(result["verified"])
            listing = standard_archive.list_entries(first)
            self.assertEqual([row["path"] for row in listing["entries"]],
                             ["project", "project/README.txt", "project/empty", "project/notes", "project/notes/raw.bin"])
            verified = standard_archive.verify(first, max_output_bytes=1024)
            self.assertTrue(verified["exact_reconstruction"])
            inspected = standard_archive.inspect(first)
            self.assertEqual(inspected["configuration"]["profile"], "STANDARD_V1")
            self.assertEqual(inspected["registry_root"], registry["registry_root"])
            searched = standard_archive.search(first, "example:greeting")
            self.assertEqual(searched["matches"][0]["csil_id"], 7)
            self.assertEqual(searched["matches"][0]["occurrences"][0]["path"], "project/README.txt")
            restored = root / "restored"
            standard_archive.unpack(first, restored, max_output_bytes=1024)
            self.assertEqual((restored / "project" / "README.txt").read_bytes(),
                             (source / "README.txt").read_bytes())
            self.assertEqual((restored / "project" / "notes" / "raw.bin").read_bytes(),
                             (source / "notes" / "raw.bin").read_bytes())
            standard_archive.pack([source], second, registry=registry)
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_selective_unpack_dry_run_and_cache(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as name:
            root = Path(name); source = self.fixture(root); cache = root / "cache"
            archive = root / "archive.crys"
            planned = standard_archive.pack([source], archive, dry_run=True)
            self.assertEqual(planned["candidate_measurements"], "DEFERRED_UNTIL_PACK")
            self.assertFalse(archive.exists())
            first = standard_archive.pack([source], archive, cache_root=cache)
            self.assertEqual(first["cache_hits"], 0)
            second_archive = root / "archive2.crys"
            second = standard_archive.pack([source], second_archive, cache_root=cache)
            self.assertEqual(second["cache_hits"], 2)
            restored = root / "selected"
            result = standard_archive.unpack(archive, restored, only=["project/README.txt"], max_output_bytes=1024)
            self.assertEqual(result["files"], 1)
            self.assertTrue((restored / "project" / "README.txt").is_file())
            self.assertFalse((restored / "project" / "notes" / "raw.bin").exists())

    def test_cli_path_first_and_machine_help(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as name:
            root = Path(name); source = root / "hello.txt"; source.write_text("hello\n", encoding="utf-8")
            output = root / "hello.crys"
            env = dict(os.environ); env["PYTHONPATH"] = str(ROOT / "src")
            run = subprocess.run([sys.executable, "-B", "-m", "semcrys", "--progress", "quiet",
                                  str(source), "-o", str(output)], cwd=ROOT, env=env,
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
            self.assertEqual(json.loads(run.stdout)["schema"], "semcrys.standard-pack-result.v0.1")
            help_run = subprocess.run([sys.executable, "-B", "-m", "semcrys", "help-json"],
                                      cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(help_run.returncode, 0, help_run.stderr + help_run.stdout)
            commands = {row["command"] for row in json.loads(help_run.stdout)["commands"]}
            self.assertTrue({"pack", "unpack", "list", "verify", "search", "explain-default"} <= commands)

    def test_chunk_deduplication_and_overlap_refusals(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as name:
            root = Path(name); source = root / "source"; source.mkdir()
            data = bytes(range(256)) * 2
            (source / "large.bin").write_bytes(data)
            archive = root / "chunked.crys"
            result = standard_archive.pack([source], archive, workers=1, chunk_bytes=256)
            self.assertEqual(result["chunks"], 2)
            self.assertEqual(result["unique_chunks"], 1)
            verified = standard_archive.verify(archive, max_output_bytes=len(data))
            self.assertTrue(verified["exact_reconstruction"])
            restored = root / "restored"
            standard_archive.unpack(archive, restored, max_output_bytes=len(data))
            self.assertEqual((restored / "source" / "large.bin").read_bytes(), data)
            with self.assertRaisesRegex(standard_archive.StandardRefusal,
                                       "HELD_STANDARD_OUTPUT_OVERLAPS_SOURCE"):
                standard_archive.pack([source], source / "inside.crys", dry_run=True)
            with self.assertRaisesRegex(standard_archive.StandardRefusal,
                                       "HELD_STANDARD_CACHE_OVERLAPS_SOURCE"):
                standard_archive.pack([source], root / "other.crys",
                                      cache_root=source / "cache", dry_run=True)

    def test_global_help_json_alias(self):
        env = dict(os.environ); env["PYTHONPATH"] = str(ROOT / "src")
        run = subprocess.run([sys.executable, "-B", "-m", "semcrys", "--help-json"],
                             cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
        self.assertEqual(json.loads(run.stdout)["schema"],
                         "semcrys.installed-capability-surface.v0.1")

    def test_default_contract_exposes_compression_boundary(self):
        contract = standard_archive.default_contract()
        representation = contract["representation"]
        self.assertEqual(representation["references"],
                         "UNSIGNED_VARIABLE_LENGTH_LOCAL_INTEGER_IDS_IN_PACKED_BYTES")
        self.assertIn("EXACT_CHUNK_DEDUPLICATION", representation["automatic_reuse"])
        self.assertTrue(representation["standard_phrase_mining"])
        self.assertEqual(representation["adaptive_composition"]["default"], "AUTO")
        rooted = dict(contract)
        profile_root = rooted.pop("profile_root")
        self.assertEqual(profile_root, standard_archive._root(rooted))

    def test_small_recurrence_is_not_admitted(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as name:
            root = Path(name); source = root / "small"; source.mkdir()
            for index in range(3):
                (source / f"{index}.txt").write_text("alpha beta\n", encoding="utf-8")
            archive = root / "small.crys"
            result = standard_archive.pack([source], archive, workers=1)
            self.assertGreaterEqual(result["composition"]["groups_considered"], 1)
            self.assertEqual(result["composition"]["groups_selected"], 0)
            self.assertGreaterEqual(result["composition"]["groups_held_or_unprofitable"], 1)
            self.assertTrue(standard_archive.verify(archive, max_output_bytes=1024)["exact_reconstruction"])

    def test_large_cross_document_structure_can_win_composition_court(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as name:
            root = Path(name); source = root / "collection"; source.mkdir(); work = root / "work"; work.mkdir()
            shared = " ".join(f"clause{index:05d}" for index in range(600)) + "\n"
            originals = []; group = []; sources = {}
            for index in range(20):
                path = source / f"document-{index}.txt"
                body = f"unique-prefix-{index}\n{shared}unique-suffix-{index}\n"
                data = body.encode(); path.write_bytes(data); originals.append(data)
                key = (hashlib.sha256(data).hexdigest(), len(data)); sources[key] = path
                group.append({"key": key, "source_sha256": key[0], "source_bytes": key[1]})
            with mock.patch.object(standard_archive, "CODECS", ("NONE",)):
                segment, census = standard_archive._collection_segment(
                    group, sources, work, 0, "payload/segment-00000000.crys", None)
            self.assertTrue(census["eligible"])
            self.assertIsNotNone(segment)
            self.assertEqual(segment["kind"], "COMPOSED_COLLECTION")
            self.assertNotEqual(segment["composition"]["selected_id"], "ORIGINAL")
            restored = root / "collection.decoded"
            from streaming_app.core import decode_file
            decode_file(Path(segment["source_path"]), restored, max_decoded_bytes=sum(map(len, originals)))
            self.assertEqual(restored.read_bytes(), b"".join(originals))

    def test_collection_materialization_and_cache_reuse(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as name:
            root = Path(name); source = root / "source.txt"
            data = ("alpha beta gamma delta\n" * 200).encode(); source.write_bytes(data)
            key = (hashlib.sha256(data).hexdigest(), len(data))
            group = [{"key": key, "source_sha256": key[0], "source_bytes": key[1]}]
            sources = {key: source}; cache = root / "cache"
            work = root / "work"; work.mkdir()
            with mock.patch.object(standard_archive, "CODECS", ("NONE",)):
                segment, census = standard_archive._collection_segment(
                    group, sources, work, 0, "payload/segment-00000000.crys", None, cache)
            self.assertIsNotNone(segment)
            body = root / "body.zip"
            with zipfile.ZipFile(body, "w") as archive:
                standard_archive._zip_write(archive, segment["path"], Path(segment["source_path"]))
            members = root / "members"; members.mkdir()
            materialized = standard_archive._materialize_segment(body, segment, members, 0)
            self.assertEqual([path.read_bytes() for path in materialized], [data])
            work2 = root / "work2"; work2.mkdir()
            with mock.patch.object(standard_archive, "CODECS", ("NONE",)):
                cached, cached_census = standard_archive._collection_segment(
                    group, sources, work2, 0, "payload/segment-00000000.crys", None, cache)
            self.assertTrue(cached_census["cache_hit"])
            self.assertEqual(Path(cached["source_path"]).read_bytes(),
                             Path(segment["source_path"]).read_bytes())

    def test_composition_can_be_ablated(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as name:
            root = Path(name); source = root / "source"; source.mkdir()
            (source / "text.txt").write_text("repeat repeat repeat repeat\n", encoding="utf-8")
            archive = root / "off.crys"
            result = standard_archive.pack([source], archive, composition="off", workers=1)
            self.assertEqual(result["composition"]["groups_considered"], 0)
            self.assertEqual(standard_archive.inspect(archive)["composition_mode"], "off")

    def test_composed_decoder_supports_packaged_bz2_outer_codec(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as name:
            root = Path(name); source = root / "source.txt"
            source.write_text("alpha beta gamma delta\n" * 40, encoding="utf-8", newline="\n")
            first = root / "first.crys"; composed = root / "composed.crys"; restored = root / "restored.txt"
            from streaming_app.core import decode_file, encode_file
            from semcrys.second_pass import transform
            encode_file(source, first, profile="C:SELF_CONTAINED_TOKEN",
                        outer_codec="BZ2_1", legend_policy="TOTAL")
            result = transform(first, composed, selection="ALL", rounds=4, min_count=2)
            self.assertEqual(result["selected_configuration"]["outer_codec"], "BZ2_1")
            decode_file(composed, restored, max_decoded_bytes=source.stat().st_size)
            self.assertEqual(restored.read_bytes(), source.read_bytes())

    def test_in_memory_and_disk_fractionators_are_event_identical(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as name:
            root = Path(name); values = [1, 2, 1, 2, 1, 2, 3, 1, 2, 3] * 4
            from semcrys.event_stream import EventSpool, fractionate_disk
            from semcrys.second_pass import fractionate
            spool = EventSpool.write(root / "events.bin", values)
            for hot in (None, 3):
                memory, memory_pairs = fractionate(values, [5, 4, 3], rounds=8,
                                                    min_count=2, hot_only=hot)
                disk, disk_pairs = fractionate_disk(spool, [5, 4, 3],
                                                    workspace=root / f"disk-{hot}", rounds=8,
                                                    min_count=2, hot_only=hot)
                self.assertEqual(list(disk), memory)
                self.assertEqual(disk_pairs, memory_pairs)


if __name__ == "__main__":
    unittest.main()
