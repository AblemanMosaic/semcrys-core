from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

FORBIDDEN = ("/__pycache__/", ".pyc", "/.git/", "/dist/")
ROOT = Path(__file__).resolve().parent.parent
TEMP_ROOT = ROOT / "release-work" / "release-verification"


def temporary_directory():
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=TEMP_ROOT)


def bind_temp_environment(environment, root):
    bound = dict(environment)
    for name in ("TEMP", "TMP", "TMPDIR"):
        bound[name] = str(root)
    return bound


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, code):
    if not condition:
        raise RuntimeError(code)


def inspect_zip(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "ZIP_DUPLICATE_MEMBER")
        for name in names:
            relative = PurePosixPath(name)
            require(
                not relative.is_absolute()
                and ".." not in relative.parts
                and "\\" not in name,
                f"UNSAFE_ZIP_MEMBER:{name}",
            )
            normalized = "/" + name.replace("\\", "/")
            require(not any(token in normalized for token in FORBIDDEN), f"FORBIDDEN_ARCHIVE_MEMBER:{name}")
        bad = archive.testzip()
        require(bad is None, f"ZIP_CRC:{bad}")
        return names


def safe_extract_zip(path, root):
    inspect_zip(path)
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            relative = PurePosixPath(info.filename)
            target = root.joinpath(*relative.parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as destination:
                while block := source.read(1024 * 1024):
                    destination.write(block)


def inspect_tar(path):
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        require(len(names) == len(set(names)), "TAR_DUPLICATE_MEMBER")
        roots = set()
        for member in members:
            relative = PurePosixPath(member.name)
            require(
                not relative.is_absolute()
                and ".." not in relative.parts
                and "\\" not in member.name,
                f"UNSAFE_TAR_MEMBER:{member.name}",
            )
            require(member.isfile() or member.isdir(), f"TAR_UNSAFE_TYPE:{member.name}")
            if relative.parts:
                roots.add(relative.parts[0])
        require(roots == {"semcrys-linux-x64"}, "LINUX_ARCHIVE_ROOT")
        return names


def safe_extract_tar(path, root):
    inspect_tar(path)
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            relative = PurePosixPath(member.name)
            target = root.joinpath(*relative.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            source = archive.extractfile(member)
            require(source is not None, f"TAR_FILE_UNREADABLE:{member.name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with source, target.open("wb") as destination:
                while block := source.read(1024 * 1024):
                    destination.write(block)
            target.chmod(member.mode & 0o777)


def verify_rooted_json(path, root_field, schema):
    value = json.loads(path.read_text(encoding="utf-8"))
    require(value.get("schema") == schema, f"SCHEMA:{path.name}")
    subject = dict(value)
    claimed = subject.pop(root_field)
    encoded = json.dumps(
        subject, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode()
    require(hashlib.sha256(encoded).hexdigest() == claimed, f"ROOT:{path.name}")
    return value


def verify_standalone_manifest(application, manifest_name, schema):
    manifest_path = application / manifest_name
    require(manifest_path.is_file(), f"STANDALONE_MANIFEST_MISSING:{manifest_name}")
    manifest = verify_rooted_json(manifest_path, "manifest_root", schema)
    expected = {manifest_name}
    for row in manifest["files"]:
        relative = PurePosixPath(row["path"])
        require(
            not relative.is_absolute() and ".." not in relative.parts,
            "STANDALONE_MEMBER_PATH",
        )
        member = application.joinpath(*relative.parts)
        require(member.is_file(), "STANDALONE_MEMBER_MISSING:" + row["path"])
        require(
            member.stat().st_size == row["bytes"] and sha256(member) == row["sha256"],
            "STANDALONE_MEMBER_DRIFT:" + row["path"],
        )
        expected.add(row["path"])
    actual = {
        item.relative_to(application).as_posix()
        for item in application.rglob("*")
        if item.is_file()
    }
    require(actual == expected, "STANDALONE_MEMBER_EXTRAS")
    custody = application / manifest["bundled_runtime"]["manifest"]
    custody_value = verify_rooted_json(
        custody, "runtime_root", "semcrys.bundled-runtime.v0.1"
    )
    require(
        custody_value["runtime_root"] == manifest["bundled_runtime"]["runtime_root"],
        "STANDALONE_RUNTIME_ROOT",
    )
    require((application / "THIRD-PARTY-NOTICES.txt").is_file(), "STANDALONE_NOTICES")
    require(custody_value["python"]["license_present"] is True, "PYTHON_LICENSE_MISSING")
    return manifest


def exercise_standalone(executable, application, root, platform_name):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env = bind_temp_environment(env, root)
    help_run = subprocess.run(
        [str(executable), "--help-json"],
        cwd=application,
        env=env,
        capture_output=True,
        text=True,
    )
    require(
        help_run.returncode == 0
        and json.loads(help_run.stdout).get("schema")
        == "semcrys.installed-capability-surface.v0.1",
        platform_name + "_EXECUTABLE_HELP",
    )
    fixture = root / "fixture.txt"
    fixture.write_text("standalone semantic replay\n", encoding="utf-8")
    archive_path = root / "fixture.crys"
    restored = root / "restored"
    packed = subprocess.run(
        [
            str(executable),
            "--progress",
            "quiet",
            "pack",
            str(fixture),
            "-o",
            str(archive_path),
            "--no-cache",
            "--workers",
            "1",
        ],
        cwd=application,
        env=env,
        capture_output=True,
        text=True,
    )
    require(
        packed.returncode == 0 and json.loads(packed.stdout).get("verified") is True,
        platform_name + "_EXECUTABLE_PACK",
    )
    verified = subprocess.run(
        [str(executable), "--progress", "quiet", "verify", str(archive_path)],
        cwd=application,
        env=env,
        capture_output=True,
        text=True,
    )
    require(verified.returncode == 0, platform_name + "_EXECUTABLE_VERIFY")
    unpacked = subprocess.run(
        [
            str(executable),
            "--progress",
            "quiet",
            "unpack",
            str(archive_path),
            str(restored),
        ],
        cwd=application,
        env=env,
        capture_output=True,
        text=True,
    )
    require(
        unpacked.returncode == 0
        and (restored / "fixture.txt").read_bytes() == fixture.read_bytes(),
        platform_name + "_EXECUTABLE_UNPACK",
    )
    return "PACK_VERIFY_UNPACK_PASS"


def run_json(python_path, arguments, extra_env=None):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(python_path)
    env.update(extra_env or {})
    completed = subprocess.run([sys.executable, "-B", *arguments], capture_output=True, text=True, env=env)
    require(completed.returncode == 0, "PACKAGED_EXECUTION")
    payload = json.loads(completed.stdout)
    return payload


def verify_windows_bundle(path):
    with temporary_directory() as directory:
        root = Path(directory)
        safe_extract_zip(path, root)
        application = root / "semcrys-windows-x64"
        manifest = verify_standalone_manifest(
            application,
            "WINDOWS-MANIFEST.json",
            "semcrys.windows-standalone-manifest.v0.2",
        )
        if platform.system() != "Windows":
            return "STRUCTURE_ONLY_FOREIGN_PLATFORM"
        executable = application / manifest["entry_point"]
        return exercise_standalone(executable, application, root, "WINDOWS")


def verify_linux_bundle(path):
    with temporary_directory() as directory:
        root = Path(directory)
        safe_extract_tar(path, root)
        application = root / "semcrys-linux-x64"
        manifest = verify_standalone_manifest(
            application,
            "LINUX-MANIFEST.json",
            "semcrys.linux-standalone-manifest.v0.2",
        )
        require(
            manifest["glibc"]["required"]
            in manifest["external_runtime_dependencies"][0],
            "LINUX_GLIBC_DECLARATION",
        )
        if platform.system() != "Linux" or platform.machine().lower() not in (
            "x86_64",
            "amd64",
        ):
            return "STRUCTURE_ONLY_FOREIGN_PLATFORM"
        executable = application / manifest["entry_point"]
        return exercise_standalone(executable, application, root, "LINUX")


def main(argv=None):
    manifest_path = Path((argv or sys.argv[1:])[0]).resolve()
    base = manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = manifest["version"]
    subject = dict(manifest)
    claimed = subject.pop("manifest_root")
    canonical = json.dumps(subject, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    require(hashlib.sha256(canonical).hexdigest() == claimed, "MANIFEST_ROOT")
    checked = []
    ultra = None
    windows_status = "NOT_PRESENT"
    linux_status = "NOT_PRESENT"
    for row in manifest["artifacts"]:
        path = base / row["path"]
        require(path.is_file(), f"MISSING:{row['path']}")
        require(path.stat().st_size == row["bytes"], f"SIZE:{row['path']}")
        require(sha256(path) == row["sha256"], f"HASH:{row['path']}")
        if path.suffix in {".zip", ".whl", ".pyz"}:
            inspect_zip(path)
        if row["role"] == "STANDALONE_LINUX_X64":
            inspect_tar(path)
        if row["role"] == "ULTRA_RECURSIVE_METALEGEND_ASSET":
            ultra = path
        if row["role"] == "STANDALONE_WINDOWS_X64":
            windows_status = verify_windows_bundle(path)
        if row["role"] == "STANDALONE_LINUX_X64":
            linux_status = verify_linux_bundle(path)
        checked.append(row["path"])

    zipapp = next(base / row["path"] for row in manifest["artifacts"] if row["role"] == "STDLIB_ZIPAPP")
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run([sys.executable, "-B", str(zipapp), "capabilities"], capture_output=True, text=True, env=env)
    require(completed.returncode == 0, "ZIPAPP_EXECUTION")
    payload = json.loads(completed.stdout)
    require(payload.get("schema") == "semcrys.core-capabilities.v0.2", "ZIPAPP_CAPABILITIES")

    source = next(base / row["path"] for row in manifest["artifacts"] if row["role"] == "SOURCE_REPOSITORY")
    with temporary_directory() as directory:
        child_temp = Path(directory) / "child-temp"
        child_temp.mkdir()
        child_env = bind_temp_environment(env, child_temp)
        extracted = Path(directory) / "source"
        safe_extract_zip(source, extracted)
        source_root = extracted / f"semcrys-core-{version}"
        require((source_root / "src" / "semcrys_core" / "cli.py").is_file(), "SOURCE_LAYOUT")
        source_payload = run_json(source_root / "src", ["-m", "semcrys_core", "capabilities"])
        require(source_payload.get("schema") == "semcrys.core-capabilities.v0.2", "SOURCE_CAPABILITIES")

        installed = Path(directory) / "installed"
        wheel = next(base / row["path"] for row in manifest["artifacts"] if row["role"] == "PURE_PYTHON_WHEEL")
        install = subprocess.run([sys.executable, "-B", "-m", "pip", "install", "--no-deps", "--disable-pip-version-check", "--target", str(installed), str(wheel)], capture_output=True, text=True, env=child_env)
        require(install.returncode == 0, "WHEEL_INSTALL")
        wheel_payload = run_json(installed, ["-m", "semcrys_core", "capabilities"])
        pure_status = run_json(installed, ["-m", "semcrys_core", "native-status"])
        require(pure_status.get("available") is False and pure_status.get("selected") is False, "PURE_WHEEL_NATIVE_LEAK")
        require(source_payload["capability_root"] == wheel_payload["capability_root"] == payload["capability_root"], "PACKAGED_CAPABILITY_DRIFT")

        native_rows = [row for row in manifest["artifacts"] if row["role"] == "NATIVE_WHEEL"]
        native_rehearsal = "NOT_PRESENT"
        if native_rows:
            native_wheel = base / native_rows[0]["path"]
            compatible = platform.system() == "Windows" and "win_amd64" in native_wheel.name
            if compatible:
                native_installed = Path(directory) / "native-installed"
                install = subprocess.run([sys.executable, "-B", "-m", "pip", "install", "--no-deps", "--disable-pip-version-check", "--target", str(native_installed), str(native_wheel)], capture_output=True, text=True, env=child_env)
                require(install.returncode == 0, "NATIVE_WHEEL_INSTALL")
                native_payload = run_json(native_installed, ["-m", "semcrys_core", "capabilities"])
                native_status = run_json(native_installed, ["-m", "semcrys_core", "native-status"], {"SEMCRYS_NATIVE": "required"})
                require(native_status.get("available") is True and native_status.get("selected") is True, "NATIVE_WHEEL_NOT_SELECTED")
                require(native_payload["capability_root"] == payload["capability_root"], "NATIVE_CAPABILITY_DRIFT")
                native_rehearsal = "PASS"
            else:
                native_rehearsal = "STRUCTURE_ONLY_FOREIGN_PLATFORM"

    bundle = base / f"semcrys-core-{version}-offline-bundle.zip"
    require(bundle.is_file(), "BUNDLE_MISSING")
    names = inspect_zip(bundle)
    require("ULTRA_FAMILY.mleg" in names and "RELEASE-MANIFEST.json" in names, "BUNDLE_CUSTODY")
    with temporary_directory() as directory:
        safe_extract_zip(bundle, Path(directory))
        extracted = Path(directory) / "ULTRA_FAMILY.mleg"
        require(ultra is not None and sha256(extracted) == sha256(ultra), "BUNDLE_ULTRA_ROOT")

    result = {"status": "PASS", "manifest_root": claimed, "checked": checked, "source_rehearsal": "PASS", "pure_wheel_install_rehearsal": "PASS", "native_wheel_install_rehearsal": native_rehearsal, "standalone_windows_rehearsal": windows_status, "standalone_linux_rehearsal": linux_status, "zipapp_capability_root": payload["capability_root"], "authority_effect": "NONE"}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, RuntimeError, zipfile.BadZipFile) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, indent=2, sort_keys=True))
        raise SystemExit(1)
