"""Seekable framed recursive metalegends with exact legend restoration.

The SCMLEG2 physical profile keeps the proven block-local prefix recipes but
compresses bounded superframes independently. A reader can therefore resolve a
single legend integer without inflating the complete recursive representation.
The public product remains SemCrys v0.1; this is an additive physical dialect.
"""
from __future__ import annotations

from collections import OrderedDict
import bisect
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import struct
import tempfile
from typing import Iterable, Iterator

from streaming_app.core import Refusal, protect_outputs
from streaming_legend.core import CHUNK, LegendReader, _vdec, _venc, canonical, file_sha256

from .metalegend_cache import MetalegendCache
from .recursive_metalegend import (
    ALLOWED_PRESETS,
    DEFAULT_BLOCK_ENTRIES,
    EXTREME_PRESET,
    MAX_ENTRIES,
    MAX_LEGEND_BYTES,
    MAX_VALUE_BYTES,
    MIN_BLOCK_ENTRIES,
    MAX_BLOCK_ENTRIES,
)


MAGIC = b"SCMLEG2\n"
PROLOGUE = struct.Struct(">8sI")
SCHEMA = "semcrys.seekable-metalegend.v0.1"
RESULT_SCHEMA = "semcrys.seekable-metalegend-result.v0.1"
PROFILE = "SEEKABLE_PREFIX_SUPERFRAMES_V1"
FRAME_MAGIC = b"RMF2"
ENVELOPE_MAGIC = b"RME2"
MAX_HEADER_BYTES = 8 * 1024 * 1024
MAX_FRAME_RECIPE_BYTES = 64 * 1024 * 1024
MAX_FRAME_COMPRESSED_BYTES = 64 * 1024 * 1024
MAX_FRAME_BLOCKS = 256
DEFAULT_FRAME_BLOCKS = 16

CACHE_PROFILES = {
    "COMPACT": {"memory_frames": 4, "decoded_bytes": 16 * 1024 * 1024,
                "promotion_fraction": 0.75, "auto_promote": False},
    "BALANCED": {"memory_frames": 16, "decoded_bytes": 96 * 1024 * 1024,
                 "promotion_fraction": 0.35, "auto_promote": False},
    "THROUGHPUT": {"memory_frames": 64, "decoded_bytes": 512 * 1024 * 1024,
                   "promotion_fraction": 0.10, "auto_promote": True},
}


def _fail(code: str) -> None:
    raise Refusal(code)


def _root(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _blob(output: io.BytesIO, value: bytes) -> None:
    output.write(_venc(len(value)))
    output.write(value)


def _read_blob(source: io.BytesIO, *, boundary: int, maximum: int) -> bytes:
    size = _vdec(source, boundary=boundary)
    if size > maximum or source.tell() + size > boundary:
        _fail("HELD_SEEKABLE_META_BLOB_LIMIT")
    value = source.read(size)
    if len(value) != size:
        _fail("HELD_SEEKABLE_META_TRUNCATED")
    return value


def _shared_prefix(previous: bytes, current: bytes) -> int:
    limit = min(len(previous), len(current))
    index = 0
    while index < limit and previous[index] == current[index]:
        index += 1
    return index


def _compress(raw: bytes, presets: list[int]) -> tuple[bytes, int]:
    candidates = [(lzma.compress(raw, format=lzma.FORMAT_XZ, preset=preset), preset)
                  for preset in presets]
    return min(candidates, key=lambda row: (len(row[0]), row[1]))


def _decompress(raw: bytes, *, maximum: int) -> bytes:
    try:
        value = lzma.decompress(raw, format=lzma.FORMAT_XZ, memlimit=1024 * 1024 * 1024)
    except lzma.LZMAError as error:
        raise Refusal("HELD_SEEKABLE_META_LZMA") from error
    if len(value) > maximum:
        _fail("HELD_SEEKABLE_META_FRAME_LIMIT")
    return value


def _frame_row(*, role: str, ordinal: int, first_id: int | None, entry_count: int,
               block_count: int, offset: int, compressed: bytes, recipe: bytes,
               preset: int) -> dict:
    return {
        "role": role,
        "ordinal": ordinal,
        "first_id": first_id,
        "entry_count": entry_count,
        "block_count": block_count,
        "offset": offset,
        "compressed_bytes": len(compressed),
        "compressed_sha256": hashlib.sha256(compressed).hexdigest(),
        "recipe_bytes": len(recipe),
        "recipe_sha256": hashlib.sha256(recipe).hexdigest(),
        "selected_preset": preset,
    }


def _encode_data_frame(blocks: list[list[bytes]]) -> bytes:
    stream = io.BytesIO()
    stream.write(FRAME_MAGIC)
    stream.write(_venc(len(blocks)))
    for values in blocks:
        stream.write(_venc(len(values)))
        anchor = values[0]
        _blob(stream, anchor)
        previous = anchor
        for value in values[1:]:
            prefix = _shared_prefix(previous, value)
            stream.write(_venc(prefix))
            _blob(stream, value[prefix:])
            previous = value
    return stream.getvalue()


def _decode_data_frame(raw: bytes, row: dict, *, materialize: bool = True) -> list[bytes]:
    stream = io.BytesIO(raw)
    if stream.read(len(FRAME_MAGIC)) != FRAME_MAGIC:
        _fail("HELD_SEEKABLE_META_FRAME_MAGIC")
    block_count = _vdec(stream, boundary=len(raw))
    if block_count != row["block_count"]:
        _fail("HELD_SEEKABLE_META_BLOCK_COUNT")
    values: list[bytes] = []
    entries = 0
    for _ in range(block_count):
        count = _vdec(stream, boundary=len(raw))
        if not 1 <= count <= MAX_BLOCK_ENTRIES:
            _fail("HELD_SEEKABLE_META_BLOCK_COUNT")
        anchor = _read_blob(stream, boundary=len(raw), maximum=MAX_VALUE_BYTES)
        if materialize:
            values.append(anchor)
        entries += 1
        previous = anchor
        for _ in range(count - 1):
            prefix = _vdec(stream, boundary=len(raw))
            remainder = _read_blob(stream, boundary=len(raw), maximum=MAX_VALUE_BYTES)
            if prefix > len(previous):
                _fail("HELD_SEEKABLE_META_RECIPE_REFERENCE")
            value = previous[:prefix] + remainder
            if len(value) > MAX_VALUE_BYTES:
                _fail("HELD_SEEKABLE_META_VALUE_LIMIT")
            if materialize:
                values.append(value)
            entries += 1
            previous = value
    if entries != row["entry_count"] or stream.read(1):
        _fail("HELD_SEEKABLE_META_FRAME_BOUNDARY")
    return values


def _encode_envelope(prefix: bytes, suffix: bytes) -> bytes:
    stream = io.BytesIO()
    stream.write(ENVELOPE_MAGIC)
    _blob(stream, prefix)
    _blob(stream, suffix)
    return stream.getvalue()


def _decode_envelope(raw: bytes) -> tuple[bytes, bytes]:
    stream = io.BytesIO(raw)
    if stream.read(len(ENVELOPE_MAGIC)) != ENVELOPE_MAGIC:
        _fail("HELD_SEEKABLE_META_ENVELOPE_MAGIC")
    prefix = _read_blob(stream, boundary=len(raw), maximum=MAX_HEADER_BYTES)
    suffix = _read_blob(stream, boundary=len(raw), maximum=MAX_LEGEND_BYTES)
    if stream.read(1):
        _fail("HELD_SEEKABLE_META_ENVELOPE_BOUNDARY")
    return prefix, suffix


HEADER_FIELDS = {
    "schema", "standing", "profile", "recursion_depth", "source_legend_sha256",
    "source_legend_bytes", "source_legend_header", "entry_count", "block_entries",
    "blocks", "frame_blocks", "data_frames", "frame_count", "directory",
    "directory_root", "payload_bytes", "payload_sha256", "candidate_presets",
    "entry_payload_bytes", "shared_prefix_bytes", "prefix_bytes", "suffix_bytes",
    "exact_original_legend", "targeted_lookup", "cache_contract", "security_claim",
    "semantic_identity_effect", "instance_root",
}
ROW_FIELDS = {
    "role", "ordinal", "first_id", "entry_count", "block_count", "offset",
    "compressed_bytes", "compressed_sha256", "recipe_bytes", "recipe_sha256",
    "selected_preset",
}


def _validate_header(value: object) -> dict:
    if type(value) is not dict or set(value) != HEADER_FIELDS:
        _fail("HELD_SEEKABLE_META_HEADER_FIELDS")
    header = value
    if (header["schema"] != SCHEMA or header["standing"] != "CANDIDATE_ONLY"
            or header["profile"] != PROFILE or header["recursion_depth"] != 1):
        _fail("HELD_SEEKABLE_META_HEADER_SCHEMA")
    if (header["exact_original_legend"] is not True or header["targeted_lookup"] is not True
            or header["security_claim"] != "NONE"
            or header["semantic_identity_effect"] != "NONE"):
        _fail("HELD_SEEKABLE_META_HEADER_CLAIMS")
    roots = ("source_legend_sha256", "directory_root", "payload_sha256", "instance_root")
    for field in roots:
        item = header[field]
        if type(item) is not str or len(item) != 64 or any(ch not in "0123456789abcdef" for ch in item):
            _fail("HELD_SEEKABLE_META_ROOT")
    integers = ("source_legend_bytes", "entry_count", "block_entries", "blocks",
                "frame_blocks", "data_frames", "frame_count", "payload_bytes",
                "entry_payload_bytes", "shared_prefix_bytes", "prefix_bytes", "suffix_bytes")
    if any(type(header[field]) is not int or header[field] < 0 for field in integers):
        _fail("HELD_SEEKABLE_META_INTEGER")
    if not MIN_BLOCK_ENTRIES <= header["block_entries"] <= MAX_BLOCK_ENTRIES:
        _fail("HELD_SEEKABLE_META_BLOCK_SIZE")
    if not 1 <= header["frame_blocks"] <= MAX_FRAME_BLOCKS:
        _fail("HELD_SEEKABLE_META_FRAME_BLOCKS")
    presets = header["candidate_presets"]
    if type(presets) is not list or presets != sorted(set(presets)) or not presets:
        _fail("HELD_SEEKABLE_META_PRESETS")
    if any(type(item) is not int or item not in ALLOWED_PRESETS for item in presets):
        _fail("HELD_SEEKABLE_META_PRESETS")
    directory = header["directory"]
    if type(directory) is not list or len(directory) != header["frame_count"]:
        _fail("HELD_SEEKABLE_META_DIRECTORY")
    expected_offset = 0
    expected_id = 1
    data_frames = 0
    blocks = 0
    for ordinal, row in enumerate(directory):
        if type(row) is not dict or set(row) != ROW_FIELDS or row["ordinal"] != ordinal:
            _fail("HELD_SEEKABLE_META_DIRECTORY_ROW")
        if row["role"] not in {"ENVELOPE", "DATA"} or row["offset"] != expected_offset:
            _fail("HELD_SEEKABLE_META_DIRECTORY_ROW")
        for field in ("entry_count", "block_count", "offset", "compressed_bytes",
                      "recipe_bytes", "selected_preset"):
            if type(row[field]) is not int or row[field] < 0:
                _fail("HELD_SEEKABLE_META_DIRECTORY_ROW")
        for field in ("compressed_sha256", "recipe_sha256"):
            item = row[field]
            if type(item) is not str or len(item) != 64 or any(ch not in "0123456789abcdef" for ch in item):
                _fail("HELD_SEEKABLE_META_DIRECTORY_ROW")
        if row["selected_preset"] not in presets or row["compressed_bytes"] > MAX_FRAME_COMPRESSED_BYTES:
            _fail("HELD_SEEKABLE_META_DIRECTORY_ROW")
        if row["recipe_bytes"] > MAX_FRAME_RECIPE_BYTES:
            _fail("HELD_SEEKABLE_META_DIRECTORY_ROW")
        if ordinal == 0:
            if row["role"] != "ENVELOPE" or row["first_id"] is not None or row["entry_count"] or row["block_count"]:
                _fail("HELD_SEEKABLE_META_ENVELOPE_ROW")
        else:
            if (row["role"] != "DATA" or row["first_id"] != expected_id
                    or not 1 <= row["block_count"] <= header["frame_blocks"]
                    or row["entry_count"] <= 0):
                _fail("HELD_SEEKABLE_META_DATA_ROW")
            expected_id += row["entry_count"]
            data_frames += 1
            blocks += row["block_count"]
        expected_offset += row["compressed_bytes"]
    if (expected_offset != header["payload_bytes"] or expected_id - 1 != header["entry_count"]
            or data_frames != header["data_frames"] or blocks != header["blocks"]):
        _fail("HELD_SEEKABLE_META_DIRECTORY_TOTAL")
    if header["directory_root"] != _root(directory):
        _fail("HELD_SEEKABLE_META_DIRECTORY_ROOT")
    cache_contract = header["cache_contract"]
    expected_cache = {
        "frame_cache": "ROOT_VERIFIED_DERIVABLE",
        "full_legend_cache": "EXACT_SOURCE_ROOT_VERIFIED_DERIVABLE",
        "promotion": "EXPLICIT_OR_PROFILE_THRESHOLD",
        "identity_effect": "NONE",
    }
    if cache_contract != expected_cache:
        _fail("HELD_SEEKABLE_META_CACHE_CONTRACT")
    body = {key: item for key, item in header.items() if key != "instance_root"}
    if header["instance_root"] != _root(body):
        _fail("HELD_SEEKABLE_META_INSTANCE_ROOT")
    return header


def _read_header(path: Path) -> tuple[dict, int]:
    with path.open("rb") as handle:
        fixed = handle.read(PROLOGUE.size)
        if len(fixed) != PROLOGUE.size:
            _fail("HELD_SEEKABLE_META_TRUNCATED")
        magic, header_size = PROLOGUE.unpack(fixed)
        if magic != MAGIC or header_size > MAX_HEADER_BYTES:
            _fail("HELD_SEEKABLE_META_MAGIC")
        raw = handle.read(header_size)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError, RecursionError) as error:
        raise Refusal("HELD_SEEKABLE_META_HEADER") from error
    if canonical(value) != raw:
        _fail("HELD_SEEKABLE_META_NONCANONICAL_HEADER")
    return _validate_header(value), PROLOGUE.size + header_size


def _frame_bytes(path: Path, payload_start: int, row: dict) -> bytes:
    with path.open("rb") as handle:
        handle.seek(payload_start + row["offset"])
        raw = handle.read(row["compressed_bytes"])
    if len(raw) != row["compressed_bytes"] or hashlib.sha256(raw).hexdigest() != row["compressed_sha256"]:
        _fail("HELD_SEEKABLE_META_COMPRESSED_FRAME_ROOT")
    return raw


def inspect(path: str | Path, *, verify_frames: bool = True) -> dict:
    source = Path(path)
    header, payload_start = _read_header(source)
    if source.stat().st_size != payload_start + header["payload_bytes"]:
        _fail("HELD_SEEKABLE_META_FILE_SIZE")
    frames_verified = 0
    if verify_frames:
        payload_digest = hashlib.sha256()
        for row in header["directory"]:
            compressed = _frame_bytes(source, payload_start, row)
            payload_digest.update(compressed)
            recipe = _decompress(compressed, maximum=MAX_FRAME_RECIPE_BYTES)
            if len(recipe) != row["recipe_bytes"] or hashlib.sha256(recipe).hexdigest() != row["recipe_sha256"]:
                _fail("HELD_SEEKABLE_META_RECIPE_ROOT")
            if row["role"] == "ENVELOPE":
                _decode_envelope(recipe)
            else:
                _decode_data_frame(recipe, row, materialize=False)
            frames_verified += 1
        if payload_digest.hexdigest() != header["payload_sha256"]:
            _fail("HELD_SEEKABLE_META_PAYLOAD_ROOT")
    return {
        "schema": "semcrys.seekable-metalegend-inspection.v0.1",
        "status": "PASS",
        "standing": "CANDIDATE_ONLY",
        "path": str(source),
        "sha256": file_sha256(source),
        "bytes": source.stat().st_size,
        "frames_verified": frames_verified,
        "configuration": header,
    }


def build(source: str | Path, output: str | Path, *,
          block_entries: int = DEFAULT_BLOCK_ENTRIES,
          frame_blocks: int = DEFAULT_FRAME_BLOCKS,
          candidate_presets: Iterable[int] = (9, EXTREME_PRESET),
          require_smaller: bool = True) -> dict:
    source = Path(source)
    output = Path(output)
    if output.suffix.lower() != ".mleg":
        _fail("HELD_SEEKABLE_META_SUFFIX_REQUIRED")
    if not MIN_BLOCK_ENTRIES <= block_entries <= MAX_BLOCK_ENTRIES:
        _fail("HELD_SEEKABLE_META_BLOCK_SIZE")
    if not 1 <= frame_blocks <= MAX_FRAME_BLOCKS:
        _fail("HELD_SEEKABLE_META_FRAME_BLOCKS")
    presets = sorted(set(candidate_presets))
    if not presets or any(type(item) is not int or item not in ALLOWED_PRESETS for item in presets):
        _fail("HELD_SEEKABLE_META_PRESETS")
    if type(require_smaller) is not bool:
        _fail("HELD_SEEKABLE_META_ADMISSION_POLICY")
    if source.stat().st_size > MAX_LEGEND_BYTES:
        _fail("HELD_SEEKABLE_META_SOURCE_LIMIT")
    with source.open("rb") as handle:
        signature = handle.read(len(MAGIC))
    if signature in {MAGIC, b"SCMLEG1\n"}:
        _fail("HELD_SEEKABLE_META_NESTING")
    protect_outputs([output], [source])
    if output.exists() or output.is_symlink():
        _fail("HELD_SEEKABLE_META_DESTINATION_EXISTS")

    reader = LegendReader(source, max_entries=MAX_ENTRIES, max_value_bytes=MAX_VALUE_BYTES)
    reader.verify(check_duplicates=False)
    with source.open("rb") as handle:
        prefix = handle.read(reader.entries_start)
        handle.seek(reader.index_offset)
        suffix = handle.read()

    frames: list[bytes] = []
    directory: list[dict] = []
    payload_digest = hashlib.sha256()
    offset = 0
    envelope = _encode_envelope(prefix, suffix)
    compressed, preset = _compress(envelope, presets)
    directory.append(_frame_row(role="ENVELOPE", ordinal=0, first_id=None,
                                entry_count=0, block_count=0, offset=offset,
                                compressed=compressed, recipe=envelope, preset=preset))
    frames.append(compressed)
    payload_digest.update(compressed)
    offset += len(compressed)

    iterator = iter(reader.iter_values())
    remaining = reader.count
    next_id = 1
    blocks_total = 0
    entry_payload_bytes = 0
    shared_prefix_bytes = 0
    while remaining:
        superframe: list[list[bytes]] = []
        frame_entries = 0
        for _ in range(frame_blocks):
            if not remaining:
                break
            count = min(block_entries, remaining)
            values = []
            for _ in range(count):
                try:
                    _, value = next(iterator)
                except StopIteration as error:
                    raise Refusal("HELD_SEEKABLE_META_ENTRY_COUNT") from error
                values.append(value)
                entry_payload_bytes += len(value)
            previous = values[0]
            for value in values[1:]:
                shared_prefix_bytes += _shared_prefix(previous, value)
                previous = value
            superframe.append(values)
            remaining -= count
            frame_entries += count
            blocks_total += 1
        recipe = _encode_data_frame(superframe)
        if len(recipe) > MAX_FRAME_RECIPE_BYTES:
            _fail("HELD_SEEKABLE_META_FRAME_LIMIT")
        compressed, preset = _compress(recipe, presets)
        ordinal = len(directory)
        directory.append(_frame_row(role="DATA", ordinal=ordinal, first_id=next_id,
                                    entry_count=frame_entries, block_count=len(superframe),
                                    offset=offset, compressed=compressed, recipe=recipe,
                                    preset=preset))
        frames.append(compressed)
        payload_digest.update(compressed)
        offset += len(compressed)
        next_id += frame_entries
    try:
        next(iterator)
    except StopIteration:
        pass
    else:
        _fail("HELD_SEEKABLE_META_ENTRY_COUNT")

    body = {
        "schema": SCHEMA,
        "standing": "CANDIDATE_ONLY",
        "profile": PROFILE,
        "recursion_depth": 1,
        "source_legend_sha256": file_sha256(source),
        "source_legend_bytes": source.stat().st_size,
        "source_legend_header": reader.header,
        "entry_count": reader.count,
        "block_entries": block_entries,
        "blocks": blocks_total,
        "frame_blocks": frame_blocks,
        "data_frames": len(directory) - 1,
        "frame_count": len(directory),
        "directory": directory,
        "directory_root": _root(directory),
        "payload_bytes": offset,
        "payload_sha256": payload_digest.hexdigest(),
        "candidate_presets": presets,
        "entry_payload_bytes": entry_payload_bytes,
        "shared_prefix_bytes": shared_prefix_bytes,
        "prefix_bytes": len(prefix),
        "suffix_bytes": len(suffix),
        "exact_original_legend": True,
        "targeted_lookup": True,
        "cache_contract": {
            "frame_cache": "ROOT_VERIFIED_DERIVABLE",
            "full_legend_cache": "EXACT_SOURCE_ROOT_VERIFIED_DERIVABLE",
            "promotion": "EXPLICIT_OR_PROFILE_THRESHOLD",
            "identity_effect": "NONE",
        },
        "security_claim": "NONE",
        "semantic_identity_effect": "NONE",
    }
    header = {**body, "instance_root": _root(body)}
    raw_header = canonical(header)
    if len(raw_header) > MAX_HEADER_BYTES:
        _fail("HELD_SEEKABLE_META_HEADER_LIMIT")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="semcrys-seekable-mleg-", dir=output.parent) as name:
        pending = Path(name) / "output.pending"
        with pending.open("wb") as target:
            target.write(PROLOGUE.pack(MAGIC, len(raw_header)))
            target.write(raw_header)
            for frame in frames:
                target.write(frame)
            target.flush()
            os.fsync(target.fileno())
        if require_smaller and pending.stat().st_size >= source.stat().st_size:
            _fail("HELD_SEEKABLE_META_NOT_SMALLER")
        pending.replace(output)
    result = inspect(output)
    return {
        "schema": RESULT_SCHEMA,
        "operation": "BUILD",
        "status": "PASS",
        "standing": "CANDIDATE_ONLY",
        "source_legend_sha256": body["source_legend_sha256"],
        "source_legend_bytes": body["source_legend_bytes"],
        "metalegend_sha256": result["sha256"],
        "metalegend_bytes": result["bytes"],
        "raw_reduction_bytes": body["source_legend_bytes"] - result["bytes"],
        "raw_reduction_percent": round((1 - result["bytes"] / body["source_legend_bytes"]) * 100, 6),
        "configuration": body,
    }


class SeekableMetalegendReader:
    def __init__(self, path: str | Path, *, cache_root: str | Path | None = None,
                 cache_profile: str = "BALANCED", memory_frames: int | None = None,
                 decoded_cache_bytes: int | None = None,
                 auto_promote: bool | None = None) -> None:
        self.path = Path(path)
        self.header, self.payload_start = _read_header(self.path)
        if self.path.stat().st_size != self.payload_start + self.header["payload_bytes"]:
            _fail("HELD_SEEKABLE_META_FILE_SIZE")
        if cache_profile not in CACHE_PROFILES:
            _fail("HELD_SEEKABLE_META_CACHE_PROFILE")
        profile = CACHE_PROFILES[cache_profile]
        self.cache_profile = cache_profile
        self.memory_frames = profile["memory_frames"] if memory_frames is None else memory_frames
        if type(self.memory_frames) is not int or not 0 <= self.memory_frames <= 1024:
            _fail("HELD_SEEKABLE_META_MEMORY_CACHE")
        self.decoded_cache_bytes = (profile["decoded_bytes"] if decoded_cache_bytes is None
                                    else decoded_cache_bytes)
        if type(self.decoded_cache_bytes) is not int or not 0 <= self.decoded_cache_bytes <= 4 * 1024**3:
            _fail("HELD_SEEKABLE_META_DECODED_CACHE")
        self.auto_promote = profile["auto_promote"] if auto_promote is None else auto_promote
        if type(self.auto_promote) is not bool:
            _fail("HELD_SEEKABLE_META_AUTO_PROMOTE")
        self.promotion_fraction = profile["promotion_fraction"]
        self.cache = None if cache_root is None else MetalegendCache(cache_root, self.header["instance_root"])
        self._memory: OrderedDict[int, bytes] = OrderedDict()
        self._decoded: OrderedDict[int, tuple[list[bytes], int]] = OrderedDict()
        self._decoded_bytes = 0
        self._touched: set[int] = set()
        self._starts = [row["first_id"] for row in self.header["directory"][1:]]
        self._full_reader: LegendReader | None = None
        self.stats = {"frame_loads": 0, "memory_hits": 0, "decoded_hits": 0,
                      "lookups": 0,
                      "full_legend_hits": 0, "promotions": 0}
        self._open_full_if_present()

    @property
    def count(self) -> int:
        return self.header["entry_count"]

    def _open_full_if_present(self) -> None:
        if self.cache is None:
            return
        path = self.cache.verified_full(self.header["source_legend_sha256"],
                                        self.header["source_legend_bytes"])
        if path is not None:
            self._full_reader = LegendReader(path, max_entries=MAX_ENTRIES,
                                             max_value_bytes=MAX_VALUE_BYTES)
            self._full_reader.verify(check_duplicates=False)

    def _recipe(self, row: dict) -> bytes:
        ordinal = row["ordinal"]
        if ordinal in self._memory:
            self._memory.move_to_end(ordinal)
            self.stats["memory_hits"] += 1
            return self._memory[ordinal]
        raw = None if self.cache is None else self.cache.load_frame(
            ordinal, row["recipe_sha256"], row["recipe_bytes"])
        if raw is None:
            compressed = _frame_bytes(self.path, self.payload_start, row)
            raw = _decompress(compressed, maximum=MAX_FRAME_RECIPE_BYTES)
            if len(raw) != row["recipe_bytes"] or hashlib.sha256(raw).hexdigest() != row["recipe_sha256"]:
                _fail("HELD_SEEKABLE_META_RECIPE_ROOT")
            if self.cache is not None:
                self.cache.store_frame(ordinal, row["recipe_sha256"], raw)
            self.stats["frame_loads"] += 1
        if self.memory_frames:
            self._memory[ordinal] = raw
            self._memory.move_to_end(ordinal)
            while len(self._memory) > self.memory_frames:
                self._memory.popitem(last=False)
        return raw

    def _row_for(self, identifier: int) -> dict:
        if type(identifier) is not int or not 1 <= identifier <= self.count:
            _fail("HELD_SEEKABLE_META_ID_RANGE")
        index = bisect.bisect_right(self._starts, identifier) - 1
        if index < 0:
            _fail("HELD_SEEKABLE_META_ID_RANGE")
        return self.header["directory"][index + 1]

    def _values(self, row: dict) -> list[bytes]:
        ordinal = row["ordinal"]
        if ordinal in self._decoded:
            self._decoded.move_to_end(ordinal)
            self.stats["decoded_hits"] += 1
            return self._decoded[ordinal][0]
        values = _decode_data_frame(self._recipe(row), row)
        retained = sum(len(value) + 40 for value in values)
        if retained <= self.decoded_cache_bytes:
            self._decoded[ordinal] = (values, retained)
            self._decoded_bytes += retained
            self._decoded.move_to_end(ordinal)
            while self._decoded and self._decoded_bytes > self.decoded_cache_bytes:
                _, (_, released) = self._decoded.popitem(last=False)
                self._decoded_bytes -= released
        return values

    def get(self, identifier: int) -> bytes:
        self.stats["lookups"] += 1
        if self._full_reader is not None:
            self.stats["full_legend_hits"] += 1
            return self._full_reader.get(identifier)
        row = self._row_for(identifier)
        values = self._values(row)
        self._touched.add(row["ordinal"])
        value = values[identifier - row["first_id"]]
        if self.auto_promote and self.promotion_recommended:
            self.prepare_full_cache()
        return value

    def get_many(self, identifiers: Iterable[int]) -> dict[int, bytes]:
        requested = list(dict.fromkeys(identifiers))
        result = {}
        if self._full_reader is not None:
            for identifier in requested:
                result[identifier] = self.get(identifier)
            return result
        grouped: dict[int, tuple[dict, list[int]]] = {}
        for identifier in requested:
            row = self._row_for(identifier)
            grouped.setdefault(row["ordinal"], (row, []))[1].append(identifier)
        for ordinal in sorted(grouped):
            row, ids = grouped[ordinal]
            values = self._values(row)
            self._touched.add(ordinal)
            for identifier in ids:
                self.stats["lookups"] += 1
                result[identifier] = values[identifier - row["first_id"]]
        if self.auto_promote and self.promotion_recommended:
            self.prepare_full_cache()
        return result

    @property
    def promotion_recommended(self) -> bool:
        frames = self.header["data_frames"]
        return bool(frames and len(self._touched) / frames >= self.promotion_fraction)

    def prepare_full_cache(self) -> Path:
        if self.cache is None:
            _fail("HELD_SEEKABLE_META_CACHE_REQUIRED")
        existing = self.cache.verified_full(self.header["source_legend_sha256"],
                                            self.header["source_legend_bytes"])
        if existing is not None:
            if self._full_reader is None:
                self._open_full_if_present()
            return existing
        self.cache.full.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix="legend.", suffix=".leg",
                                            dir=self.cache.full)
        os.close(descriptor)
        pending = Path(name)
        pending.unlink()
        try:
            restore(self.path, pending)
            path = self.cache.publish_full(pending, self.header["source_legend_sha256"],
                                           self.header["source_legend_bytes"])
        finally:
            try:
                pending.unlink()
            except FileNotFoundError:
                pass
        self._open_full_if_present()
        self.stats["promotions"] += 1
        return path

    def receipt(self) -> dict:
        return {
            "schema": "semcrys.seekable-metalegend-reader-receipt.v0.1",
            "instance_root": self.header["instance_root"],
            "cache_profile": self.cache_profile,
            "data_frames": self.header["data_frames"],
            "touched_frames": len(self._touched),
            "promotion_fraction": self.promotion_fraction,
            "promotion_recommended": self.promotion_recommended,
            "full_legend_ready": self._full_reader is not None,
            "decoded_cache_limit_bytes": self.decoded_cache_bytes,
            "decoded_cache_retained_bytes": self._decoded_bytes,
            "decoded_cache_frames": len(self._decoded),
            "stats": dict(self.stats),
            "cache": None if self.cache is None else self.cache.receipt(),
            "semantic_identity_effect": "NONE",
            "authority_effect": "NONE",
        }


def iter_values(source: str | Path, *, cache_root: str | Path | None = None,
                cache_profile: str = "BALANCED") -> Iterator[tuple[int, bytes]]:
    reader = SeekableMetalegendReader(source, cache_root=cache_root,
                                      cache_profile=cache_profile)
    for row in reader.header["directory"][1:]:
        values = _decode_data_frame(reader._recipe(row), row)
        for offset, value in enumerate(values):
            yield row["first_id"] + offset, value


def restore(source: str | Path, output: str | Path) -> dict:
    source = Path(source)
    output = Path(output)
    if output.suffix.lower() != ".leg":
        _fail("HELD_SEEKABLE_META_LEGEND_SUFFIX_REQUIRED")
    protect_outputs([output], [source])
    if output.exists() or output.is_symlink():
        _fail("HELD_SEEKABLE_META_DESTINATION_EXISTS")
    view = inspect(source, verify_frames=False)
    header = view["configuration"]
    reader = SeekableMetalegendReader(source, memory_frames=1)
    envelope_row = header["directory"][0]
    prefix, suffix = _decode_envelope(reader._recipe(envelope_row))
    if len(prefix) != header["prefix_bytes"] or len(suffix) != header["suffix_bytes"]:
        _fail("HELD_SEEKABLE_META_ENVELOPE")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="semcrys-seekable-restore-", dir=output.parent) as name:
        pending = Path(name) / "restored.leg"
        with pending.open("wb") as target:
            target.write(prefix)
            for identifier, value in iter_values(source):
                if identifier < 1:
                    _fail("HELD_SEEKABLE_META_ENTRY_COUNT")
                target.write(_venc(len(value)))
                target.write(value)
            target.write(suffix)
            target.flush()
            os.fsync(target.fileno())
        if (pending.stat().st_size != header["source_legend_bytes"]
                or file_sha256(pending) != header["source_legend_sha256"]):
            _fail("HELD_SEEKABLE_META_EXACT_INVERSE")
        LegendReader(pending, max_entries=MAX_ENTRIES,
                     max_value_bytes=MAX_VALUE_BYTES).verify(check_duplicates=False)
        pending.replace(output)
    return {
        "schema": RESULT_SCHEMA,
        "operation": "RESTORE",
        "status": "PASS",
        "standing": "CANDIDATE_ONLY",
        "metalegend_sha256": view["sha256"],
        "source_legend_sha256": file_sha256(output),
        "source_legend_bytes": output.stat().st_size,
        "exact_original_legend": True,
    }


def verify(source: str | Path) -> dict:
    source = Path(source)
    inspected = inspect(source, verify_frames=True)
    with tempfile.TemporaryDirectory(prefix="semcrys-seekable-verify-", dir=source.parent) as name:
        restored = Path(name) / "restored.leg"
        result = restore(source, restored)
    return {**result, "operation": "VERIFY", "frames_verified": inspected["frames_verified"],
            "verified_without_retained_original_legend": True}
