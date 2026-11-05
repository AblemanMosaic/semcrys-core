from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from semcrys.protected_artifact import (
    MAGIC,
    PADDING_FIXED,
    PADDING_POWER_OF_TWO,
    ProtectedArtifactHold,
    inspect_bytes,
    protect_bytes,
    rotate_bytes,
    unprotect_bytes,
    write_atomic,
)
from semcrys_core.dispatch import detect_bytes


KEY = b"0123456789abcdef0123456789abcdef"
NEW_KEY = b"fedcba9876543210fedcba9876543210"


class ProtectedArtifactTests(unittest.TestCase):
    def test_group_legend_round_trip_and_padding(self):
        source = b"group legend archive" * 200
        envelope, receipt = protect_bytes(
            source, key=KEY, role="GROUP_LEGEND_ARCHIVE", padding_policy=PADDING_POWER_OF_TWO
        )
        viewed = inspect_bytes(envelope)
        self.assertEqual(detect_bytes(envelope), "PROTECTED_ARTIFACT_0_1")
        self.assertEqual(viewed["role"], "GROUP_LEGEND_ARCHIVE")
        self.assertGreater(viewed["padded_plaintext_bytes"], len(source))
        restored, opened = unprotect_bytes(envelope, key=KEY)
        self.assertEqual(restored, source)
        self.assertIsNone(opened["source_sha256"])
        self.assertIsNone(receipt["source_sha256"])
        self.assertIsNone(opened["source_bytes"])
        self.assertIsNone(receipt["source_bytes"])

    def test_public_header_hides_source_metadata_and_unlinks_key_identifier(self):
        source = b"same protected artifact" * 20
        first, _ = protect_bytes(source, key=KEY, role="GENERIC_ARTIFACT")
        second, _ = protect_bytes(source, key=KEY, role="GENERIC_ARTIFACT")
        first_view = inspect_bytes(first)
        second_view = inspect_bytes(second)
        for field in ("source_bytes", "source_sha256"):
            self.assertNotIn(field, first_view)
            self.assertNotIn(field, second_view)
        self.assertEqual(first_view["private_metadata"], "ENCRYPTED_SOURCE_LENGTH_AND_SHA256")
        self.assertNotEqual(first_view["key_identifier"], second_view["key_identifier"])
        self.assertNotEqual(first, second)

    def test_wrong_key_and_tamper_refuse(self):
        envelope, _ = protect_bytes(b"index", key=KEY, role="SEMANTIC_INDEX")
        with self.assertRaises(ProtectedArtifactHold):
            unprotect_bytes(envelope, key=NEW_KEY)
        damaged = bytearray(envelope)
        damaged[-1] ^= 1
        with self.assertRaises(ProtectedArtifactHold):
            unprotect_bytes(bytes(damaged), key=KEY)

    def test_rerooted_malformed_size_refuses_with_typed_hold(self):
        import hashlib
        import json

        envelope, _ = protect_bytes(b"index", key=KEY, role="SEMANTIC_INDEX")
        header_size = int.from_bytes(envelope[len(MAGIC):len(MAGIC) + 8], "big")
        start = len(MAGIC) + 8
        header = json.loads(envelope[start:start + header_size])
        header["padded_plaintext_bytes"] = "not-an-integer"
        header.pop("envelope_root")
        canonical = json.dumps(header, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
        header["envelope_root"] = hashlib.sha256(canonical).hexdigest()
        encoded = json.dumps(header, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
        malformed = MAGIC + len(encoded).to_bytes(8, "big") + encoded + envelope[start + header_size:]
        with self.assertRaisesRegex(ProtectedArtifactHold, "HELD_PROTECTED_PLAINTEXT_SIZE"):
            inspect_bytes(malformed)

    def test_fixed_class_refuses_undersized_bucket(self):
        with self.assertRaises(ProtectedArtifactHold):
            protect_bytes(
                b"too large", key=KEY, role="GENERIC_ARTIFACT",
                padding_policy=PADDING_FIXED, padding_bucket=4,
            )

    def test_rotation_preserves_plaintext_identity(self):
        source = b"seekable metalegend bytes"
        envelope, _ = protect_bytes(source, key=KEY, role="RECURSIVE_METALEGEND")
        rotated, receipt = rotate_bytes(envelope, old_key=KEY, new_key=NEW_KEY)
        restored, _ = unprotect_bytes(rotated, key=NEW_KEY)
        self.assertEqual(restored, source)
        self.assertFalse(receipt["source_reencoded"])

    def test_atomic_write_refuses_existing_destination(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "protected.bin"
            output.write_bytes(b"existing")
            with self.assertRaisesRegex(ProtectedArtifactHold, "HELD_PROTECTED_DESTINATION_EXISTS"):
                write_atomic(output, b"replacement")
            self.assertEqual(output.read_bytes(), b"existing")


if __name__ == "__main__":
    unittest.main()
