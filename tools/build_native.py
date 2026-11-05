from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "native" / "semcrys_native.c"
ABI_VERSION = 2


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def platform_name() -> tuple[str, str]:
    system = platform.system()
    if system == "Windows":
        return "win_amd64", "semcrys_native.dll"
    if system == "Darwin":
        return "macos_" + platform.machine().lower(), "libsemcrys_native.dylib"
    return "linux_" + platform.machine().lower(), "libsemcrys_native.so"


def select_compiler(explicit: str | None):
    candidates = [explicit] if explicit else (["gcc", "clang", "cc"] if platform.system() != "Windows" else ["gcc", "clang", "cl"])
    for candidate in candidates:
        if candidate and shutil.which(candidate):
            return candidate
    raise RuntimeError("HELD_NATIVE_COMPILER_UNAVAILABLE")


def compiler_version(compiler: str) -> str:
    command = [compiler, "--version"] if Path(compiler).name.lower() != "cl.exe" and compiler.lower() != "cl" else [compiler]
    completed = subprocess.run(command, capture_output=True, text=True)
    text = (completed.stdout or completed.stderr).splitlines()
    return text[0].strip() if text else Path(compiler).name


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler")
    args = parser.parse_args(argv)
    tag, filename = platform_name()
    target_dir = ROOT / "src" / "semcrys_native" / "_bin" / tag
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename
    compiler = select_compiler(args.compiler)
    if Path(compiler).name.lower() == "cl.exe" or compiler.lower() == "cl":
        command = [compiler, "/nologo", "/O2", "/LD", str(SOURCE), "/link", f"/OUT:{target}"]
    elif platform.system() == "Darwin":
        command = [compiler, "-O3", "-std=c11", "-dynamiclib", "-fvisibility=hidden", str(SOURCE), "-o", str(target)]
    else:
        command = [compiler, "-O3", "-std=c11", "-Wall", "-Wextra", "-Werror", "-shared", "-fPIC", "-fvisibility=hidden", "-static-libgcc", "-Wl,--no-insert-timestamp", str(SOURCE), "-o", str(target)]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError("HELD_NATIVE_BUILD_FAILED\n" + completed.stdout + completed.stderr)
    record = {
        "schema": "semcrys.native-build.v0.1",
        "abi_version": ABI_VERSION,
        "system": platform.system(),
        "machine": platform.machine(),
        "platform_tag": tag,
        "compiler": compiler_version(compiler),
        "source_sha256": digest(SOURCE),
        "binary_sha256": digest(target),
        "authority_effect": "NONE",
    }
    record["build_root"] = hashlib.sha256(canonical(record)).hexdigest()
    manifest = target.with_name(target.name + ".manifest.json")
    manifest.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": "PASS", "binary": str(target), **record}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
