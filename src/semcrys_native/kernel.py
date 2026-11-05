from __future__ import annotations

import ctypes
import hashlib
import json
import os
import platform
import threading
from array import array
from pathlib import Path
from typing import Callable, Iterable

ABI_VERSION = 2
POLICIES = {"auto", "off", "required"}
DEFAULT_THRESHOLD = 128


class NativeRequiredError(RuntimeError):
    pass


_lock = threading.Lock()
_library = None
_load_attempted = False
_load_reason = "NOT_ATTEMPTED"
_binary_sha256 = None
_manifest = None
_metrics = {
    "pack_calls": 0,
    "pack_values": 0,
    "unpack_calls": 0,
    "unpack_values": 0,
    "parse_calls": 0,
    "parse_events": 0,
    "fold_calls": 0,
    "fold_input_events": 0,
    "fallback_calls": 0,
}


def _policy() -> str:
    value = os.environ.get("SEMCRYS_NATIVE", "auto").strip().lower()
    if value not in POLICIES:
        raise NativeRequiredError("HELD_NATIVE_POLICY")
    return value


def _threshold() -> int:
    try:
        value = int(os.environ.get("SEMCRYS_NATIVE_THRESHOLD", DEFAULT_THRESHOLD))
    except ValueError:
        raise NativeRequiredError("HELD_NATIVE_THRESHOLD") from None
    if value < 1 or value > (1 << 31):
        raise NativeRequiredError("HELD_NATIVE_THRESHOLD")
    return value


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _candidate_names() -> tuple[str, ...]:
    if os.name == "nt":
        return ("semcrys_native.dll",)
    if platform.system() == "Darwin":
        return ("libsemcrys_native.dylib",)
    return ("libsemcrys_native.so",)


def _configure(library) -> None:
    u64p = ctypes.POINTER(ctypes.c_uint64)
    u8p = ctypes.POINTER(ctypes.c_ubyte)
    sizep = ctypes.POINTER(ctypes.c_size_t)
    library.semcrys_native_abi.argtypes = []
    library.semcrys_native_abi.restype = ctypes.c_uint32
    library.semcrys_pack_u63.argtypes = [u64p, ctypes.c_size_t, u8p, ctypes.c_size_t, sizep]
    library.semcrys_pack_u63.restype = ctypes.c_int
    library.semcrys_unpack_u63.argtypes = [u8p, ctypes.c_size_t, u64p, ctypes.c_size_t, sizep]
    library.semcrys_unpack_u63.restype = ctypes.c_int
    library.semcrys_parse_packed_events.argtypes = [
        u8p, ctypes.c_size_t, u64p, u64p, ctypes.c_size_t, sizep,
    ]
    library.semcrys_parse_packed_events.restype = ctypes.c_int
    library.semcrys_fold_pairs.argtypes = [
        u64p, ctypes.c_size_t, u64p, u64p, u64p, ctypes.c_size_t,
        u64p, ctypes.c_size_t, sizep,
    ]
    library.semcrys_fold_pairs.restype = ctypes.c_int


def _load():
    global _library, _load_attempted, _load_reason, _binary_sha256, _manifest
    with _lock:
        if _load_attempted:
            return _library
        _load_attempted = True
        root = Path(__file__).resolve().parent / "_bin"
        for name in _candidate_names():
            for binary in sorted(root.glob(f"*/{name}")) if root.is_dir() else ():
                manifest_path = binary.with_name(binary.name + ".manifest.json")
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    observed = _hash(binary)
                    if manifest.get("schema") != "semcrys.native-build.v0.1":
                        continue
                    if manifest.get("abi_version") != ABI_VERSION or manifest.get("binary_sha256") != observed:
                        continue
                    if manifest.get("system") != platform.system() or manifest.get("machine", "").lower() != platform.machine().lower():
                        continue
                    library = ctypes.CDLL(str(binary))
                    _configure(library)
                    if library.semcrys_native_abi() != ABI_VERSION:
                        continue
                    _library = library
                    _manifest = manifest
                    _binary_sha256 = observed
                    _load_reason = "HASH_BOUND_NATIVE_KERNEL_LOADED"
                    return _library
                except (OSError, ValueError, KeyError, json.JSONDecodeError):
                    continue
        _load_reason = "NO_COMPATIBLE_HASH_BOUND_NATIVE_KERNEL"
        return None


def _selected_library():
    policy = _policy()
    if policy == "off":
        return None
    library = _load()
    if library is None and policy == "required":
        raise NativeRequiredError(_load_reason)
    return library


def _increment(**values: int) -> None:
    with _lock:
        for key, value in values.items():
            _metrics[key] += value


def reset_metrics() -> None:
    with _lock:
        for key in _metrics:
            _metrics[key] = 0


def runtime_status() -> dict:
    library = _load()
    with _lock:
        metrics = dict(_metrics)
    return {
        "schema": "semcrys.native-runtime.v0.1",
        "policy": _policy().upper(),
        "available": library is not None,
        "selected": library is not None and _policy() != "off",
        "abi_version": ABI_VERSION,
        "binary_sha256": _binary_sha256,
        "build_root": _manifest.get("build_root") if _manifest else None,
        "reason": "DISABLED_BY_POLICY" if _policy() == "off" else _load_reason,
        "threshold_events": _threshold(),
        "metrics": metrics,
        "authority_effect": "NONE",
    }


def pack_varints(values: list[int], python_impl: Callable[[list[int]], bytes]) -> bytes:
    if len(values) < _threshold():
        _increment(fallback_calls=1)
        return python_impl(values)
    library = _selected_library()
    if library is None:
        _increment(fallback_calls=1)
        return python_impl(values)
    try:
        source = array("Q", values)
    except (OverflowError, TypeError, ValueError):
        _increment(fallback_calls=1)
        return python_impl(values)
    if source.itemsize != 8:
        _increment(fallback_calls=1)
        return python_impl(values)
    count = len(source)
    source_buffer = (ctypes.c_uint64 * count).from_buffer(source)
    target = (ctypes.c_ubyte * max(1, count * 10))()
    written = ctypes.c_size_t()
    code = library.semcrys_pack_u63(source_buffer, count, target, len(target), ctypes.byref(written))
    if code != 0:
        _increment(fallback_calls=1)
        return python_impl(values)
    _increment(pack_calls=1, pack_values=count)
    return bytes(target[:written.value])


def unpack_varints(data: bytes, python_impl: Callable[[bytes], list[int]]) -> list[int]:
    if len(data) < _threshold():
        _increment(fallback_calls=1)
        return python_impl(data)
    library = _selected_library()
    if library is None:
        _increment(fallback_calls=1)
        return python_impl(data)
    source = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    target = (ctypes.c_uint64 * max(1, len(data)))()
    count = ctypes.c_size_t()
    code = library.semcrys_unpack_u63(source, len(data), target, len(target), ctypes.byref(count))
    if code != 0:
        _increment(fallback_calls=1)
        return python_impl(data)
    _increment(unpack_calls=1, unpack_values=count.value)
    return list(target[:count.value])


def parse_packed_events(data: bytes, python_impl):
    if len(data) < _threshold():
        _increment(fallback_calls=1)
        return python_impl(data)
    library = _selected_library()
    if library is None:
        _increment(fallback_calls=1)
        return python_impl(data)
    source = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    count = ctypes.c_size_t()
    code = library.semcrys_parse_packed_events(source, len(data), None, None, 0, ctypes.byref(count))
    if code != 0:
        _increment(fallback_calls=1)
        return python_impl(data)
    values = array("Q", [0]) * count.value
    lengths = array("Q", [0]) * count.value
    if values.itemsize != 8 or lengths.itemsize != 8:
        _increment(fallback_calls=1)
        return python_impl(data)
    value_buffer = (ctypes.c_uint64 * count.value).from_buffer(values) if count.value else None
    length_buffer = (ctypes.c_uint64 * count.value).from_buffer(lengths) if count.value else None
    code = library.semcrys_parse_packed_events(
        source, len(data), value_buffer, length_buffer, count.value, ctypes.byref(count),
    )
    if code != 0:
        _increment(fallback_calls=1)
        return python_impl(data)
    _increment(parse_calls=1, parse_events=count.value)
    return values, lengths


def fold_pairs(
    events: list[int],
    entries: Iterable[dict],
    python_impl: Callable[[list[int]], list[int]],
) -> list[int]:
    if len(events) < _threshold():
        _increment(fallback_calls=1)
        return python_impl(events)
    library = _selected_library()
    if library is None:
        _increment(fallback_calls=1)
        return python_impl(events)
    try:
        rows = list(entries)
        source = array("Q", events)
        left = array("Q", (row["pair"][0] for row in rows))
        right = array("Q", (row["pair"][1] for row in rows))
        replacements = array("Q", (row["id"] for row in rows))
    except (OverflowError, TypeError, ValueError, KeyError, IndexError):
        _increment(fallback_calls=1)
        return python_impl(events)
    if any(values.itemsize != 8 for values in (source, left, right, replacements)):
        _increment(fallback_calls=1)
        return python_impl(events)
    if not rows:
        return list(events)
    event_count = len(source)
    rule_count = len(rows)
    source_buffer = (ctypes.c_uint64 * event_count).from_buffer(source)
    left_buffer = (ctypes.c_uint64 * rule_count).from_buffer(left)
    right_buffer = (ctypes.c_uint64 * rule_count).from_buffer(right)
    replacement_buffer = (ctypes.c_uint64 * rule_count).from_buffer(replacements)
    target = (ctypes.c_uint64 * max(1, event_count))()
    count = ctypes.c_size_t()
    code = library.semcrys_fold_pairs(
        source_buffer, event_count, left_buffer, right_buffer, replacement_buffer,
        rule_count, target, len(target), ctypes.byref(count),
    )
    if code != 0:
        _increment(fallback_calls=1)
        return python_impl(events)
    _increment(fold_calls=1, fold_input_events=event_count)
    return list(target[:count.value])
