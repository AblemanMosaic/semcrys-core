"""Bounded local cache for framed recursive metalegends.

Cache entries are derivable acceleration artifacts. Every read is verified
against roots committed by the metalegend header; cache presence never changes
semantic identity, authority, or exact inverse requirements.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import tempfile


class MetalegendCache:
    def __init__(self, root: str | Path, instance_root: str) -> None:
        self.root = Path(root) / "metalegend" / instance_root
        self.frames = self.root / "frames"
        self.full = self.root / "full"
        self.stats = {"frame_hits": 0, "frame_misses": 0, "frame_writes": 0,
                      "full_hits": 0, "full_misses": 0, "full_writes": 0}

    @staticmethod
    def _sha(raw: bytes) -> str:
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _atomic_write(path: Path, raw: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".pending",
                                                  dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def frame_path(self, ordinal: int, recipe_sha256: str) -> Path:
        return self.frames / f"{ordinal:08d}-{recipe_sha256}.recipe"

    def load_frame(self, ordinal: int, recipe_sha256: str, recipe_bytes: int) -> bytes | None:
        path = self.frame_path(ordinal, recipe_sha256)
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            self.stats["frame_misses"] += 1
            return None
        if len(raw) != recipe_bytes or self._sha(raw) != recipe_sha256:
            try:
                path.unlink()
            except OSError:
                pass
            self.stats["frame_misses"] += 1
            return None
        self.stats["frame_hits"] += 1
        return raw

    def store_frame(self, ordinal: int, recipe_sha256: str, raw: bytes) -> Path:
        if self._sha(raw) != recipe_sha256:
            raise ValueError("HELD_METALEGEND_CACHE_FRAME_ROOT")
        path = self.frame_path(ordinal, recipe_sha256)
        if not path.exists():
            self._atomic_write(path, raw)
            self.stats["frame_writes"] += 1
        return path

    def full_path(self, source_legend_sha256: str) -> Path:
        return self.full / f"{source_legend_sha256}.leg"

    def verified_full(self, source_legend_sha256: str, source_legend_bytes: int) -> Path | None:
        path = self.full_path(source_legend_sha256)
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            self.stats["full_misses"] += 1
            return None
        if size != source_legend_bytes:
            try:
                path.unlink()
            except OSError as error:
                raise ValueError("HELD_METALEGEND_CACHE_INVALID_FULL") from error
            self.stats["full_misses"] += 1
            return None
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while block := handle.read(1024 * 1024):
                digest.update(block)
        if digest.hexdigest() != source_legend_sha256:
            try:
                path.unlink()
            except OSError as error:
                raise ValueError("HELD_METALEGEND_CACHE_INVALID_FULL") from error
            self.stats["full_misses"] += 1
            return None
        self.stats["full_hits"] += 1
        return path

    def publish_full(self, pending: Path, source_legend_sha256: str,
                     source_legend_bytes: int) -> Path:
        path = self.full_path(source_legend_sha256)
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = self.verified_full(source_legend_sha256, source_legend_bytes)
        if existing is not None:
            pending.unlink(missing_ok=True)
            return existing
        os.replace(pending, path)
        self.stats["full_writes"] += 1
        return path

    def receipt(self) -> dict:
        return {
            "schema": "semcrys.metalegend-cache-receipt.v0.1",
            "cache_role": "DERIVABLE_LOCAL_ACCELERATION_ONLY",
            "semantic_identity_effect": "NONE",
            "authority_effect": "NONE",
            "stats": dict(self.stats),
        }
