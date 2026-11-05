from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from standalone_custody import canonical_source_root, establish_standalone_custody

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "release-work" / "windows-executable"
VERSION = "0.1.0"
FIXED_TIME = (2026, 11, 1, 0, 0, 0)
PACKAGES = ("semcrys", "semcrys_core", "semcrys_lite", "semcrys_native",
            "streaming_app", "streaming_legend")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()


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


def canonicalize_zip(path: Path) -> None:
    pending = path.with_suffix(path.suffix + ".canonical")
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(pending, "w") as target:
        for name in sorted(source.namelist()):
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.create_system = 3
            info.external_attr = 0o644 << 16
            target.writestr(info, source.read(name), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    os.replace(pending, path)


def build(destination: Path) -> dict:
    if sys.platform != "win32":
        raise RuntimeError("HELD_WINDOWS_EXECUTABLE_REQUIRES_WINDOWS")
    try:
        import PyInstaller  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("HELD_PYINSTALLER_UNAVAILABLE") from exc
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    data_root = WORK / "package-data"
    for package in PACKAGES:
        package_source_root = ROOT / "src" / package
        target_root = data_root / package
        for source in sorted(package_source_root.rglob("*")):
            relative = source.relative_to(package_source_root)
            if not source.is_file() or "__pycache__" in relative.parts or source.suffix == ".pyc":
                continue
            target = target_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    command = [sys.executable, "-B", "-m", "PyInstaller", "--noconfirm", "--clean",
               "--onedir", "--contents-directory", "runtime", "--name", "semcrys",
               "--distpath", str(WORK / "dist"), "--workpath", str(WORK / "build"),
               "--specpath", str(WORK), "--paths", str(ROOT / "src")]
    for package in PACKAGES:
        command.extend(["--collect-all", package])
        command.extend(["--add-data", f"{data_root / package};{package}"])
    command.append(str(ROOT / "tools" / "semcrys_entry.py"))
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["SOURCE_DATE_EPOCH"] = "1793491200"
    completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError("HELD_WINDOWS_EXECUTABLE_BUILD\n" + completed.stdout[-4000:] + completed.stderr[-8000:])

    application = WORK / "dist" / "semcrys"
    exe = application / "semcrys.exe"
    if not exe.is_file():
        raise RuntimeError("HELD_WINDOWS_EXECUTABLE_MISSING")
    canonicalize_zip(application / "runtime" / "base_library.zip")
    shutil.copyfile(ROOT / "assets" / "legends" / "ULTRA_FAMILY.mleg",
                    application / "ULTRA_FAMILY.mleg")
    shutil.copyfile(ROOT / "LICENSE", application / "LICENSE")
    shutil.copyfile(ROOT / "NOTICE", application / "NOTICE")
    (application / "START.BAT").write_text(
        '@echo off\r\nsetlocal\r\ncd /d "%~dp0"\r\nsemcrys.exe --help\r\n',
        encoding="ascii", newline="")
    (application / "README.txt").write_text(
        "SemCrys 0.1.0 standalone Windows CLI\n\n"
        "Run START.BAT for help, or invoke semcrys.exe from PowerShell/cmd.\n"
        "Quick start: semcrys.exe PATH -o ARCHIVE.crys\n"
        "Machine discovery: semcrys.exe --help-json\n"
        "The sibling Ultra asset is pinned for advanced shared-legend workflows.\n"
        "Standard archive encoding is self-contained and is not encryption.\n"
        "See THIRD-PARTY-NOTICES.txt and BUNDLED-RUNTIME.json.\n",
        encoding="utf-8", newline="\n")

    custody = establish_standalone_custody(
        application, platform_id="windows_x86_64"
    )

    rows = []
    for path in sorted(application.rglob("*")):
        if path.is_file():
            rows.append({"path": path.relative_to(application).as_posix(),
                         "bytes": path.stat().st_size, "sha256": sha256(path)})
    manifest = {"schema": "semcrys.windows-standalone-manifest.v0.2",
                "standing": "PUBLICATION_CANDIDATE", "version": VERSION,
                "platform": "windows_x86_64",
                "entry_point": "semcrys.exe",
                "external_runtime_dependencies": [],
                "bundled_runtime": {
                    "manifest": "BUNDLED-RUNTIME.json",
                    "runtime_root": custody["runtime_root"],
                    "secure_profile": custody["bundled_profiles"]["secure"],
                },
                "native_acceleration": {
                    "bundled": True,
                    "fallback": "PURE_PYTHON_REFERENCE",
                },
                "build_identity": {
                    "source_root": source_root(),
                    "python": platform.python_version(),
                    "machine": platform.machine(),
                },
                "ultra_asset": "ULTRA_FAMILY.mleg", "files": rows,
                "security_claim": "BOUNDED_IMPLEMENTED_PROFILE_NO_PROTOCOL_SECURITY_PROOF",
                "authority_effect": "NONE"}
    manifest["manifest_root"] = hashlib.sha256(canonical(manifest)).hexdigest()
    (application / "WINDOWS-MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w") as archive:
        for path in sorted(application.rglob("*")):
            if not path.is_file():
                continue
            relative = Path("semcrys-windows-x64") / path.relative_to(application)
            info = zipfile.ZipInfo(relative.as_posix(), FIXED_TIME)
            info.create_system = 3
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return {"status": "PASS", "output": str(destination), "sha256": sha256(destination),
            "bytes": destination.stat().st_size, "manifest_root": manifest["manifest_root"],
            "runtime_root": custody["runtime_root"],
            "files": len(rows) + 1}


def main(argv=None) -> int:
    arguments = argv or sys.argv[1:]
    destination = Path(arguments[0]).resolve() if arguments else ROOT / "dist" / f"semcrys-{VERSION}-windows-x64.zip"
    print(json.dumps(build(destination), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

