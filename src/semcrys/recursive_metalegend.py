"""One-level recursive legend recipes with byte-exact legend restoration.

The input is an ordered logical SemCrys legend.  The output does not embed that
legend's entry region: it records bounded block-local prefix/suffix recipes over
the ordered entries, plus the small exact structural envelope required to
restore the original .leg bytes.  A recursive metalegend is therefore distinct
from the cross-document record pool historically exposed as ``metalegend``.
"""
from __future__ import annotations

import hashlib
import json
import lzma
from pathlib import Path
import struct
import tempfile
from typing import BinaryIO, Iterable

from streaming_app.core import Refusal, protect_outputs
from streaming_legend.core import (
    CHUNK,
    LegendReader,
    _vdec,
    _venc,
    canonical,
    file_sha256,
)


MAGIC = b"SCMLEG1\n"
PROLOGUE = struct.Struct(">8sI")
RECIPE_MAGIC = b"RML1"
SCHEMA = "semcrys.recursive-metalegend.v0.1"
RESULT_SCHEMA = "semcrys.recursive-metalegend-result.v0.1"
MAX_LEGEND_BYTES = 1024 * 1024 * 1024
MAX_RECIPE_BYTES = 2 * MAX_LEGEND_BYTES
MAX_ENTRIES = 1_000_000_000
MAX_VALUE_BYTES = 16 * 1024 * 1024
DEFAULT_BLOCK_ENTRIES = 4096
MIN_BLOCK_ENTRIES = 16
MAX_BLOCK_ENTRIES = 65536
MAX_HEADER_BYTES = 1024 * 1024
EXTREME_PRESET = 9 | lzma.PRESET_EXTREME
ALLOWED_PRESETS = set(range(10)) | {EXTREME_PRESET}


def _fail(code: str) -> None:
    raise Refusal(code)


def _sha_stream(path: Path) -> str:
    return file_sha256(path)


def _blob(output: BinaryIO, value: bytes) -> None:
    output.write(_venc(len(value)))
    output.write(value)


def _read_blob(source: BinaryIO, *, boundary: int, maximum: int) -> bytes:
    size = _vdec(source, boundary=boundary)
    if size > maximum or source.tell() + size > boundary:
        _fail("HELD_RECURSIVE_META_BLOB_LIMIT")
    value = source.read(size)
    if len(value) != size:
        _fail("HELD_RECURSIVE_META_TRUNCATED")
    return value


def _shared_prefix(previous: bytes, current: bytes) -> int:
    limit = min(len(previous), len(current))
    prefix = 0
    while prefix < limit and previous[prefix] == current[prefix]:
        prefix += 1
    return prefix


def _write_recipes(source: Path, target: Path, *, block_entries: int) -> dict:
    reader = LegendReader(source, max_entries=MAX_ENTRIES, max_value_bytes=MAX_VALUE_BYTES)
    reader.verify(check_duplicates=False)
    with source.open("rb") as handle:
        prefix = handle.read(reader.entries_start)
        handle.seek(reader.index_offset)
        suffix = handle.read()
    digest = hashlib.sha256()
    entry_bytes = shared_prefix_bytes = shared_suffix_bytes = 0
    blocks = 0
    with target.open("wb") as output:
        def emit(raw: bytes) -> None:
            output.write(raw)
            digest.update(raw)

        emit(RECIPE_MAGIC)
        raw = _venc(len(prefix)) + prefix + _venc(len(suffix)) + suffix
        emit(raw)
        iterator = iter(reader.iter_values())
        remaining = reader.count
        while remaining:
            count = min(block_entries, remaining)
            emit(_venc(count))
            try:
                _, anchor = next(iterator)
            except StopIteration as error:
                raise Refusal("HELD_RECURSIVE_META_ENTRY_COUNT") from error
            emit(_venc(len(anchor)) + anchor)
            entry_bytes += len(anchor)
            previous = anchor
            for _ in range(count - 1):
                try:
                    _, value = next(iterator)
                except StopIteration as error:
                    raise Refusal("HELD_RECURSIVE_META_ENTRY_COUNT") from error
                prefix_size = _shared_prefix(previous, value)
                remainder = value[prefix_size:]
                emit(_venc(prefix_size) + _venc(len(remainder)) + remainder)
                entry_bytes += len(value)
                shared_prefix_bytes += prefix_size
                previous = value
            remaining -= count
            blocks += 1
        try:
            next(iterator)
        except StopIteration:
            pass
        else:
            _fail("HELD_RECURSIVE_META_ENTRY_COUNT")
    return {
        "recipe_sha256": digest.hexdigest(),
        "recipe_bytes": target.stat().st_size,
        "entry_payload_bytes": entry_bytes,
        "shared_prefix_bytes": shared_prefix_bytes,
        "shared_suffix_bytes": shared_suffix_bytes,
        "blocks": blocks,
        "legend_header": reader.header,
        "entry_count": reader.count,
        "prefix_bytes": len(prefix),
        "suffix_bytes": len(suffix),
    }


def _compress(source: Path, target: Path, *, preset: int) -> None:
    compressor = lzma.LZMACompressor(format=lzma.FORMAT_XZ, preset=preset)
    with source.open("rb") as incoming, target.open("wb") as output:
        while block := incoming.read(CHUNK):
            output.write(compressor.compress(block))
        output.write(compressor.flush())


def _decompress(source: BinaryIO, target: Path, *, maximum: int) -> tuple[int, str]:
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=1024 * 1024 * 1024)
    digest = hashlib.sha256()
    total = 0
    with target.open("wb") as output:
        while block := source.read(CHUNK):
            try:
                decoded = decoder.decompress(block, max_length=maximum - total + 1)
            except lzma.LZMAError as error:
                raise Refusal("HELD_RECURSIVE_META_LZMA") from error
            total += len(decoded)
            if total > maximum:
                _fail("HELD_RECURSIVE_META_RECIPE_LIMIT")
            output.write(decoded)
            digest.update(decoded)
        if not decoder.eof or decoder.unused_data:
            _fail("HELD_RECURSIVE_META_LZMA_BOUNDARY")
    return total, digest.hexdigest()


def _header_body(header: dict) -> dict:
    return {key: value for key, value in header.items() if key != "instance_root"}


def _validate_header(header: object) -> dict:
    fields = {
        "schema", "standing", "profile", "recursion_depth", "source_legend_sha256",
        "source_legend_bytes", "source_legend_header", "entry_count", "block_entries",
        "blocks", "recipe_sha256", "recipe_bytes", "compressed_recipe_sha256",
        "compressed_recipe_bytes", "outer_codec", "selected_preset", "candidate_presets",
        "entry_payload_bytes", "shared_prefix_bytes", "shared_suffix_bytes",
        "prefix_bytes", "suffix_bytes", "exact_original_legend", "security_claim",
        "semantic_identity_effect", "instance_root",
    }
    if type(header) is not dict or set(header) != fields:
        _fail("HELD_RECURSIVE_META_HEADER_FIELDS")
    if (header["schema"] != SCHEMA or header["standing"] != "CANDIDATE_ONLY"
            or header["profile"] != "RECURSIVE_PREFIX_RECIPE_V1"
            or header["recursion_depth"] != 1):
        _fail("HELD_RECURSIVE_META_HEADER_SCHEMA")
    if header["outer_codec"] != "LZMA_XZ" or header["security_claim"] != "NONE":
        _fail("HELD_RECURSIVE_META_HEADER_PROFILE")
    if header["semantic_identity_effect"] != "NONE" or header["exact_original_legend"] is not True:
        _fail("HELD_RECURSIVE_META_HEADER_CLAIMS")
    roots = ("source_legend_sha256", "recipe_sha256", "compressed_recipe_sha256", "instance_root")
    for field in roots:
        value = header[field]
        if type(value) is not str or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            _fail("HELD_RECURSIVE_META_ROOT")
    integer_fields = ("source_legend_bytes", "entry_count", "block_entries", "blocks",
                      "recipe_bytes", "compressed_recipe_bytes", "selected_preset",
                      "entry_payload_bytes", "shared_prefix_bytes", "shared_suffix_bytes",
                      "prefix_bytes", "suffix_bytes")
    if any(type(header[field]) is not int or header[field] < 0 for field in integer_fields):
        _fail("HELD_RECURSIVE_META_INTEGER")
    if not MIN_BLOCK_ENTRIES <= header["block_entries"] <= MAX_BLOCK_ENTRIES:
        _fail("HELD_RECURSIVE_META_BLOCK_SIZE")
    presets = header["candidate_presets"]
    if type(presets) is not list or presets != sorted(set(presets)) or header["selected_preset"] not in presets:
        _fail("HELD_RECURSIVE_META_PRESETS")
    if header["instance_root"] != hashlib.sha256(canonical(_header_body(header))).hexdigest():
        _fail("HELD_RECURSIVE_META_INSTANCE_ROOT")
    return header


def inspect(path: str | Path) -> dict:
    source = Path(path)
    with source.open("rb") as handle:
        fixed = handle.read(PROLOGUE.size)
        if len(fixed) != PROLOGUE.size:
            _fail("HELD_RECURSIVE_META_TRUNCATED")
        magic, header_size = PROLOGUE.unpack(fixed)
        if magic != MAGIC or header_size > MAX_HEADER_BYTES:
            _fail("HELD_RECURSIVE_META_MAGIC")
        raw_header = handle.read(header_size)
        try:
            header = json.loads(raw_header.decode("utf-8"))
        except (UnicodeError, ValueError, RecursionError) as error:
            raise Refusal("HELD_RECURSIVE_META_HEADER") from error
        if canonical(header) != raw_header:
            _fail("HELD_RECURSIVE_META_NONCANONICAL_HEADER")
        header = _validate_header(header)
        digest = hashlib.sha256()
        size = 0
        while block := handle.read(CHUNK):
            digest.update(block)
            size += len(block)
    if size != header["compressed_recipe_bytes"] or digest.hexdigest() != header["compressed_recipe_sha256"]:
        _fail("HELD_RECURSIVE_META_COMPRESSED_ROOT")
    return {
        "schema": "semcrys.recursive-metalegend-inspection.v0.1",
        "status": "PASS",
        "standing": "CANDIDATE_ONLY",
        "path": str(source),
        "sha256": file_sha256(source),
        "bytes": source.stat().st_size,
        "configuration": header,
    }


def build(source: str | Path, output: str | Path, *, block_entries: int = DEFAULT_BLOCK_ENTRIES,
          candidate_presets: Iterable[int] = (9, EXTREME_PRESET),
          require_smaller: bool = True) -> dict:
    source = Path(source)
    output = Path(output)
    if output.suffix.lower() != ".mleg":
        _fail("HELD_RECURSIVE_META_SUFFIX_REQUIRED")
    if not MIN_BLOCK_ENTRIES <= block_entries <= MAX_BLOCK_ENTRIES:
        _fail("HELD_RECURSIVE_META_BLOCK_SIZE")
    if source.stat().st_size > MAX_LEGEND_BYTES:
        _fail("HELD_RECURSIVE_META_SOURCE_LIMIT")
    with source.open("rb") as handle:
        if handle.read(len(MAGIC)) == MAGIC:
            _fail("HELD_RECURSIVE_META_NESTING")
    presets = sorted(set(candidate_presets))
    if not presets or any(type(value) is not int or value not in ALLOWED_PRESETS for value in presets):
        _fail("HELD_RECURSIVE_META_PRESETS")
    if type(require_smaller) is not bool:
        _fail("HELD_RECURSIVE_META_ADMISSION_POLICY")
    protect_outputs([output], [source])
    if output.exists() or output.is_symlink():
        _fail("HELD_RECURSIVE_META_DESTINATION_EXISTS")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="semcrys-mleg-", dir=output.parent) as name:
        work = Path(name)
        recipe = work / "recipe.bin"
        facts = _write_recipes(source, recipe, block_entries=block_entries)
        candidates = []
        for preset in presets:
            candidate = work / f"recipe-{preset}.xz"
            _compress(recipe, candidate, preset=preset)
            candidates.append((candidate.stat().st_size, preset, candidate))
        compressed_bytes, selected_preset, selected = min(candidates)
        body = {
            "schema": SCHEMA,
            "standing": "CANDIDATE_ONLY",
            "profile": "RECURSIVE_PREFIX_RECIPE_V1",
            "recursion_depth": 1,
            "source_legend_sha256": file_sha256(source),
            "source_legend_bytes": source.stat().st_size,
            "source_legend_header": facts["legend_header"],
            "entry_count": facts["entry_count"],
            "block_entries": block_entries,
            "blocks": facts["blocks"],
            "recipe_sha256": facts["recipe_sha256"],
            "recipe_bytes": facts["recipe_bytes"],
            "compressed_recipe_sha256": _sha_stream(selected),
            "compressed_recipe_bytes": compressed_bytes,
            "outer_codec": "LZMA_XZ",
            "selected_preset": selected_preset,
            "candidate_presets": presets,
            "entry_payload_bytes": facts["entry_payload_bytes"],
            "shared_prefix_bytes": facts["shared_prefix_bytes"],
            "shared_suffix_bytes": facts["shared_suffix_bytes"],
            "prefix_bytes": facts["prefix_bytes"],
            "suffix_bytes": facts["suffix_bytes"],
            "exact_original_legend": True,
            "security_claim": "NONE",
            "semantic_identity_effect": "NONE",
        }
        header = {**body, "instance_root": hashlib.sha256(canonical(body)).hexdigest()}
        raw_header = canonical(header)
        if len(raw_header) > MAX_HEADER_BYTES:
            _fail("HELD_RECURSIVE_META_HEADER_LIMIT")
        pending = work / "output.pending"
        with pending.open("wb") as target, selected.open("rb") as compressed:
            target.write(PROLOGUE.pack(MAGIC, len(raw_header)))
            target.write(raw_header)
            while block := compressed.read(CHUNK):
                target.write(block)
        if require_smaller and pending.stat().st_size >= source.stat().st_size:
            _fail("HELD_RECURSIVE_META_NOT_SMALLER")
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
        "admission": "STRICTLY_SMALLER_THAN_SOURCE" if require_smaller else "EXPANSION_ALLOWED",
        "configuration": body,
    }


def restore(source: str | Path, output: str | Path) -> dict:
    source = Path(source)
    output = Path(output)
    if output.suffix.lower() != ".leg":
        _fail("HELD_RECURSIVE_META_LEGEND_SUFFIX_REQUIRED")
    protect_outputs([output], [source])
    if output.exists() or output.is_symlink():
        _fail("HELD_RECURSIVE_META_DESTINATION_EXISTS")
    view = inspect(source)
    header = view["configuration"]
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="semcrys-mleg-restore-", dir=output.parent) as name:
        work = Path(name)
        recipe = work / "recipe.bin"
        with source.open("rb") as handle:
            _, header_size = PROLOGUE.unpack(handle.read(PROLOGUE.size))
            handle.seek(PROLOGUE.size + header_size)
            size, digest = _decompress(handle, recipe, maximum=MAX_RECIPE_BYTES)
        if size != header["recipe_bytes"] or digest != header["recipe_sha256"]:
            _fail("HELD_RECURSIVE_META_RECIPE_ROOT")
        pending = work / "restored.leg"
        with recipe.open("rb") as recipes, pending.open("wb") as target:
            boundary = recipe.stat().st_size
            if recipes.read(len(RECIPE_MAGIC)) != RECIPE_MAGIC:
                _fail("HELD_RECURSIVE_META_RECIPE_MAGIC")
            prefix = _read_blob(recipes, boundary=boundary, maximum=MAX_HEADER_BYTES)
            suffix = _read_blob(recipes, boundary=boundary, maximum=MAX_LEGEND_BYTES)
            if len(prefix) != header["prefix_bytes"] or len(suffix) != header["suffix_bytes"]:
                _fail("HELD_RECURSIVE_META_ENVELOPE")
            target.write(prefix)
            remaining = header["entry_count"]
            blocks = 0
            while remaining:
                count = _vdec(recipes, boundary=boundary)
                if not 1 <= count <= min(header["block_entries"], remaining):
                    _fail("HELD_RECURSIVE_META_BLOCK_COUNT")
                anchor = _read_blob(recipes, boundary=boundary, maximum=MAX_VALUE_BYTES)
                target.write(_venc(len(anchor)) + anchor)
                previous = anchor
                for _ in range(count - 1):
                    prefix_size = _vdec(recipes, boundary=boundary)
                    remainder = _read_blob(recipes, boundary=boundary, maximum=MAX_VALUE_BYTES)
                    if prefix_size > len(previous):
                        _fail("HELD_RECURSIVE_META_RECIPE_REFERENCE")
                    value = previous[:prefix_size] + remainder
                    if len(value) > MAX_VALUE_BYTES:
                        _fail("HELD_RECURSIVE_META_VALUE_LIMIT")
                    target.write(_venc(len(value)) + value)
                    previous = value
                remaining -= count
                blocks += 1
            if blocks != header["blocks"] or recipes.read(1):
                _fail("HELD_RECURSIVE_META_RECIPE_BOUNDARY")
            target.write(suffix)
        if pending.stat().st_size != header["source_legend_bytes"] or file_sha256(pending) != header["source_legend_sha256"]:
            _fail("HELD_RECURSIVE_META_EXACT_INVERSE")
        reader = LegendReader(pending, max_entries=MAX_ENTRIES, max_value_bytes=MAX_VALUE_BYTES)
        reader.verify(check_duplicates=False)
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
    with tempfile.TemporaryDirectory(prefix="semcrys-mleg-verify-", dir=source.parent) as name:
        output = Path(name) / "restored.leg"
        result = restore(source, output)
    return {**result, "operation": "VERIFY", "verified_without_retained_original_legend": True}
