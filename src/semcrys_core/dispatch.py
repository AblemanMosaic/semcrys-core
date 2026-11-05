from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from streaming_legend.crys_v2 import MAGIC as FULL_MAGIC
from semcrys_lite.core import CONTAINER_MAGIC as LITE_MAGIC
from semcrys.recursive_metalegend import MAGIC as WHOLE_METALEGEND_MAGIC
from semcrys.seekable_metalegend import MAGIC as SEEKABLE_METALEGEND_MAGIC
from semcrys.protected_artifact import MAGIC as PROTECTED_ARTIFACT_MAGIC


class DispatchRefusal(RuntimeError):
    pass


def detect_bytes(data: bytes) -> str:
    if data.startswith(FULL_MAGIC):
        return "FULL_CRYS_0_2"
    if data.startswith(LITE_MAGIC):
        return "LITE_CRYS_0_3_BINARY"
    if data.startswith(SEEKABLE_METALEGEND_MAGIC):
        return "SEEKABLE_METALEGEND_0_1"
    if data.startswith(WHOLE_METALEGEND_MAGIC):
        return "WHOLE_STREAM_METALEGEND_0_1"
    if data.startswith(PROTECTED_ARTIFACT_MAGIC):
        return "PROTECTED_ARTIFACT_0_1"
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise DispatchRefusal("HELD_UNKNOWN_SEMCRYS_FORMAT")
    if isinstance(value, dict) and str(value.get("schema", "")).startswith("semcrys-lite.crys.v0."):
        return "LITE_CRYS_0_3_TEXT"
    raise DispatchRefusal("HELD_UNKNOWN_SEMCRYS_FORMAT")


def detect_path(path: Path) -> str:
    return detect_bytes(path.read_bytes())


def inspect_path(path: Path) -> dict[str, Any]:
    dialect = detect_path(path)
    if dialect in {"SEEKABLE_METALEGEND_0_1", "WHOLE_STREAM_METALEGEND_0_1"}:
        from semcrys.metalegend import inspect
        result = inspect(path)
    elif dialect == "PROTECTED_ARTIFACT_0_1":
        from semcrys.protected_artifact import inspect_bytes
        result = inspect_bytes(path.read_bytes())
    elif dialect.startswith("FULL_"):
        from semcrys.artifacts import inspect_artifact
        result = inspect_artifact(path)
    else:
        from semcrys_lite.core import inspect_container
        result = inspect_container(path.read_bytes())
    return {"dialect": dialect, "inspection": result}
