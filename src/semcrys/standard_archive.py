"""Turnkey, manifest-bearing SemCrys archives.

The Standard profile composes existing verified single-file codecs.  It adds a
safe path manifest and lifecycle operations without changing codec identities.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import struct
import tempfile
import zipfile
import zlib
from array import array
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from semcrys.codec_selection import DEFAULT_CODECS, encode_selected, load as load_selection, select
from semcrys_core.semantic import integerize, validate_registry
from streaming_app.core import Refusal, decode_file, iter_units, protect_outputs
from streaming_legend.core import canonical, file_sha256
from streaming_legend.crys_v2 import Limits, inspect_crys, write_crys
from streaming_legend import scratch_io as sio
from .group_legend import MAX_DOCUMENTS as GROUP_MAX_DOCUMENTS, MAX_INPUT as GROUP_MAX_INPUT
from .group_legend import _restore as restore_group_legend, pack as pack_group_legend
from .second_pass import MAX_EVENTS as COMPOSITION_MAX_EVENTS
from .second_pass import MAX_SOURCE as COMPOSITION_MAX_SOURCE
from .second_pass import transform as compose_second_pass

SCHEMA = "semcrys.standard-archive-instance.v0.3"
MANIFEST_SCHEMA = "semcrys.standard-archive-manifest.v0.3"
BODY_SCHEMA = "semcrys.standard-archive-body.v0.3"
LEGACY_SCHEMA_TRIPLES = {
    ("semcrys.standard-archive-instance.v0.2",
     "semcrys.standard-archive-manifest.v0.2",
     "semcrys.standard-archive-body.v0.2"),
}
PROFILE = "STANDARD_V1"
OBJECTIVE = "MIN_COMPLETE_DELIVERY_BYTES_WITH_FULL_ELIGIBLE_INTEGERIZATION_ADAPTIVE_COMPOSITION_AND_PORTABLE_REPLAY"
CODECS = tuple(DEFAULT_CODECS)
MAX_FILES = 100_000
MAX_TOTAL_BYTES = 1 << 40
MAX_FILE_BYTES = MAX_TOTAL_BYTES
DEFAULT_CHUNK_BYTES = 32 * 1024 * 1024
MAX_CHUNK_BYTES = 64 * 1024 * 1024
MAX_MANIFEST_BYTES = 256 * 1024 * 1024
COMPOSITION_MIN_COUNT = 3
COMPOSITION_ROUNDS = 400
COMPOSITION_SKETCH_CELLS = 1 << 16
COMPOSITION_MIN_POTENTIAL_SAVINGS = 1024
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


class StandardRefusal(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def _root(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _require(condition: bool, code: str, detail: str = "") -> None:
    if not condition:
        raise StandardRefusal(code, detail)


def _safe_path(value: str) -> str:
    _require(isinstance(value, str) and value and "\\" not in value and "\x00" not in value,
             "HELD_STANDARD_PATH", str(value))
    path = PurePosixPath(value)
    _require(not path.is_absolute() and all(part not in ("", ".", "..") for part in path.parts),
             "HELD_STANDARD_PATH", value)
    _require(not any(":" in part for part in path.parts), "HELD_STANDARD_PATH", value)
    return path.as_posix()


def _reparse(info: os.stat_result) -> bool:
    return bool(getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _metadata(path: Path) -> dict[str, int]:
    info = path.stat(follow_symlinks=False)
    return {"mode": stat.S_IMODE(info.st_mode), "mtime_ns": info.st_mtime_ns}


def _within(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def _protect_locations(inputs: Iterable[Path | str], output: Path,
                       cache_root: Path | None = None) -> None:
    target = output.resolve(strict=False)
    cache = cache_root.resolve(strict=False) if cache_root is not None else None
    for value in inputs:
        source = Path(value).absolute().resolve(strict=False)
        if source.is_dir():
            _require(not _within(target, source), "HELD_STANDARD_OUTPUT_OVERLAPS_SOURCE", str(target))
            if cache is not None:
                _require(not _within(cache, source), "HELD_STANDARD_CACHE_OVERLAPS_SOURCE", str(cache))
        else:
            _require(target != source, "HELD_STANDARD_OUTPUT_OVERLAPS_SOURCE", str(target))
        if cache is not None:
            _require(cache != target and not _within(target, cache),
                     "HELD_STANDARD_CACHE_OVERLAPS_OUTPUT", str(cache))


def inventory(inputs: Iterable[Path | str], *, output: Path | None = None,
              max_files: int = MAX_FILES, max_total_bytes: int = MAX_TOTAL_BYTES,
              max_file_bytes: int = MAX_FILE_BYTES) -> dict[str, Any]:
    paths = [Path(value).absolute() for value in inputs]
    _require(paths, "HELD_STANDARD_NO_INPUT")
    _require(len(paths) <= max_files, "HELD_STANDARD_INPUT_COUNT")
    excluded = output.absolute() if output is not None else None
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    total = 0

    def add(path: Path, archive_path: str, kind: str) -> None:
        nonlocal total
        archive_path = _safe_path(archive_path)
        _require(archive_path not in seen, "HELD_STANDARD_PATH_COLLISION", archive_path)
        seen.add(archive_path)
        info = path.lstat()
        _require(not path.is_symlink() and not _reparse(info), "HELD_STANDARD_REPARSE_POINT", str(path))
        row: dict[str, Any] = {"path": archive_path, "kind": kind, **_metadata(path)}
        if kind == "file":
            _require(stat.S_ISREG(info.st_mode), "HELD_STANDARD_NONREGULAR", str(path))
            _require(info.st_size <= max_file_bytes, "HELD_STANDARD_FILE_LIMIT", str(path))
            total += info.st_size
            _require(total <= max_total_bytes, "HELD_STANDARD_TOTAL_LIMIT")
            row.update(bytes=info.st_size, sha256=file_sha256(path), source_path=str(path))
        rows.append(row)

    multiple = len(paths) > 1
    for source in paths:
        _require(source.exists(), "HELD_STANDARD_INPUT_MISSING", str(source))
        _require(excluded is None or source != excluded, "HELD_STANDARD_OUTPUT_OVERLAPS_SOURCE")
        base = source.name or "root"
        if source.is_file():
            add(source, base, "file")
            continue
        _require(source.is_dir(), "HELD_STANDARD_NONREGULAR", str(source))
        if multiple or source.name:
            add(source, base, "directory")
        for child in sorted(source.rglob("*"), key=lambda item: item.relative_to(source).as_posix()):
            absolute = child.absolute()
            _require(excluded is None or absolute != excluded, "HELD_STANDARD_OUTPUT_OVERLAPS_SOURCE")
            relative = child.relative_to(source).as_posix()
            archive_path = f"{base}/{relative}" if (multiple or source.name) else relative
            if child.is_dir():
                add(child, archive_path, "directory")
            else:
                add(child, archive_path, "file")
    file_rows = [row for row in rows if row["kind"] == "file"]
    _require(len(file_rows) <= max_files, "HELD_STANDARD_FILE_COUNT")
    public_rows = [{k: v for k, v in row.items() if k != "source_path"} for row in rows]
    source_tree_root = _root(public_rows)
    return {"rows": rows, "public_rows": public_rows, "file_count": len(file_rows),
            "directory_count": len(rows) - len(file_rows), "source_bytes": total,
            "source_tree_root": source_tree_root}


def default_output(inputs: Iterable[Path | str], source_tree_root: str) -> Path:
    paths = [Path(value) for value in inputs]
    if len(paths) == 1:
        source = paths[0]
        name = source.name or "archive"
        if source.is_file() and source.suffix:
            name = source.stem
        return source.absolute().parent / f"{name}.crys"
    return Path.cwd() / f"semcrys-bundle-{source_tree_root[:12]}.crys"


def default_contract() -> dict[str, Any]:
    value = {
        "schema": "semcrys.standard-profile.v0.1",
        "profile": PROFILE,
        "recommended": True,
        "objective": OBJECTIVE,
        "constraints": ["BYTE_EXACT_RECONSTRUCTION", "FULL_ELIGIBLE_LOCAL_INTEGERIZATION",
                        "SELF_CONTAINED_RECOVERY", "NO_SOURCE_MUTATION", "VERIFIED_FINAL_REPRESENTATION"],
        "candidate_codecs": list(CODECS),
        "semantic_boundary": {
            "local_integerization": "DEFAULT_FOR_ELIGIBLE_UTF8",
            "csil_binding": "CALLER_SUPPLIED_REGISTRY_ONLY_NO_CANONICAL_EFFECT_FROM_COMPILATION",
            "gti": "OPTIONAL_REGISTRY_ROOTED_OCCURRENCE_INDEX",
            "manufactured_identity": False,
        },
        "representation": {
            "text_units": "LOSSLESS_TOKEN_PUNCTUATION_AND_WHITESPACE_EVENTS",
            "references": "UNSIGNED_VARIABLE_LENGTH_LOCAL_INTEGER_IDS_IN_PACKED_BYTES",
            "automatic_reuse": ["EXACT_CHUNK_DEDUPLICATION", "IDENTICAL_LEGEND_RECORD_POOLING",
                                "ADAPTIVE_LOCAL_AND_CROSS_DOCUMENT_EVENT_COMPOSITION"],
            "adaptive_composition": {
                "mechanism": "BOUNDED_SHARED_UTF8_COLLECTION_PLUS_RECURSIVE_ADJACENT_EVENT_SECOND_PASS",
                "scope": "UNIQUE_ELIGIBLE_PAYLOADS_WITH_MANIFEST_PRESERVED_FILE_BOUNDARIES",
                "admission": "MIN_COMPLETE_SEGMENT_DELIVERY_CHARGES_BODY_LEGEND_CONTAINER_MANIFEST_AND_DECLARED_DEPENDENCIES",
                "continuum": "REJECT_UNPROFITABLE_SMALL_SEQUENCE_ADMIT_PROFITABLE_RECURRING_STRUCTURE",
                "default": "AUTO",
                "ablation": "OFF",
            },
            "standard_phrase_mining": True,
            "composition_identity": "TRANSPORT_ONLY_NOT_CSIL_OR_SEMANTIC_IDENTITY",
        },
        "security_claim": "NONE",
        "global_optimality": False,
    }
    value["profile_root"] = _root(value)
    return value


def plan(inputs: Iterable[Path | str], *, output: Path | None = None,
         mode: str = "semantic", registry: dict[str, Any] | None = None) -> dict[str, Any]:
    inputs = list(inputs)
    _require(mode in ("semantic", "smallest", "portable"), "HELD_STANDARD_MODE", mode)
    inv = inventory(inputs, output=output)
    registry_root = validate_registry(registry) if registry is not None else None
    return {"status": "PASS", "schema": "semcrys.standard-plan.v0.1", "profile": PROFILE,
            "mode": mode, "objective": OBJECTIVE if mode != "smallest" else "MIN_MEASURED_SELF_CONTAINED_BYTES",
            "inputs": len(inputs),
            "files": inv["file_count"], "directories": inv["directory_count"],
            "source_bytes": inv["source_bytes"], "source_tree_root": inv["source_tree_root"],
            "registry_root": registry_root, "candidate_codecs": list(CODECS),
            "candidate_measurements": "DEFERRED_UNTIL_PACK", "source_mutation": False,
            "external_dependencies": [], "security_claim": "NONE"}


def _utf8(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for _ in iter(lambda: handle.read(1024 * 1024), ""):
                pass
        return True
    except UnicodeDecodeError:
        return False


def _zip_write(archive: zipfile.ZipFile, name: str, source: bytes | Path) -> None:
    info = zipfile.ZipInfo(_safe_path(name), ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o100600 << 16
    with archive.open(info, "w") as output:
        if isinstance(source, bytes):
            output.write(source)
        else:
            with source.open("rb") as incoming:
                shutil.copyfileobj(incoming, output, 1024 * 1024)


def _cache_key(source_root: str, source_bytes: int, mode: str, utf8: bool) -> str:
    return _root({"profile": PROFILE, "source_sha256": source_root, "source_bytes": source_bytes,
                  "mode": mode, "utf8": utf8, "codecs": CODECS})


def _selection(source: Path, work: Path, stem: str, profile: str, policy: str,
               progress, codecs: tuple[str, ...] | None = None) -> dict[str, Any]:
    selection_path = work / f"{stem}.selection.json"
    target = work / f"{stem}.crys"
    select(source, selection_path, profile=profile, legend_policy=policy, codecs=CODECS if codecs is None else codecs,
           accounting="COLD", max_source_bytes=MAX_CHUNK_BYTES, progress=progress)
    encode_selected(source, selection_path, target, progress=progress)
    selection = load_selection(selection_path)[0]
    return {"container": target, "selection_root": selection["selection_root"],
            "profile": profile, "legend_policy": policy}


def _atomic_cache_store(source: Path, target: Path, receipt: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(prefix=target.name + ".", suffix=".pending",
                                         dir=target.parent, delete=False)
    pending = Path(handle.name); handle.close()
    try:
        shutil.copyfile(source, pending)
        os.replace(pending, target)
        receipt_path = target.with_suffix(".json")
        data = canonical(receipt)
        with tempfile.NamedTemporaryFile(prefix=receipt_path.name + ".", suffix=".pending",
                                         dir=target.parent, delete=False) as stream:
            stream.write(data); receipt_pending = Path(stream.name)
        os.replace(receipt_pending, receipt_path)
    finally:
        pending.unlink(missing_ok=True)


def _encode_one(row: dict[str, Any], work: Path, ordinal: int, mode: str,
                cache_root: Path | None, progress) -> dict[str, Any]:
    source = Path(row["source_path"])
    is_utf8 = _utf8(source)
    key = _cache_key(row["sha256"], row["bytes"], mode, is_utf8)
    target = work / f"{ordinal:08d}.crys"
    cache_hit = False
    cache_write_failed = False
    cache = cache_root / key[:2] / f"{key}.crys" if cache_root is not None else None
    cached_receipt = cache.with_suffix(".json") if cache is not None else None
    if cache is not None and cache.is_file() and cached_receipt is not None and cached_receipt.is_file():
        try:
            receipt = json.loads(cached_receipt.read_text(encoding="utf-8"))
            inverse = work / f"cache-{ordinal}.decoded"
            result = decode_file(cache, inverse, max_decoded_bytes=row["bytes"])
            if (result["output_sha256"] == row["sha256"] and
                    receipt.get("cache_key") == key and
                    receipt.get("container_sha256") == file_sha256(cache)):
                shutil.copyfile(cache, target)
                cache_hit = True
        except (OSError, ValueError, json.JSONDecodeError):
            cache_hit = False

    chosen: dict[str, Any] | None = None
    if not cache_hit:
        if progress:
            progress({"stage": "STANDARD_CHUNK_MEASURE", "index": ordinal, "path": row["path"],
                      "chunk": row["chunk_index"]})
        candidates: list[dict[str, Any]] = []
        if is_utf8:
            candidates.append(_selection(source, work, f"{ordinal:08d}-token",
                                         "C:SELF_CONTAINED_TOKEN",
                                         "TOTAL" if mode != "smallest" else "PROFITABLE", progress))
        if not is_utf8 or mode == "smallest":
            candidates.append(_selection(source, work, f"{ordinal:08d}-raw",
                                         "C:RAW_BYTES", "PROFITABLE", progress))
        chosen = min(candidates, key=lambda item: (item["container"].stat().st_size,
                                                   candidates.index(item)))
        shutil.copyfile(chosen["container"], target)
        if cache is not None:
            try:
                _atomic_cache_store(target, cache, {
                    "schema": "semcrys.standard-cache-receipt.v0.1", "cache_key": key,
                    "source_sha256": row["sha256"], "source_bytes": row["bytes"],
                    "container_sha256": file_sha256(target), "container_bytes": target.stat().st_size,
                    "mode": mode, "verified_inverse": True,
                })
            except OSError:
                cache_write_failed = True

    inspection = inspect_crys(target)
    config = inspection["configuration"]
    result = {"container": target, "container_sha256": file_sha256(target),
              "container_bytes": target.stat().st_size, "profile": config["profile"],
              "outer_codec": config["outer_codec"], "legend_policy": config["legend_policy"],
              "integerization": "FULL_ELIGIBLE_LOCAL" if is_utf8 and config["profile"] != "C:RAW_BYTES" and config["legend_policy"] == "TOTAL" else
                                "PROFITABLE_LOCAL" if is_utf8 and config["profile"] != "C:RAW_BYTES" else
                                "NOT_APPLICABLE_RAW_BYTES",
              "cache_hit": cache_hit, "selection_root": chosen["selection_root"] if chosen else None,
              "cache_write_failed": cache_write_failed,
              "source_sha256": row["sha256"], "source_bytes": row["bytes"],
              "key": (row["sha256"], row["bytes"])}
    return result


def _encode_task(arguments: tuple[dict[str, Any], str, int, str, str | None]) -> dict[str, Any]:
    row, work, ordinal, mode, cache = arguments
    return _encode_one(row, Path(work), ordinal, mode, Path(cache) if cache else None, None)


def _chunk_rows(file_rows: list[dict[str, Any]], work: Path,
                chunk_bytes: int) -> tuple[list[dict[str, Any]], list[list[tuple[str, int]]]]:
    _require(type(chunk_bytes) is int and 1 <= chunk_bytes <= MAX_CHUNK_BYTES,
             "HELD_STANDARD_CHUNK_LIMIT")
    chunks: list[dict[str, Any]] = []
    file_keys: list[list[tuple[str, int]]] = []
    chunk_root = work / "chunks"; chunk_root.mkdir()
    for file_index, row in enumerate(file_rows):
        keys: list[tuple[str, int]] = []
        source = Path(row["source_path"])
        text_source = _utf8(source)
        if row["bytes"] <= chunk_bytes:
            key = (row["sha256"], row["bytes"]); keys.append(key)
            chunks.append({**row, "chunk_index": 0, "chunk_count": 1})
        else:
            digest = hashlib.sha256(); total = 0; chunk_index = 0
            with source.open("rb") as incoming:
                while True:
                    block = incoming.read(chunk_bytes)
                    if not block: break
                    if text_source and incoming.tell() < row["bytes"]:
                        window = block[-min(len(block), 64 * 1024):]
                        candidates = [window.rfind(bytes([value])) for value in (9, 10, 13, 32)]
                        boundary = max(candidates)
                        cut = len(block) - len(window) + boundary + 1 if boundary >= 0 else len(block)
                        if boundary < 0:
                            for fallback in range(len(block), max(-1, len(block) - 4), -1):
                                try:
                                    block[:fallback].decode("utf-8"); cut = fallback; break
                                except UnicodeDecodeError:
                                    continue
                        if cut < len(block):
                            incoming.seek(cut - len(block), os.SEEK_CUR)
                            block = block[:cut]
                    digest.update(block); total += len(block)
                    path = chunk_root / f"{file_index:08d}-{chunk_index:08d}.bin"
                    path.write_bytes(block)
                    root = hashlib.sha256(block).hexdigest(); key = (root, len(block)); keys.append(key)
                    chunks.append({**row, "source_path": str(path), "sha256": root,
                                   "bytes": len(block), "chunk_index": chunk_index,
                                   "chunk_count": 0})
                    chunk_index += 1
            _require(total == row["bytes"] and digest.hexdigest() == row["sha256"],
                     "HELD_STANDARD_SOURCE_CHANGED", row["path"])
            for chunk in chunks[-chunk_index:]:
                chunk["chunk_count"] = chunk_index
        file_keys.append(keys)
    return chunks, file_keys


def _encode_unique(chunks: list[dict[str, Any]], work: Path, mode: str,
                   cache: Path | None, workers: int, progress) -> tuple[list[dict[str, Any]], dict[tuple[str, int], dict[str, Any]]]:
    first: dict[tuple[str, int], dict[str, Any]] = {}
    for row in chunks:
        first.setdefault((row["sha256"], row["bytes"]), row)
    rows = list(first.values())
    resolved = min(max(1, workers or min(4, os.cpu_count() or 1)), max(1, len(rows)))
    results: list[dict[str, Any] | None] = [None] * len(rows)
    if resolved == 1:
        for index, row in enumerate(rows):
            results[index] = _encode_one(row, work, index, mode, cache, progress)
            if progress:
                progress({"stage": "STANDARD_CHUNK_ENCODED", "chunks": index + 1,
                          "total_chunks": len(rows), "path": row["path"]})
    else:
        arguments = [(row, str(work), index, mode, str(cache) if cache else None)
                     for index, row in enumerate(rows)]
        with ProcessPoolExecutor(max_workers=resolved) as executor:
            pending = {executor.submit(_encode_task, value): index for index, value in enumerate(arguments)}
            completed = 0
            for future in as_completed(pending):
                index = pending[future]; results[index] = future.result(); completed += 1
                if progress:
                    progress({"stage": "STANDARD_CHUNK_ENCODED", "chunks": completed,
                              "total_chunks": len(rows), "path": rows[index]["path"]})
    encoded = [row for row in results if row is not None]
    return encoded, {row["key"]: row for row in encoded}


def _encoding_descriptor(row: dict[str, Any]) -> dict[str, Any]:
    return {k: row.get(k) for k in
            ("profile", "outer_codec", "legend_policy", "integerization", "selection_root")}


def _segment_cost(segment: dict[str, Any]) -> int:
    public = {k: v for k, v in segment.items() if k != "source_path"}
    return segment["bytes"] + len(canonical(public))


def _baseline_segment(group: list[dict[str, Any]], work: Path, segment_index: int,
                      path: str) -> dict[str, Any]:
    if len(group) == 1:
        payload = group[0]["container"]; kind = "DIRECT"; meta_duplicates = 0
    else:
        directory = work / f"group-legend-{segment_index:08d}"
        receipt = pack_group_legend(directory, sources=[row["container"] for row in group],
                                  placement="EMBEDDED", selection="MIN_TOTAL", outer_codec="LZMA",
                                  max_input_bytes=GROUP_MAX_INPUT, layout="WHOLE_BUNDLE",
                                  accounting="COLD", progress=None)
        payload = directory / "archive.crys"; kind = "METALEGEND"
        meta_duplicates = receipt["duplicates_removed_from_pool"]
    members = [{"container_sha256": row["container_sha256"],
                "container_bytes": row["container_bytes"],
                "source_sha256": row["source_sha256"], "source_bytes": row["source_bytes"],
                "encoding": _encoding_descriptor(row)} for row in group]
    return {"path": path, "kind": kind, "sha256": file_sha256(payload),
            "bytes": payload.stat().st_size, "members": members,
            "group_legend_duplicates_removed": meta_duplicates,
            "source_path": str(payload)}


def _write_collection(group: list[dict[str, Any]], sources: dict[tuple[str, int], Path],
                      target: Path) -> tuple[str, list[int]]:
    digest = hashlib.sha256(); offsets = []; offset = 0
    with target.open("wb") as output:
        for row in group:
            offsets.append(offset); source = sources[row["key"]]
            member_digest = hashlib.sha256(); member_bytes = 0
            with source.open("rb") as incoming:
                for block in iter(lambda: incoming.read(1024 * 1024), b""):
                    output.write(block); digest.update(block); member_digest.update(block)
                    member_bytes += len(block); offset += len(block)
            _require(member_bytes == row["source_bytes"] and
                     member_digest.hexdigest() == row["source_sha256"],
                     "HELD_STANDARD_SOURCE_CHANGED")
    return digest.hexdigest(), offsets


def _composition_census(source: Path) -> dict[str, Any]:
    counts = array("H", [0]) * COMPOSITION_SKETCH_CELLS
    spans = array("H", [0]) * COMPOSITION_SKETCH_CELLS
    previous = previous_bytes = None; events = 0; maximum = 0
    for kind, value in iter_units(source):
        events += 1
        if events > COMPOSITION_MAX_EVENTS:
            return {"eligible": False, "events": events, "maximum_bucket": maximum,
                    "reason": "EVENT_LIMIT"}
        token = zlib.crc32(value, zlib.crc32(kind.encode("ascii")))
        if previous is not None:
            cell = ((previous * 0x9E3779B1) ^ token) & (COMPOSITION_SKETCH_CELLS - 1)
            if counts[cell] < 65535:
                counts[cell] += 1
            spans[cell] = min(65535, max(spans[cell], previous_bytes + len(value)))
            maximum = max(maximum, counts[cell])
        previous = token; previous_bytes = len(value)
    potential = sum((count - 1) * max(span - 1, 0)
                    for count, span in zip(counts, spans) if count >= COMPOSITION_MIN_COUNT)
    eligible = maximum >= COMPOSITION_MIN_COUNT and potential >= COMPOSITION_MIN_POTENTIAL_SAVINGS
    reason = None if eligible else ("NO_REPEATED_PAIR_AT_MINIMUM_COUNT" if maximum < COMPOSITION_MIN_COUNT
                                    else "UPPER_BOUND_BELOW_COMPOSITION_INVOCATION_FLOOR")
    return {"eligible": eligible, "events": events, "maximum_bucket": maximum,
            "potential_savings_upper_bound_bytes": potential,
            "invocation_floor_bytes": COMPOSITION_MIN_POTENTIAL_SAVINGS, "reason": reason}


def _collection_segment(group: list[dict[str, Any]], sources: dict[tuple[str, int], Path],
                        work: Path, segment_index: int, path: str, progress,
                        cache_root: Path | None = None) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    combined = work / f"collection-{segment_index:08d}.source"
    collection_root, offsets = _write_collection(group, sources, combined)
    census = _composition_census(combined)
    if progress:
        progress({"stage": "STANDARD_COMPOSITION_CENSUS", "segment": segment_index + 1,
                  "members": len(group), **census})
    if not census["eligible"]:
        return None, census
    composed = work / f"collection-{segment_index:08d}-composed.crys"
    cache_key = _root({"schema": "semcrys.standard-composition-cache-key.v0.1",
                       "profile": PROFILE, "collection_sha256": collection_root,
                       "collection_bytes": combined.stat().st_size,
                       "members": [row["key"] for row in group], "codecs": list(CODECS),
                       "minimum_count": COMPOSITION_MIN_COUNT, "rounds": COMPOSITION_ROUNDS})
    cached = cache_root / "composition" / cache_key[:2] / f"{cache_key}.crys" if cache_root else None
    cache_receipt = cached.with_suffix(".json") if cached is not None else None
    court_data = None; cache_hit = False; selected_root = None
    if cached is not None and cached.is_file() and cache_receipt is not None and cache_receipt.is_file():
        try:
            receipt = json.loads(cache_receipt.read_text(encoding="utf-8"))
            check = work / f"collection-{segment_index:08d}-cache-check"
            inverse = decode_file(cached, check, max_decoded_bytes=combined.stat().st_size)
            if (receipt.get("cache_key") == cache_key and
                    receipt.get("container_sha256") == file_sha256(cached) and
                    inverse["output_sha256"] == collection_root and
                    isinstance(receipt.get("court"), dict)):
                shutil.copyfile(cached, composed); court_data = receipt["court"]
                selected_root = receipt.get("selection_root"); cache_hit = True
        except (OSError, ValueError, json.JSONDecodeError, Refusal):
            cache_hit = False
    if court_data is None:
        selected = _selection(combined, work, f"collection-{segment_index:08d}-token",
                              "C:SELF_CONTAINED_TOKEN", "TOTAL", progress)
        selected_root = selected["selection_root"]
        try:
            court = compose_second_pass(selected["container"], composed, selection="MIN_DELIVERY",
                                        accounting="COLD", rounds=COMPOSITION_ROUNDS,
                                        min_count=COMPOSITION_MIN_COUNT,
                                        max_source_bytes=COMPOSITION_MAX_SOURCE,
                                        max_events=COMPOSITION_MAX_EVENTS, progress=progress)
        except Refusal as exc:
            census = {**census, "eligible": False, "reason": str(exc), "cache_hit": False}
            if progress:
                progress({"stage": "STANDARD_COMPOSITION_HELD", "segment": segment_index + 1,
                          "reason": str(exc)})
            return None, census
        court_data = {"selected_id": court["selected_id"],
                      "saved_delivery_bytes": court["saved_delivery_bytes"],
                      "candidates": court["candidates"]}
        if cached is not None:
            try:
                _atomic_cache_store(composed, cached, {
                    "schema": "semcrys.standard-composition-cache-receipt.v0.1",
                    "cache_key": cache_key, "collection_sha256": collection_root,
                    "collection_bytes": combined.stat().st_size,
                    "container_sha256": file_sha256(composed), "court": court_data,
                    "selection_root": selected_root, "verified_inverse": True})
            except OSError:
                pass
    config = inspect_crys(composed)["configuration"]
    composition_selected = court_data["selected_id"] != "ORIGINAL"
    encoding = {"profile": config["profile"], "outer_codec": config["outer_codec"],
                "legend_policy": "TOTAL", "integerization": "FULL_ELIGIBLE_LOCAL",
                "selection_root": selected_root}
    members = [{"source_sha256": row["source_sha256"], "source_bytes": row["source_bytes"],
                "offset": offset, "encoding": encoding}
               for row, offset in zip(group, offsets)]
    measurements = [{k: row[k] for k in
                     ("id", "container_bytes", "body_bytes", "legend_bytes", "delivery_bytes",
                      "events", "pairs", "fractionation_realization", "text_inverse", "event_inverse") if k in row}
                    for row in court_data["candidates"]]
    census = {**census, "cache_hit": cache_hit}
    segment = {"path": path,
               "kind": "COMPOSED_COLLECTION" if composition_selected else "INTEGER_COLLECTION",
               "sha256": file_sha256(composed), "bytes": composed.stat().st_size,
               "members": members, "collection_sha256": collection_root,
               "collection_bytes": combined.stat().st_size,
               "composition": {"selected_id": court_data["selected_id"],
                               "saved_from_collection_first_pass_bytes": court_data["saved_delivery_bytes"],
                               "minimum_count": COMPOSITION_MIN_COUNT,
                               "rounds": COMPOSITION_ROUNDS,
                               "cross_document": len(group) > 1,
                               "census": census, "candidates": measurements},
               "group_legend_duplicates_removed": 0, "source_path": str(composed)}
    return segment, census


def _segment_payloads(encoded: list[dict[str, Any]], sources: dict[tuple[str, int], Path],
                      work: Path, composition: str, progress, cache_root: Path | None = None) -> tuple[
                          list[dict[str, Any]], dict[tuple[str, int], tuple[int, int]], dict[str, int]]:
    groups: list[list[dict[str, Any]]] = []
    ordered = ([row for row in encoded if row["integerization"] != "NOT_APPLICABLE_RAW_BYTES"] +
               [row for row in encoded if row["integerization"] == "NOT_APPLICABLE_RAW_BYTES"])
    current: list[dict[str, Any]] = []; amount = source_amount = 0; current_text = None
    for row in ordered:
        size = row["container_bytes"]; text = row["integerization"] != "NOT_APPLICABLE_RAW_BYTES"
        source_limit = COMPOSITION_MAX_SOURCE if text else MAX_TOTAL_BYTES
        if current and (text != current_text or len(current) == GROUP_MAX_DOCUMENTS or
                        amount + size > GROUP_MAX_INPUT or source_amount + row["source_bytes"] > source_limit):
            groups.append(current); current = []; amount = source_amount = 0
        current.append(row); amount += size; source_amount += row["source_bytes"]; current_text = text
    if current: groups.append(current)
    segments: list[dict[str, Any]] = []
    locations: dict[tuple[str, int], tuple[int, int]] = {}
    summary = {"groups_considered": 0, "groups_selected": 0, "cross_document_groups_selected": 0,
               "saved_complete_segment_bytes": 0, "groups_held_or_unprofitable": 0,
               "composition_cache_hits": 0}
    for segment_index, group in enumerate(groups):
        path = f"payload/segment-{segment_index:08d}.crys"
        if progress:
            progress({"stage": "STANDARD_SEGMENT_CONTROL", "segment": segment_index + 1,
                      "total_segments": len(groups), "members": len(group)})
        baseline = _baseline_segment(group, work, segment_index, path)
        selected = baseline
        text_group = all(row["integerization"] != "NOT_APPLICABLE_RAW_BYTES" for row in group)
        if composition == "auto" and text_group:
            summary["groups_considered"] += 1
            candidate, census = _collection_segment(group, sources, work, segment_index, path, progress, cache_root)
            summary["composition_cache_hits"] += int(census.get("cache_hit", False))
            if candidate is not None:
                baseline_cost = _segment_cost(baseline); candidate_cost = _segment_cost(candidate)
                candidate["composition"]["control_complete_segment_bytes"] = baseline_cost
                candidate["composition"]["candidate_complete_segment_bytes"] = candidate_cost
                candidate["composition"]["saved_complete_segment_bytes"] = baseline_cost - candidate_cost
                if candidate_cost < baseline_cost:
                    selected = candidate; summary["groups_selected"] += 1
                    summary["cross_document_groups_selected"] += int(len(group) > 1)
                    summary["saved_complete_segment_bytes"] += baseline_cost - candidate_cost
                else:
                    summary["groups_held_or_unprofitable"] += 1
            else:
                summary["groups_held_or_unprofitable"] += 1
        segments.append(selected)
        for member, row in enumerate(group):
            locations[row["key"]] = (segment_index, member)
        if progress:
            progress({"stage": "STANDARD_SEGMENT_SELECTED", "segment": segment_index + 1,
                      "kind": selected["kind"], "bytes": selected["bytes"],
                      "composition_selected": selected is not baseline})
    return segments, locations, summary


def pack(inputs: Iterable[Path | str], output: Path | str | None = None, *, mode: str = "semantic",
         registry: dict[str, Any] | None = None, cache_root: Path | str | None = None,
         workers: int = 0, chunk_bytes: int = DEFAULT_CHUNK_BYTES,
         composition: str = "auto", dry_run: bool = False, progress=None) -> dict[str, Any]:
    inputs = list(inputs)
    provisional = inventory(inputs, output=Path(output).absolute() if output is not None else None)
    target = Path(output).absolute() if output is not None else default_output(inputs, provisional["source_tree_root"])
    protect_outputs([target], [Path(value) for value in inputs])
    _require(not target.exists() and not target.is_symlink(), "HELD_STANDARD_DESTINATION_EXISTS", str(target))
    _require(type(workers) is int and 0 <= workers <= 64, "HELD_STANDARD_WORKERS")
    _require(type(chunk_bytes) is int and 1 <= chunk_bytes <= MAX_CHUNK_BYTES,
             "HELD_STANDARD_CHUNK_LIMIT")
    _require(composition in ("auto", "off"), "HELD_STANDARD_COMPOSITION_MODE")
    cache = Path(cache_root).absolute() if cache_root is not None else None
    _protect_locations(inputs, target, cache)
    if dry_run:
        return {**plan(inputs, output=target, mode=mode, registry=registry), "output": str(target),
                "workers": workers, "chunk_bytes": chunk_bytes,
                "composition": composition,
                "cache_root": str(cache) if cache is not None else None}
    _require(mode in ("semantic", "smallest", "portable"), "HELD_STANDARD_MODE", mode)
    registry_root = validate_registry(registry) if registry is not None else None
    target.parent.mkdir(parents=True, exist_ok=True)
    if progress: progress({"stage": "STANDARD_INVENTORY_COMPLETE", "files": provisional["file_count"],
                           "bytes": provisional["source_bytes"]})
    with tempfile.TemporaryDirectory(prefix="semcrys-standard-", dir=target.parent) as name:
        work = Path(name)
        file_rows = [row for row in provisional["rows"] if row["kind"] == "file"]
        chunks, file_keys = _chunk_rows(file_rows, work, chunk_bytes)
        encoded, by_key = _encode_unique(chunks, work, mode, cache, workers, progress)
        chunk_source = {(row["sha256"], row["bytes"]): Path(row["source_path"]) for row in chunks}
        segments, locations, composition_summary = _segment_payloads(
            encoded, chunk_source, work, composition, progress, cache)
        entries = []
        file_index = 0
        semantic_streams: dict[str, bytes] = {}
        semantic_descriptors: dict[tuple[str, int], dict[str, Any]] = {}
        semantic_objects: dict[tuple[str, int], dict[str, Any]] = {}
        postings: dict[int, list[list[int]]] = {}
        semantic_events = semantic_bound = 0
        if registry is not None:
            for unique_index, realization in enumerate(encoded):
                if realization["integerization"] == "NOT_APPLICABLE_RAW_BYTES":
                    continue
                key = realization["key"]
                stream = integerize(chunk_source[key].read_bytes(), registry)
                data = canonical(stream); path = f"semantic/{unique_index:08d}.json"
                semantic_streams[path] = data; semantic_objects[key] = stream
                semantic_descriptors[key] = {"path": path, "sha256": hashlib.sha256(data).hexdigest(),
                                             "stream_root": stream["stream_root"]}
        for row in provisional["rows"]:
            public = {k: v for k, v in row.items() if k != "source_path"}
            if row["kind"] == "file":
                references = []
                for chunk_index, key in enumerate(file_keys[file_index]):
                    realization = by_key[key]; segment, member = locations[key]
                    member_descriptor = segments[segment]["members"][member]
                    semantic = semantic_descriptors.get(key)
                    references.append({"segment": segment, "member": member,
                                       "bytes": key[1], "sha256": key[0],
                                       "encoding": member_descriptor.get("encoding", _encoding_descriptor(realization)),
                                       "semantic_stream": semantic})
                    stream = semantic_objects.get(key)
                    if stream is not None:
                        semantic_events += stream["event_count"]
                        semantic_bound += stream["semantic_event_count"]
                        for token_index, event in enumerate(stream["events"]):
                            if event[0] == 0:
                                postings.setdefault(event[1], []).append([file_index, chunk_index, token_index])
                public["chunks"] = references
                file_index += 1
            entries.append(public)
        gti_data = None; gti_descriptor = None
        if registry is not None:
            terms = []
            for row in registry["entries"]:
                terms.append({"csil_id": row["integer_id"], "semantic_key": row["semantic_key"],
                              "surface": row["surface"], "occurrences": postings.get(row["integer_id"], [])})
            gti = {"schema": "semcrys.global-term-index.v0.1.candidate",
                   "standing": "CALLER_SUPPLIED_REGISTRY_NO_CANONICAL_IDENTITY_EFFECT",
                   "registry_root": registry_root,
                   "csil_identity": "CALLER_REGISTRY_ROOT_PLUS_POSITIVE_INTEGER_NO_CANONICAL_EFFECT",
                   "index_role": "TERM_ALIAS_OR_KEY_TO_CSIL_ID_AND_OCCURRENCES",
                   "document_local_ids_included": False, "terms": terms}
            gti["gti_root"] = _root(gti); gti_data = canonical(gti)
            gti_descriptor = {"path": "index/gti.json", "sha256": hashlib.sha256(gti_data).hexdigest(),
                              "gti_root": gti["gti_root"]}
        manifest = {"schema": MANIFEST_SCHEMA, "profile": PROFILE, "source_tree_root": provisional["source_tree_root"],
                    "entries": entries, "file_count": provisional["file_count"],
                    "directory_count": provisional["directory_count"], "source_bytes": provisional["source_bytes"],
                    "chunk_count": sum(len(keys) for keys in file_keys),
                    "unique_chunk_count": len(encoded),
                    "segments": [{k: v for k, v in segment.items() if k != "source_path"} for segment in segments],
                    "registry_root": registry_root, "global_term_index": gti_descriptor,
                    "semantic_event_count": semantic_events,
                    "caller_semantic_event_count": semantic_bound,
                    "caller_semantic_coverage": (semantic_bound / semantic_events if semantic_events else None),
                    "composition_mode": composition, "composition_summary": composition_summary}
        manifest["manifest_root"] = _root(manifest)
        manifest_data = canonical(manifest)
        _require(len(manifest_data) <= MAX_MANIFEST_BYTES, "HELD_STANDARD_MANIFEST_LIMIT")
        body = work / "archive.body"
        with zipfile.ZipFile(body, "w", allowZip64=True) as archive:
            _zip_write(archive, "manifest.json", manifest_data)
            for segment in segments:
                _zip_write(archive, segment["path"], Path(segment["source_path"]))
            for path, data in sorted(semantic_streams.items()):
                _zip_write(archive, path, data)
            if gti_data is not None:
                _zip_write(archive, "index/gti.json", gti_data)
        configuration = {"schema": SCHEMA, "standing": "CANDIDATE_ONLY", "profile": PROFILE,
                         "objective": OBJECTIVE if mode != "smallest" else "MIN_MEASURED_SELF_CONTAINED_BYTES",
                         "mode": mode, "body_schema": BODY_SCHEMA, "manifest_root": manifest["manifest_root"],
                         "source_tree_root": provisional["source_tree_root"], "file_count": provisional["file_count"],
                         "directory_count": provisional["directory_count"], "source_bytes": provisional["source_bytes"],
                         "chunk_bytes": chunk_bytes, "chunk_count": manifest["chunk_count"],
                         "unique_chunk_count": manifest["unique_chunk_count"], "segment_count": len(segments),
                         "composition_mode": composition, "composition_summary": composition_summary,
                         "registry_root": registry_root, "candidate_codecs": list(CODECS),
                         "external_dependencies": [], "path_policy": "SAFE_RELATIVE_POSIX_NO_REPARSE",
                         "metadata_policy": "MODE_AND_MTIME_NS", "security_claim": "NONE",
                         "global_optimality": False, "source_mutation": False,
                         "operation_sequence": ["INVENTORY", "CHUNK", "DEDUPLICATE", "MEASURE", "ENCODE",
                                                "CENSUS_RECURRING_EVENTS", "COURT_ADAPTIVE_COMPOSITION",
                                                "POOL_METALEGENDS", "BIND_SEMANTIC_INDEX", "BIND_MANIFEST",
                                                "VERIFY", "PUBLISH"]}
        configuration["instance_constitution_sha256"] = _root(configuration)
        pending = work / "result.crys"
        write_crys(pending, configuration=configuration, body=body,
                   decoded_sha256=provisional["source_tree_root"])
        verification = verify(pending, max_output_bytes=max(provisional["source_bytes"], 1))
        _require(verification["source_tree_root"] == provisional["source_tree_root"], "HELD_STANDARD_VERIFY_ROOT")
        os.replace(pending, target)
    if progress: progress({"stage": "STANDARD_COMPLETE", "output": str(target), "sha256": file_sha256(target)})
    return {"status": "PASS", "schema": "semcrys.standard-pack-result.v0.1", "output": str(target),
            "output_sha256": file_sha256(target), "output_bytes": target.stat().st_size,
            "source_tree_root": provisional["source_tree_root"], "source_bytes": provisional["source_bytes"],
            "files": provisional["file_count"], "directories": provisional["directory_count"],
            "chunks": manifest["chunk_count"], "unique_chunks": manifest["unique_chunk_count"],
            "segments": len(segments), "workers": min(max(1, workers or min(4, os.cpu_count() or 1)), max(1, len(encoded))),
            "mode": mode, "profile": PROFILE, "registry_root": registry_root,
            "cache_hits": sum(row["cache_hit"] for row in encoded), "verified": True,
            "cache_write_failures": sum(row["cache_write_failed"] for row in encoded),
            "composition_mode": composition, "composition": composition_summary,
            "input_mutation": False, "security_claim": "NONE"}


def _load(source: Path | str, work: Path) -> tuple[dict[str, Any], dict[str, Any], Path]:
    source = Path(source)
    body = work / "body.zip"
    with body.open("wb") as sink:
        view = inspect_crys(source, body_sink=sink,
                            limits=Limits(max_control_bytes=MAX_MANIFEST_BYTES,
                                          max_section_bytes=1 << 44, max_total_payload_bytes=1 << 44))
    config = view["configuration"]
    accepted_pairs = {(SCHEMA, BODY_SCHEMA)} | {(schema, body) for schema, _, body in LEGACY_SCHEMA_TRIPLES}
    _require((config.get("schema"), config.get("body_schema")) in accepted_pairs,
             "HELD_STANDARD_SCHEMA")
    claimed = config.get("instance_constitution_sha256")
    subject = dict(config); subject.pop("instance_constitution_sha256", None)
    _require(claimed == _root(subject), "HELD_STANDARD_CONFIGURATION_ROOT")
    try:
        archive = zipfile.ZipFile(body)
        names = archive.namelist()
        _require(len(names) == len(set(names)) and "manifest.json" in names, "HELD_STANDARD_BODY_INDEX")
        _require(all(_safe_path(name) == name for name in names), "HELD_STANDARD_BODY_PATH")
        data = archive.read("manifest.json")
        _require(len(data) <= MAX_MANIFEST_BYTES, "HELD_STANDARD_MANIFEST_LIMIT")
        manifest = json.loads(data.decode("utf-8"))
        _require(canonical(manifest) == data, "HELD_STANDARD_MANIFEST_CANONICAL")
    except (zipfile.BadZipFile, KeyError, UnicodeError, ValueError) as exc:
        if isinstance(exc, StandardRefusal): raise
        raise StandardRefusal("HELD_STANDARD_BODY") from exc
    finally:
        if "archive" in locals(): archive.close()
    claimed_manifest = manifest.get("manifest_root")
    subject = dict(manifest); subject.pop("manifest_root", None)
    triple = (config.get("schema"), manifest.get("schema"), config.get("body_schema"))
    _require(triple == (SCHEMA, MANIFEST_SCHEMA, BODY_SCHEMA) or triple in LEGACY_SCHEMA_TRIPLES,
             "HELD_STANDARD_SCHEMA")
    _require(claimed_manifest == _root(subject), "HELD_STANDARD_MANIFEST_ROOT")
    _require(config.get("manifest_root") == claimed_manifest and
             config.get("source_tree_root") == manifest.get("source_tree_root"), "HELD_STANDARD_CORRESPONDENCE")
    _validate_manifest(manifest, names)
    return view, manifest, body


def _validate_manifest(manifest: dict[str, Any], names: list[str]) -> None:
    if manifest.get("schema") == MANIFEST_SCHEMA:
        _require(manifest.get("composition_mode") in ("auto", "off") and
                 isinstance(manifest.get("composition_summary"), dict),
                 "HELD_STANDARD_COMPOSITION_MANIFEST")
    entries = manifest.get("entries")
    _require(isinstance(entries, list) and len(entries) <= MAX_FILES * 2, "HELD_STANDARD_MANIFEST_ENTRIES")
    seen: set[str] = set(); files = directories = source_bytes = 0
    expected = {"manifest.json"}
    segments = manifest.get("segments")
    _require(isinstance(segments, list) and len(segments) <= MAX_FILES, "HELD_STANDARD_SEGMENTS")
    for index, segment in enumerate(segments):
        _require(isinstance(segment, dict) and segment.get("kind") in
                 ("DIRECT", "METALEGEND", "INTEGER_COLLECTION", "COMPOSED_COLLECTION"),
                 "HELD_STANDARD_SEGMENT")
        path = _safe_path(segment.get("path")); expected.add(path)
        _require(path == f"payload/segment-{index:08d}.crys" and
                 isinstance(segment.get("members"), list) and segment["members"],
                 "HELD_STANDARD_SEGMENT_ORDER")
        if segment["kind"] == "DIRECT":
            _require(len(segment["members"]) == 1, "HELD_STANDARD_SEGMENT_KIND")
        elif segment["kind"] == "METALEGEND":
            _require(len(segment["members"]) > 1, "HELD_STANDARD_SEGMENT_KIND")
        else:
            _require(type(segment.get("collection_bytes")) is int and
                     segment["collection_bytes"] == sum(row.get("source_bytes", -1)
                                                        for row in segment["members"]) and
                     isinstance(segment.get("collection_sha256"), str) and
                     len(segment["collection_sha256"]) == 64 and
                     all(c in "0123456789abcdef" for c in segment["collection_sha256"]) and
                     isinstance(segment.get("composition"), dict),
                     "HELD_STANDARD_COLLECTION")
            offset = 0
            for member in segment["members"]:
                _require(member.get("offset") == offset, "HELD_STANDARD_COLLECTION_OFFSET")
                offset += member.get("source_bytes", -1)
    gti = manifest.get("global_term_index")
    if gti is not None:
        _require(isinstance(gti, dict) and _safe_path(gti.get("path")) == "index/gti.json",
                 "HELD_STANDARD_GTI_DESCRIPTOR")
        expected.add("index/gti.json")
    for row in entries:
        _require(isinstance(row, dict), "HELD_STANDARD_MANIFEST_ENTRY")
        path = _safe_path(row.get("path"))
        _require(path not in seen, "HELD_STANDARD_PATH_COLLISION", path); seen.add(path)
        _require(row.get("kind") in ("file", "directory"), "HELD_STANDARD_ENTRY_KIND")
        if row["kind"] == "directory": directories += 1; continue
        files += 1; source_bytes += row.get("bytes", -1)
        chunks = row.get("chunks")
        _require(isinstance(chunks, list) and chunks, "HELD_STANDARD_FILE_CHUNKS")
        chunk_total = 0
        for chunk in chunks:
            _require(isinstance(chunk, dict) and type(chunk.get("segment")) is int and
                     0 <= chunk["segment"] < len(segments), "HELD_STANDARD_CHUNK_REFERENCE")
            segment = segments[chunk["segment"]]
            _require(type(chunk.get("member")) is int and 0 <= chunk["member"] < len(segment["members"]),
                     "HELD_STANDARD_CHUNK_REFERENCE")
            member = segment["members"][chunk["member"]]
            _require(chunk.get("sha256") == member.get("source_sha256") and
                     chunk.get("bytes") == member.get("source_bytes"), "HELD_STANDARD_CHUNK_ROOT")
            chunk_total += chunk["bytes"]
            semantic = chunk.get("semantic_stream")
            if semantic is not None:
                path = _safe_path(semantic.get("path")); expected.add(path)
        _require(chunk_total == row.get("bytes"), "HELD_STANDARD_FILE_CHUNK_BYTES")
    _require(files == manifest.get("file_count") and directories == manifest.get("directory_count") and
             source_bytes == manifest.get("source_bytes"), "HELD_STANDARD_MANIFEST_COUNTS")
    _require(sum(len(row["chunks"]) for row in entries if row["kind"] == "file") == manifest.get("chunk_count"),
             "HELD_STANDARD_CHUNK_COUNT")
    _require(set(names) == expected, "HELD_STANDARD_BODY_EXTRAS")


def inspect(source: Path | str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="semcrys-standard-inspect-") as name:
        view, manifest, _ = _load(source, Path(name))
    return {"status": "PASS", "schema": "semcrys.standard-inspection.v0.1",
            "archive_sha256": view["file_sha256"], "configuration": view["configuration"],
            "manifest_root": manifest["manifest_root"], "source_tree_root": manifest["source_tree_root"],
            "files": manifest["file_count"], "directories": manifest["directory_count"],
            "source_bytes": manifest["source_bytes"], "chunks": manifest["chunk_count"],
            "unique_chunks": manifest["unique_chunk_count"], "segments": len(manifest["segments"]),
            "registry_root": manifest["registry_root"],
            "gti_root": manifest["global_term_index"]["gti_root"] if manifest["global_term_index"] else None,
            "caller_semantic_coverage": manifest["caller_semantic_coverage"],
            "composition_mode": manifest.get("composition_mode", "off"),
            "composition": manifest.get("composition_summary", {}),
            "security_claim": "NONE"}


def list_entries(source: Path | str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="semcrys-standard-list-") as name:
        _, manifest, _ = _load(source, Path(name))
    return {"status": "PASS", "schema": "semcrys.standard-list.v0.1",
            "source_tree_root": manifest["source_tree_root"],
            "entries": [{k: row[k] for k in ("path", "kind", "bytes", "sha256") if k in row}
                        for row in manifest["entries"]]}


def _read_rooted_json(body: Path, descriptor: dict[str, Any], root_field: str,
                      code: str) -> dict[str, Any]:
    with zipfile.ZipFile(body) as archive:
        data = archive.read(descriptor["path"])
    _require(hashlib.sha256(data).hexdigest() == descriptor["sha256"], code)
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise StandardRefusal(code) from exc
    _require(canonical(value) == data, code)
    claimed = value.get(root_field); subject = dict(value); subject.pop(root_field, None)
    _require(claimed == _root(subject) == descriptor[root_field], code)
    return value


def _validate_gti(manifest: dict[str, Any], body: Path) -> dict[str, Any] | None:
    descriptor = manifest.get("global_term_index")
    if descriptor is None:
        return None
    gti = _read_rooted_json(body, descriptor, "gti_root", "HELD_STANDARD_GTI_ROOT")
    _require(gti.get("schema") == "semcrys.global-term-index.v0.1.candidate" and
             gti.get("registry_root") == manifest.get("registry_root") and
             isinstance(gti.get("terms"), list), "HELD_STANDARD_GTI_SCHEMA")
    file_entries = [row for row in manifest["entries"] if row["kind"] == "file"]
    for term in gti["terms"]:
        _require(type(term.get("csil_id")) is int and term["csil_id"] > 0 and
                 isinstance(term.get("semantic_key"), str) and isinstance(term.get("surface"), str) and
                 isinstance(term.get("occurrences"), list), "HELD_STANDARD_GTI_TERM")
        for occurrence in term["occurrences"]:
            _require(isinstance(occurrence, list) and len(occurrence) == 3 and
                     all(type(value) is int and value >= 0 for value in occurrence),
                     "HELD_STANDARD_GTI_OCCURRENCE")
            file_index, chunk_index, _ = occurrence
            _require(file_index < len(file_entries) and
                     chunk_index < len(file_entries[file_index]["chunks"]),
                     "HELD_STANDARD_GTI_OCCURRENCE")
    return gti


def search(source: Path | str, query: str) -> dict[str, Any]:
    _require(isinstance(query, str) and query, "HELD_STANDARD_SEARCH_QUERY")
    with tempfile.TemporaryDirectory(prefix="semcrys-standard-search-") as name:
        _, manifest, body = _load(source, Path(name))
        gti = _validate_gti(manifest, body)
        _require(gti is not None, "HELD_STANDARD_GTI_MISSING")
        claimed = gti["gti_root"]
        matches = []
        for term in gti["terms"]:
            if query in (str(term["csil_id"]), term["semantic_key"], term["surface"]):
                file_entries = [row for row in manifest["entries"] if row["kind"] == "file"]
                occurrences = [{"path": file_entries[file_index]["path"], "chunk_index": chunk_index,
                                "token_index": token_index}
                               for file_index, chunk_index, token_index in term["occurrences"]]
                matches.append({**{k: term[k] for k in ("csil_id", "semantic_key", "surface")},
                                "occurrences": occurrences})
    return {"status": "PASS", "schema": "semcrys.global-term-search.v0.1.candidate",
            "registry_root": gti["registry_root"], "gti_root": claimed, "query": query,
            "matches": matches, "match_count": len(matches),
            "canonical_identity_effect": "NONE_CALLER_REGISTRY_ONLY"}


def _extract_member(body: Path, name: str, target: Path) -> None:
    with zipfile.ZipFile(body) as archive, archive.open(name) as incoming, target.open("wb") as output:
        shutil.copyfileobj(incoming, output, 1024 * 1024)


def _materialize_segment(body: Path, descriptor: dict[str, Any], work: Path,
                         segment_index: int) -> list[Path]:
    archive = work / f"segment-{segment_index:08d}.crys"
    _extract_member(body, descriptor["path"], archive)
    _require(archive.stat().st_size == descriptor["bytes"] and
             file_sha256(archive) == descriptor["sha256"], "HELD_STANDARD_SEGMENT_ROOT")
    if descriptor["kind"] in ("INTEGER_COLLECTION", "COMPOSED_COLLECTION"):
        combined = work / f"segment-{segment_index:08d}-collection.decoded"
        result = decode_file(archive, combined, max_decoded_bytes=descriptor["collection_bytes"])
        _require(result["output_sha256"] == descriptor["collection_sha256"] and
                 combined.stat().st_size == descriptor["collection_bytes"],
                 "HELD_STANDARD_COLLECTION_INVERSE")
        containers = []
        with combined.open("rb") as incoming:
            for member_index, member in enumerate(descriptor["members"]):
                _require(incoming.tell() == member["offset"], "HELD_STANDARD_COLLECTION_OFFSET")
                target = work / f"segment-{segment_index:08d}-member-{member_index:08d}.decoded"
                remaining = member["source_bytes"]
                with target.open("wb") as output:
                    while remaining:
                        block = incoming.read(min(1024 * 1024, remaining))
                        _require(bool(block), "HELD_STANDARD_COLLECTION_TRUNCATED")
                        output.write(block); remaining -= len(block)
                _require(file_sha256(target) == member["source_sha256"],
                         "HELD_STANDARD_COLLECTION_MEMBER_ROOT")
                containers.append(target)
        return containers
    if descriptor["kind"] == "DIRECT":
        containers = [archive]
    else:
        restored = work / f"segment-{segment_index:08d}-restored"
        result = restore_group_legend(archive, restored,
                                    max_output_bytes=sum(row["container_bytes"] for row in descriptor["members"]))
        containers = [restored / row["file"] for row in result["restored_artifacts"]
                      if row["kind"] == "CONTAINER"]
    _require(len(containers) == len(descriptor["members"]), "HELD_STANDARD_SEGMENT_MEMBERS")
    for path, member in zip(containers, descriptor["members"]):
        _require(path.stat().st_size == member["container_bytes"] and
                 file_sha256(path) == member["container_sha256"], "HELD_STANDARD_PAYLOAD_ROOT")
    return containers


def verify(source: Path | str, *, max_output_bytes: int = MAX_TOTAL_BYTES, progress=None) -> dict[str, Any]:
    source = Path(source)
    _require(isinstance(max_output_bytes, int) and 0 <= max_output_bytes <= MAX_TOTAL_BYTES,
             "HELD_STANDARD_OUTPUT_LIMIT")
    with tempfile.TemporaryDirectory(prefix="semcrys-standard-verify-", dir=source.parent) as name:
        work = Path(name); view, manifest, body = _load(source, work)
        _validate_gti(manifest, body)
        total = 0; files = 0; materialized: dict[int, list[Path]] = {}
        for row in manifest["entries"]:
            if row["kind"] != "file": continue
            total += row["bytes"]; _require(total <= max_output_bytes, "HELD_STANDARD_OUTPUT_LIMIT")
            digest = hashlib.sha256(); size = 0
            for chunk_index, chunk in enumerate(row["chunks"]):
                segment_index = chunk["segment"]
                if segment_index not in materialized:
                    materialized[segment_index] = _materialize_segment(
                        body, manifest["segments"][segment_index], work, segment_index)
                container = materialized[segment_index][chunk["member"]]
                collection = manifest["segments"][segment_index]["kind"] in (
                    "INTEGER_COLLECTION", "COMPOSED_COLLECTION")
                decoded = container
                if not collection:
                    decoded = work / f"{files:08d}-{chunk_index:08d}.decoded"
                    result = decode_file(container, decoded, max_decoded_bytes=chunk["bytes"])
                    _require(result["output_sha256"] == chunk["sha256"] and
                             decoded.stat().st_size == chunk["bytes"], "HELD_STANDARD_CHUNK_INVERSE", row["path"])
                with decoded.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(block); size += len(block)
                semantic_descriptor = chunk.get("semantic_stream")
                if semantic_descriptor:
                    stream = _read_rooted_json(body, semantic_descriptor, "stream_root",
                                               "HELD_STANDARD_SEMANTIC_ROOT")
                    _require(stream.get("source_sha256") == chunk["sha256"] and
                             stream.get("source_bytes") == chunk["bytes"] and
                             stream.get("registry_root") == manifest.get("registry_root"),
                             "HELD_STANDARD_SEMANTIC_CORRESPONDENCE")
            _require(digest.hexdigest() == row["sha256"] and size == row["bytes"],
                     "HELD_STANDARD_SOURCE_INVERSE", row["path"])
            files += 1
            if progress: progress({"stage": "STANDARD_VERIFY_FILE", "files": files,
                                   "total_files": manifest["file_count"], "path": row["path"]})
    return {"status": "PASS", "schema": "semcrys.standard-verification.v0.1",
            "archive_sha256": view["file_sha256"], "manifest_root": manifest["manifest_root"],
            "source_tree_root": manifest["source_tree_root"], "files": files,
            "source_bytes": total, "exact_reconstruction": True, "external_dependencies": [],
            "security_claim": "NONE"}


def unpack(source: Path | str, output: Path | str, *, only: Iterable[str] = (),
           max_output_bytes: int = MAX_TOTAL_BYTES, progress=None) -> dict[str, Any]:
    source, target = Path(source), Path(output).absolute()
    protect_outputs([target], [source])
    _require(not target.exists() and not target.is_symlink(), "HELD_STANDARD_DESTINATION_EXISTS", str(target))
    selected = {_safe_path(value) for value in only}
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="semcrys-standard-unpack-", dir=target.parent) as name:
        work = Path(name); _, manifest, body = _load(source, work)
        known = {row["path"] for row in manifest["entries"]}
        _require(selected <= known, "HELD_STANDARD_SELECTION_MISSING", ",".join(sorted(selected - known)))
        stage = work / "result"; stage.mkdir(); total = files = 0
        materialized: dict[int, list[Path]] = {}
        rows = [row for row in manifest["entries"] if not selected or row["path"] in selected]
        for row in rows:
            destination = stage.joinpath(*PurePosixPath(row["path"]).parts)
            _require(destination.resolve().is_relative_to(stage.resolve()), "HELD_STANDARD_EXTRACTION_PATH")
            if row["kind"] == "directory": destination.mkdir(parents=True, exist_ok=True); continue
            total += row["bytes"]; _require(total <= max_output_bytes, "HELD_STANDARD_OUTPUT_LIMIT")
            destination.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256(); size = 0
            with destination.open("wb") as output_stream:
                for chunk_index, chunk in enumerate(row["chunks"]):
                    segment_index = chunk["segment"]
                    if segment_index not in materialized:
                        materialized[segment_index] = _materialize_segment(
                            body, manifest["segments"][segment_index], work, segment_index)
                    container = materialized[segment_index][chunk["member"]]
                    collection = manifest["segments"][segment_index]["kind"] in (
                        "INTEGER_COLLECTION", "COMPOSED_COLLECTION")
                    decoded = container
                    if not collection:
                        decoded = work / f"selected-{files:08d}-{chunk_index:08d}.decoded"
                        result = decode_file(container, decoded, max_decoded_bytes=chunk["bytes"])
                        _require(result["output_sha256"] == chunk["sha256"], "HELD_STANDARD_CHUNK_INVERSE")
                    with decoded.open("rb") as incoming:
                        for block in iter(lambda: incoming.read(1024 * 1024), b""):
                            output_stream.write(block); digest.update(block); size += len(block)
            _require(size == row["bytes"] and digest.hexdigest() == row["sha256"],
                     "HELD_STANDARD_SOURCE_INVERSE")
            files += 1
            if progress: progress({"stage": "STANDARD_UNPACK_FILE", "files": files, "path": row["path"]})
        for row in sorted(rows, key=lambda item: item["path"].count("/"), reverse=True):
            destination = stage.joinpath(*PurePosixPath(row["path"]).parts)
            if destination.exists():
                try: os.chmod(destination, row["mode"])
                except OSError: pass
                try: os.utime(destination, ns=(row["mtime_ns"], row["mtime_ns"]), follow_symlinks=False)
                except (OSError, NotImplementedError):
                    try: os.utime(destination, ns=(row["mtime_ns"], row["mtime_ns"]))
                    except OSError: pass
        os.replace(stage, target)
    return {"status": "PASS", "schema": "semcrys.standard-unpack-result.v0.1",
            "output": str(target), "source_tree_root": manifest["source_tree_root"],
            "files": files, "bytes": total, "selection": sorted(selected),
            "exact_reconstruction": True, "security_claim": "NONE"}
