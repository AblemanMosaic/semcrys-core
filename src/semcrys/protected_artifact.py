"""Authenticated protection for complete SemCrys dependency artifacts.

This envelope is deliberately separate from semantic identity. It can protect a
group legend, index, bespoke legend, or recursive metalegend without changing
the bytes that artifact represents. It uses the optional secure dependency and
makes no whole-protocol security claim.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import tempfile
from pathlib import Path
from typing import Any


MAGIC = b"SCPROT1\n"
SCHEMA = "semcrys.protected-artifact.v0.1"
ROLES = (
    "GROUP_LEGEND_ARCHIVE",
    "SEMANTIC_INDEX",
    "BESPOKE_LEGEND",
    "RECURSIVE_METALEGEND",
    "GENERIC_ARTIFACT",
)
PADDING_NONE = "NONE"
PADDING_POWER_OF_TWO = "POWER_OF_TWO"
PADDING_MULTIPLE = "MULTIPLE"
PADDING_FIXED = "FIXED_CLASS"
PADDING_POLICIES = (PADDING_NONE, PADDING_POWER_OF_TWO, PADDING_MULTIPLE, PADDING_FIXED)
MAX_PROTECTED_PLAINTEXT_BYTES = 512 * 1024 * 1024
MAX_ARTIFACT_BYTES = MAX_PROTECTED_PLAINTEXT_BYTES - 8


class ProtectedArtifactHold(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require(condition: bool, code: str, detail: str = "") -> None:
    if not condition:
        raise ProtectedArtifactHold(code, detail)


def _backend():
    try:
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    except ImportError as error:
        raise ProtectedArtifactHold("HELD_AEAD_BACKEND_UNAVAILABLE", "INSTALL_SEMCRYS_SECURE_PROFILE") from error
    return AESGCM, HKDF, hashes, InvalidTag


def _target_size(value: int, policy: str, bucket: int | None) -> int:
    _require(policy in PADDING_POLICIES, "HELD_PROTECTED_PADDING_POLICY", policy)
    if policy == PADDING_NONE:
        return value
    if policy == PADDING_POWER_OF_TWO:
        return 1 if value <= 1 else 1 << (value - 1).bit_length()
    _require(isinstance(bucket, int) and bucket > 0, "HELD_PROTECTED_PADDING_BUCKET")
    if policy == PADDING_FIXED:
        _require(bucket >= value, "HELD_PROTECTED_PADDING_FIXED_CLASS")
        return bucket
    return ((value + bucket - 1) // bucket) * bucket


def _derive_keys(key: bytes, salt: bytes) -> tuple[bytes, bytes]:
    _AESGCM, HKDF, hashes, _InvalidTag = _backend()
    material = HKDF(
        algorithm=hashes.SHA256(), length=64, salt=salt,
        info=b"semcrys-protected-artifact-v0.1-subkeys",
    ).derive(key)
    return material[:32], material[32:]


def _key_identifier(identifier_key: bytes, artifact_id: str) -> str:
    return hmac.new(
        identifier_key,
        b"semcrys-protected-artifact-key-id-v2\x00" + artifact_id.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()[:32]


def protect_bytes(data: bytes, *, key: bytes, role: str,
                  padding_policy: str = PADDING_POWER_OF_TWO,
                  padding_bucket: int | None = None) -> tuple[bytes, dict[str, Any]]:
    _require(isinstance(data, bytes) and len(data) <= MAX_ARTIFACT_BYTES, "HELD_PROTECTED_ARTIFACT_SIZE")
    _require(isinstance(key, bytes) and len(key) >= 32, "HELD_AEAD_KEY_TOO_SHORT", "MINIMUM_32_BYTES")
    _require(role in ROLES, "HELD_PROTECTED_ARTIFACT_ROLE", role)
    AESGCM, _HKDF, _hashes, _InvalidTag = _backend()
    artifact_id = secrets.token_hex(16)
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    private_metadata = _canonical({
        "source_sha256": _sha(data),
        "source_bytes": len(data),
    })
    minimum = len(data) + len(private_metadata) + 8
    target = _target_size(minimum, padding_policy, padding_bucket)
    _require(target <= MAX_PROTECTED_PLAINTEXT_BYTES, "HELD_PROTECTED_PADDING_SIZE")
    plaintext = (
        len(private_metadata).to_bytes(8, "big") + private_metadata + data
        + secrets.token_bytes(target - minimum)
    )
    encryption_key, identifier_key = _derive_keys(key, salt)
    context = {
        "schema": SCHEMA,
        "artifact_id": artifact_id,
        "role": role,
        "padding_policy": padding_policy,
        "padding_bucket": padding_bucket,
        "padded_plaintext_bytes": len(plaintext),
        "algorithm": "AES-256-GCM",
        "kdf": "HKDF-SHA256",
        "key_identifier": _key_identifier(identifier_key, artifact_id),
        "private_metadata": "ENCRYPTED_SOURCE_LENGTH_AND_SHA256",
        "semantic_identity_effect": "NONE",
        "security_claim": "NONE",
    }
    aad = _canonical(context)
    ciphertext = AESGCM(encryption_key).encrypt(nonce, plaintext, aad)
    header = {
        **context,
        "salt_b64": base64.b64encode(salt).decode("ascii"),
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "aad_sha256": _sha(aad),
        "ciphertext_sha256": _sha(ciphertext),
        "ciphertext_bytes": len(ciphertext),
        "primitive_claim": "ESTABLISHED_AEAD_INTEGRATION_WITHOUT_END_TO_END_SECURITY_PROOF",
    }
    header["envelope_root"] = _sha(_canonical(header))
    encoded_header = _canonical(header)
    envelope = MAGIC + len(encoded_header).to_bytes(8, "big") + encoded_header + ciphertext
    receipt = {
        "schema": "semcrys.protected-artifact-receipt.v0.1",
        "operation": "PROTECT",
        "status": "PASS",
        "role": role,
        "source_sha256": None,
        "source_bytes": None,
        "source_metadata": "ENCRYPTED_REDACTED_FROM_PUBLIC_RECEIPT",
        "envelope_sha256": _sha(envelope),
        "envelope_bytes": len(envelope),
        "envelope_root": header["envelope_root"],
        "padding_policy": padding_policy,
        "key_identifier": context["key_identifier"],
        "security_claim": "NONE",
    }
    receipt["receipt_root"] = _sha(_canonical(receipt))
    return envelope, receipt


def _parse(envelope: bytes) -> tuple[dict[str, Any], bytes, dict[str, Any]]:
    _require(len(envelope) <= MAX_PROTECTED_PLAINTEXT_BYTES + (2 << 20),
             "HELD_PROTECTED_ENVELOPE_SIZE")
    _require(envelope.startswith(MAGIC) and len(envelope) >= len(MAGIC) + 8, "HELD_PROTECTED_ENVELOPE_MAGIC")
    header_size = int.from_bytes(envelope[len(MAGIC):len(MAGIC) + 8], "big")
    start = len(MAGIC) + 8
    end = start + header_size
    _require(0 < header_size <= 1 << 20 and end <= len(envelope), "HELD_PROTECTED_ENVELOPE_HEADER")
    try:
        header = json.loads(envelope[start:end].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtectedArtifactHold("HELD_PROTECTED_ENVELOPE_HEADER") from error
    _require(isinstance(header, dict), "HELD_PROTECTED_ENVELOPE_HEADER")
    claimed = header.get("envelope_root")
    unrooted = dict(header)
    unrooted.pop("envelope_root", None)
    _require(isinstance(claimed, str) and hmac.compare_digest(_sha(_canonical(unrooted)), claimed),
             "HELD_PROTECTED_ENVELOPE_ROOT")
    ciphertext = envelope[end:]
    _require(len(ciphertext) == header.get("ciphertext_bytes")
             and hmac.compare_digest(_sha(ciphertext), str(header.get("ciphertext_sha256"))),
             "HELD_PROTECTED_CIPHERTEXT_ROOT")
    context_keys = (
        "schema", "artifact_id", "role", "padding_policy",
        "padding_bucket", "padded_plaintext_bytes", "algorithm", "kdf", "key_identifier",
        "private_metadata", "semantic_identity_effect", "security_claim",
    )
    context = {field: header.get(field) for field in context_keys}
    _require(context["schema"] == SCHEMA and context["role"] in ROLES, "HELD_PROTECTED_ENVELOPE_SCHEMA")
    _require(context["algorithm"] == "AES-256-GCM" and context["kdf"] == "HKDF-SHA256",
             "HELD_PROTECTED_ENVELOPE_ALGORITHM")
    _require(context["semantic_identity_effect"] == "NONE" and context["security_claim"] == "NONE",
             "HELD_PROTECTED_ENVELOPE_CLAIM")
    _require(isinstance(context["padded_plaintext_bytes"], int)
             and 8 <= context["padded_plaintext_bytes"] <= MAX_PROTECTED_PLAINTEXT_BYTES,
             "HELD_PROTECTED_PLAINTEXT_SIZE")
    _require(context["padding_policy"] in PADDING_POLICIES,
             "HELD_PROTECTED_PADDING_POLICY")
    _require(context["padding_bucket"] is None
             or isinstance(context["padding_bucket"], int),
             "HELD_PROTECTED_PADDING_BUCKET")
    _require(context["private_metadata"] == "ENCRYPTED_SOURCE_LENGTH_AND_SHA256",
             "HELD_PROTECTED_PRIVATE_METADATA")
    _require(isinstance(context["key_identifier"], str)
             and len(context["key_identifier"]) == 32,
             "HELD_PROTECTED_KEY_IDENTIFIER")
    _require(len(ciphertext) == context["padded_plaintext_bytes"] + 16,
             "HELD_PROTECTED_CIPHERTEXT_SIZE")
    return header, ciphertext, context


def inspect_bytes(envelope: bytes) -> dict[str, Any]:
    header, _ciphertext, _context = _parse(envelope)
    return {
        "schema": "semcrys.protected-artifact-inspection.v0.1",
        "status": "PASS",
        **{field: header[field] for field in (
            "artifact_id", "role", "padding_policy",
            "padding_bucket", "padded_plaintext_bytes", "ciphertext_bytes", "key_identifier",
            "private_metadata", "envelope_root", "security_claim",
        )},
        "envelope_sha256": _sha(envelope),
        "envelope_bytes": len(envelope),
    }


def unprotect_bytes(envelope: bytes, *, key: bytes) -> tuple[bytes, dict[str, Any]]:
    _require(isinstance(key, bytes) and len(key) >= 32, "HELD_AEAD_KEY_TOO_SHORT", "MINIMUM_32_BYTES")
    header, ciphertext, context = _parse(envelope)
    try:
        salt = base64.b64decode(header["salt_b64"], validate=True)
        nonce = base64.b64decode(header["nonce_b64"], validate=True)
    except (KeyError, ValueError) as error:
        raise ProtectedArtifactHold("HELD_PROTECTED_ENVELOPE_NONCE") from error
    _require(len(salt) == 16 and len(nonce) == 12, "HELD_PROTECTED_ENVELOPE_NONCE")
    encryption_key, identifier_key = _derive_keys(key, salt)
    _require(
        hmac.compare_digest(_key_identifier(identifier_key, context["artifact_id"]), context["key_identifier"]),
        "HELD_PROTECTED_KEY_IDENTIFIER",
    )
    aad = _canonical(context)
    _require(hmac.compare_digest(_sha(aad), str(header.get("aad_sha256"))), "HELD_PROTECTED_AAD_ROOT")
    AESGCM, _HKDF, _hashes, InvalidTag = _backend()
    try:
        plaintext = AESGCM(encryption_key).decrypt(nonce, ciphertext, aad)
    except InvalidTag as error:
        raise ProtectedArtifactHold("HELD_PROTECTED_AUTHENTICATION") from error
    _require(len(plaintext) == context["padded_plaintext_bytes"] and len(plaintext) >= 8,
             "HELD_PROTECTED_PLAINTEXT_SIZE")
    metadata_size = int.from_bytes(plaintext[:8], "big")
    _require(0 < metadata_size <= len(plaintext) - 8, "HELD_PROTECTED_PRIVATE_METADATA")
    try:
        metadata = json.loads(plaintext[8:8 + metadata_size].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtectedArtifactHold("HELD_PROTECTED_PRIVATE_METADATA") from error
    _require(isinstance(metadata, dict) and set(metadata) == {"source_bytes", "source_sha256"},
             "HELD_PROTECTED_PRIVATE_METADATA")
    source_size = metadata.get("source_bytes")
    source_root = metadata.get("source_sha256")
    source_start = 8 + metadata_size
    _require(isinstance(source_size, int) and 0 <= source_size <= MAX_ARTIFACT_BYTES
             and source_start + source_size <= len(plaintext), "HELD_PROTECTED_SOURCE_SIZE")
    _require(isinstance(source_root, str) and len(source_root) == 64,
             "HELD_PROTECTED_SOURCE_ROOT")
    source = plaintext[source_start:source_start + source_size]
    _require(hmac.compare_digest(_sha(source), source_root), "HELD_PROTECTED_SOURCE_ROOT")
    receipt = {
        "schema": "semcrys.protected-artifact-receipt.v0.1",
        "operation": "UNPROTECT",
        "status": "PASS",
        "role": context["role"],
        "source_sha256": None,
        "source_bytes": None,
        "source_metadata": "VERIFIED_AFTER_AUTHENTICATED_DECRYPTION_REDACTED_FROM_RECEIPT",
        "envelope_sha256": _sha(envelope),
        "envelope_root": header["envelope_root"],
        "key_identifier": context["key_identifier"],
        "security_claim": "NONE",
    }
    receipt["receipt_root"] = _sha(_canonical(receipt))
    return source, receipt


def rotate_bytes(envelope: bytes, *, old_key: bytes, new_key: bytes) -> tuple[bytes, dict[str, Any]]:
    inspection = inspect_bytes(envelope)
    source, opened = unprotect_bytes(envelope, key=old_key)
    rotated, protected = protect_bytes(
        source,
        key=new_key,
        role=inspection["role"],
        padding_policy=inspection["padding_policy"],
        padding_bucket=inspection["padding_bucket"],
    )
    receipt = {
        "schema": "semcrys.protected-artifact-receipt.v0.1",
        "operation": "ROTATE_KEY",
        "status": "PASS",
        "role": inspection["role"],
        "source_sha256": None,
        "source_bytes": None,
        "source_metadata": "VERIFIED_DURING_KEY_ROTATION_REDACTED_FROM_RECEIPT",
        "prior_envelope_sha256": opened["envelope_sha256"],
        "envelope_sha256": protected["envelope_sha256"],
        "envelope_root": protected["envelope_root"],
        "old_key_identifier": inspection["key_identifier"],
        "new_key_identifier": protected["key_identifier"],
        "source_reencoded": False,
        "security_claim": "NONE",
    }
    receipt["receipt_root"] = _sha(_canonical(receipt))
    return rotated, receipt


def protect_file(source: Path, output: Path, **kwargs: Any) -> dict[str, Any]:
    envelope, receipt = protect_bytes(source.read_bytes(), **kwargs)
    write_atomic(output, envelope)
    return receipt


def unprotect_file(source: Path, output: Path, *, key: bytes) -> dict[str, Any]:
    data, receipt = unprotect_bytes(source.read_bytes(), key=key)
    write_atomic(output, data)
    return receipt


def write_atomic(output: Path, data: bytes) -> None:
    _require(not output.exists(), "HELD_PROTECTED_DESTINATION_EXISTS", str(output))
    output.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=output.name + ".", suffix=".tmp", dir=output.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
