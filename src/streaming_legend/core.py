"""Streaming binary .leg v0.2 with sparse random-access index."""

from __future__ import annotations
from streaming_legend import scratch_io as sio

import base64
import hashlib
import io
import json
import os
import sqlite3
import struct
import tempfile
from .cache import SharedLookupCache
from pathlib import Path
from typing import Iterable, Iterator

MAGIC = b"SCLEG\r\n\x1a"
VERSION = (0, 2)
PROLOGUE = struct.Struct(">8sHHI")
FOOTER = struct.Struct(">4sQQ32s32s")
FOOTER_MAGIC = b"LEND"
U64 = struct.Struct(">Q")
CHUNK = 1024 * 1024
# One verified sparse block per reader, never a whole-legend value cache.
# Both dimensions are bounded because tiny records can still have large metadata.
LOOKUP_BLOCK_BYTES = 1024 * 1024
LOOKUP_BLOCK_ENTRIES = 4096


class LegendError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _venc(number: int) -> bytes:
    if type(number) is not int or not 0 <= number <= (1 << 64) - 1:
        raise LegendError("HELD_LEGEND_VARINT_U64_RANGE")
    output = bytearray()
    while True:
        byte = number & 0x7F
        number >>= 7
        output.append(byte | (0x80 if number else 0))
        if not number:
            return bytes(output)


def _vdec(handle, *, boundary: int) -> int:
    number = 0
    shift = 0
    while True:
        if handle.tell() >= boundary:
            raise LegendError("HELD_TRUNCATED_LEGEND_ENTRY")
        raw = handle.read(1)
        if len(raw) != 1 or shift > 63:
            raise LegendError("HELD_MALFORMED_LEGEND_VARINT")
        byte = raw[0]
        if shift == 63 and byte > 1: raise LegendError("HELD_LEGEND_VARINT_U64_RANGE")
        number |= (byte & 0x7F) << shift
        if not byte & 0x80:
            if shift and byte == 0: raise LegendError("HELD_NONCANONICAL_LEGEND_VARINT")
            return number
        shift += 7


def _unique_db(path: Path | None = None):
    if path is None:
        descriptor, name = sio.mkstemp(prefix="semcrys-leg-unique-", suffix=".sqlite3")
        sio.close_fd(descriptor)
        target = Path(name)
        owned = True
    else:
        target = path
        owned = False
    connection = None
    try:
        connection = sio.sqlite_connect(target)
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("PRAGMA synchronous=OFF")
        connection.execute("PRAGMA temp_store=FILE")
        connection.execute("CREATE TABLE IF NOT EXISTS seen(value BLOB PRIMARY KEY) WITHOUT ROWID")
        return connection, target, owned
    except BaseException:
        if connection is not None: connection.close()
        if owned: sio.unlink(target,missing_ok=True)
        raise


def write_legend(
    path: str | os.PathLike[str],
    values: Iterable[bytes | str],
    *,
    entry_count: int,
    legend_id: str,
    unit_mode: str = "TOKEN",
    parent_sha256: str | None = None,
    index_stride: int = 256,
    max_value_bytes: int = 16 * 1024 * 1024,
) -> dict:
    target = Path(path)
    if target.suffix.lower() != ".leg":
        raise LegendError("HELD_LEG_SUFFIX_REQUIRED", str(target))
    if type(entry_count) is not int or type(index_stride) is not int or entry_count < 0 or index_stride < 1:
        raise LegendError("HELD_INVALID_LEGEND_DIMENSIONS")
    if parent_sha256 is not None and (not isinstance(parent_sha256, str) or len(parent_sha256) != 64 or any(c not in "0123456789abcdef" for c in parent_sha256)):
        raise LegendError("HELD_INVALID_PARENT_ROOT")
    header = {
        "schema": "semcrys.legend.binary.v0.2",
        "standing": "CANDIDATE_ONLY",
        "legend_id": legend_id,
        "unit_mode": unit_mode,
        "parent_sha256": parent_sha256,
        "entry_count": entry_count,
        "index_stride": index_stride,
    }
    header_bytes = canonical(header)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, pending_name = sio.mkstemp(
        prefix=target.name + ".", suffix=".pending", dir=target.parent
    )
    sio.close_fd(descriptor)
    pending = Path(pending_name)
    connection = unique_path = None
    owned = False
    blocks = 0
    count = 0
    entries_digest = hashlib.sha256()
    try:
        connection, unique_path, owned = _unique_db()
        with sio.open_output(pending,"wb") as output, sio.temporary_file(mode='w+b',dir=target.parent) as index_spool:
            output.write(PROLOGUE.pack(MAGIC, *VERSION, len(header_bytes)))
            output.write(header_bytes)
            entries_start = output.tell()
            for item in values:
                value = item.encode("utf-8") if isinstance(item, str) else bytes(item)
                if len(value) > max_value_bytes:
                    raise LegendError("HELD_LEGEND_VALUE_LIMIT", str(len(value)))
                try:
                    connection.execute("INSERT INTO seen(value) VALUES (?)", (value,))
                except sqlite3.IntegrityError as exc:
                    raise LegendError("HELD_DUPLICATE_LEGEND_VALUE", str(count + 1)) from exc
                if count % index_stride == 0:
                    index_spool.write(U64.pack(output.tell() - entries_start))
                    blocks += 1
                frame = _venc(len(value)) + value
                output.write(frame)
                entries_digest.update(frame)
                count += 1
            if count != entry_count:
                raise LegendError("HELD_LEGEND_ENTRY_COUNT_MISMATCH", f"{count}!={entry_count}")
            index_offset = output.tell()
            index_length = index_spool.tell()
            index_spool.seek(0)
            index_digest = hashlib.sha256()
            while block := index_spool.read(CHUNK):
                output.write(block); index_digest.update(block)
            output.write(
                FOOTER.pack(
                    FOOTER_MAGIC,
                    index_offset,
                    index_length,
                    entries_digest.digest(),
                    index_digest.digest(),
                )
            )
        sio.replace(pending, target)
        return {
            "schema": "semcrys.legend-write-result.v0.2",
            "status": "PASS",
            "path": str(target),
            "sha256": file_sha256(target),
            "bytes": target.stat().st_size,
            "entry_count": count,
            "index_blocks": blocks,
        }
    except BaseException:
        sio.unlink(pending,missing_ok=True)
        raise
    finally:
        if connection is not None: connection.close()
        if owned and unique_path is not None:
            sio.unlink(unique_path,missing_ok=True)


class LegendReader:
    def __init__(self, path: str | os.PathLike[str], *, max_entries: int = 1_000_000_000, max_value_bytes: int = 16 * 1024 * 1024, lookup_cache=None) -> None:
        self.path = Path(path)
        if lookup_cache is not None and type(lookup_cache) is not SharedLookupCache:
            raise LegendError('HELD_LOOKUP_CACHE_TYPE')
        self._shared_lookup_cache = lookup_cache
        if type(max_entries) is not int or max_entries<0 or type(max_value_bytes) is not int or max_value_bytes<0:
            raise LegendError('HELD_INVALID_LEGEND_LIMIT')
        self._initial_signature = self._signature(self.path.stat())
        self._verified_signature = None
        self.index_validation_passes = 0
        self._lookup_block = None
        self.lookup_stats = {"block_loads": 0, "block_hits": 0, "direct_reads": 0}
        self.max_entries = max_entries
        self.max_value_bytes = max_value_bytes
        with self.path.open("rb") as handle:
            # On Windows path stat and descriptor fstat can expose different
            # ctime semantics. Compare each channel only against its own origin.
            self._initial_handle_signature=self._signature(os.fstat(handle.fileno()))
            fixed = handle.read(PROLOGUE.size)
            if len(fixed) != PROLOGUE.size:
                raise LegendError("HELD_TRUNCATED_LEGEND")
            magic, major, minor, header_size = PROLOGUE.unpack(fixed)
            if magic != MAGIC:
                raise LegendError("HELD_BAD_LEGEND_MAGIC")
            if (major, minor) != VERSION:
                raise LegendError("HELD_UNSUPPORTED_LEGEND_VERSION", f"{major}.{minor}")
            if header_size > 1024 * 1024:
                raise LegendError("HELD_LEGEND_HEADER_LIMIT")
            header_data = handle.read(header_size)
            try:
                self.header = json.loads(header_data.decode("utf-8"))
            except (UnicodeDecodeError, ValueError, RecursionError) as exc:
                raise LegendError("HELD_INVALID_LEGEND_HEADER") from exc
            keys = {"schema", "standing", "legend_id", "unit_mode", "parent_sha256", "entry_count", "index_stride"}
            if type(self.header) is not dict or set(self.header) != keys:
                raise LegendError("HELD_LEGEND_HEADER_FIELDS")
            try:
                canonical_header = canonical(self.header)
            except (UnicodeError, ValueError, RecursionError) as exc:
                raise LegendError("HELD_INVALID_LEGEND_HEADER") from exc
            if canonical_header != header_data or self.header.get("schema") != "semcrys.legend.binary.v0.2":
                raise LegendError("HELD_NONCANONICAL_LEGEND_HEADER")
            if self.header.get("standing") != "CANDIDATE_ONLY":
                raise LegendError("HELD_LEGEND_STANDING")
            for key in ("legend_id", "unit_mode"):
                if not isinstance(self.header[key], str) or not self.header[key]:
                    raise LegendError("HELD_LEGEND_HEADER_TYPE", key)
            parent = self.header["parent_sha256"]
            if parent is not None and (not isinstance(parent, str) or len(parent) != 64 or any(c not in "0123456789abcdef" for c in parent)):
                raise LegendError("HELD_INVALID_PARENT_ROOT")
            self.count = self.header.get("entry_count")
            self.stride = self.header.get("index_stride")
            if type(self.count) is not int or not 0 <= self.count <= max_entries or type(self.stride) is not int or self.stride < 1:
                raise LegendError("HELD_LEGEND_DIMENSION_LIMIT")
            self.entries_start = handle.tell()
            if self.path.stat().st_size < self.entries_start + FOOTER.size:
                raise LegendError("HELD_TRUNCATED_LEGEND")
            handle.seek(-FOOTER.size, 2)
            footer = handle.read(FOOTER.size)
            magic, self.index_offset, self.index_length, self.entries_digest, self.index_digest = FOOTER.unpack(footer)
            if magic != FOOTER_MAGIC:
                raise LegendError("HELD_BAD_LEGEND_FOOTER")
            expected_blocks = (self.count + self.stride - 1) // self.stride
            if self.index_length != expected_blocks * U64.size:
                raise LegendError("HELD_LEGEND_INDEX_LENGTH")
            if self.index_offset < self.entries_start or self.index_offset + self.index_length + FOOTER.size != self.path.stat().st_size:
                raise LegendError("HELD_LEGEND_OFFSETS")

        self._check_snapshot()

    @staticmethod
    def _signature(stat):
        return (stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)

    def _check_snapshot(self,handle=None):
        observed=self._signature(os.fstat(handle.fileno()) if handle is not None else self.path.stat())
        expected=self._initial_handle_signature if handle is not None else self._initial_signature
        if observed != expected: raise LegendError('HELD_LEGEND_CHANGED_REOPEN_REQUIRED')
        return observed

    def iter_values(self) -> Iterator[tuple[int, bytes]]:
        with self.path.open("rb") as handle:
            self._check_snapshot(handle)
            handle.seek(self.entries_start)
            for identifier in range(1, self.count + 1):
                length = _vdec(handle, boundary=self.index_offset)
                if length > self.max_value_bytes or handle.tell() + length > self.index_offset:
                    raise LegendError("HELD_LEGEND_VALUE_LIMIT", str(length))
                value = handle.read(length)
                if len(value) != length:
                    raise LegendError("HELD_TRUNCATED_LEGEND_ENTRY")
                yield identifier, value
            if handle.tell() != self.index_offset:
                raise LegendError("HELD_LEGEND_ENTRY_REGION_MISMATCH")
            self._check_snapshot(handle)

    def verify(self, *, check_duplicates: bool = True) -> dict:
        self._check_snapshot()
        digest = hashlib.sha256()
        with self.path.open("rb") as handle:
            handle.seek(self.entries_start)
            remaining = self.index_offset - self.entries_start
            while remaining:
                chunk = handle.read(min(CHUNK, remaining))
                if not chunk:
                    raise LegendError("HELD_TRUNCATED_LEGEND_ENTRY_REGION")
                remaining -= len(chunk)
                digest.update(chunk)
        if digest.digest() != self.entries_digest:
            raise LegendError("HELD_LEGEND_ENTRY_DIGEST")
        index_digest = hashlib.sha256()
        connection = unique_path = None
        owned = False
        try:
            if check_duplicates:
                connection, unique_path, owned = _unique_db()
            blocks = 0
            with self.path.open("rb") as handle, self.path.open('rb') as index:
                self._check_snapshot(handle); self._check_snapshot(index)
                index.seek(self.index_offset)
                handle.seek(self.entries_start)
                for identifier in range(1, self.count + 1):
                    if (identifier - 1) % self.stride == 0:
                        raw=index.read(U64.size)
                        if len(raw)!=U64.size: raise LegendError('HELD_LEGEND_INDEX_LENGTH')
                        index_digest.update(raw); blocks += 1
                        if U64.unpack(raw)[0]!=handle.tell()-self.entries_start:
                            raise LegendError('HELD_LEGEND_INDEX_CONTENT')
                    length = _vdec(handle, boundary=self.index_offset)
                    if length > self.max_value_bytes or handle.tell() + length > self.index_offset:
                        raise LegendError("HELD_LEGEND_VALUE_LIMIT", str(length))
                    value = handle.read(length)
                    if len(value)!=length: raise LegendError('HELD_TRUNCATED_LEGEND_ENTRY')
                    if check_duplicates:
                        try:
                            connection.execute("INSERT INTO seen(value) VALUES (?)", (value,))
                        except sqlite3.IntegrityError as exc:
                            raise LegendError("HELD_DUPLICATE_LEGEND_VALUE", str(identifier)) from exc
                if handle.tell() != self.index_offset:
                    raise LegendError("HELD_LEGEND_ENTRY_REGION_MISMATCH")
                self._check_snapshot(handle); self._check_snapshot(index)
            if index_digest.digest()!=self.index_digest: raise LegendError('HELD_LEGEND_INDEX_DIGEST')
            root=file_sha256(self.path)
            self._verified_signature=self._check_snapshot()
            self.index_validation_passes += 1
            return {
                "schema": "semcrys.legend-verification.v0.2",
                "status": "PASS",
                "sha256": root,
                "entry_count": self.count,
                "index_blocks": blocks,
            }
        finally:
            if connection is not None:
                connection.close()
            if owned and unique_path is not None:
                sio.unlink(unique_path,missing_ok=True)

    def _load_lookup_block(self, handle, block: int, offset: int) -> bool:
        count = min(self.stride, self.count - block * self.stride)
        if count > LOOKUP_BLOCK_ENTRIES:
            return False
        end = self.index_offset - self.entries_start
        if (block + 1) * U64.size < self.index_length:
            handle.seek(self.index_offset + (block + 1) * U64.size)
            raw = handle.read(U64.size)
            if len(raw) != U64.size:
                raise LegendError("HELD_LEGEND_INDEX_LENGTH")
            end = U64.unpack(raw)[0]
        if not offset < end <= self.index_offset - self.entries_start:
            raise LegendError("HELD_LEGEND_INDEX_CONTENT")
        if end - offset > LOOKUP_BLOCK_BYTES:
            return False
        shared = self._shared_lookup_cache
        if shared is not None and not shared.reserve(self,end-offset,count):
            return False
        # Release the old block before allocating the next: no growing block map.
        self._lookup_block = None
        try:
            handle.seek(self.entries_start + offset)
            data = handle.read(end - offset)
            if len(data) != end - offset:
                raise LegendError("HELD_TRUNCATED_LEGEND_ENTRY")
            spans = []
            with io.BytesIO(data) as cursor:
                for _ in range(count):
                    length = _vdec(cursor, boundary=len(data))
                    start = cursor.tell()
                    if length > self.max_value_bytes or start + length > len(data):
                        raise LegendError("HELD_LEGEND_VALUE_LIMIT")
                    spans.append((start, length))
                    cursor.seek(length, 1)
                if cursor.tell() != len(data):
                    raise LegendError("HELD_LEGEND_ENTRY_REGION_MISMATCH")
            self._check_snapshot(handle)
            self._check_snapshot()
            self._lookup_block = (block, data, spans)
        except BaseException:
            if shared is not None: shared.release(self)
            raise
        self.lookup_stats["block_loads"] += 1
        return True

    def _lookup_block_value(self, identifier: int) -> bytes:
        _, data, spans = self._lookup_block
        start, length = spans[(identifier - 1) % self.stride]
        if length > self.max_value_bytes:
            raise LegendError("HELD_LEGEND_VALUE_LIMIT")
        value = data[start:start + length]
        self._check_snapshot()
        return value

    def get(self, identifier: int) -> bytes:
        if type(identifier) is not int or not 1 <= identifier <= self.count:
            raise LegendError("HELD_LEGEND_ID_RANGE", str(identifier))
        if self._verified_signature is None: self.verify(check_duplicates=False)
        self._check_snapshot()
        block = (identifier - 1) // self.stride
        current = block * self.stride + 1
        with self.path.open("rb") as handle:
            self._check_snapshot(handle)
            if self._lookup_block is not None and self._lookup_block[0] == block:
                # Windows path stat exposes creation time where descriptor
                # fstat exposes change time. A path-only hit weakens custody.
                self.lookup_stats["block_hits"] += 1
                if self._shared_lookup_cache is not None: self._shared_lookup_cache.touch(self)
                value = self._lookup_block_value(identifier)
                self._check_snapshot(handle)
                return value
            handle.seek(self.index_offset+block*U64.size)
            raw=handle.read(U64.size)
            if len(raw)!=U64.size: raise LegendError('HELD_LEGEND_INDEX_LENGTH')
            offset=U64.unpack(raw)[0]
            if offset>=self.index_offset-self.entries_start: raise LegendError('HELD_LEGEND_INDEX_CONTENT')
            if self._load_lookup_block(handle, block, offset):
                return self._lookup_block_value(identifier)
            self.lookup_stats["direct_reads"] += 1
            handle.seek(self.entries_start + offset)
            while current <= identifier:
                length = _vdec(handle, boundary=self.index_offset)
                if length > self.max_value_bytes or handle.tell()+length>self.index_offset:
                    raise LegendError("HELD_LEGEND_VALUE_LIMIT")
                value = handle.read(length)
                if len(value) != length:
                    raise LegendError("HELD_TRUNCATED_LEGEND_ENTRY")
                if current == identifier:
                    self._check_snapshot(handle)
                    return value
                current += 1
        raise LegendError("HELD_LEGEND_ID_RANGE", str(identifier))


def build_lookup_cache(legend_path: str | os.PathLike[str], cache_path: str | os.PathLike[str]) -> dict:
    reader = LegendReader(legend_path)
    verified = reader.verify()
    target = Path(cache_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, pending_name = sio.mkstemp(prefix=target.name + ".", suffix=".pending", dir=target.parent)
    sio.close_fd(descriptor)
    pending = Path(pending_name)
    connection = None
    try:
        connection = sio.sqlite_connect(pending)
        connection.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("CREATE TABLE lookup(value BLOB PRIMARY KEY, id INTEGER NOT NULL) WITHOUT ROWID")
        connection.executemany("INSERT INTO lookup(value,id) VALUES (?,?)", ((value, identifier) for identifier, value in reader.iter_values()))
        connection.execute("INSERT INTO meta(key,value) VALUES ('legend_sha256',?)", (verified["sha256"],))
        connection.commit()
        connection.close()
        connection = None
        sio.replace(pending, target)
    except BaseException:
        if connection is not None:
            connection.close()
            connection = None
        sio.unlink(pending,missing_ok=True)
        raise
    finally:
        if connection is not None:
            connection.close()
    return {"schema": "semcrys.legend-lookup-cache.v0.2", "status": "PASS", "path": str(target), "legend_sha256": verified["sha256"], "entries": reader.count}


def migrate_json_v01(source: str | os.PathLike[str], target: str | os.PathLike[str], *, index_stride: int = 256) -> dict:
    source_path = Path(source)
    target_path = Path(target)
    if source_path.resolve() == target_path.resolve() or (target_path.exists() and os.path.samefile(source_path,target_path)):
        raise LegendError('HELD_SOURCE_OUTPUT_ALIAS')
    with source_path.open('rb') as handle:
        data=handle.read(64*1024*1024+1)
    if len(data)>64*1024*1024: raise LegendError('HELD_ARTIFACT_SIZE_LIMIT')
    try:
        value = json.loads(data.decode('utf-8'))
        if type(value) is not dict or canonical(value)!=data: raise LegendError('HELD_NONCANONICAL_ARTIFACT')
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc,LegendError): raise
        raise LegendError("HELD_INVALID_V0_1_LEGEND") from exc
    if set(value)!={'schema','standing','legend_id','unit_mode','parent_sha256','entries'} or value['schema']!='semcrys.legend.v0.1' or value['standing']!='CANDIDATE_ONLY' or type(value['entries']) is not list:
        raise LegendError("HELD_INVALID_V0_1_LEGEND")
    for key in ('legend_id','unit_mode'):
        if not isinstance(value[key],str) or not value[key]: raise LegendError('HELD_LEGEND_HEADER_TYPE',key)
    if value['parent_sha256'] is not None: raise LegendError('HELD_PARENT_ROOT_REMAP_REQUIRED')
    def values():
        for index,row in enumerate(value['entries'],1):
            if type(row) is not dict or set(row)!={'id','value_b64'} or type(row['id']) is not int or row['id']!=index:
                raise LegendError('HELD_LEGEND_ID_SEQUENCE')
            try:
                encoded=row['value_b64']
                if not isinstance(encoded,str): raise ValueError()
                decoded=base64.b64decode(encoded,validate=True)
                if base64.b64encode(decoded).decode('ascii')!=encoded: raise ValueError()
            except ValueError as exc: raise LegendError('HELD_LEGEND_BASE64') from exc
            yield decoded
    result = write_legend(
        target,
        values(),
        entry_count=len(value["entries"]),
        legend_id=value['legend_id'],
        unit_mode=value['unit_mode'],
        index_stride=index_stride,
    )
    return {**result,'source_sha256':hashlib.sha256(data).hexdigest()}
