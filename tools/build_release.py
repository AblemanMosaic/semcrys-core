from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
VERSION = "0.1.0"
PREFIX = f"semcrys-core-{VERSION}"
FIXED_TIME = (2026, 11, 1, 0, 0, 0)
EXCLUDED = {
    ".git",
    ".pytest_cache",
    ".test-tmp",
    "__pycache__",
    "dist",
    "release-inputs",
    "release-work",
}
EXCLUDED_FILES = {".semcrys-publication.lock"}
ROOT_TEMP_DIRECTORY = re.compile(r"tmp[a-z0-9_]{6,}", re.IGNORECASE)
ULTRA = ROOT / "assets" / "legends" / "ULTRA_FAMILY.mleg"
BOUNDARY = ROOT / "evidence" / "EXACT-ARTIFACT-BOUNDARY.json"


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def info(name, executable=False):
    item = zipfile.ZipInfo(name, FIXED_TIME)
    item.compress_type = zipfile.ZIP_DEFLATED
    item.create_system = 3
    item.external_attr = ((0o755 if executable else 0o644) & 0xFFFF) << 16
    return item


def write_entry(archive, name, data, executable=False):
    archive.writestr(info(name, executable), data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def source_path_excluded(path, relative):
    if path.name in EXCLUDED_FILES or any(part in EXCLUDED for part in relative.parts):
        return True
    if path.suffix in {".pyc", ".pyo"}:
        return True
    if relative.parts and ROOT_TEMP_DIRECTORY.fullmatch(relative.parts[0]):
        return True
    return relative.as_posix() in {
        "assets/legends/ULTRA_FAMILY.crys",
        "assets/legends/ULTRA_FAMILY.mleg",
        "evidence/PUBLICATION-COURT.json",
        "evidence/EXACT-ARTIFACT-BOUNDARY.json",
        "evidence/EXACT-ARTIFACT-BOUNDARY-RECEIPT.json",
    }


def source_files():
    for path in sorted(ROOT.rglob("*")):
        relative = path.relative_to(ROOT)
        if source_path_excluded(path, relative):
            continue
        if not path.is_file():
            continue
        yield path, relative


NATIVE_SUFFIXES = {".dll", ".so", ".dylib"}


def package_files(*, include_native=True):
    for path in sorted((ROOT / "src").rglob("*")):
        relative = path.relative_to(ROOT / "src")
        if not include_native and "_bin" in relative.parts:
            continue
        if path.is_file() and "__pycache__" not in relative.parts and path.suffix not in {".pyc", ".pyo"}:
            yield path, relative


def build_source(path):
    with zipfile.ZipFile(path, "w") as archive:
        for source, relative in source_files():
            write_entry(archive, f"{PREFIX}/{relative.as_posix()}", source.read_bytes())


def build_zipapp(path):
    with zipfile.ZipFile(path, "w") as archive:
        write_entry(archive, "__main__.py", b"from semcrys_core.cli import main\nraise SystemExit(main())\n")
        for source, relative in package_files(include_native=False):
            write_entry(archive, relative.as_posix(), source.read_bytes())


def wheel_hash(data):
    encoded = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
    return f"sha256={encoded}"


def build_wheel(path, *, tag, include_native):
    dist_info = f"semcrys_core-{VERSION}.dist-info"
    rows = []
    with zipfile.ZipFile(path, "w") as archive:
        def add(name, data):
            write_entry(archive, name, data)
            rows.append((name, wheel_hash(data), str(len(data))))
        for source, relative in package_files(include_native=include_native):
            add(relative.as_posix(), source.read_bytes())
        metadata = (
            "Metadata-Version: 2.3\nName: semcrys-core\n"
            f"Version: {VERSION}\nSummary: SemCrys unified compiler and integerization core\n"
            "Requires-Python: >=3.11\nProvides-Extra: secure\n"
            "Requires-Dist: cryptography>=42; extra == 'secure'\nLicense-Expression: Apache-2.0\n\n"
        ).encode()
        wheel = (
            "Wheel-Version: 1.0\nGenerator: semcrys-stdlib-builder\n"
            f"Root-Is-Purelib: {'false' if include_native else 'true'}\nTag: {tag}\n"
        ).encode()
        entry = b"[console_scripts]\nsemcrys-core=semcrys_core.cli:main\nsemcrys=semcrys.cli:main\nsemcrys-lite=semcrys_lite.cli:main\n"
        add(f"{dist_info}/METADATA", metadata)
        add(f"{dist_info}/WHEEL", wheel)
        add(f"{dist_info}/entry_points.txt", entry)
        add(f"{dist_info}/licenses/LICENSE", (ROOT / "LICENSE").read_bytes())
        record_name = f"{dist_info}/RECORD"
        record = "".join(f"{name},{hash_value},{size}\n" for name, hash_value, size in rows) + f"{record_name},,\n"
        write_entry(archive, record_name, record.encode())


def artifact(path, role):
    data = path.read_bytes()
    return {"path": path.name, "role": role, "bytes": len(data), "sha256": digest(data)}


def sidecar(path):
    value = f"{digest(path.read_bytes())}  {path.name}\n"
    path.with_name(path.name + ".sha256").write_text(value, encoding="ascii", newline="\n")


def build_bundle(path, members, manifest_path):
    with zipfile.ZipFile(path, "w") as archive:
        for member in members:
            write_entry(archive, member.name, member.read_bytes())
        write_entry(archive, ULTRA.name, ULTRA.read_bytes())
        write_entry(archive, manifest_path.name, manifest_path.read_bytes())


def write_boundary(paths):
    rows = [
        {
            "destination_path": path.name,
            "required_by": "publisher:release-verification",
            "sha256": digest(path.read_bytes()),
            "source_path": f"dist/{path.name}",
        }
        for path in sorted(paths, key=lambda item: item.name)
    ]
    value = {
        "schema": "codex.exact-artifact-boundary.v1",
        "boundary_id": "SEMCRYS-CORE-0.1.0-PUBLICATION-DIST",
        "artifacts": rows,
        "runner_required_paths": [row["destination_path"] for row in rows],
        "allow_extra_artifacts": False,
        "policy": {
            "maximum_transfers": 1,
            "maximum_invocations": 1,
            "maximum_retries": 0,
            "preserve_prior_custody": True,
            "terminal_capture": ["stdout", "stderr", "exit_code", "terminal_receipt"],
        },
    }
    BOUNDARY.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def load_court(path, schema, artifact_path, *, expected_source_root):
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != schema or value.get("status") != "PASS":
        raise RuntimeError("PLATFORM_COURT_NOT_PASS:" + path.name)
    artifact_hash = digest(artifact_path.read_bytes())
    if artifact_hash not in {row.get("sha256") for row in value.get("builds", [])}:
        raise RuntimeError("PLATFORM_COURT_ARTIFACT_DRIFT:" + path.name)
    if value.get("toolchain", {}).get("source_root") != expected_source_root:
        raise RuntimeError("PLATFORM_COURT_SOURCE_DRIFT:" + path.name)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--linux-standalone",
        type=Path,
        default=ROOT / "release-inputs" / f"semcrys-{VERSION}-linux-x64.tar.gz",
    )
    parser.add_argument(
        "--linux-court",
        type=Path,
        default=ROOT / "evidence" / "LINUX-STANDALONE-COURT.json",
    )
    parser.add_argument(
        "--windows-court",
        type=Path,
        default=ROOT / "evidence" / "WINDOWS-STANDALONE-COURT.json",
    )
    parser.add_argument(
        "--windows-standalone",
        type=Path,
        default=ROOT / "release-inputs" / f"semcrys-{VERSION}-windows-x64.zip",
    )
    args = parser.parse_args(argv)
    release_contract = json.loads((ROOT / "RELEASE_CONTRACT.json").read_text(encoding="utf-8"))
    publication_decision = json.loads((ROOT / "PUBLICATION_DECISION.json").read_text(encoding="utf-8"))
    if (publication_decision.get("decision") != "AUTHORIZED_FOR_GITHUB_PUBLICATION"
            or release_contract.get("publication_authorized") is not True
            or release_contract.get("publication_decision_root") != publication_decision.get("decision_root")):
        raise RuntimeError("PUBLICATION_DECISION_NOT_BOUND")
    linux_input = args.linux_standalone.resolve()
    windows_input = args.windows_standalone.resolve()
    if not linux_input.is_file():
        raise RuntimeError("LINUX_STANDALONE_INPUT_MISSING")
    if not windows_input.is_file():
        raise RuntimeError("WINDOWS_STANDALONE_INPUT_MISSING")
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    source = DIST / f"{PREFIX}-source.zip"
    zipapp = DIST / f"{PREFIX}.pyz"
    wheel = DIST / f"semcrys_core-{VERSION}-py3-none-any.whl"
    build_source(source)
    build_zipapp(zipapp)
    build_wheel(wheel, tag="py3-none-any", include_native=False)
    dist_ultra = DIST / ULTRA.name
    shutil.copyfile(ULTRA, dist_ultra)
    native_binaries = [path for path, _ in package_files(include_native=True) if path.suffix.lower() in NATIVE_SUFFIXES]
    native_wheel = None
    if native_binaries:
        native_manifest = json.loads(native_binaries[0].with_name(native_binaries[0].name + ".manifest.json").read_text(encoding="utf-8"))
        native_tag = "py3-none-" + native_manifest["platform_tag"]
        native_wheel = DIST / f"semcrys_core-{VERSION}-{native_tag}.whl"
        build_wheel(native_wheel, tag=native_tag, include_native=True)
    windows_bundle = DIST / f"semcrys-{VERSION}-windows-x64.zip"
    shutil.copyfile(windows_input, windows_bundle)
    linux_bundle = DIST / f"semcrys-{VERSION}-linux-x64.tar.gz"
    shutil.copyfile(linux_input, linux_bundle)
    linux_court = load_court(
        args.linux_court,
        "semcrys.linux-standalone-court.v0.2",
        linux_bundle,
        expected_source_root=__import__("build_linux_executable").source_root(),
    )
    windows_court = load_court(
        args.windows_court,
        "semcrys.windows-standalone-court.v0.2",
        windows_bundle,
        expected_source_root=__import__("build_windows_executable").source_root(),
    )
    artifacts = [
        artifact(source, "SOURCE_REPOSITORY"),
        artifact(zipapp, "STDLIB_ZIPAPP"),
        artifact(wheel, "PURE_PYTHON_WHEEL"),
    ]
    if native_wheel is not None:
        artifacts.append(artifact(native_wheel, "NATIVE_WHEEL"))
    artifacts.append(artifact(windows_bundle, "STANDALONE_WINDOWS_X64"))
    artifacts.append(artifact(linux_bundle, "STANDALONE_LINUX_X64"))
    artifacts.append(artifact(dist_ultra, "ULTRA_RECURSIVE_METALEGEND_ASSET"))
    manifest = {
        "schema": "semcrys.release-manifest.v0.2",
        "standing": "PUBLICATION_CANDIDATE",
        "version": VERSION,
        "artifacts": artifacts,
        "runtime_dependencies": {"base": [], "secure_profile": ["cryptography>=42"], "native_profile": []},
        "standard_cli": {
            "entry_point": "semcrys",
            "default_profile": "STANDARD_V1",
            "path_first_pack": True,
            "standalone_platforms": [
                "windows_x86_64",
                "linux_x86_64",
            ],
        },
        "standalone_qualification": {
            "windows": windows_court["court_root"],
            "linux": linux_court["court_root"],
            "linux_glibc_floor": linux_court["glibc_floor"],
        },
        "component_qualification": {
            "seekable_metalegend_court_root": release_contract["ultra"]["qualification_court_root"],
            "security_projection_court_root": release_contract["security_projection"]["court_root"],
            "security_projection_standing": "BUILDER_QUALIFICATION_NOT_INDEPENDENT_CRYPTOANALYSIS",
        },
        "security_projection": {
            "lite_profiles": [
                "homophonic", "homophonic-positional", "maximum-concealment",
                "private-balanced", "private-maximum",
            ],
            "protected_artifact_envelope": "semcrys.protected-artifact.v0.1",
            "security_claim": "NONE",
        },
        "native_acceleration": {
            "optional": True,
            "pure_python_fallback": True,
            "abi_version": 2,
            "bundled_platforms": [json.loads(path.with_name(path.name + ".manifest.json").read_text(encoding="utf-8"))["platform_tag"] for path in native_binaries],
        },
        "authority_effect": "NONE",
        "publication_authorized": True,
        "publication_decision_root": publication_decision["decision_root"],
        "verification_status": "SELF_VERIFYING_EXTERNAL_REPLAY_PENDING",
        "formal_external_certification": "NOT_CLAIMED"
    }
    manifest["manifest_root"] = digest(canonical(manifest))
    manifest_path = DIST / "RELEASE-MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    bundle = DIST / f"{PREFIX}-offline-bundle.zip"
    members = [source, zipapp, wheel] + ([native_wheel] if native_wheel is not None else []) + [windows_bundle, linux_bundle]
    build_bundle(bundle, members, manifest_path)
    release_paths = members + [dist_ultra, manifest_path, bundle]
    for path in release_paths:
        sidecar(path)
    boundary_paths = release_paths + [path.with_name(path.name + ".sha256") for path in release_paths]
    write_boundary(boundary_paths)
    result = {"status": "PASS", "manifest_root": manifest["manifest_root"], "bundle": artifact(bundle, "OFFLINE_BUNDLE"), "artifacts": manifest["artifacts"]}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
