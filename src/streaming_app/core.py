"""Bounded-memory SemCrys application over the frozen v0.2 artifact ABIs."""

from __future__ import annotations
from streaming_legend import scratch_io as sio

import bz2
import codecs
import hashlib
import io
import json
import lzma
import os
import sqlite3
import sys
import tempfile
import time
import unicodedata
from collections import OrderedDict
from array import array
from pathlib import Path
from typing import BinaryIO, Iterator, Mapping, Sequence
from .legend_context import governed_context
from semcrys_native import pack_varints as _native_pack_varints,parse_packed_events as _native_parse_packed_events

HERE = Path(__file__).resolve().parent
# The successor vendors its implementation. Frozen predecessors are evidence,
# never imported as hidden runtime dependencies.

from streaming_legend import write_legend  # noqa: E402
from streaming_legend.assembly import ExecutionLegendReader as LegendReader,MODES as ASSEMBLY_MODES,COMPACT_MODE,ABI as ASSEMBLY_ABI,FAMILY_ABI
from streaming_legend.core import canonical, file_sha256  # noqa: E402
from streaming_legend.glyph import load as load_glyph, alphabet_parameters, code_width
from streaming_legend.crys_v2 import (  # noqa: E402
    MAGIC as CRYS_MAGIC,
    PROLOGUE,
    SECTION,
    VERSION as CRYS_VERSION,
    inspect_crys,
    write_crys,
    Limits,
)

PREDECESSOR_HEAD = "66eada34e3979929ab98eea00806121d2da3a76f11599861917616e57669e1d3"
PACKED_MAGIC = b"SPV2"
RAW_MAGIC = b"RAW2"
CHUNK = 1024 * 1024
MAX_UNIT_BYTES = 4096
FULL_NATIVE_PACK_MIN_RUN = 512
NATIVE_PARSE_MAX_BYTES = 64 * 1024 * 1024
DECODE_RESOLUTION_BATCH = 8192

# NONE and LZMA are the frozen dev73 spellings.  Their configuration and bytes
# must remain unchanged.  The explicit spellings below are successor-only
# profiles whose algorithm parameters are bound in the Instance Constitution.
LEGACY_OUTER_CODECS = ("NONE", "LZMA")
EXTENDED_OUTER_CODECS = (
    "LZMA2_XZ_0", "LZMA2_XZ_6", "LZMA2_XZ_9", "BZ2_1", "BZ2_9",
)
REQUESTABLE_OUTER_CODECS = LEGACY_OUTER_CODECS + EXTENDED_OUTER_CODECS + (
    "ZSTD", "ZSTD_DICT",
)


def outer_codec_configuration(name: str) -> dict | None:
    """Return the rooted codec contract fragment, or None for frozen dev73.

    Zstandard names are deliberately requestable so the CLI can fail with a
    typed capability hold instead of hiding or silently substituting a codec.
    """
    if name in LEGACY_OUTER_CODECS:
        return None
    if name in ("ZSTD", "ZSTD_DICT"):
        raise Refusal("HELD_OPTIONAL_CODEC_ADAPTER_NOT_PACKAGED", name)
    if name.startswith("LZMA2_XZ_") and name[-1:] in ("0", "6", "9"):
        level = int(name[-1])
        return {
            "schema": "semcrys.outer-codec-configuration.v0.1",
            "name": name,
            "codec": "LZMA2",
            "codec_version": "XZ_STREAM_FORMAT_1_0",
            "framing": "XZ",
            "level": level,
            "dictionary": {"mode": "NONE", "sha256": None},
            "operation_sequence": ["ENCODE_PHYSICAL_BODY", "APPLY_OUTER_CODEC"],
        }
    if name.startswith("BZ2_") and name[-1:] in ("1", "9"):
        level = int(name[-1])
        return {
            "schema": "semcrys.outer-codec-configuration.v0.1",
            "name": name,
            "codec": "BZIP2",
            "codec_version": "BZIP2_STREAM_FORMAT_1_0",
            "framing": "BZIP2",
            "level": level,
            "dictionary": {"mode": "NONE", "sha256": None},
            "operation_sequence": ["ENCODE_PHYSICAL_BODY", "APPLY_OUTER_CODEC"],
        }
    raise Refusal("HELD_OUTER_CODEC_UNAVAILABLE", name)


class Refusal(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def _rooted(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _is_root(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def protect_outputs(outputs, inputs):
    """Reject path, symlink and hard-link aliases before any output write."""
    checked = [Path(path) for path in inputs]
    for value in outputs:
        path = Path(value)
        for other in checked:
            same = path.resolve() == other.resolve()
            if not same and path.exists() and other.exists():
                same = os.path.samefile(path, other)
            if same: raise Refusal("HELD_PROTECTED_PATH_ALIAS", str(path))
        checked.append(path)


def _snapshot(source: Path, target: Path, expected: str | None = None) -> str:
    digest = hashlib.sha256()
    with source.open("rb") as incoming, sio.open_output(target,"wb") as outgoing:
        for block in iter(lambda: incoming.read(CHUNK), b""):
            digest.update(block); outgoing.write(block)
    root = digest.hexdigest()
    if expected is not None and root != expected: raise Refusal("HELD_DEPENDENCY_CHANGED_DURING_READ")
    return root


def _snapshot_legends(paths, directory, context=None):
    if context is not None: return [row['path'] for row in context.rows(paths)]
    rows = _load_legends(paths)
    snapshots = []
    for index, row in enumerate(rows):
        target = directory / f"dependency-{index}.leg"
        _snapshot(row["path"], target, row["sha256"])
        snapshots.append(target)
    return snapshots


def _is_word(character: str) -> bool:
    return unicodedata.category(character)[0] in {"L", "N", "M"}


def _is_nospace_script(character: str) -> bool:
    code = ord(character)
    return 0x3400 <= code <= 0x9FFF or 0x3040 <= code <= 0x30FF or 0xAC00 <= code <= 0xD7AF


def iter_units(
    path: str | os.PathLike[str], *, chunk_bytes: int = CHUNK, max_unit_bytes: int = MAX_UNIT_BYTES
) -> Iterator[tuple[str, bytes]]:
    """Yield lossless units using bounded carry; oversize units become literals."""
    if chunk_bytes < 1 or max_unit_bytes < 4:
        raise Refusal("HELD_INVALID_SCANNER_LIMIT")
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    mode: str | None = None
    pending = bytearray()
    oversized = False

    def flush(kind: str | None = None) -> Iterator[tuple[str, bytes]]:
        nonlocal pending
        if pending:
            yield kind or ("lit" if oversized else mode) or "sep", bytes(pending)
            pending = bytearray()

    def append(encoded: bytes, target_mode: str) -> Iterator[tuple[str, bytes]]:
        nonlocal mode, oversized
        if mode != target_mode:
            yield from flush()
            mode = target_mode
            oversized = False
        if len(pending) + len(encoded) > max_unit_bytes:
            oversized = True
            yield from flush("lit")
        pending.extend(encoded)
        if len(pending) >= max_unit_bytes:
            oversized = True
            yield from flush("lit")

    try:
        with Path(path).open("rb") as handle:
            while raw := handle.read(chunk_bytes):
                for character in decoder.decode(raw, final=False):
                    encoded = character.encode("utf-8")
                    if _is_nospace_script(character):
                        yield from flush()
                        mode = None
                        oversized = False
                        yield "unit", encoded
                    elif _is_word(character):
                        yield from append(encoded, "unit")
                    else:
                        # Punctuation is kept with separators. This conservative
                        # scanner does not infer language-specific morphology.
                        yield from append(encoded, "sep")
            decoder.decode(b"", final=True)
    except UnicodeDecodeError as exc:
        raise Refusal("HELD_SOURCE_NOT_UTF8", str(exc.start)) from exc
    yield from flush()


def _load_legends(paths: Sequence[str | os.PathLike[str]], context=None) -> list[dict]:
    if context is not None: return context.rows(paths)
    rows = []
    for value in paths:
        path = Path(value)
        verified = LegendReader(path).verify()
        rows.append({"path": path, "sha256": verified["sha256"], "entries": verified["entry_count"]})
    return rows


def compile_funnel(
    *,
    source_sha256: str,
    profile: str,
    external_legends: Sequence[str | os.PathLike[str]] = (),
    outer_codec: str = "NONE",
    legend_policy: str | None = None,
    security_request: str = "NONE",
    max_unit_bytes: int = MAX_UNIT_BYTES,
    projection: str = 'PACKED', glyph_registry=None, glyph_placement: str = 'EMBEDDED',
    fold_front=None, fold_placement='EMBEDDED', accounting=None, receiver_roots=(),
    legend_context=None,
) -> dict:
    allowed = {
        "C:SELF_CONTAINED_TOKEN", "T:PRESHARED_TOKEN",
        "A:LONGITUDINAL_TOKEN_DELTA", "C:RAW_BYTES",
    }
    if not isinstance(profile, str) or profile not in allowed:
        raise Refusal("HELD_PROFILE_UNAVAILABLE", profile)
    codec_configuration = outer_codec_configuration(outer_codec)
    if legend_policy is None:
        legend_policy = "TOTAL" if profile == "A:LONGITUDINAL_TOKEN_DELTA" else "PROFITABLE"
    if legend_policy not in {"TOTAL", "PROFITABLE"}:
        raise Refusal("HELD_LEGEND_POLICY_UNAVAILABLE", legend_policy)
    if profile == "A:LONGITUDINAL_TOKEN_DELTA" and legend_policy != "TOTAL":
        raise Refusal("HELD_LONGITUDINAL_REQUIRES_TOTAL_DELTA")
    if not _is_root(source_sha256):
        raise Refusal("HELD_INVALID_SOURCE_ROOT")
    if security_request != "NONE":
        raise Refusal("HELD_SECURITY_CAPABILITY_UNAVAILABLE", security_request)
    if type(max_unit_bytes) is not int or not 4 <= max_unit_bytes <= MAX_UNIT_BYTES:
        raise Refusal("HELD_INVALID_SCANNER_LIMIT")
    projection_config = _projection_configuration(projection,glyph_registry,glyph_placement,profile)
    glyph = projection_config if projection=='GLYPH' else None
    integer_projection = projection_config if projection=='INTEGER' else None
    if fold_placement not in ('EMBEDDED','EXTERNAL'): raise Refusal('HELD_FOLD_PLACEMENT')
    if fold_front is None and (fold_placement!='EMBEDDED' or accounting is not None or receiver_roots):
        raise Refusal('HELD_UNUSED_FOLD_CONFIGURATION')
    if accounting is None and receiver_roots: raise Refusal('HELD_TRANSFER_ACCOUNTING_REQUIRED')
    if fold_placement=='EXTERNAL' and accounting is None: raise Refusal('HELD_TRANSFER_ACCOUNTING_REQUIRED')
    legends = _load_legends(external_legends, legend_context)
    from streaming_legend.assembly import PAIR_MODE
    if any(LegendReader(r['path']).header['unit_mode']=='META_RECORDS_V1' for r in legends):
        raise Refusal('HELD_META_REQUIRES_UNPACK')
    if any(LegendReader(r['path']).header['unit_mode']==PAIR_MODE for r in legends):
        raise Refusal('HELD_COMPOSED_REQUIRES_SECOND_PASS_WORKFLOW')
    assembly_roots=[r['sha256'] for r in legends if LegendReader(r['path']).header['unit_mode'] in ASSEMBLY_MODES]
    compact_assembly=any(LegendReader(r['path']).header['unit_mode']==COMPACT_MODE for r in legends)
    if assembly_roots and (projection!='PACKED' or fold_front is not None):
        raise Refusal('HELD_ASSEMBLY_COMPOSITION_NOT_YET_QUALIFIED')
    if profile in {"T:PRESHARED_TOKEN", "A:LONGITUDINAL_TOKEN_DELTA"} and not legends:
        raise Refusal("HELD_REQUIRED_PRESHARED_LEGEND_MISSING")
    if profile in {"C:SELF_CONTAINED_TOKEN", "C:RAW_BYTES"} and legends:
        raise Refusal("HELD_UNUSED_EXTERNAL_LEGEND")
    specification = {"schema": "semcrys.specification.v0.2", "profiles": sorted(allowed), "security_claim": "NONE"}
    specification['projections']={'PACKED':'ALL_PROFILES','GLYPH':'TOKEN_PROFILES_WITH_QUALIFIED_EXACT_TEMPLATE_REGISTRY',
        'INTEGER':'TOKEN_PROFILES_HUMAN_INSPECTION_NOT_BYTE_OPTIMALITY'}
    cm1 = {"schema": "semcrys.cm1.functional.v0.2", "profile": profile,
        "status": "CONFIGURATION_ADMISSIBLE_INPUT_PREFLIGHT_PENDING",
        "configuration_preconditions_satisfied": True, "input_validity_claim": "NOT_YET_TESTED"}
    cm2 = {
        "schema": "semcrys.cm2.desirable.v0.2", "outer_codec": outer_codec,
        "legend_policy": legend_policy, "selection_claim": "USER_SELECTED_NOT_GLOBALLY_OPTIMAL",
    }
    instance = {
        "schema": "semcrys.instance-constitution.v0.2", "standing": "CANDIDATE_ONLY",
        "predecessor_head": PREDECESSOR_HEAD, "profile": profile,
        "source_sha256": source_sha256,
        "external_legend_roots": [row["sha256"] for row in legends],
        "outer_codec": outer_codec, "legend_policy": legend_policy,
        "tokenizer": "UNICODE_CATEGORY_LOSSLESS_V1", "max_unit_bytes": max_unit_bytes,
        "oversize_policy": "BOUNDED_LITERAL_CHUNKS_NOT_LEGEND_ELIGIBLE",
        "implicit_fallback": False, "security_claim": "NONE",
    }
    if glyph is not None:
        instance.update(glyph)
        instance['schema']='semcrys.instance-constitution.v0.3'
        cm1['glyph_registry_prerequisites_satisfied']=True
        cm2['projection']='GLYPH'; cm2['projection_objective']='EXPLICIT_SYMBOLIC_OUTPUT_NOT_BYTE_OPTIMALITY'
    if integer_projection is not None:
        instance.update(integer_projection)
        instance['schema']='semcrys.instance-constitution.v0.10'
        cm1['integer_projection_prerequisites_satisfied']=True
        cm2['projection']='INTEGER';cm2['projection_objective']='HUMAN_INSPECTION_AND_INTERCHANGE_NOT_BYTE_OPTIMALITY'
    if assembly_roots:
        instance.update(schema='semcrys.instance-constitution.v0.6',assembly_abi=ASSEMBLY_ABI,assembly_legend_roots=assembly_roots)
        if compact_assembly: instance.update(schema='semcrys.instance-constitution.v0.7',assembly_abi=FAMILY_ABI)
        cm1['assembly']='EXACT_BOUNDED_PROGRAM_EXPANSION; NO_GRAMMATICAL_INFERENCE'
        cm2['assembly']='EXPLICIT_LEGEND_CHOICE; BODY_IDS_PRESERVED; LEGEND_COST_MUST_BE_MEASURED'
    if fold_front is not None:
        from streaming_legend import fold
        if profile!='T:PRESHARED_TOKEN' or len(legends)!=1 or projection!='PACKED' or max_unit_bytes!=4096:
            raise Refusal('HELD_FOLD_CONFIGURATION_UNAVAILABLE')
        header,_,_,front_data,root=fold.load(fold_front)
        if header['base_legend_sha256']!=legends[0]['sha256'] or header['base_entries']!=legends[0]['entries']:
            raise Refusal('HELD_FOLD_BASE_BINDING')
        instance.update(schema='semcrys.instance-constitution.v0.5' if fold_placement=='EXTERNAL' else 'semcrys.instance-constitution.v0.4',tokenizer=fold.TOKENIZER,
            fold_projection=fold.binding(header,root,fold_placement),fold_fallback='FULL_PROJECTED_VIEW_CONSTITUENT_LOOKUP_V1')
        cm1['fold_prerequisite']='EXACT_SINGLE_BASE_AND_BOUNDED_DESCRIPTOR_BOUND; EXPANSION_VALIDATION_PENDING'
        cm2['fold_front_cap']=header['front_cap']; cm2['fold_selection']='EXPLICIT_NOT_SCALE_OR_HORIZON_OPTIMAL'
        if header['schema']==fold.COMPACT_SCHEMA:
            cm1['fold_provenance']='ROOT_REFERENCED_NOT_VERIFIED; NOT_REQUIRED_FOR_INVERSE'
            cm2['fold_accounting_scope']='EXECUTION_ONLY; SEPARATE_AUDIT_DOSSIER_EXCLUDED'
    if codec_configuration is not None:
        if projection_config is not None or fold_front is not None or assembly_roots:
            raise Refusal('HELD_EXTENDED_CODEC_COMPOSITION_NOT_QUALIFIED')
        instance.update(schema='semcrys.instance-constitution.v0.9',
            outer_codec_configuration=codec_configuration)
        cm2['outer_codec_configuration']=codec_configuration
        cm2['selection_claim']='EXPLICIT_CODEC_CONFIGURATION_NOT_GLOBALLY_OPTIMAL'
    result = {
        "schema": "semcrys.configuration-funnel.v0.2", "specification": specification,
        "cm1": cm1, "cm2": cm2, "instance_constitution": instance,
        "instance_constitution_sha256": _rooted(instance),
    }
    if accounting is not None:
        from .transfer import compile_transfer
        dependencies=[{'role':'BASE','sha256':r['sha256'],'bytes':r['path'].stat().st_size} for r in legends]
        if fold_placement=='EXTERNAL': dependencies.append({'role':'FOLD_PROJECTION','sha256':root,'bytes':len(front_data)})
        result['transfer_instance']=compile_transfer(accounting=accounting,receiver_roots=receiver_roots,
            dependencies=dependencies,realization_plan_root=result['instance_constitution_sha256'])
    return result


def _projection_configuration(projection,path,placement,profile):
    if projection not in ('PACKED','GLYPH','INTEGER'): raise Refusal('HELD_PROJECTION_UNAVAILABLE')
    if projection=='PACKED':
        if path is not None or placement!='EMBEDDED': raise Refusal('HELD_UNUSED_GLYPH_CONFIGURATION')
        return None
    if profile=='C:RAW_BYTES': raise Refusal('HELD_PROJECTION_REQUIRES_TOKEN_PROFILE')
    if projection=='INTEGER':
        if path is not None or placement!='EMBEDDED':raise Refusal('HELD_UNUSED_GLYPH_CONFIGURATION')
        from .integer_projection import CODEC
        return {'projection':'INTEGER','integer_codec':CODEC}
    if path is None: raise Refusal('HELD_GLYPH_REGISTRY_REQUIRED')
    if placement not in ('EMBEDDED','EXTERNAL'): raise Refusal('HELD_GLYPH_PLACEMENT')
    registry,_,root=load_glyph(path); radix,escape=alphabet_parameters(registry)
    return {'projection':'GLYPH','glyph_registry_sha256':root,'glyph_placement':placement,
        'glyph_codec':'TOKEN_ID_BASE_N_FIXED_WIDTH_V1','glyph_radix':radix,'glyph_literal_escape':escape}


def _open_count_db(path: Path) -> sqlite3.Connection:
    connection = sio.sqlite_connect(path)
    connection.execute("PRAGMA journal_mode=OFF")
    connection.execute("PRAGMA synchronous=OFF")
    connection.execute("PRAGMA temp_store=FILE")
    connection.execute("CREATE TABLE counts(value BLOB PRIMARY KEY, n INTEGER NOT NULL, eligible INTEGER NOT NULL) WITHOUT ROWID")
    return connection


def _count_units(source: Path, db_path: Path, *, max_unit_bytes: int) -> tuple[int, int]:
    connection = _open_count_db(db_path)
    batch: dict[tuple[bytes, int], int] = {}
    total = batch_bytes = 0
    try:
        for kind, value in iter_units(source, max_unit_bytes=max_unit_bytes):
            key = (value, 0 if kind == "lit" else 1)
            if key not in batch: batch_bytes += len(value)
            batch[key] = batch.get(key, 0) + 1
            total += 1
            if len(batch) >= 8192 or batch_bytes >= CHUNK:
                connection.executemany(
                    "INSERT INTO counts(value,n,eligible) VALUES (?,?,?) ON CONFLICT(value) DO UPDATE SET n=n+excluded.n,eligible=MIN(eligible,excluded.eligible)",
                    ((value, n, eligible) for (value, eligible), n in batch.items()),
                )
                connection.commit(); batch.clear(); batch_bytes = 0
        if batch:
            connection.executemany(
                "INSERT INTO counts(value,n,eligible) VALUES (?,?,?) ON CONFLICT(value) DO UPDATE SET n=n+excluded.n,eligible=MIN(eligible,excluded.eligible)",
                ((value, n, eligible) for (value, eligible), n in batch.items()),
            )
            connection.commit()
        return total, connection.execute("SELECT COUNT(*) FROM counts").fetchone()[0]
    finally:
        connection.close()


def _build_stack_db(paths: Sequence[Path], db_path: Path, context=None) -> tuple[sqlite3.Connection, int]:
    if context is not None: return context.stack(paths)
    connection = sio.sqlite_connect(db_path)
    connection.execute("PRAGMA journal_mode=OFF"); connection.execute("PRAGMA synchronous=OFF")
    connection.execute("PRAGMA temp_store=FILE")
    connection.execute("CREATE TABLE lookup(value BLOB PRIMARY KEY, id INTEGER NOT NULL) WITHOUT ROWID")
    offset = 0
    try:
        for path in paths:
            reader = LegendReader(path)
            try:
                connection.executemany("INSERT INTO lookup(value,id) VALUES (?,?)", ((v, offset + i) for i, v in reader.iter_values()))
            except sqlite3.IntegrityError as exc:
                raise Refusal("HELD_DUPLICATE_VALUE_ACROSS_LEGEND_STACK", path.name) from exc
            offset += reader.count; connection.commit()
        return connection, offset
    except Exception:
        connection.close(); raise


def _select_local_legend(count_db: Path, output: Path, *, policy: str, base_lookup: sqlite3.Connection | None, parent_root: str | None) -> dict:
    # Counts are immutable after manufacture. Store the final rank in a new,
    # budgeted primary B-tree; never reopen owned counts for unreserved growth
    # or delegate sorting to an unaccounted SQLite temporary file.
    connection = sio.sqlite_connect(Path(count_db).resolve().as_uri()+'?mode=ro',uri=True)
    selected_path=Path(output).with_suffix('.selection.sqlite3');selected=None
    try:
        selected=sio.sqlite_connect(selected_path)
        selected.execute("CREATE TABLE ranked(rank INTEGER NOT NULL,value BLOB NOT NULL,PRIMARY KEY(rank,value)) WITHOUT ROWID")
        predicate = "eligible=1" if policy == "TOTAL" else "eligible=1 AND n>=2 AND n*(length(value)-1)>=2"
        for value, count in connection.execute(f"SELECT value,n FROM counts WHERE {predicate}"):
            if base_lookup is not None and base_lookup.execute("SELECT 1 FROM lookup WHERE value=?", (value,)).fetchone():
                continue
            selected.execute("INSERT INTO ranked(rank,value) VALUES (?,?)", (-count,value))
        selected.commit()
        count=selected.execute("SELECT COUNT(*) FROM ranked").fetchone()[0]
        def values() -> Iterator[bytes]:
            for (value,) in selected.execute("SELECT value FROM ranked ORDER BY rank ASC,value ASC"):
                yield value
        return write_legend(output, values(), entry_count=count, legend_id="STREAMING-LOCAL", unit_mode="TOKEN", parent_sha256=parent_root)
    finally:
        if selected is not None:selected.close()
        connection.close()
        sio.unlink(selected_path,missing_ok=True)


def _venc(number: int) -> bytes:
    if type(number) is not int or not 0 <= number <= (1 << 64) - 1:
        raise Refusal("HELD_VARINT_U64_RANGE")
    output = bytearray()
    while True:
        byte = number & 0x7F; number >>= 7
        output.append(byte | (0x80 if number else 0))
        if not number:
            return bytes(output)


def _vdec(handle: BinaryIO) -> int | None:
    raw = handle.read(1)
    if not raw:
        return None
    number = shift = 0
    while True:
        byte = raw[0]
        if shift == 63 and byte > 1: raise Refusal("HELD_VARINT_U64_RANGE")
        number |= (byte & 0x7F) << shift
        if not byte & 0x80:
            if shift and byte == 0: raise Refusal("HELD_NONCANONICAL_VARINT")
            return number
        shift += 7
        if shift > 63:
            raise Refusal("HELD_MALFORMED_BODY_VARINT")
        raw = handle.read(1)
        if not raw:
            raise Refusal("HELD_TRUNCATED_BODY_VARINT")


def _pack_varint_batch_python(values: list[int]) -> bytes:
    return b"".join(_venc(value) for value in values)


def _pack_varint_batch(values: list[int]) -> bytes:
    """Pack a symbol run without changing the frozen packed-token byte stream."""
    if len(values) < FULL_NATIVE_PACK_MIN_RUN:
        return _pack_varint_batch_python(values)
    return _native_pack_varints(values, _pack_varint_batch_python)


class _Lookup:
    def __init__(self, connection: sqlite3.Connection, limit: int = 4096) -> None:
        self.connection, self.limit = connection, limit
        self.cache: OrderedDict[bytes, int | None] = OrderedDict()
        self.cache_bytes = 0

    def get(self, value: bytes) -> int | None:
        if value in self.cache:
            result = self.cache.pop(value); self.cache[value] = result; return result
        row = self.connection.execute("SELECT id FROM lookup WHERE value=?", (value,)).fetchone()
        result = row[0] if row else None
        self.cache[value] = result
        self.cache_bytes += len(value)
        while len(self.cache) > self.limit or self.cache_bytes > CHUNK:
            key, _ = self.cache.popitem(last=False); self.cache_bytes -= len(key)
        return result


def _encode_token_body(source: Path, output: Path, lookup: sqlite3.Connection, *, max_unit_bytes: int) -> dict:
    digest = hashlib.sha256(); units = symbols = literals = 0; cache = _Lookup(lookup)
    with sio.open_output(output,"wb") as handle:
        handle.write(PACKED_MAGIC); digest.update(PACKED_MAGIC)
        pending_symbols: list[int] = []

        def flush_symbols() -> None:
            if not pending_symbols:
                return
            frame = _pack_varint_batch(pending_symbols)
            handle.write(frame); digest.update(frame); pending_symbols.clear()

        for kind, value in iter_units(source, max_unit_bytes=max_unit_bytes):
            identifier = None if kind == "lit" else cache.get(value)
            units += 1
            if identifier is None:
                flush_symbols()
                frame = _venc(0) + _venc(len(value)) + value
                handle.write(frame); digest.update(frame); literals += 1
            else:
                pending_symbols.append(identifier); symbols += 1
                if len(pending_symbols) >= 8192:
                    flush_symbols()
        flush_symbols()
    return {"sha256": digest.hexdigest(), "bytes": output.stat().st_size, "units": units, "symbols": symbols, "literals": literals}


def _encode_raw_body(source: Path, output: Path) -> dict:
    digest = hashlib.sha256()
    with sio.open_output(output,"wb") as target, source.open("rb") as handle:
        target.write(RAW_MAGIC); digest.update(RAW_MAGIC)
        while chunk := handle.read(CHUNK):
            target.write(chunk); digest.update(chunk)
    return {"sha256": digest.hexdigest(), "bytes": output.stat().st_size, "units": 0, "symbols": 0, "literals": 0}


def _lzma_compress(source: Path, target: Path, *, preset: int = 6) -> None:
    compressor = lzma.LZMACompressor(format=lzma.FORMAT_XZ, preset=preset)
    with source.open("rb") as incoming, sio.open_output(target,"wb") as outgoing:
        while chunk := incoming.read(CHUNK): outgoing.write(compressor.compress(chunk))
        outgoing.write(compressor.flush())


def _lzma_decompress(source: Path, target: Path, *, max_decoded_bytes: int) -> None:
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=256 * 1024 * 1024)
    total = 0
    with source.open("rb") as incoming, sio.open_output(target,"wb") as outgoing:
        while chunk := incoming.read(CHUNK):
            if decoder.eof: raise Refusal("HELD_TRAILING_LZMA_BODY")
            try: value = decoder.decompress(chunk, max_length=CHUNK)
            except lzma.LZMAError as exc: raise Refusal("HELD_INVALID_LZMA_BODY") from exc
            while value:
                total += len(value)
                if total > max_decoded_bytes: raise Refusal("HELD_DECODED_SIZE_LIMIT")
                outgoing.write(value)
                if decoder.eof or decoder.needs_input:
                    break
                value = decoder.decompress(b"", max_length=CHUNK)
            if decoder.unused_data: raise Refusal("HELD_TRAILING_LZMA_BODY")
        if not decoder.eof: raise Refusal("HELD_TRUNCATED_LZMA_BODY")


def _bz2_compress(source: Path, target: Path, *, level: int) -> None:
    compressor = bz2.BZ2Compressor(level)
    with source.open("rb") as incoming, sio.open_output(target,"wb") as outgoing:
        while chunk := incoming.read(CHUNK): outgoing.write(compressor.compress(chunk))
        outgoing.write(compressor.flush())


def _bz2_decompress(source: Path, target: Path, *, max_decoded_bytes: int) -> None:
    decoder = bz2.BZ2Decompressor(); total = 0
    with source.open("rb") as incoming, sio.open_output(target,"wb") as outgoing:
        while chunk := incoming.read(CHUNK):
            if decoder.eof: raise Refusal("HELD_TRAILING_BZ2_BODY")
            try: value = decoder.decompress(chunk, max_length=CHUNK)
            except OSError as exc: raise Refusal("HELD_INVALID_BZ2_BODY") from exc
            while value:
                total += len(value)
                if total > max_decoded_bytes: raise Refusal("HELD_DECODED_SIZE_LIMIT")
                outgoing.write(value)
                if decoder.eof or decoder.needs_input: break
                value = decoder.decompress(b"", max_length=CHUNK)
            if decoder.unused_data: raise Refusal("HELD_TRAILING_BZ2_BODY")
        if not decoder.eof: raise Refusal("HELD_TRUNCATED_BZ2_BODY")


def _compress_outer(source: Path, target: Path, codec: str) -> None:
    if codec == "LZMA":
        _lzma_compress(source, target); return
    config = outer_codec_configuration(codec)
    if config is None: raise Refusal("HELD_OUTER_CODEC_UNAVAILABLE", codec)
    if config["codec"] == "LZMA2":
        _lzma_compress(source, target, preset=config["level"]); return
    if config["codec"] == "BZIP2":
        _bz2_compress(source, target, level=config["level"]); return
    raise Refusal("HELD_OUTER_CODEC_UNAVAILABLE", codec)


def _decompress_outer(source: Path, target: Path, codec: str, *, max_decoded_bytes: int) -> None:
    if codec == "LZMA" or codec.startswith("LZMA2_XZ_"):
        _lzma_decompress(source, target, max_decoded_bytes=max_decoded_bytes); return
    if codec.startswith("BZ2_"):
        _bz2_decompress(source, target, max_decoded_bytes=max_decoded_bytes); return
    raise Refusal("HELD_OUTER_CODEC_UNAVAILABLE", codec)


def _encode_snapshot(
    source: str | os.PathLike[str], output: str | os.PathLike[str], *, profile: str,
    external_legends: Sequence[str | os.PathLike[str]] = (), outer_codec: str = "NONE",
    legend_policy: str | None = None, security_request: str = "NONE", max_unit_bytes: int = MAX_UNIT_BYTES,
    projection='PACKED', glyph_registry=None, glyph_placement='EMBEDDED',
    fold_front=None, fold_placement='EMBEDDED', accounting=None, receiver_roots=(),
    legend_context=None,
) -> dict:
    total_started=time.perf_counter_ns();phase_wall_ns={}
    def measured(name,function):
        started=time.perf_counter_ns();value=function();phase_wall_ns[name]=time.perf_counter_ns()-started;return value
    source_path, target = Path(source), Path(output); source_root = file_sha256(source_path)
    if target.suffix.lower() != ".crys": raise Refusal("HELD_CRYS_SUFFIX_REQUIRED")
    if source_path.resolve() == target.resolve(): raise Refusal("HELD_SOURCE_OUTPUT_ALIAS")
    funnel = measured('COMPILE_FUNNEL',lambda:compile_funnel(source_sha256=source_root, profile=profile, external_legends=external_legends,
        outer_codec=outer_codec, legend_policy=legend_policy, security_request=security_request, max_unit_bytes=max_unit_bytes,
        projection=projection,glyph_registry=glyph_registry,glyph_placement=glyph_placement,fold_front=fold_front,
        fold_placement=fold_placement,accounting=accounting,receiver_roots=receiver_roots,legend_context=legend_context))
    legend_policy = funnel["instance_constitution"]["legend_policy"]
    external = measured('LOAD_LEGENDS',lambda:_load_legends(external_legends, legend_context)); target.parent.mkdir(parents=True, exist_ok=True)
    with sio.TempDirectory(prefix="ss-", dir=target.parent) as name:
        work = Path(name); stack_paths = [row["path"] for row in external]; count_stats = None; local = None
        if profile in {"C:SELF_CONTAINED_TOKEN", "A:LONGITUDINAL_TOKEN_DELTA"}:
            count_db = work / "counts.sqlite3"; count_stats = measured('COUNT_UNITS',lambda:_count_units(source_path, count_db, max_unit_bytes=max_unit_bytes))
            base_connection = None
            if stack_paths: base_connection, _ = _build_stack_db(stack_paths, work / "base.sqlite3", legend_context)
            try:
                local = measured('SELECT_LOCAL_LEGEND',lambda:_select_local_legend(count_db, work / "local.leg",
                    policy=legend_policy,
                    base_lookup=base_connection, parent_root=external[-1]["sha256"] if external else None))
            finally:
                if base_connection is not None: base_connection.close()
            stack_paths.append(work / "local.leg")
        front_view=None
        if fold_front is not None:
            from .fold_projection import FoldView
            front_view=FoldView(fold_front,stack_paths[0],legend_context)
            physical=work/'body.bin'; body_stats=front_view.encode(source_path,physical)
        elif profile == "C:RAW_BYTES":
            physical = work / "body.bin"; body_stats = measured('ENCODE_RAW_BODY',lambda:_encode_raw_body(source_path, physical))
        else:
            stack_connection, stack_entries = _build_stack_db(stack_paths, work / "stack.sqlite3", legend_context)
            try:
                physical = work / "body.bin"; body_stats = measured('ENCODE_TOKEN_BODY',lambda:_encode_token_body(source_path, physical, stack_connection, max_unit_bytes=max_unit_bytes))
            finally: stack_connection.close()
        glyph_stats=None; glyph_binding=None;integer_stats=None
        if projection=='GLYPH':
            from .glyph_projection import encode as emit_glyphs
            registry,_,glyph_root=load_glyph(glyph_registry)
            projected=work/'glyph.body'
            glyph_stats=emit_glyphs(physical,projected,registry,entries=stack_entries,max_unit_bytes=max_unit_bytes)
            physical=projected
            glyph_binding=(glyph_placement,glyph_registry if glyph_placement=='EMBEDDED' else glyph_root)
        elif projection=='INTEGER':
            from .integer_projection import encode as emit_integers
            projected=work/'integer.body'
            integer_stats=emit_integers(physical,projected,entries=stack_entries,max_unit_bytes=max_unit_bytes)
            physical=projected
        body = physical
        if outer_codec != "NONE":
            body = work / ("body.xz" if outer_codec == "LZMA" or outer_codec.startswith("LZMA2_XZ_") else "body.bz2")
            measured('COMPRESS_OUTER',lambda:_compress_outer(physical, body, outer_codec))
        bindings: list[tuple[str, str, str | os.PathLike[str]]] = []
        for index, row in enumerate(external): bindings.append(("BASE" if index == 0 else "DELTA", "EXTERNAL", row["sha256"]))
        if local is not None: bindings.append(("BASE" if not external else "DELTA", "EMBEDDED", work / "local.leg"))
        instance = dict(funnel["instance_constitution"])
        instance["legend_stack"] = [{"role": role, "mode": mode, "sha256": file_sha256(Path(value)) if mode == "EMBEDDED" else str(value)} for role, mode, value in bindings]
        instance["physical_body_schema"] = "semcrys.packed-token.v0.2" if profile != "C:RAW_BYTES" else "semcrys.raw-body.v0.2"
        if glyph_stats is not None:
            instance['physical_body_schema']='semcrys.glyph-token.v0.1'
            instance['glyph_width']=glyph_stats['width']; instance['glyph_legend_entries']=stack_entries
        if integer_stats is not None:
            instance['physical_body_schema']='semcrys.integer-token.v0.1';instance['integer_legend_entries']=stack_entries
        if front_view is not None: instance['physical_body_schema']='semcrys.folded-front-packed.v0.1'
        instance["instance_constitution_sha256"] = _rooted(instance)
        receipt = {"schema": "semcrys.streaming-realization-receipt.v0.1", "standing": "CANDIDATE_ONLY",
            "source_sha256": source_root, "source_bytes": source_path.stat().st_size,
            "body_stats": body_stats, "count_stats": count_stats, "outer_codec": outer_codec, "security_claim": "NONE"}
        codec_configuration=outer_codec_configuration(outer_codec)
        if codec_configuration is not None:
            receipt['outer_codec_configuration']=codec_configuration
            receipt['outer_codec_accounting']={
                'physical_body_bytes':physical.stat().st_size,
                'outer_body_bytes':body.stat().st_size,
                'encoder_runtime':{'python':sys.version.split()[0]},
                'dictionary_bytes':0,
            }
        if glyph_stats is not None:
            receipt['body_stats_stage']='PACKED_ID_STREAM_BEFORE_GLYPH_PROJECTION'
            receipt['glyph_projection_stats']={**glyph_stats,'sha256':file_sha256(physical),'stage':'GLYPH_STREAM_BEFORE_OUTER_CODEC'}
        if integer_stats is not None:
            receipt['body_stats_stage']='PACKED_ID_STREAM_BEFORE_INTEGER_PROJECTION'
            receipt['integer_projection_stats']={**integer_stats,'sha256':file_sha256(physical),
                'stage':'INTEGER_STREAM_BEFORE_OUTER_CODEC'}
        front_accounting=None
        if front_view is not None:
            front_accounting={'base_legend_bytes':external[0]['path'].stat().st_size,
                'projection_artifact_bytes':len(front_view.data),'projection_signal_bytes':len(front_view.signal),
                'physical_body_bytes':body_stats['bytes'],'outer_body_bytes':body.stat().st_size,
                'projection_placement':'EXTERNAL_DEPENDENCY' if fold_placement=='EXTERNAL' else 'EMBEDDED_EACH_CONTAINER_NOT_PRESHARED',
                'outer_codec':outer_codec,'xz_preset':6 if outer_codec=='LZMA' else None}
            receipt['fold_accounting']=front_accounting
        pending = work / "candidate.crys"
        measured('WRITE_CONTAINER',lambda:write_crys(pending, configuration=instance, body=body, legend_stack=bindings, decoded_sha256=source_root, receipts=[receipt],glyph_binding=glyph_binding,
            fold_projection=front_view.data if front_view is not None and fold_placement=='EMBEDDED' else None,
            fold_reference=instance['fold_projection'] if front_view is not None and fold_placement=='EXTERNAL' else None))
        check = work / "decoded.check"; postwrite_started=time.perf_counter_ns(); decode_file(pending, check, external_legends=external_legends,
            glyph_registry=glyph_registry if projection=='GLYPH' and glyph_placement=='EXTERNAL' else None,
            fold_front=fold_front if fold_placement=='EXTERNAL' else None,legend_context=legend_context)
        phase_wall_ns['POSTWRITE_RECONSTRUCTION']=time.perf_counter_ns()-postwrite_started
        if file_sha256(check) != source_root: raise Refusal("HELD_POSTWRITE_RECONSTRUCTION_MISMATCH")
        if legend_context is not None: legend_context.verify_used()
        sio.replace(pending, target)
    phase_wall_ns['TOTAL']=time.perf_counter_ns()-total_started
    result = {"schema": "semcrys.streaming-encode-result.v0.1", "status": "PASS", "standing": "CANDIDATE_ONLY",
        "output_sha256": file_sha256(target), "source_sha256": source_root,
        "effective_configuration": instance, "receipt": receipt,
        "postwrite_reconstruction":{"status":"PASS","output_sha256":source_root,
            "proof":"DECODED_CANDIDATE_BYTES_HASH_MATCH_SOURCE"},
        "execution_metrics":{"schema":"semcrys.execution-metrics.v0.1","phase_wall_ns":phase_wall_ns,
            "scope":"NONCANONICAL_RUNTIME_OBSERVATION_NOT_CONTAINER_IDENTITY"},
        **({'accounting':{**front_accounting,'container_bytes':target.stat().st_size,
            **({'warm_wire_bytes':target.stat().st_size} if fold_placement=='EMBEDDED' else {}),
            'cold_acquisition_plus_wire_bytes':target.stat().st_size+front_accounting['base_legend_bytes']+
                (front_accounting['projection_artifact_bytes'] if fold_placement=='EXTERNAL' else 0)}}
            if front_accounting is not None else {})}
    if 'transfer_instance' in funnel:
        from .transfer import receipt as transfer_receipt
        result['transfer']=transfer_receipt(funnel['transfer_instance'],[{'sha256':result['output_sha256'],'bytes':target.stat().st_size}])
    return result


def _capture_controls(source: Path, directory: Path, *, limits=None):
    body_path = directory / "captured.body"
    with sio.open_output(body_path,"wb") as sink:
        inspected = inspect_crys(source, body_sink=sink, capture_directory=directory, limits=limits)
    return inspected, body_path, [Path(path) for path in inspected["embedded_paths"]]


class _IdResolver:
    def __init__(self, paths: Sequence[Path], cache_limit: int = 32768, cache_bytes_limit: int = 8*CHUNK, context=None) -> None:
        self.readers = []; total = 0
        for path in paths:
            reader = context.reader(path) if context is not None else LegendReader(path)
            total += reader.count; self.readers.append((total, reader))
        self.total = total; self.cache: OrderedDict[int, bytes] = OrderedDict(); self.cache_limit = cache_limit
        self.cache_bytes_limit=cache_bytes_limit
        self.cache_bytes = 0

    def get(self, identifier: int) -> bytes:
        if identifier in self.cache:
            value = self.cache.pop(identifier); self.cache[identifier] = value; return value
        lower = 0
        for upper, reader in self.readers:
            if identifier <= upper:
                value = reader.get(identifier - lower); self.cache[identifier] = value
                if not value: raise Refusal("HELD_EMPTY_LEGEND_VALUE")
                self.cache_bytes += len(value)
                while len(self.cache) > self.cache_limit or self.cache_bytes > self.cache_bytes_limit:
                    _, evicted = self.cache.popitem(last=False); self.cache_bytes -= len(evicted)
                return value
            lower = upper
        raise Refusal("HELD_BODY_ID_RANGE", str(identifier))

    def get_many(self,identifiers) -> list[bytes]:
        results=[None]*len(identifiers);missing={}
        for position,identifier in enumerate(identifiers):
            if type(identifier) is not int or not 1<=identifier<=self.total:
                raise Refusal("HELD_BODY_ID_RANGE",str(identifier))
            if identifier in self.cache:
                value=self.cache.pop(identifier);self.cache[identifier]=value;results[position]=value
            else: missing.setdefault(identifier,[]).append(position)
        lower=0
        for upper,reader in self.readers:
            local=[identifier for identifier in missing if lower<identifier<=upper]
            if local:
                local_ids=[identifier-lower for identifier in local]
                values=reader.get_many(local_ids) if hasattr(reader,'get_many') else [reader.get(identifier) for identifier in local_ids]
                for identifier,value in zip(local,values):
                    if not value: raise Refusal("HELD_EMPTY_LEGEND_VALUE")
                    self.cache[identifier]=value;self.cache_bytes+=len(value)
                    for position in missing.pop(identifier):results[position]=value
            lower=upper
        if missing: raise Refusal("HELD_BODY_ID_RANGE",str(next(iter(missing))))
        while len(self.cache)>self.cache_limit or self.cache_bytes>self.cache_bytes_limit:
            _,evicted=self.cache.popitem(last=False);self.cache_bytes-=len(evicted)
        return results


def _parse_packed_events_python(data: bytes):
    values=array('Q');lengths=array('Q');handle=io.BytesIO(data)
    while True:
        identifier=_vdec(handle)
        if identifier is None:break
        if identifier:
            values.append(identifier);lengths.append(0);continue
        length=_vdec(handle)
        if length is None or length<1:raise Refusal("HELD_LITERAL_LENGTH")
        offset=handle.tell()
        if offset+length>len(data):raise Refusal("HELD_TRUNCATED_LITERAL")
        values.append(offset);lengths.append(length);handle.seek(length,1)
    return values,lengths


def _decode_physical(body: Path, output: Path, config: Mapping[str, object], legends: Sequence[Path], *, max_decoded_bytes: int, legend_context=None,fold_view=None) -> None:
    from streaming_legend import block_output
    with body.open("rb") as handle, block_output.open_output(output,"wb") as target:
        total = 0
        def emit(value: bytes) -> None:
            nonlocal total
            total += len(value)
            if total > max_decoded_bytes: raise Refusal("HELD_DECODED_SIZE_LIMIT")
            target.write(value)
        magic = handle.read(4)
        if magic == RAW_MAGIC:
            if config["profile"] != "C:RAW_BYTES": raise Refusal("HELD_BODY_PROFILE_MISMATCH")
            while chunk := handle.read(CHUNK): emit(chunk)
            return
        from .fold_projection import BODY_MAGIC as FOLD_MAGIC
        if magic != (FOLD_MAGIC if fold_view is not None else PACKED_MAGIC): raise Refusal("HELD_BODY_MAGIC")
        if config["profile"] == "C:RAW_BYTES": raise Refusal("HELD_BODY_PROFILE_MISMATCH")
        resolver = fold_view if fold_view is not None else _IdResolver(legends, context=legend_context)
        if fold_view is None and body.stat().st_size-4<=NATIVE_PARSE_MAX_BYTES:
            data=handle.read();values,lengths=_native_parse_packed_events(data,_parse_packed_events_python);index=0
            while index<len(values):
                length=lengths[index]
                if length:
                    if length>int(config.get("max_unit_bytes",MAX_UNIT_BYTES)):raise Refusal("HELD_LITERAL_LENGTH")
                    offset=values[index];value=data[offset:offset+length]
                    if len(value)!=length:raise Refusal("HELD_TRUNCATED_LITERAL")
                    emit(value);index+=1;continue
                end=index
                while end<len(values) and lengths[end]==0 and end-index<DECODE_RESOLUTION_BATCH:end+=1
                emit(b''.join(resolver.get_many(values[index:end])));index=end
            return
        while True:
            identifier = _vdec(handle)
            if identifier is None: break
            if identifier: emit(resolver.get(identifier))
            else:
                length = _vdec(handle)
                if length is None or length < 1 or length > int(config.get("max_unit_bytes", MAX_UNIT_BYTES)): raise Refusal("HELD_LITERAL_LENGTH")
                value = handle.read(length)
                if len(value) != length: raise Refusal("HELD_TRUNCATED_LITERAL")
                emit(value)


@governed_context
def decode_file(
    source: str | os.PathLike[str], output: str | os.PathLike[str], *,
    external_legends: Sequence[str | os.PathLike[str]] = (), max_decoded_bytes: int = 1 << 40,
    max_container_bytes: int = 1 << 40,
    glyph_registry=None, fold_front=None,
    legend_context=None,
) -> dict:
    source_path, target = Path(source), Path(output)
    protect_outputs([target], [source_path, *external_legends,*([glyph_registry] if glyph_registry is not None else [])])
    protect_outputs([target],legend_context.protected_paths())
    if fold_front is not None: protect_outputs([target],[fold_front])
    if type(max_decoded_bytes) is not int or max_decoded_bytes < 0: raise Refusal("HELD_INVALID_DECODE_LIMIT")
    if type(max_container_bytes) is not int or not 0 <= max_container_bytes <= (1 << 64)-1: raise Refusal("HELD_INVALID_CONTAINER_LIMIT")
    if source_path.stat().st_size > max_container_bytes: raise Refusal("HELD_CONTAINER_SIZE_LIMIT")
    target.parent.mkdir(parents=True, exist_ok=True)
    with sio.TempDirectory(prefix="sd-", dir=target.parent) as name:
        work = Path(name)
        provided_glyph=None; provided_glyph_root=None
        if glyph_registry is not None: provided_glyph,_,provided_glyph_root=load_glyph(glyph_registry)
        snapshots = _snapshot_legends(external_legends, work, legend_context)
        provided_by_root = {file_sha256(path): path for path in snapshots}
        inspected, captured_body, embedded = _capture_controls(source_path, work,
            limits=Limits(max_section_bytes=max_container_bytes, max_total_payload_bytes=max_container_bytes))
        config = inspected["configuration"]
        _validate_configuration(config, inspected["header"])
        if config.get('schema') in ('semcrys.instance-constitution.v0.8','semcrys.instance-constitution.v0.11'):
            # New critical IC: one self-contained composed legend, never a
            # silent interpretation of existing token, glyph or folded bodies.
            if external_legends or glyph_registry is not None or fold_front is not None:
                raise Refusal('HELD_COMPOSED_UNUSED_DEPENDENCIES')
            if len(embedded)!=1: raise Refusal('HELD_COMPOSED_STACK')
            from semcrys.second_pass import decode_physical
            physical=captured_body
            if config['outer_codec']!='NONE':
                physical=work/'physical.body'
                _decompress_outer(captured_body,physical,config['outer_codec'],
                    max_decoded_bytes=10*max_decoded_bytes+24)
            pending=work/'decoded.pending'
            decode_physical(physical,pending,config,embedded[0],max_decoded_bytes=max_decoded_bytes)
            observed=file_sha256(pending)
            if observed!=config['source_sha256']: raise Refusal('HELD_DECODED_ROOT_MISMATCH')
            legend_context.verify_used()
            sio.replace(pending,target)
            return {'schema':'semcrys.streaming-decode-result.v0.1','status':'PASS',
                'output_sha256':observed,'container_sha256':inspected['file_sha256'],
                'original_packed_event_stream_verified':True,'external_decoder_dependencies':[]}
        fold_path=inspected['fold_projection_path']
        binding=config.get('fold_projection')
        if binding is None or binding['mode']=='EMBEDDED':
            if fold_front is not None: raise Refusal('HELD_UNUSED_FOLD_CONFIGURATION')
        else:
            if fold_front is None: raise Refusal('HELD_EXTERNAL_FOLD_MISSING')
            from streaming_legend import fold
            fh,_,_,fd,fr=fold.load(fold_front)
            if fr!=binding['sha256']: raise Refusal('HELD_EXTERNAL_FOLD_ROOT')
            if fold.binding(fh,fr,'EXTERNAL')!=binding: raise Refusal('HELD_CONFIGURATION_FOLD_BINDING')
            fold_path=work/'front.leg'; sio.write_bytes(fold_path,fd)
        glyph_binding=inspected['header']['glyph_binding']
        glyph_value=None
        if glyph_binding is None:
            if provided_glyph is not None: raise Refusal('HELD_UNUSED_GLYPH_CONFIGURATION')
        elif glyph_binding['mode']=='EMBEDDED':
            if provided_glyph is not None: raise Refusal('HELD_UNUSED_GLYPH_CONFIGURATION')
            glyph_value=inspected['glyph_registry']
        else:
            if provided_glyph is None: raise Refusal('HELD_EXTERNAL_GLYPH_MISSING')
            if provided_glyph_root!=glyph_binding['sha256']: raise Refusal('HELD_EXTERNAL_GLYPH_ROOT')
            glyph_value=provided_glyph
        embedded_iter = iter(embedded); stack = []
        for binding in inspected["header"]["legend_bindings"]:
            if binding["mode"] == "EXTERNAL":
                if binding["sha256"] not in provided_by_root: raise Refusal("HELD_EXTERNAL_LEGEND_MISSING", binding["sha256"])
                stack.append(provided_by_root[binding["sha256"]])
            else:
                path = next(embedded_iter, None)
                if path is None or file_sha256(path) != binding["sha256"]: raise Refusal("HELD_EMBEDDED_LEGEND_ORDER")
                stack.append(path)
        _validate_lineage(stack)
        from streaming_legend.assembly import PAIR_MODE
        if any(LegendReader(p).header['unit_mode']=='META_RECORDS_V1' for p in stack):
            raise Refusal('HELD_META_REQUIRES_UNPACK')
        if any(LegendReader(p).header['unit_mode']==PAIR_MODE for p in stack):
            raise Refusal('HELD_COMPOSED_REQUIRES_SECOND_PASS_WORKFLOW')
        actual_assemblies=[file_sha256(p) for p in stack if LegendReader(p).header['unit_mode'] in ASSEMBLY_MODES]
        if actual_assemblies!=config.get('assembly_legend_roots',[]): raise Refusal('HELD_ASSEMBLY_CONFIGURATION_BINDING')
        expected_abi=FAMILY_ABI if any(LegendReader(p).header['unit_mode']==COMPACT_MODE for p in stack) else ASSEMBLY_ABI
        if actual_assemblies and config['assembly_abi']!=expected_abi: raise Refusal('HELD_ASSEMBLY_ABI_BINDING')
        connection, stack_entries = _build_stack_db(stack, work / "decode-stack.sqlite3", legend_context)
        connection.close()
        fold_view=None
        if config.get('fold_projection') is not None:
            from .fold_projection import FoldView
            fold_view=FoldView(fold_path,stack[0],legend_context)
        if glyph_value is not None:
            radix,escape=alphabet_parameters(glyph_value)
            if radix!=config['glyph_radix'] or escape!=config['glyph_literal_escape'] or stack_entries!=config['glyph_legend_entries'] or code_width(stack_entries,radix)!=config['glyph_width']:
                raise Refusal('HELD_GLYPH_PARAMETERS')
        integer_projection=config.get('projection')=='INTEGER'
        if integer_projection and stack_entries!=config['integer_legend_entries']:
            raise Refusal('HELD_INTEGER_PARAMETERS')
        physical = captured_body
        if config.get("outer_codec") != "NONE":
            # Packed framing can exceed the final decoded-byte budget. A 64-bit
            # varint uses at most ten bytes per nonempty decoded unit.
            # The outer body is bounded according to its physical projection,
            # not the smaller reconstructed SPV2 stream.  An INTEGER event may
            # use 22 bytes (``I:`` + u64 decimal + LF); one source byte can form
            # one event.  Literals are smaller than that bound.
            limit=(256*max_decoded_bytes+5 if glyph_value is not None else
                24*max_decoded_bytes+5 if integer_projection else
                10*max_decoded_bytes+4)
            physical = work / "physical.body"; _decompress_outer(captured_body, physical, config["outer_codec"], max_decoded_bytes=limit)
        if glyph_value is not None:
            from .glyph_projection import decode as unproject_glyphs
            packed=work/'glyph-unprojected.body'
            unproject_glyphs(physical,packed,glyph_value,entries=stack_entries,width=config['glyph_width'],
                escape=config['glyph_literal_escape'],max_unit_bytes=config['max_unit_bytes'],max_packed_bytes=10*max_decoded_bytes+4)
            physical=packed
        elif integer_projection:
            from .integer_projection import decode as unproject_integers
            packed=work/'integer-unprojected.body'
            unproject_integers(physical,packed,entries=stack_entries,max_unit_bytes=config['max_unit_bytes'],
                max_packed_bytes=10*max_decoded_bytes+4)
            physical=packed
        pending = work / "decoded.pending"; _decode_physical(physical, pending, config, stack, max_decoded_bytes=max_decoded_bytes,legend_context=legend_context,fold_view=fold_view)
        if pending.stat().st_size > max_decoded_bytes: raise Refusal("HELD_DECODED_SIZE_LIMIT")
        expected = inspected["header"].get("decoded_sha256"); observed = file_sha256(pending)
        if expected and observed != expected: raise Refusal("HELD_DECODED_ROOT_MISMATCH")
        if legend_context is not None: legend_context.verify_used()
        sio.replace(pending, target)
    return {"schema": "semcrys.streaming-decode-result.v0.1", "status": "PASS",
        "output_sha256": observed, "container_sha256": inspected["file_sha256"]}


def _validate_configuration(config: dict, header: dict) -> None:
    if type(config) is dict and config.get('schema') in ('semcrys.metalegend-instance.v0.1','semcrys.metalegend-bundle-instance.v0.1',
                                                      'semcrys.metalegend-instance.v0.2','semcrys.metalegend-bundle-instance.v0.2'):
        raise Refusal('HELD_META_REQUIRES_UNPACK')
    if type(config) is dict and config.get('schema') in ('semcrys.instance-constitution.v0.8','semcrys.instance-constitution.v0.11'):
        from semcrys.second_pass import validate_configuration
        validate_configuration(config,header); return
    required = {"schema", "standing", "predecessor_head", "profile", "source_sha256", "external_legend_roots",
        "outer_codec", "legend_policy", "tokenizer", "max_unit_bytes", "oversize_policy", "implicit_fallback", "security_claim",
        "legend_stack", "physical_body_schema", "instance_constitution_sha256"}
    extended_codec=type(config) is dict and config.get('schema')=='semcrys.instance-constitution.v0.9'
    if extended_codec: required |= {'outer_codec_configuration'}
    glyph=type(config) is dict and config.get('projection')=='GLYPH'
    integer_projection=type(config) is dict and config.get('projection')=='INTEGER'
    folded=type(config) is dict and 'fold_projection' in config
    assembled=type(config) is dict and 'assembly_legend_roots' in config
    if assembled: required |= {'assembly_legend_roots','assembly_abi'}
    if folded: required |= {'fold_projection','fold_fallback'}
    if glyph:
        required |= {'projection','glyph_registry_sha256','glyph_placement','glyph_codec','glyph_radix','glyph_literal_escape','glyph_width','glyph_legend_entries'}
    if integer_projection:required |= {'projection','integer_codec','integer_legend_entries'}
    if type(config) is not dict or set(config) != required: raise Refusal("HELD_CONFIGURATION_FIELDS")
    from streaming_legend import fold
    if folded: fold.validate_binding(config['fold_projection'])
    schema=('semcrys.instance-constitution.v0.5' if config['fold_projection']['mode']=='EXTERNAL' else 'semcrys.instance-constitution.v0.4') if folded else ('semcrys.instance-constitution.v0.3' if glyph else 'semcrys.instance-constitution.v0.10' if integer_projection else 'semcrys.instance-constitution.v0.2')
    if assembled:
        if glyph or integer_projection or folded or config['assembly_abi'] not in (ASSEMBLY_ABI,FAMILY_ABI): raise Refusal('HELD_ASSEMBLY_COMPOSITION_NOT_YET_QUALIFIED')
        roots=config['assembly_legend_roots']
        if type(roots) is not list or not roots or any(not _is_root(r) for r in roots) or len(set(roots))!=len(roots):
            raise Refusal('HELD_ASSEMBLY_CONFIGURATION_BINDING')
        schema='semcrys.instance-constitution.v0.7' if config['assembly_abi']==FAMILY_ABI else 'semcrys.instance-constitution.v0.6'
    if extended_codec:
        if glyph or integer_projection or folded or assembled: raise Refusal('HELD_EXTENDED_CODEC_COMPOSITION_NOT_QUALIFIED')
        schema='semcrys.instance-constitution.v0.9'
    if config.get("schema") != schema or config.get("standing") != "CANDIDATE_ONLY":
        raise Refusal("HELD_CONFIGURATION_SCHEMA")
    if config.get("profile") not in ("C:RAW_BYTES", "C:SELF_CONTAINED_TOKEN", "T:PRESHARED_TOKEN", "A:LONGITUDINAL_TOKEN_DELTA"):
        raise Refusal("HELD_PROFILE_UNAVAILABLE")
    if extended_codec:
        expected_codec=outer_codec_configuration(config.get('outer_codec'))
        if expected_codec is None or config.get('outer_codec_configuration')!=expected_codec:
            raise Refusal('HELD_OUTER_CODEC_CONFIGURATION')
    elif config.get("outer_codec") not in LEGACY_OUTER_CODECS:
        raise Refusal("HELD_OUTER_CODEC_UNAVAILABLE")
    if config["predecessor_head"] != PREDECESSOR_HEAD: raise Refusal("HELD_CONFIGURATION_PREDECESSOR")
    from streaming_legend import fold
    if config["tokenizer"] != (fold.TOKENIZER if folded else "UNICODE_CATEGORY_LOSSLESS_V1"): raise Refusal("HELD_TOKENIZER_UNAVAILABLE")
    if config["oversize_policy"] != "BOUNDED_LITERAL_CHUNKS_NOT_LEGEND_ELIGIBLE": raise Refusal("HELD_OVERSIZE_POLICY_UNAVAILABLE")
    if config["legend_policy"] not in ("TOTAL", "PROFITABLE"): raise Refusal("HELD_LEGEND_POLICY_UNAVAILABLE")
    if config["profile"] == "A:LONGITUDINAL_TOKEN_DELTA" and config["legend_policy"] != "TOTAL":
        raise Refusal("HELD_LONGITUDINAL_REQUIRES_TOTAL_DELTA")
    expected_body = "semcrys.raw-body.v0.2" if config["profile"] == "C:RAW_BYTES" else "semcrys.packed-token.v0.2"
    if glyph:
        if config['profile']=='C:RAW_BYTES' or config['glyph_codec']!='TOKEN_ID_BASE_N_FIXED_WIDTH_V1': raise Refusal('HELD_GLYPH_PROFILE')
        expected_body='semcrys.glyph-token.v0.1'
        expected_binding={'schema':'semcrys.glyph-registry.v0.1','mode':config['glyph_placement'],'sha256':config['glyph_registry_sha256']}
        if header['glyph_binding']!=expected_binding: raise Refusal('HELD_CONFIGURATION_GLYPH_BINDING')
        if type(config['glyph_width']) is not int or not 1<=config['glyph_width']<=64 or type(config['glyph_radix']) is not int or not 2<=config['glyph_radix']<=65536 or type(config['glyph_legend_entries']) is not int or not 0<=config['glyph_legend_entries']<=(1<<64)-1:
            raise Refusal('HELD_GLYPH_PARAMETERS')
    elif header['glyph_binding'] is not None: raise Refusal('HELD_UNUSED_GLYPH_BINDING')
    if integer_projection:
        from .integer_projection import CODEC
        if config['profile']=='C:RAW_BYTES' or config['integer_codec']!=CODEC or type(config['integer_legend_entries']) is not int or not 0<=config['integer_legend_entries']<=(1<<64)-1:
            raise Refusal('HELD_INTEGER_PARAMETERS')
        expected_body='semcrys.integer-token.v0.1'
    if folded:
        if config['fold_fallback']!='FULL_PROJECTED_VIEW_CONSTITUENT_LOOKUP_V1': raise Refusal('HELD_FOLD_FALLBACK_POLICY')
        if glyph or integer_projection or config['profile']!='T:PRESHARED_TOKEN' or config['max_unit_bytes']!=4096 or len(header['legend_bindings'])!=1:
            raise Refusal('HELD_FOLD_CONFIGURATION_UNAVAILABLE')
        if config['fold_projection']['base_legend_sha256']!=header['legend_bindings'][0]['sha256']:
            raise Refusal('HELD_FOLD_BASE_BINDING')
        expected_body='semcrys.folded-front-packed.v0.1'
    if config["physical_body_schema"] != expected_body: raise Refusal("HELD_PHYSICAL_BODY_SCHEMA")
    if config.get("security_claim") != "NONE" or config.get("implicit_fallback") is not False:
        raise Refusal("HELD_CONFIGURATION_CLAIM")
    maximum = config.get("max_unit_bytes")
    if type(maximum) is not int or not 4 <= maximum <= MAX_UNIT_BYTES: raise Refusal("HELD_INVALID_SCANNER_LIMIT")
    claimed = config.get("instance_constitution_sha256")
    unrooted = {key: value for key, value in config.items() if key != "instance_constitution_sha256"}
    if _rooted(unrooted) != claimed: raise Refusal("HELD_INSTANCE_CONSTITUTION_ROOT")
    bindings = [{key: row[key] for key in ("role", "mode", "sha256")} for row in header["legend_bindings"]]
    if bindings != config.get("legend_stack"): raise Refusal("HELD_CONFIGURATION_LEGEND_STACK")
    if config.get("source_sha256") != header.get("decoded_sha256"): raise Refusal("HELD_CONFIGURATION_SOURCE_ROOT")
    if not _is_root(config["source_sha256"]): raise Refusal("HELD_INVALID_SOURCE_ROOT")
    if config["external_legend_roots"] != [r["sha256"] for r in bindings if r["mode"] == "EXTERNAL"]:
        raise Refusal("HELD_EXTERNAL_ROOT_SEQUENCE")
    roles = [row["role"] for row in bindings]; modes = [row["mode"] for row in bindings]
    if roles and roles != ["BASE"] + ["DELTA"] * (len(roles)-1): raise Refusal("HELD_APPLICATION_LEGEND_ROLES")
    profile = config["profile"]
    if profile == "C:RAW_BYTES" and bindings: raise Refusal("HELD_RAW_PROFILE_LEGENDS")
    if profile == "C:SELF_CONTAINED_TOKEN" and modes != ["EMBEDDED"]: raise Refusal("HELD_SELF_CONTAINED_STACK")
    if profile == "T:PRESHARED_TOKEN" and (not modes or any(m != "EXTERNAL" for m in modes)): raise Refusal("HELD_PRESHARED_STACK")
    if profile == "A:LONGITUDINAL_TOKEN_DELTA" and (len(modes)<2 or modes != ["EXTERNAL"]*(len(modes)-1)+["EMBEDDED"]):
        raise Refusal("HELD_LONGITUDINAL_STACK")


def _validate_lineage(paths):
    parent = None
    for path in paths:
        reader = LegendReader(path)
        if reader.header["parent_sha256"] != parent: raise Refusal("HELD_LEGEND_PARENT_SEQUENCE")
        parent = file_sha256(path)


@governed_context
def encode_file(source, output, *, profile, external_legends=(), outer_codec="NONE",
    legend_policy=None, security_request="NONE", max_unit_bytes=MAX_UNIT_BYTES,
    projection='PACKED',glyph_registry=None,glyph_placement='EMBEDDED',fold_front=None,
    fold_placement='EMBEDDED',accounting=None,receiver_roots=(),legend_context=None):
    source, target = Path(source), Path(output)
    protect_outputs([target], [source, *external_legends,*([glyph_registry] if glyph_registry is not None else [])])
    if fold_front is not None: protect_outputs([target],[fold_front])
    protect_outputs([target],legend_context.protected_paths())
    if target.suffix.lower() != ".crys": raise Refusal("HELD_CRYS_SUFFIX_REQUIRED")
    target.parent.mkdir(parents=True, exist_ok=True)
    with sio.TempDirectory(prefix="semcrys-inputs-", dir=target.parent) as name:
        work = Path(name); snapshot = work / "input.bytes"
        _snapshot(source, snapshot)
        legends = _snapshot_legends(external_legends, work, legend_context)
        _validate_lineage(legends)
        glyph_snapshot=None
        if glyph_registry is not None:
            _,glyph_data,_=load_glyph(glyph_registry); glyph_snapshot=work/'glyph.gly'; sio.write_bytes(glyph_snapshot,glyph_data)
        fold_snapshot=None
        if fold_front is not None:
            from streaming_legend import fold
            _,_,_,data,_=fold.load(fold_front); fold_snapshot=work/'front.leg'; sio.write_bytes(fold_snapshot,data)
        return _encode_snapshot(snapshot, target, profile=profile, external_legends=legends,
            outer_codec=outer_codec, legend_policy=legend_policy, security_request=security_request, max_unit_bytes=max_unit_bytes,
            projection=projection,glyph_registry=glyph_snapshot,glyph_placement=glyph_placement,fold_front=fold_snapshot,
            fold_placement=fold_placement,accounting=accounting,receiver_roots=receiver_roots,legend_context=legend_context)
