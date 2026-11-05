from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .contract import capabilities, profiles, verify_self
from .dispatch import DispatchRefusal, detect_path, inspect_path
from .semantic import SemanticRefusal, build_registry, integerize, restore


def _emit(value) -> None:
    print(json.dumps(value, ensure_ascii=True, sort_keys=True))


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "full":
        from semcrys.cli import main as full_main
        return full_main(argv[1:])
    if argv and argv[0] == "lite":
        from semcrys_lite.cli import main as lite_main
        return lite_main(argv[1:])

    parser = argparse.ArgumentParser(prog="semcrys-core")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("capabilities")
    sub.add_parser("profiles")
    sub.add_parser("native-status")
    verify = sub.add_parser("verify-self")
    verify.add_argument("--asset-root", type=Path)
    detect = sub.add_parser("detect")
    detect.add_argument("source", type=Path)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("source", type=Path)
    semantic = sub.add_parser("semantic").add_subparsers(dest="semantic_command", required=True)
    registry = semantic.add_parser("build-registry")
    registry.add_argument("entries", type=Path)
    registry.add_argument("output", type=Path)
    integer = semantic.add_parser("integerize")
    integer.add_argument("source", type=Path)
    integer.add_argument("registry", type=Path)
    integer.add_argument("output", type=Path)
    integer.add_argument("--bindings", type=Path)
    recover = semantic.add_parser("restore")
    recover.add_argument("source", type=Path)
    recover.add_argument("registry", type=Path)
    recover.add_argument("output", type=Path)
    args = parser.parse_args(argv)

    try:
        if args.command == "capabilities":
            _emit(capabilities())
        elif args.command == "profiles":
            _emit(profiles())
        elif args.command == "native-status":
            from semcrys_native import runtime_status
            _emit(runtime_status())
        elif args.command == "verify-self":
            _emit(verify_self(args.asset_root))
        elif args.command == "detect":
            _emit({"status": "PASS", "dialect": detect_path(args.source)})
        elif args.command == "inspect":
            _emit(inspect_path(args.source))
        elif args.semantic_command == "build-registry":
            value = build_registry(_read_json(args.entries))
            _write_json(args.output, value)
            _emit({"status": "PASS", "registry_root": value["registry_root"], "entries": value["entry_count"]})
        elif args.semantic_command == "integerize":
            value = integerize(args.source.read_bytes(), _read_json(args.registry), _read_json(args.bindings) if args.bindings else None)
            _write_json(args.output, value)
            _emit({"status": "PASS", "stream_root": value["stream_root"], "coverage": 1.0})
        elif args.semantic_command == "restore":
            data = restore(_read_json(args.source), _read_json(args.registry))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(data)
            _emit({"status": "PASS", "bytes": len(data)})
        return 0
    except (OSError, ValueError, DispatchRefusal, SemanticRefusal, RuntimeError) as error:
        _emit({"status": "HELD", "code": str(error), "type": type(error).__name__})
        return 1
