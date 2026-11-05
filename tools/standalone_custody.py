from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import shutil
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode()


def canonical_source_root(root: Path, paths) -> str:
    """Bind source files with host-independent repository path ordering."""
    unique = set(paths)
    rows = [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in sorted(
            unique, key=lambda item: item.relative_to(root).as_posix()
        )
    ]
    return hashlib.sha256(canonical(rows)).hexdigest()


def rooted(value: dict, field: str) -> dict:
    return {**value, field: hashlib.sha256(canonical(value)).hexdigest()}


def _copy_first(candidates: list[Path], destination: Path) -> bool:
    for source in candidates:
        if source.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            return True
    return False


def _distribution_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _copy_distribution_licenses(name: str, destination: Path) -> list[str]:
    try:
        distribution = importlib.metadata.distribution(name)
    except importlib.metadata.PackageNotFoundError:
        return []
    copied = []
    for item in distribution.files or []:
        relative = Path(str(item))
        lowered = relative.name.lower()
        if not any(token in lowered for token in ("license", "copying", "notice")):
            continue
        source = Path(distribution.locate_file(item))
        if not source.is_file():
            continue
        target = destination / name / relative.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        copied.append(target.relative_to(destination.parent).as_posix())
    return sorted(set(copied))


def _copy_system_notices(destination: Path) -> list[str]:
    if not sys.platform.startswith("linux"):
        return []
    python_series = f"python{sys.version_info.major}.{sys.version_info.minor}"
    patterns = (
        f"/usr/share/doc/{python_series}/copyright",
        f"/usr/share/doc/{python_series}-minimal/copyright",
        "/usr/share/doc/python3/copyright",
        "/usr/share/doc/libssl3*/copyright",
        "/usr/share/doc/openssl/copyright",
        "/usr/share/doc/zlib1g/copyright",
        "/usr/share/doc/libbz2-1.0/copyright",
        "/usr/share/doc/liblzma5/copyright",
        "/usr/share/doc/libsqlite3-0/copyright",
        "/usr/share/doc/libexpat1/copyright",
        "/usr/share/doc/libffi8/copyright",
        "/usr/share/doc/libgcc-s1/copyright",
        "/usr/share/doc/libtinfo6/copyright",
    )
    copied = []
    seen = set()
    for pattern in patterns:
        for source in sorted(Path("/").glob(pattern.lstrip("/"))):
            if not source.is_file() or source.resolve() in seen:
                continue
            seen.add(source.resolve())
            package = source.parent.name
            target = destination / "system" / f"{package}-copyright.txt"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            copied.append(target.relative_to(destination.parent).as_posix())
    return sorted(copied)


def _runtime_binary_rows(application: Path) -> list[dict]:
    suffixes = (".dll", ".pyd", ".so", ".dylib")
    rows = []
    for path in sorted(application.rglob("*")):
        if not path.is_file():
            continue
        name = path.name.lower()
        if not (name.endswith(suffixes) or ".so." in name or name.startswith("libpython")):
            continue
        rows.append(
            {
                "path": path.relative_to(application).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    return rows


def establish_standalone_custody(application: Path, *, platform_id: str) -> dict:
    licenses = application / "licenses"
    licenses.mkdir(parents=True, exist_ok=True)
    python_candidates = [
        Path(sys.base_prefix) / "LICENSE.txt",
        Path(sys.base_prefix) / "LICENSE",
        Path(sys.prefix) / "LICENSE.txt",
    ]
    if sys.platform.startswith("linux"):
        python_series = f"python{sys.version_info.major}.{sys.version_info.minor}"
        python_candidates.extend(
            [
                Path("/usr/share/doc") / python_series / "copyright",
                Path("/usr/share/doc") / f"{python_series}-minimal" / "copyright",
                Path("/usr/share/doc/python3/copyright"),
            ]
        )
    python_license = licenses / "PYTHON-LICENSE.txt"
    python_license_present = _copy_first(python_candidates, python_license)
    copied = []
    if python_license_present:
        copied.append(python_license.relative_to(application).as_posix())
    copied.extend(_copy_distribution_licenses("pyinstaller", licenses))
    copied.extend(_copy_distribution_licenses("cryptography", licenses))
    copied.extend(_copy_distribution_licenses("cffi", licenses))
    copied.extend(_copy_system_notices(licenses))

    runtime_rows = _runtime_binary_rows(application)
    bundled_cryptography = any("cryptography" in row["path"] for row in runtime_rows)
    notice = (
        "SemCrys standalone third-party runtime notice\n\n"
        "This standalone application includes a pinned Python runtime and may "
        "include third-party binary libraries discovered by PyInstaller. These "
        "components retain their own licenses; they are not relicensed by the "
        "SemCrys Apache-2.0 notice. Exact runtime files and hashes are recorded "
        "in BUNDLED-RUNTIME.json. Available redistribution notices are under "
        "licenses/.\n\n"
        "The source, wheel, and zipapp profiles remain standard-library-only "
        "unless the optional secure profile is installed. The standalone is a "
        "self-contained distribution and therefore has no separately installed "
        "Python dependency.\n"
    )
    (application / "THIRD-PARTY-NOTICES.txt").write_text(
        notice, encoding="utf-8", newline="\n"
    )
    custody = rooted(
        {
            "schema": "semcrys.bundled-runtime.v0.1",
            "platform": platform_id,
            "python": {
                "implementation": platform.python_implementation(),
                "version": platform.python_version(),
                "license_present": python_license_present,
            },
            "build_tools": {
                "pyinstaller": _distribution_version("pyinstaller"),
            },
            "bundled_profiles": {
                "base": True,
                "secure": bundled_cryptography,
            },
            "external_install_dependencies": [],
            "runtime_binaries": runtime_rows,
            "license_files": sorted(set(copied)),
            "authority_effect": "NONE",
        },
        "runtime_root",
    )
    (application / "BUNDLED-RUNTIME.json").write_text(
        json.dumps(custody, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return custody
