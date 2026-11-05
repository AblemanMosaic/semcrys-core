"""Streaming .crys v0.2 binding binary .leg v0.2 artifacts."""

from __future__ import annotations
from streaming_legend import scratch_io as sio

import hashlib
import json
import os
import struct
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Mapping, Sequence
import re

from .core import LegendError, canonical, file_sha256
from .assembly import ExecutionLegendReader as LegendReader
from .glyph import load as load_glyph, parse as parse_glyph
from . import fold

MAGIC = b"CRYS\r\n\x1a\n"
VERSION = (0, 2)
PROLOGUE = struct.Struct(">8sHHI")
SECTION = struct.Struct(">4sHHQ32s")
CRITICAL = 1
CHUNK = 1024 * 1024
KNOWN = {b"ICFG", b"LEGD", b"GLYP", b"FRNT", b"FREF", b"BODY", b"RCPT", b"DONE"}
RANK = {b"ICFG": 0, b"LEGD": 1, b"GLYP": 2, b"FRNT": 2, b"FREF": 2, b"BODY": 3, b"RCPT": 4}


class CrysV2Error(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclass(frozen=True)
class Limits:
    max_header_bytes: int = 1024 * 1024
    max_control_bytes: int = 4 * 1024 * 1024
    max_section_bytes: int = 1 << 42
    max_total_payload_bytes: int = 1 << 44
    max_sections: int = 4096
    max_legend_entries: int = 1_000_000_000

    def __post_init__(self):
        for name, value in self.__dict__.items():
            if type(value) is not int or not 0 <= value <= (1 << 64) - 1:
                raise CrysV2Error("HELD_INVALID_RESOURCE_LIMIT", name)


def _is_root(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _object(data: bytes, label: str) -> dict:
    try:
        value = json.loads(data.decode("utf-8"))
        if type(value) is not dict or canonical(value) != data:
            raise CrysV2Error("HELD_NONCANONICAL_OBJECT", label)
        return value
    except (ValueError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, CrysV2Error): raise
        raise CrysV2Error("HELD_INVALID_JSON_OBJECT", label) from exc


def _check_header(header: dict, limits: Limits) -> None:
    keys = {"schema", "standing", "artifact_kind", "configuration_sha256", "encoded_body_sha256", "decoded_sha256", "legend_bindings", "glyph_binding"}
    if set(header) != keys or header["schema"] != "semcrys.crys.header.v0.2":
        raise CrysV2Error("HELD_HEADER_SCHEMA")
    if header["standing"] != "CANDIDATE_ONLY" or header["artifact_kind"] != "ENCODED":
        raise CrysV2Error("HELD_HEADER_DISPOSITION")
    for key in ("configuration_sha256", "encoded_body_sha256"):
        if not _is_root(header[key]): raise CrysV2Error("HELD_INVALID_ROOT", key)
    if header["decoded_sha256"] is not None and not _is_root(header["decoded_sha256"]):
        raise CrysV2Error("HELD_INVALID_ROOT", "decoded_sha256")
    glyph=header['glyph_binding']
    if glyph is not None:
        if type(glyph) is not dict or set(glyph)!={'mode','sha256','schema'} or glyph['mode'] not in ('EMBEDDED','EXTERNAL') or glyph['schema']!='semcrys.glyph-registry.v0.1' or not _is_root(glyph['sha256']):
            raise CrysV2Error('HELD_GLYPH_BINDING_SCHEMA')
    bindings = header["legend_bindings"]
    if type(bindings) is not list or len(bindings) > limits.max_sections:
        raise CrysV2Error("HELD_LEGEND_BINDINGS_SCHEMA")
    roots = []
    for row in bindings:
        if type(row) is not dict or set(row) != {"role", "mode", "sha256", "schema"}:
            raise CrysV2Error("HELD_LEGEND_BINDING_SCHEMA")
        if row["role"] not in ("BASE", "DELTA", "META", "ASSEMBLY") or row["mode"] not in ("EXTERNAL", "EMBEDDED"):
            raise CrysV2Error("HELD_INVALID_LEGEND_BINDING")
        if row["schema"] != "semcrys.legend.binary.v0.2" or not _is_root(row["sha256"]):
            raise CrysV2Error("HELD_LEGEND_BINDING_SCHEMA")
        roots.append(row["sha256"])
    if len(set(roots)) != len(roots): raise CrysV2Error("HELD_DUPLICATE_LEGEND_BINDING")


def _measure(source: bytes | Path) -> tuple[int, bytes]:
    digest = hashlib.sha256()
    total = 0
    if isinstance(source, bytes):
        return len(source), hashlib.sha256(source).digest()
    with source.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            total += len(chunk)
            digest.update(chunk)
    return total, digest.digest()


def _copy(source: bytes | Path, output: BinaryIO, stream: hashlib._Hash | None = None) -> None:
    if isinstance(source, bytes):
        output.write(source)
        if stream is not None:
            stream.update(source)
        return
    with source.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            output.write(chunk)
            if stream is not None:
                stream.update(chunk)


def _binding(role: str, mode: str, root: str) -> dict:
    if role not in {"BASE", "DELTA", "META", "ASSEMBLY"} or mode not in {"EMBEDDED", "EXTERNAL"}:
        raise CrysV2Error("HELD_INVALID_LEGEND_BINDING", f"{role}/{mode}")
    if not _is_root(root):
        raise CrysV2Error("HELD_INVALID_LEGEND_ROOT")
    return {"role": role, "mode": mode, "sha256": root, "schema": "semcrys.legend.binary.v0.2"}


def write_crys(
    output: str | os.PathLike[str],
    *,
    configuration: Mapping[str, object],
    body: bytes | str | os.PathLike[str],
    legend_stack: Sequence[tuple[str, str, str | os.PathLike[str]]] = (),
    decoded_sha256: str | None = None,
    receipts: Sequence[Mapping[str, object]] = (),
    glyph_binding: tuple[str,str | os.PathLike[str]] | None = None,
    fold_projection: bytes | None = None,
    fold_reference: Mapping[str, object] | None = None,
) -> dict:
    target = Path(output)
    if target.suffix.lower() != ".crys":
        raise CrysV2Error("HELD_CRYS_SUFFIX_REQUIRED", str(target))
    config_data = canonical(dict(configuration))
    reference_data=None
    if fold_projection is not None and fold_reference is not None: raise CrysV2Error('HELD_FOLD_PLACEMENT_CONFLICT')
    if fold_reference is not None:
        reference_data=fold.reference(fold_reference)
        if configuration.get('fold_projection')!=fold_reference: raise CrysV2Error('HELD_CONFIGURATION_FOLD_BINDING')
    if fold_projection is not None:
        front_header,_,_=fold.parse(fold_projection)
        if configuration.get('fold_projection')!=fold.binding(front_header,hashlib.sha256(fold_projection).hexdigest()):
            raise CrysV2Error('HELD_CONFIGURATION_FOLD_BINDING')
    elif fold_reference is None and configuration.get('fold_projection') is not None: raise CrysV2Error('HELD_FOLD_PROJECTION_MISSING')
    body_source: bytes | Path = body if isinstance(body, bytes) else Path(body)
    bindings = []
    embedded: list[Path] = []
    for role, mode, value in legend_stack:
        if mode == "EMBEDDED":
            path = Path(value)
            verified = LegendReader(path).verify()
            bindings.append(_binding(role, mode, verified["sha256"]))
            embedded.append(path)
        else:
            bindings.append(_binding(role, mode, str(value)))
    glyph=None; glyph_data=None
    if glyph_binding is not None:
        mode,value=glyph_binding
        if mode=='EMBEDDED': _,glyph_data,root=load_glyph(value)
        elif mode=='EXTERNAL': root=str(value)
        else: raise CrysV2Error('HELD_GLYPH_BINDING_SCHEMA')
        glyph={'mode':mode,'sha256':root,'schema':'semcrys.glyph-registry.v0.1'}
    body_size, body_digest = _measure(body_source)
    header = {
        "schema": "semcrys.crys.header.v0.2",
        "standing": "CANDIDATE_ONLY",
        "artifact_kind": "ENCODED",
        "configuration_sha256": hashlib.sha256(config_data).hexdigest(),
        "encoded_body_sha256": body_digest.hex(),
        "decoded_sha256": decoded_sha256,
        "legend_bindings": bindings,
        "glyph_binding": glyph,
    }
    sections: list[tuple[bytes, bytes | Path, bool]] = [(b"ICFG", config_data, True)]
    sections.extend((b"LEGD", path, True) for path in embedded)
    if glyph_data is not None: sections.append((b'GLYP',glyph_data,True))
    if fold_projection is not None: sections.append((b'FRNT',fold_projection,True))
    if reference_data is not None: sections.append((b'FREF',reference_data,True))
    sections.append((b"BODY", body_source, True))
    sections.extend((b"RCPT", canonical(dict(receipt)), False) for receipt in receipts)
    header_data = canonical(header)
    _check_header(header, Limits())
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, pending_name = sio.mkstemp(prefix=target.name + ".", suffix=".pending", dir=target.parent)
    sio.close_fd(descriptor)
    pending = Path(pending_name)
    stream = hashlib.sha256()
    records = []
    try:
        with sio.open_output(pending,"wb") as handle:
            prefix = PROLOGUE.pack(MAGIC, *VERSION, len(header_data)) + header_data
            handle.write(prefix)
            stream.update(prefix)
            for code, source, critical in sections:
                size, digest = _measure(source)
                flags = CRITICAL if critical else 0
                frame = SECTION.pack(code, flags, 0, size, digest)
                handle.write(frame)
                stream.update(frame)
                _copy(source, handle, stream)
                records.append({"type": code.decode(), "flags": flags, "length": size, "sha256": digest.hex()})
            manifest = canonical({"schema": "semcrys.crys.manifest.v0.2", "sections": records, "stream_sha256": stream.hexdigest()})
            handle.write(SECTION.pack(b"DONE", CRITICAL, 0, len(manifest), hashlib.sha256(manifest).digest()))
            handle.write(manifest)
        sio.replace(pending, target)
    except Exception:
        sio.unlink(pending,missing_ok=True)
        raise
    return {"schema": "semcrys.crys-write-result.v0.2", "status": "PASS", "path": str(target), "sha256": file_sha256(target), "body_bytes": body_size, "sections": records}


def _read_exact(handle: BinaryIO, size: int, label: str) -> bytes:
    data = handle.read(size)
    if len(data) != size:
        raise CrysV2Error("HELD_TRUNCATED", label)
    return data


def inspect_crys(
    source: str | os.PathLike[str],
    *,
    body_sink: BinaryIO | None = None,
    dependency_resolver: Mapping[str, str | os.PathLike[str]] | None = None,
    require_dependencies: bool = False,
    limits: Limits | None = None,
    capture_directory: Path | None = None,
    glyph_resolver: Mapping[str,str | os.PathLike[str]] | None = None,
    fold_resolver: Mapping[str,str | os.PathLike[str]] | None = None,
) -> dict:
    limits = limits or Limits()
    path = Path(source)
    resolver = dependency_resolver or {}
    stream = hashlib.sha256()
    whole_file = hashlib.sha256()
    records = []
    embedded_roots = []
    temporary_legends: list[Path] = []
    config_data = None
    glyph_data = None
    front_data = None
    reference_data = None
    front_path = None
    counts: dict[bytes, int] = {}
    last_rank = -1
    total = 0
    success = False
    try:
        with path.open("rb") as handle:
            fixed = _read_exact(handle, PROLOGUE.size, "PROLOGUE")
            magic, major, minor, header_size = PROLOGUE.unpack(fixed)
            if magic != MAGIC:
                raise CrysV2Error("HELD_BAD_MAGIC")
            if (major, minor) != VERSION:
                raise CrysV2Error("HELD_UNSUPPORTED_VERSION", f"{major}.{minor}")
            if header_size > limits.max_header_bytes:
                raise CrysV2Error("HELD_HEADER_LIMIT")
            header_data = _read_exact(handle, header_size, "HEADER")
            header = _object(header_data, "HEADER")
            _check_header(header, limits)
            stream.update(fixed + header_data)
            whole_file.update(fixed + header_data)
            while True:
                if len(records) >= limits.max_sections:
                    raise CrysV2Error("HELD_SECTION_COUNT_LIMIT")
                frame = _read_exact(handle, SECTION.size, "SECTION")
                whole_file.update(frame)
                code, flags, reserved, size, expected = SECTION.unpack(frame)
                if reserved or flags & ~CRITICAL:
                    raise CrysV2Error("HELD_RESERVED_BITS")
                if size > limits.max_section_bytes:
                    raise CrysV2Error("HELD_SECTION_SIZE_LIMIT")
                total += size
                if total > limits.max_total_payload_bytes:
                    raise CrysV2Error("HELD_TOTAL_PAYLOAD_LIMIT")
                if code in {b"ICFG", b"DONE", b"RCPT", b"GLYP", b"FRNT", b"FREF"} and size > limits.max_control_bytes:
                    raise CrysV2Error("HELD_CONTROL_SECTION_LIMIT", code.decode())
                if code in KNOWN and flags != (0 if code == b"RCPT" else CRITICAL):
                    raise CrysV2Error("HELD_SECTION_CRITICALITY", code.decode())
                if code == b"DONE":
                    data = _read_exact(handle, size, "DONE")
                    whole_file.update(data)
                    if hashlib.sha256(data).digest() != expected:
                        raise CrysV2Error("HELD_SECTION_DIGEST", "DONE")
                    manifest = _object(data, "DONE")
                    if set(manifest) != {"schema", "sections", "stream_sha256"} or manifest["schema"] != "semcrys.crys.manifest.v0.2":
                        raise CrysV2Error("HELD_MANIFEST_SCHEMA")
                    if canonical(manifest) != data or manifest.get("sections") != records or manifest.get("stream_sha256") != stream.hexdigest():
                        raise CrysV2Error("HELD_MANIFEST_MISMATCH")
                    if handle.read(1):
                        raise CrysV2Error("HELD_TRAILING_BYTES")
                    break
                if code not in KNOWN and flags & CRITICAL:
                    raise CrysV2Error("HELD_UNKNOWN_CRITICAL_SECTION", code.decode("ascii", "replace"))
                if code in RANK:
                    rank = RANK[code]
                    if rank < last_rank:
                        raise CrysV2Error("HELD_SECTION_ORDER")
                    last_rank = rank
                counts[code] = counts.get(code, 0) + 1
                if code in {b"ICFG", b"BODY", b"GLYP", b"FRNT", b"FREF"} and counts[code] != 1:
                    raise CrysV2Error("HELD_SECTION_CARDINALITY", code.decode())
                if counts.get(b'FRNT',0)+counts.get(b'FREF',0)>1: raise CrysV2Error('HELD_FOLD_PLACEMENT_CONFLICT')
                digest = hashlib.sha256()
                stream.update(frame)
                remaining = size
                temporary = None
                temporary_handle = None
                if code == b"LEGD":
                    descriptor, name = sio.mkstemp(prefix="semcrys-embedded-", suffix=".leg", dir=capture_directory)
                    temporary = Path(name)
                    temporary_legends.append(temporary)
                    temporary_handle = sio.fdopen_output(descriptor, "wb")
                capture = bytearray() if code in {b"ICFG",b"GLYP",b"FRNT",b"FREF"} else None
                if capture is not None and size > limits.max_control_bytes:
                    raise CrysV2Error("HELD_CONTROL_SECTION_LIMIT")
                try:
                    while remaining:
                        chunk = _read_exact(handle, min(CHUNK, remaining), code.decode("ascii", "replace"))
                        remaining -= len(chunk)
                        digest.update(chunk)
                        stream.update(chunk)
                        whole_file.update(chunk)
                        if capture is not None:
                            capture.extend(chunk)
                        if temporary_handle is not None:
                            temporary_handle.write(chunk)
                        if code == b"BODY" and body_sink is not None:
                            body_sink.write(chunk)
                finally:
                    if temporary_handle is not None:
                        temporary_handle.close()
                if digest.digest() != expected:
                    raise CrysV2Error("HELD_SECTION_DIGEST", code.decode("ascii", "replace"))
                if code == b"ICFG":
                    config_data = bytes(capture)
                if code == b'GLYP': glyph_data=bytes(capture)
                if code == b'FRNT': front_data=bytes(capture)
                if code == b'FREF': reference_data=bytes(capture)
                if code == b"LEGD":
                    try:
                        verified = LegendReader(temporary, max_entries=limits.max_legend_entries).verify()
                    except LegendError as exc:
                        raise CrysV2Error(exc.code, exc.detail) from exc
                    if verified["sha256"] != expected.hex():
                        raise CrysV2Error("HELD_EMBEDDED_LEGEND_ROOT")
                    embedded_roots.append(verified["sha256"])
                records.append({"type": code.decode("ascii", "replace"), "flags": flags, "length": size, "sha256": expected.hex()})
        if counts.get(b"ICFG") != 1 or counts.get(b"BODY") != 1:
            raise CrysV2Error("HELD_SECTION_CARDINALITY")
        if hashlib.sha256(config_data).hexdigest() != header.get("configuration_sha256"):
            raise CrysV2Error("HELD_CONFIGURATION_ROOT")
        configuration = _object(config_data, "ICFG")
        front_header=None
        front_binding=None
        if reference_data is not None:
            front_binding=fold.parse_reference(reference_data)
            if configuration.get('fold_projection')!=front_binding: raise CrysV2Error('HELD_CONFIGURATION_FOLD_BINDING')
            dependency=(fold_resolver or {}).get(front_binding['sha256'])
            if dependency is not None:
                front_header,_,_,front_data,digest=fold.load(dependency)
                if digest!=front_binding['sha256']: raise CrysV2Error('HELD_EXTERNAL_FOLD_ROOT')
            elif require_dependencies: raise CrysV2Error('HELD_EXTERNAL_FOLD_MISSING')
        if front_data is not None:
            front_header,_,_=fold.parse(front_data)
            mode='EXTERNAL' if reference_data is not None else 'EMBEDDED'
            front_binding=fold.binding(front_header,hashlib.sha256(front_data).hexdigest(),mode)
            if configuration.get('fold_projection')!=front_binding:
                raise CrysV2Error('HELD_CONFIGURATION_FOLD_BINDING')
            if capture_directory is not None:
                descriptor,name=sio.mkstemp(prefix='sf-',suffix='.leg',dir=capture_directory)
                front_path=Path(name)
                with sio.fdopen_output(descriptor,'wb') as output: output.write(front_data)
        elif reference_data is None and configuration.get('fold_projection') is not None: raise CrysV2Error('HELD_FOLD_PROJECTION_MISSING')
        body = next(row for row in records if row["type"] == "BODY")
        if body["sha256"] != header.get("encoded_body_sha256"):
            raise CrysV2Error("HELD_BODY_ROOT")
        glyph_registry=None; glyph=header['glyph_binding']
        if glyph_data is not None:
            if glyph is None or glyph['mode']!='EMBEDDED' or hashlib.sha256(glyph_data).hexdigest()!=glyph['sha256']:
                raise CrysV2Error('HELD_EMBEDDED_GLYPH_CORRESPONDENCE')
            glyph_registry=parse_glyph(glyph_data)
        elif glyph is not None and glyph['mode']=='EMBEDDED': raise CrysV2Error('HELD_EMBEDDED_GLYPH_MISSING')
        elif glyph is not None:
            path=(glyph_resolver or {}).get(glyph['sha256'])
            if path is not None:
                glyph_registry,_,root=load_glyph(path)
                if root!=glyph['sha256']: raise CrysV2Error('HELD_EXTERNAL_GLYPH_ROOT')
            elif require_dependencies: raise CrysV2Error('HELD_EXTERNAL_GLYPH_MISSING')
        if embedded_roots != [row["sha256"] for row in header["legend_bindings"] if row["mode"] == "EMBEDDED"]:
            raise CrysV2Error("HELD_EMBEDDED_LEGEND_CORRESPONDENCE")
        for binding in header.get("legend_bindings", []):
            if binding.get("schema") != "semcrys.legend.binary.v0.2":
                raise CrysV2Error("HELD_LEGEND_BINDING_SCHEMA")
            root = binding.get("sha256")
            if binding.get("mode") == "EMBEDDED":
                if root not in embedded_roots:
                    raise CrysV2Error("HELD_EMBEDDED_LEGEND_MISSING", str(root))
            elif binding.get("mode") == "EXTERNAL":
                if root in resolver:
                    try:
                        verified = LegendReader(resolver[root], max_entries=limits.max_legend_entries).verify()
                    except LegendError as exc:
                        raise CrysV2Error(exc.code, exc.detail) from exc
                    if verified["sha256"] != root:
                        raise CrysV2Error("HELD_EXTERNAL_LEGEND_ROOT")
                elif require_dependencies:
                    raise CrysV2Error("HELD_EXTERNAL_LEGEND_MISSING", str(root))
            else:
                raise CrysV2Error("HELD_INVALID_LEGEND_BINDING")
        success = True
        return {"schema": "semcrys.crys-inspection.v0.2", "status": "PASS", "header": header,
            "sections": records, "manifest": manifest, "file_sha256": whole_file.hexdigest(),
            "configuration": configuration,
            "glyph_registry": glyph_registry,
            "fold_projection": front_header,
            "fold_projection_binding": front_binding,
            "fold_dependency_status": 'RESOLVED' if front_data is not None else ('EXTERNAL_NOT_RESOLVED' if reference_data is not None else 'NOT_APPLICABLE'),
            "fold_projection_path": str(front_path) if front_path is not None else None,
            "embedded_paths": [str(path) for path in temporary_legends] if capture_directory is not None else []}
    finally:
        if not success or capture_directory is None:
            for temporary in temporary_legends:
                sio.unlink(temporary,missing_ok=True)
            if front_path is not None: sio.unlink(front_path,missing_ok=True)
