from __future__ import annotations

import base64
import collections
import hashlib
import hmac
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
CONCEALMENT_KEY = b"semcrys-lite-candidate-key-32b!!"

from semcrys_lite.core import (
    BODY_JSON_EVENTS,
    deserialize_container,
    serialize_container,
    ENVELOPE_TEXT,  # noqa: E402
    OCC_BOUNDED,
    OCC_HOMOPHONIC,
    OCC_PERMUTE,
    OCC_UNIQUE,
    OCC_VISIBLE,
    OUTER_LZMA,
    OUTER_NONE,
    PLACEMENT_EXTERNAL,
    POSITION_CONCEAL,
    PROFILE_DIRECT,
    PROFILE_LOCAL,
    PROFILE_PRESHARED,
    LiteHold,
    build_legend,
    canonical_bytes,
    decode_bytes,
    encode_bytes,
    explain_container,
    inspect_container,
    legend_bytes,
    rooted,
)


def body_of(container_bytes: bytes) -> dict:
    container = deserialize_container(container_bytes)
    if container.get("body_encoding") == "JSON_DIRECT":
        return container["body"]
    packed = base64.b64decode(container["body_b64"])
    if container["body_encoding"] in {"LZMA_JSON", "LZMA_PACKED_VARINT"}:
        import lzma
        packed = lzma.decompress(packed)
    if container["body_encoding"] in {"PACKED_VARINT", "LZMA_PACKED_VARINT"}:
        from semcrys_lite.core import _unpack_varints
        return {"kind": "EVENTS", "events": _unpack_varints(packed)}
    return deserialize_container(packed)


class LiteCoreTests(unittest.TestCase):
    def roundtrip(self, data: bytes, **kwargs):
        container, external, moving, receipt = encode_bytes(data, **kwargs)
        supplied = kwargs.get("legend") or external
        restored, decode_receipt = decode_bytes(container, legend=supplied, moving_legend=moving, key=kwargs.get("key"))
        self.assertEqual(data, restored)
        self.assertEqual(receipt["security_claim"], "NONE")
        self.assertEqual(decode_receipt["security_claim"], "NONE")
        return container, external, moving, receipt

    def test_legacy_v01_protected_key_identifier_still_decodes(self):
        source = b"legacy protected moving legend" * 8
        container, _external, moving, _receipt = encode_bytes(
            source,
            occurrence_mode=OCC_HOMOPHONIC,
            alias_limit=4,
            key=CONCEALMENT_KEY,
        )
        legacy_identifier = hmac.new(
            CONCEALMENT_KEY,
            b"semcrys-lite-key-identifier-v1",
            hashlib.sha256,
        ).hexdigest()[:32]
        legacy_moving = dict(moving)
        legacy_moving.pop("sealed_legend_root")
        legacy_moving["key_identifier"] = legacy_identifier
        legacy_moving["content_plaintext_bytes"] = 0
        legacy_moving = rooted(legacy_moving, "sealed_legend_root")
        legacy_container = deserialize_container(container)
        legacy_container.pop("container_root")
        legacy_container["moving_legend_binding"]["key_identifier"] = legacy_identifier
        legacy_container["moving_legend_binding"]["sealed_legend_root"] = legacy_moving["sealed_legend_root"]
        legacy_container = rooted(legacy_container, "container_root")
        restored, _ = decode_bytes(
            serialize_container(legacy_container),
            moving_legend=legacy_moving,
            key=CONCEALMENT_KEY,
        )
        self.assertEqual(restored, source)

    def test_direct_all_byte_values_roundtrip(self) -> None:
        self.roundtrip(bytes(range(256)), profile=PROFILE_DIRECT)

    def test_direct_empty_roundtrip(self) -> None:
        self.roundtrip(b"", profile=PROFILE_DIRECT)

    def test_direct_lzma_roundtrip(self) -> None:
        self.roundtrip((b"abc\x00\xff" * 1000), profile=PROFILE_DIRECT, outer_codec=OUTER_LZMA)

    def test_transparent_body_is_direct_json_not_base64(self) -> None:
        container, *_ = encode_bytes(b"abc", profile=PROFILE_DIRECT, outer_codec=OUTER_NONE, body_representation=BODY_JSON_EVENTS)
        value = deserialize_container(container)
        self.assertEqual(value["body_encoding"], "JSON_DIRECT")
        self.assertEqual(value["body"], {"kind": "EVENTS", "events": [97, 98, 99]})
        self.assertNotIn("body_b64", value)
        text_container, _t_ext, _t_mov, _t_r = encode_bytes(b"abc", profile="L:BYTE_DIRECT", envelope=ENVELOPE_TEXT, body_representation=BODY_JSON_EVENTS)
        self.assertIn('"events":[97,98,99]', text_container.decode("utf-8"))

    def test_lzma_body_is_carried_as_base64_not_direct(self) -> None:
        container, *_ = encode_bytes(b"abc" * 100, profile=PROFILE_DIRECT, outer_codec=OUTER_LZMA, body_representation=BODY_JSON_EVENTS)
        value = deserialize_container(container)
        self.assertEqual(value["body_encoding"], "LZMA_JSON")
        self.assertIn("body_b64", value)
        self.assertNotIn("body", value)

    def test_deterministic_container(self) -> None:
        data = bytes(range(256)) * 4
        first = encode_bytes(data, profile=PROFILE_DIRECT, outer_codec=OUTER_LZMA)[0]
        second = encode_bytes(data, profile=PROFILE_DIRECT, outer_codec=OUTER_LZMA)[0]
        self.assertEqual(first, second)

    def test_local_embedded_roundtrip(self) -> None:
        container, external, _moving, _receipt = self.roundtrip(b"cab cab", profile=PROFILE_LOCAL)
        self.assertIsNone(external)
        self.assertEqual(deserialize_container(container)["legend_placement"], "SELF_CONTAINED")

    def test_local_external_roundtrip(self) -> None:
        container, external, _moving, _receipt = encode_bytes(b"cab cab", profile=PROFILE_LOCAL, legend_placement=PLACEMENT_EXTERNAL)
        self.assertIsNotNone(external)
        self.assertEqual(decode_bytes(container, legend=external)[0], b"cab cab")

    def test_caller_supplied_local_legend_defaults_external(self) -> None:
        source = b"supplied legend stays outside"
        legend = build_legend(source)
        container, external, _moving, _receipt = encode_bytes(source, profile=PROFILE_LOCAL, legend=legend)
        self.assertEqual(deserialize_container(container)["legend_placement"], PLACEMENT_EXTERNAL)
        self.assertIsNotNone(external)
        self.assertEqual(decode_bytes(container, legend=external)[0], source)

    def test_preshared_universal_roundtrip(self) -> None:
        legend = build_legend(b"", universal=True)
        self.roundtrip(bytes(range(256)), profile=PROFILE_PRESHARED, legend=legend, legend_placement=PLACEMENT_EXTERNAL)

    def test_preshared_incomplete_refuses(self) -> None:
        with self.assertRaisesRegex(LiteHold, "HELD_LEGEND_COVERAGE_INCOMPLETE"):
            encode_bytes(b"abz", profile=PROFILE_PRESHARED, legend=build_legend(b"ab"), legend_placement=PLACEMENT_EXTERNAL)

    def test_visible_preserves_frequency(self) -> None:
        container, *_ = encode_bytes(b"aaaaabbc", profile=PROFILE_DIRECT, occurrence_mode=OCC_VISIBLE)
        counts = sorted(collections.Counter(body_of(container)["events"]).values())
        self.assertEqual(counts, [1, 2, 5])

    def test_keyed_permutation_roundtrip_and_preserves_frequency(self) -> None:
        key = b"correct horse battery staple"
        source = b"aaaaabbc"
        container, _external, _moving, _receipt = self.roundtrip(source, profile=PROFILE_DIRECT, occurrence_mode=OCC_PERMUTE, key=key)
        self.assertEqual(sorted(collections.Counter(body_of(container)["events"]).values()), [1, 2, 5])
        self.assertNotIn(key, container)

    def test_wrong_key_refuses(self) -> None:
        container, *_ = encode_bytes(b"secret message", profile=PROFILE_DIRECT, occurrence_mode=OCC_PERMUTE, key=b"right")
        with self.assertRaisesRegex(LiteHold, "HELD_RECONSTRUCTION_KEY_TAG_MISMATCH"):
            decode_bytes(container, key=b"wrong")

    def test_bounded_alias_respects_limit_and_roundtrips(self) -> None:
        source = b"aaaaaaaaaabbbcc"
        container, _external, moving, _receipt = self.roundtrip(
            source, profile=PROFILE_DIRECT, occurrence_mode=OCC_BOUNDED, alias_limit=2, key=CONCEALMENT_KEY
        )
        self.assertLessEqual(max(collections.Counter(body_of(container)["events"]).values()), 2)
        self.assertIsNotNone(moving)

    def test_bounded_alias_requires_moving_legend(self) -> None:
        container, *_ = encode_bytes(b"aaaa", occurrence_mode=OCC_BOUNDED, alias_limit=1, key=CONCEALMENT_KEY)
        with self.assertRaisesRegex(LiteHold, "HELD_MOVING_LEGEND_MISSING"):
            decode_bytes(container, key=CONCEALMENT_KEY)

    def test_concealment_requires_32_byte_key(self) -> None:
        for key in (None, b"short"):
            with self.assertRaisesRegex(LiteHold, "HELD_AEAD_KEY_TOO_SHORT"):
                encode_bytes(b"aaaa", occurrence_mode=OCC_UNIQUE, key=key)

    def test_unique_body_is_range_only(self) -> None:
        source = b"the the the"
        container, _external, moving, _receipt = self.roundtrip(source, occurrence_mode=OCC_UNIQUE, key=CONCEALMENT_KEY)
        public = deserialize_container(container)
        self.assertEqual(body_of(container), {"count": len(source), "kind": "RANGE", "start": 1})
        self.assertIsNone(public["source_sha256"])
        self.assertIsNone(public["moving_legend_root"])
        self.assertNotIn(b"base_events", container)
        self.assertNotIn("base_events", json.dumps(moving))
        self.assertEqual(moving["algorithm"], "AES-256-GCM")

    def test_unique_same_plaintext_has_distinct_public_containers(self) -> None:
        source = b"same message"
        first, *_ = encode_bytes(source, occurrence_mode=OCC_UNIQUE, key=CONCEALMENT_KEY)
        second, *_ = encode_bytes(source, occurrence_mode=OCC_UNIQUE, key=CONCEALMENT_KEY)
        left, right = deserialize_container(first), deserialize_container(second)
        self.assertNotEqual(first, second)
        self.assertNotEqual(left["container_root"], right["container_root"])
        self.assertNotEqual(left["moving_legend_binding"]["sealed_legend_root"], right["moving_legend_binding"]["sealed_legend_root"])

    def test_unique_equal_length_messages_share_body_shape_not_commitment(self) -> None:
        first, *_ = encode_bytes(b"alpha", occurrence_mode=OCC_UNIQUE, key=CONCEALMENT_KEY)
        second, *_ = encode_bytes(b"bravo", occurrence_mode=OCC_UNIQUE, key=CONCEALMENT_KEY)
        self.assertEqual(body_of(first), body_of(second))
        self.assertNotEqual(deserialize_container(first)["container_root"], deserialize_container(second)["container_root"])

    def test_candidate_plaintext_reencode_cannot_reproduce_public_binding(self) -> None:
        source = b"candidate plaintext"
        first, *_ = encode_bytes(source, occurrence_mode=OCC_UNIQUE, key=CONCEALMENT_KEY)
        guess, *_ = encode_bytes(source, occurrence_mode=OCC_UNIQUE, key=CONCEALMENT_KEY)
        first_binding = deserialize_container(first)["moving_legend_binding"]
        guess_binding = deserialize_container(guess)["moving_legend_binding"]
        self.assertNotEqual(first_binding["artifact_id"], guess_binding["artifact_id"])
        self.assertNotEqual(first_binding["sealed_legend_root"], guess_binding["sealed_legend_root"])

    def test_unique_wrong_moving_legend_refuses(self) -> None:
        from semcrys_lite.core import rooted, sha256

        container, _external, moving, _receipt = encode_bytes(b"abcdef", occurrence_mode=OCC_UNIQUE, key=CONCEALMENT_KEY)
        tampered = dict(moving)
        ciphertext = bytearray(base64.b64decode(tampered["ciphertext_b64"]))
        ciphertext[-1] ^= 1
        tampered.pop("sealed_legend_root")
        tampered["ciphertext_b64"] = base64.b64encode(ciphertext).decode("ascii")
        tampered["ciphertext_sha256"] = sha256(bytes(ciphertext))
        tampered = rooted(tampered, "sealed_legend_root")
        public = deserialize_container(container)
        public.pop("container_root")
        public["moving_legend_binding"]["sealed_legend_root"] = tampered["sealed_legend_root"]
        public["moving_legend_binding"]["ciphertext_sha256"] = tampered["ciphertext_sha256"]
        public = rooted(public, "container_root")
        with self.assertRaisesRegex(LiteHold, "HELD_MOVING_LEGEND_AUTHENTICATION"):
            decode_bytes(canonical_bytes(public), moving_legend=tampered, key=CONCEALMENT_KEY)

    def test_unique_wrong_key_refuses(self) -> None:
        container, _external, moving, _receipt = encode_bytes(b"abcdef", occurrence_mode=OCC_UNIQUE, key=CONCEALMENT_KEY)
        with self.assertRaisesRegex(LiteHold, "HELD_MOVING_LEGEND_AUTHENTICATION"):
            decode_bytes(container, moving_legend=moving, key=b"different-candidate-key-32bytes!")

    def test_unique_wrong_companion_refuses(self) -> None:
        container, _external, _moving, _receipt = encode_bytes(b"abcdef", occurrence_mode=OCC_UNIQUE, key=CONCEALMENT_KEY)
        _other_container, _other_external, other_moving, _other_receipt = encode_bytes(
            b"ghijkl", occurrence_mode=OCC_UNIQUE, key=CONCEALMENT_KEY
        )
        with self.assertRaisesRegex(LiteHold, "HELD_MOVING_LEGEND_MISMATCH"):
            decode_bytes(container, moving_legend=other_moving, key=CONCEALMENT_KEY)

    def test_unique_tampered_nonce_refuses_authentication(self) -> None:
        from semcrys_lite.core import rooted

        container, _external, moving, _receipt = encode_bytes(b"abcdef", occurrence_mode=OCC_UNIQUE, key=CONCEALMENT_KEY)
        tampered = dict(moving)
        nonce = bytearray(base64.b64decode(tampered["nonce_b64"]))
        nonce[0] ^= 1
        tampered.pop("sealed_legend_root")
        tampered["nonce_b64"] = base64.b64encode(nonce).decode("ascii")
        tampered = rooted(tampered, "sealed_legend_root")
        public = deserialize_container(container)
        public.pop("container_root")
        public["moving_legend_binding"]["sealed_legend_root"] = tampered["sealed_legend_root"]
        public = rooted(public, "container_root")
        with self.assertRaisesRegex(LiteHold, "HELD_MOVING_LEGEND_AUTHENTICATION"):
            decode_bytes(canonical_bytes(public), moving_legend=tampered, key=CONCEALMENT_KEY)

    def test_container_root_tamper_refuses(self) -> None:
        container, *_ = encode_bytes(b"abc")
        value = deserialize_container(container)
        value["event_count"] = 999
        with self.assertRaisesRegex(LiteHold, "HELD_CONTAINER_ROOT_MISMATCH"):
            decode_bytes(canonical_bytes(value))

    def test_body_digest_tamper_refuses_after_valid_reroot(self) -> None:
        from semcrys_lite.core import rooted
        container, *_ = encode_bytes(b"abc", body_representation=BODY_JSON_EVENTS)
        value = deserialize_container(container)
        value.pop("container_root")
        value["body"]["events"][0] = 1
        value = rooted(value, "container_root")
        with self.assertRaisesRegex(LiteHold, "HELD_BODY_DIGEST_MISMATCH"):
            decode_bytes(canonical_bytes(value))

    def test_ambiguous_body_carrier_refuses(self) -> None:
        from semcrys_lite.core import rooted
        container, *_ = encode_bytes(b"abc", body_representation=BODY_JSON_EVENTS)
        value = deserialize_container(container)
        value.pop("container_root")
        value["body_b64"] = base64.b64encode(b"{}").decode("ascii")
        value = rooted(value, "container_root")
        with self.assertRaisesRegex(LiteHold, "HELD_BODY_CARRIER_AMBIGUOUS"):
            decode_bytes(canonical_bytes(value))

    def test_explicit_legacy_v02_visible_container_decodes(self) -> None:
        from semcrys_lite.core import rooted, sha256
        body = canonical_bytes({"kind": "EVENTS", "events": [97, 98, 99]})
        legacy = rooted({
            "schema": "semcrys-lite.crys.v0.2.candidate",
            "format": "CRYS-LITE-0.2",
            "standing": "CANDIDATE_ONLY",
            "profile": PROFILE_DIRECT,
            "legend_placement": "NONE",
            "base_legend_root": None,
            "embedded_base_legend": None,
            "moving_legend_root": None,
            "moving_legend_binding": None,
            "occurrence_mode": OCC_VISIBLE,
            "alias_limit": None,
            "outer_codec": OUTER_NONE,
            "event_count": 3,
            "body_encoding": "JSON",
            "body_b64": base64.b64encode(body).decode("ascii"),
            "body_sha256": sha256(body),
            "source_sha256": sha256(b"abc"),
            "verification": {"public_equality_preserved": True},
            "security_claim": "NONE",
        }, "container_root")
        restored, _receipt = decode_bytes(canonical_bytes(legacy))
        self.assertEqual(restored, b"abc")

    def test_wrong_base_legend_refuses(self) -> None:
        source = b"abc"
        correct = build_legend(source)
        container, *_ = encode_bytes(source, profile=PROFILE_PRESHARED, legend=correct, legend_placement=PLACEMENT_EXTERNAL)
        with self.assertRaisesRegex(LiteHold, "HELD_EXTERNAL_LEGEND_MISMATCH"):
            decode_bytes(container, legend=build_legend(b"xyz"))

    def test_inspection_excludes_embedded_legend_and_body(self) -> None:
        container, *_ = encode_bytes(b"abc", profile=PROFILE_LOCAL)
        inspected = inspect_container(container)
        self.assertNotIn("embedded_base_legend", inspected)
        self.assertNotIn("body_b64", inspected)

    def test_inspection_body_flag_and_explanation(self) -> None:
        container, *_ = encode_bytes(b"abc", body_representation=BODY_JSON_EVENTS)
        inspected = inspect_container(container, include_body=True)
        self.assertEqual(inspected["body"]["events"], [97, 98, 99])
        explained = explain_container(container)
        self.assertEqual(explained["where_are_the_bytes"]["public_body_carrier"], "DIRECT_JSON")
        self.assertEqual(explained["requirements_to_reconstruct"]["runtime_key"], False)

    def test_legend_root_detects_duplicate_byte(self) -> None:
        legend = build_legend(b"ab")
        legend["entries"][1]["byte"] = legend["entries"][0]["byte"]
        with self.assertRaisesRegex(LiteHold, "HELD_LEGEND_ROOT_MISMATCH"):
            legend_bytes(legend)

    def test_cli_refusal_is_typed_and_leaves_no_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.bin"
            output = root / "output.crys"
            source.write_bytes(b"abc")
            completed = subprocess.run(
                [sys.executable, "-B", "-m", "semcrys_lite", "encode", str(source), str(output), "--profile", PROFILE_PRESHARED],
                cwd=BASE, capture_output=True, text=True,
            )
            self.assertEqual(completed.returncode, 1)
            self.assertEqual(json.loads(completed.stdout)["code"], "HELD_PRESHARED_LEGEND_REQUIRED")
            self.assertFalse(output.exists())

    def test_cli_key_is_not_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, output, receipt = root / "source.bin", root / "out.crys", root / "receipt.json"
            source.write_bytes(b"repeat repeat")
            env = dict(os.environ)
            env["SEMCRYS_LITE_KEY"] = "not-recorded-secret"
            completed = subprocess.run(
                [sys.executable, "-B", "-m", "semcrys_lite", "encode", str(source), str(output), "--occurrence", OCC_PERMUTE, "--receipt", str(receipt)],
                cwd=BASE, env=env, capture_output=True, text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertNotIn(b"not-recorded-secret", output.read_bytes())
            self.assertNotIn("not-recorded-secret", receipt.read_text(encoding="utf-8"))

    def test_cli_invalid_moving_legend_detail_is_stable_and_no_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, container, moving, restored, key_file = (
                root / "source.bin", root / "out.crys", root / "moving.leg", root / "restored.bin", root / "key.bin"
            )
            source.write_bytes(b"secret")
            key_file.write_bytes(CONCEALMENT_KEY)
            env = dict(os.environ)
            encoded = subprocess.run(
                [sys.executable, "-B", "-m", "semcrys_lite", "encode", str(source), str(container),
                 "--occurrence", OCC_UNIQUE, "--moving-legend-out", str(moving), "--key-file", str(key_file)],
                cwd=BASE, env=env, capture_output=True, text=True,
            )
            self.assertEqual(encoded.returncode, 0, encoded.stderr)
            moving.write_bytes(b"\x81")
            decoded = subprocess.run(
                [sys.executable, "-B", "-m", "semcrys_lite", "decode", str(container), str(restored),
                 "--moving-legend", str(moving), "--key-file", str(key_file)],
                cwd=BASE, env=env, capture_output=True, text=True,
            )
            refusal = json.loads(decoded.stdout)
            self.assertEqual(decoded.returncode, 1)
            self.assertEqual(refusal["code"], "HELD_MOVING_LEGEND_MALFORMED")
            self.assertEqual(refusal["detail"], "INVALID_UTF8")
            self.assertFalse(restored.exists())

    def test_cli_wrong_concealment_key_refuses_and_leaves_no_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, container, moving, restored, right_key, wrong_key = (
                root / "source.bin", root / "out.crys", root / "moving.leg", root / "restored.bin",
                root / "right.key", root / "wrong.key"
            )
            source.write_bytes(b"secret")
            right_key.write_bytes(CONCEALMENT_KEY)
            wrong_key.write_bytes(b"different-candidate-key-32bytes!")
            encoded = subprocess.run(
                [sys.executable, "-B", "-m", "semcrys_lite", "encode", str(source), str(container),
                 "--occurrence", OCC_UNIQUE, "--moving-legend-out", str(moving), "--key-file", str(right_key)],
                cwd=BASE, capture_output=True, text=True,
            )
            self.assertEqual(encoded.returncode, 0, encoded.stderr)
            decoded = subprocess.run(
                [sys.executable, "-B", "-m", "semcrys_lite", "decode", str(container), str(restored),
                 "--moving-legend", str(moving), "--key-file", str(wrong_key)],
                cwd=BASE, capture_output=True, text=True,
            )
            self.assertEqual(decoded.returncode, 1)
            self.assertEqual(json.loads(decoded.stdout)["code"], "HELD_MOVING_LEGEND_AUTHENTICATION")
            self.assertFalse(restored.exists())

    def test_size_advisory_recommends_lzma_when_reference_output_expands(self) -> None:
        _container, _external, _moving, receipt = encode_bytes(b"tiny")
        self.assertEqual(receipt["size_advisory"]["status"], "EXPANDED")
        self.assertEqual(receipt["size_advisory"]["recommendation"], "TRY_OUTER_LZMA_FOR_SIZE")

    def test_cli_demo_emits_rooted_teaching_report(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-B", "-m", "semcrys_lite", "demo"],
            cwd=BASE, capture_output=True, text=True,
        )
        report = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(report["standing"], "CANDIDATE_ONLY")
        self.assertEqual(len(report["comparison"]["rows"]), 5)
        self.assertIn("demonstration_root", report)

    def test_cli_compare_holds_keyed_rows_without_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.bin"
            source.write_bytes(b"repeat repeat")
            env = dict(os.environ)
            env.pop("SEMCRYS_LITE_KEY", None)
            completed = subprocess.run(
                [sys.executable, "-B", "-m", "semcrys_lite", "compare", str(source)],
                cwd=BASE, env=env, capture_output=True, text=True,
            )
            report = json.loads(completed.stdout)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(report["rows"][2]["status"], "HELD_KEY_REQUIRED_FOR_COMPARISON")

    def test_cli_inspect_body_and_explain(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, container = root / "source.bin", root / "out.crys"
            source.write_bytes(b"abc")
            encoded = subprocess.run(
                [sys.executable, "-B", "-m", "semcrys_lite", "encode", str(source), str(container)],
                cwd=BASE, capture_output=True, text=True,
            )
            self.assertEqual(encoded.returncode, 0, encoded.stderr)
            inspected = subprocess.run(
                [sys.executable, "-B", "-m", "semcrys_lite", "inspect", str(container), "--body"],
                cwd=BASE, capture_output=True, text=True,
            )
            explained = subprocess.run(
                [sys.executable, "-B", "-m", "semcrys_lite", "explain", str(container)],
                cwd=BASE, capture_output=True, text=True,
            )
            inspection = json.loads(inspected.stdout)
            self.assertEqual(inspection["body"]["events"], [97, 98, 99])
            self.assertEqual(inspection["body_representation"], "PACKED_VARINT")
            self.assertIn("where_are_the_bytes", json.loads(explained.stdout))

    def test_cli_homophonic_positional_preset_is_explicit_and_reversible(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.bin"
            container = root / "out.crys"
            moving = root / "moving.json"
            restored = root / "restored.bin"
            key_file = root / "key.bin"
            source.write_bytes(b"alpha beta gamma " * 37)
            key_file.write_bytes(CONCEALMENT_KEY)
            encoded = subprocess.run(
                [sys.executable, "-B", "-m", "semcrys_lite", "encode",
                 str(source), str(container), "--security-preset", "homophonic-positional",
                 "--moving-legend-out", str(moving), "--key-file", str(key_file)],
                cwd=BASE, capture_output=True, text=True,
            )
            self.assertEqual(encoded.returncode, 0, encoded.stderr)
            public = deserialize_container(container.read_bytes())
            self.assertEqual(public["position_policy"], POSITION_CONCEAL)
            self.assertEqual(public["padding_policy"], "NONE")
            decoded = subprocess.run(
                [sys.executable, "-B", "-m", "semcrys_lite", "decode",
                 str(container), str(restored), "--moving-legend", str(moving),
                 "--key-file", str(key_file)],
                cwd=BASE, capture_output=True, text=True,
            )
            self.assertEqual(decoded.returncode, 0, decoded.stderr)
            self.assertEqual(restored.read_bytes(), source.read_bytes())


if __name__ == "__main__":
    unittest.main()
