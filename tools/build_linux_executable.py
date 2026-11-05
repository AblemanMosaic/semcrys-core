"""Build the deterministic standalone Linux x86-64 CLI."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

from standalone_custody import (
    canonical,
    canonical_source_root,
    establish_standalone_custody,
    sha256,
)

ROOT = Path(__file__).resolve().parent.parent
VERSION = "0.1.0"
FIXED_TIME = (2026, 11, 1, 0, 0, 0)
FIXED_EPOCH = 1793491200
PACKAGES = (
    "semcrys",
    "semcrys_core",
    "semcrys_lite",
    "semcrys_native",
    "streaming_app",
    "streaming_legend",
)
GLIBC_PATTERN = re.compile(rb"GLIBC_([0-9]+(?:[.][0-9]+)+)")


def canonicalize_zip(path: Path) -> None:
    pending = path.with_suffix(path.suffix + ".canonical")
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(pending, "w") as target:
        for name in sorted(source.namelist()):
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.create_system = 3
            info.external_attr = 0o644 << 16
            target.writestr(
                info,
                source.read(name),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )
    os.replace(pending, path)


def _version_key(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def required_glibc(application: Path) -> dict:
    rows = []
    for path in sorted(application.rglob("*")):
        if not path.is_file():
            continue
        versions = {
            match.group(1).decode("ascii")
            for match in GLIBC_PATTERN.finditer(path.read_bytes())
        }
        if versions:
            rows.append(
                {
                    "path": path.relative_to(application).as_posix(),
                    "maximum_symbol": max(versions, key=_version_key),
                }
            )
    if not rows:
        raise RuntimeError("HELD_LINUX_EXECUTABLE_GLIBC_SYMBOLS_UNKNOWN")
    return {
        "required": max(
            (row["maximum_symbol"] for row in rows), key=_version_key
        ),
        "files": rows,
    }


def source_root() -> str:
    paths = [
        path
        for path in (ROOT / "src").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    ]
    paths.extend([
        ROOT / "tools" / "semcrys_entry.py",
        ROOT / "tools" / "standalone_custody.py",
        Path(__file__).resolve(),
        ROOT / "LICENSE",
        ROOT / "NOTICE",
        ROOT / "assets" / "legends" / "ULTRA_FAMILY.mleg",
    ])
    return canonical_source_root(ROOT, paths)


def _remove_foreign_native_payload(application: Path) -> None:
    foreign = application / "runtime" / "semcrys_native" / "_bin" / "win_amd64"
    if foreign.exists():
        shutil.rmtree(foreign)


def build(destination: Path, work: Path) -> dict:
    if not sys.platform.startswith("linux"):
        raise RuntimeError("HELD_LINUX_EXECUTABLE_REQUIRES_LINUX")
    if platform.machine().lower() not in ("x86_64", "amd64"):
        raise RuntimeError("HELD_LINUX_EXECUTABLE_REQUIRES_X86_64")
    try:
        import PyInstaller
    except ImportError as exc:
        raise RuntimeError("HELD_PYINSTALLER_UNAVAILABLE") from exc

    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    data_root = work / "package-data"
    for package in PACKAGES:
        source_root_path = ROOT / "src" / package
        target_root = data_root / package
        for source in sorted(source_root_path.rglob("*")):
            relative = source.relative_to(source_root_path)
            if (
                not source.is_file()
                or "__pycache__" in relative.parts
                or source.suffix == ".pyc"
                or (package == "semcrys_native" and "win_amd64" in relative.parts)
            ):
                continue
            target = target_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

    command = [
        sys.executable,
        "-B",
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--contents-directory",
        "runtime",
        "--name",
        "semcrys",
        "--exclude-module",
        "readline",
        "--exclude-module",
        "rlcompleter",
        "--distpath",
        str(work / "dist"),
        "--workpath",
        str(work / "build"),
        "--specpath",
        str(work),
        "--paths",
        str(ROOT / "src"),
    ]
    for package in PACKAGES:
        command.extend(["--collect-all", package])
        command.extend(
            ["--add-data", f"{data_root / package}{os.pathsep}{package}"]
        )
    command.append(str(ROOT / "tools" / "semcrys_entry.py"))
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["SOURCE_DATE_EPOCH"] = str(FIXED_EPOCH)
    completed = subprocess.run(
        command, cwd=ROOT, env=env, capture_output=True, text=True
    )
    if completed.returncode:
        raise RuntimeError(
            "HELD_LINUX_EXECUTABLE_BUILD\n"
            + completed.stdout[-4000:]
            + completed.stderr[-8000:]
        )

    application = work / "dist" / "semcrys"
    launcher = application / "semcrys"
    if not launcher.is_file():
        raise RuntimeError("HELD_LINUX_EXECUTABLE_MISSING")
    base_library = application / "runtime" / "base_library.zip"
    if base_library.is_file():
        canonicalize_zip(base_library)
    _remove_foreign_native_payload(application)
    if any(path.name.startswith("libreadline") for path in application.rglob("*")):
        raise RuntimeError("HELD_LINUX_EXECUTABLE_READLINE_BUNDLED")

    shutil.copyfile(
        ROOT / "assets" / "legends" / "ULTRA_FAMILY.mleg",
        application / "ULTRA_FAMILY.mleg",
    )
    shutil.copyfile(ROOT / "LICENSE", application / "LICENSE")
    shutil.copyfile(ROOT / "NOTICE", application / "NOTICE")
    (application / "START.sh").write_text(
        '#!/bin/sh\ncd "$(dirname "$0")"\nexec ./semcrys --help\n',
        encoding="ascii",
        newline="\n",
    )
    custody = establish_standalone_custody(
        application, platform_id="linux_x86_64"
    )
    glibc = required_glibc(application)
    host_libc = platform.libc_ver()
    build_identity = {
        "source_root": source_root(),
        "python": platform.python_version(),
        "pyinstaller": PyInstaller.__version__,
        "machine": platform.machine(),
        "host_libc": {"name": host_libc[0], "version": host_libc[1]},
    }
    (application / "README.txt").write_text(
        "SemCrys 0.1.0 standalone Linux x86-64 CLI\n\n"
        "Run ./START.sh for help, or invoke ./semcrys from a shell.\n"
        "Quick start: ./semcrys PATH -o ARCHIVE.crys\n"
        "Machine discovery: ./semcrys --help-json\n"
        "The sibling Ultra asset is pinned for shared-legend workflows.\n"
        "Standard archive encoding is self-contained and is not encryption.\n"
        f"Requires glibc {glibc['required']} or newer; no installed Python is required.\n"
        "See THIRD-PARTY-NOTICES.txt and BUNDLED-RUNTIME.json.\n",
        encoding="utf-8",
        newline="\n",
    )

    rows = []
    for path in sorted(application.rglob("*")):
        if path.is_file():
            rows.append(
                {
                    "path": path.relative_to(application).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    manifest = {
        "schema": "semcrys.linux-standalone-manifest.v0.2",
        "standing": "PUBLICATION_CANDIDATE",
        "version": VERSION,
        "platform": "linux_x86_64",
        "entry_point": "semcrys",
        "external_runtime_dependencies": [f"glibc>={glibc['required']}"],
        "bundled_runtime": {
            "manifest": "BUNDLED-RUNTIME.json",
            "runtime_root": custody["runtime_root"],
            "secure_profile": custody["bundled_profiles"]["secure"],
        },
        "native_acceleration": {
            "bundled": False,
            "fallback": "PURE_PYTHON_REFERENCE",
        },
        "glibc": glibc,
        "build_identity": build_identity,
        "ultra_asset": "ULTRA_FAMILY.mleg",
        "files": rows,
        "security_claim": "BOUNDED_IMPLEMENTED_PROFILE_NO_PROTOCOL_SECURITY_PROOF",
        "authority_effect": "NONE",
    }
    manifest["manifest_root"] = hashlib.sha256(canonical(manifest)).hexdigest()
    (application / "LINUX-MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    executable_names = {"semcrys", "START.sh"}
    destination.parent.mkdir(parents=True, exist_ok=True)
    pending = destination.with_suffix(destination.suffix + ".pending")
    with pending.open("wb") as raw:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9
        ) as gz:
            with tarfile.open(
                fileobj=gz, mode="w", format=tarfile.USTAR_FORMAT
            ) as archive:
                directories = sorted(
                    {
                        (
                            Path("semcrys-linux-x64")
                            / path.relative_to(application)
                        ).parent
                        for path in application.rglob("*")
                        if path.is_file()
                    },
                    key=lambda path: path.as_posix(),
                )
                emitted = set()
                for directory in directories:
                    for ancestor in reversed([directory, *directory.parents]):
                        name = ancestor.as_posix()
                        if name in (".", "") or name in emitted:
                            continue
                        info = tarfile.TarInfo(name)
                        info.type = tarfile.DIRTYPE
                        info.mode = 0o755
                        info.mtime = FIXED_EPOCH
                        info.uid = info.gid = 0
                        info.uname = info.gname = ""
                        archive.addfile(info)
                        emitted.add(name)
                for path in sorted(application.rglob("*")):
                    if not path.is_file():
                        continue
                    relative = Path("semcrys-linux-x64") / path.relative_to(application)
                    info = tarfile.TarInfo(relative.as_posix())
                    info.size = path.stat().st_size
                    info.mode = 0o755 if path.name in executable_names else 0o644
                    info.mtime = FIXED_EPOCH
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    with path.open("rb") as stream:
                        archive.addfile(info, stream)
    os.replace(pending, destination)
    return {
        "status": "PASS",
        "output": str(destination),
        "sha256": sha256(destination),
        "bytes": destination.stat().st_size,
        "manifest_root": manifest["manifest_root"],
        "runtime_root": custody["runtime_root"],
        "glibc_floor": glibc["required"],
        "files": len(rows) + 1,
    }


def main(argv=None) -> int:
    arguments = argv or sys.argv[1:]
    destination = (
        Path(arguments[0]).resolve()
        if arguments
        else ROOT / "dist" / f"semcrys-{VERSION}-linux-x64.tar.gz"
    )
    work = (
        Path(arguments[1]).resolve()
        if len(arguments) > 1
        else ROOT / "release-work" / "linux-executable"
    )
    print(json.dumps(build(destination, work), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
