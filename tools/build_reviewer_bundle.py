from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import zipfile


ROOT = Path(__file__).resolve().parent.parent
VERSION = "0.1.0"
REVISION = "R9"
FIXED_TIME = (2026, 11, 5, 0, 0, 0)
PREFIX = f"SemCrys-Core-{VERSION}-REVIEWER-CANDIDATE-20261105-{REVISION}"


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, code: str) -> None:
    if not condition:
        raise RuntimeError(code)


def entry(name: str, data: bytes) -> tuple[str, bytes]:
    relative = PurePosixPath(name)
    require(not relative.is_absolute() and ".." not in relative.parts, "REVIEWER_PATH")
    return relative.as_posix(), data


def reviewer_readme() -> bytes:
    return f"""# SemCrys Core {VERSION} Replacement Reviewer Candidate {REVISION}

This bounded companion carries the exact source candidate, zipapp, wheels,
seekable recursive Ultra metalegend, and current qualification courts. The
Windows and Linux standalones remain separate release assets and are bound by
the included release manifest and platform-court roots.

## Review

1. Run `VERIFY.BAT`, or `python -B verify_reviewer_bundle.py`.
2. Run `RUN-COURT.BAT`, or `python -B run_reviewer_court.py`.
3. Inspect `evidence/ULTRA-SEEKABLE-METALEGEND-COURT.json`,
   `evidence/SECURITY-PROJECTION-COURT.json`, and the release contract.

The court extracts the shipped source into a bounded temporary directory,
mounts the shipped `ULTRA_FAMILY.mleg`, and replays the publication court. No
network is used. The seekable asset restores the 54,102,082-byte Ultra legend
exactly, occupies 23,632,901 bytes, and supports rooted local-ID lookup without
whole-legend restoration.

The security court qualifies exact inverse, frequency-balanced aliases,
sample-adjusted alias correlation, independently selectable position projection,
bounded bigram/trigram shuffled-null gates, count/size classes, randomized
protected state, tamper refusal, complete group-artifact protection, and key
rotation without source re-encoding. The position result is fixture- and
metric-bounded; it is not independent cryptanalysis or a protocol proof.

## Standing

This is a locally qualified replacement candidate. It has no publication,
authority, semantic-identity, or security-certification effect. Publication
and public-history replacement remain held for an explicit human decision.
""".encode("utf-8")


def verifier_source() -> bytes:
    return b'''from __future__ import annotations
import hashlib, json
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "REVIEWER-CONTENTS.json"

def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

value = json.loads(MANIFEST.read_text(encoding="utf-8"))
subject = dict(value)
claimed = subject.pop("manifest_root")
root = hashlib.sha256(json.dumps(subject, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
failures = [] if root == claimed else [{"path": "REVIEWER-CONTENTS.json", "failure": "MANIFEST_ROOT"}]
declared = set()
declared_names = set()
for row in value["artifacts"]:
    name = row.get("path")
    relative = PurePosixPath(name) if isinstance(name, str) else PurePosixPath(".")
    safe = (isinstance(name, str) and bool(name) and "\\\\" not in name
            and not relative.is_absolute() and ".." not in relative.parts
            and name not in declared_names)
    if not safe:
        failures.append({"path": name, "failure": "UNSAFE_OR_DUPLICATE_PATH"})
        continue
    declared_names.add(name)
    path = (ROOT / relative.as_posix()).resolve()
    if not path.is_relative_to(ROOT) or path.is_symlink():
        failures.append({"path": name, "failure": "BOUNDARY_OR_LINK"})
        continue
    declared.add(path)
    if not path.is_file():
        failures.append({"path": row["path"], "failure": "MISSING"})
    elif path.stat().st_size != row["bytes"]:
        failures.append({"path": row["path"], "failure": "BYTES"})
    elif sha(path) != row["sha256"]:
        failures.append({"path": row["path"], "failure": "SHA256"})
actual = {p.resolve() for p in ROOT.rglob("*") if p.is_file() and not p.is_symlink() and p.resolve() != MANIFEST.resolve()}
for link in sorted(p for p in ROOT.rglob("*") if p.is_symlink()):
    failures.append({"path": link.relative_to(ROOT).as_posix(), "failure": "LINK_REFUSED"})
for path in sorted(actual - declared):
    failures.append({"path": path.relative_to(ROOT).as_posix(), "failure": "UNDECLARED"})
print(json.dumps({"status": "PASS" if not failures else "FAIL", "manifest_root": claimed, "artifacts": len(value["artifacts"]), "failures": failures}, indent=2, sort_keys=True))
raise SystemExit(0 if not failures else 1)
'''


def court_source() -> bytes:
    return b'''from __future__ import annotations
import json, os, shutil, subprocess, sys, tempfile, zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent
manifest = json.loads((ROOT / "release" / "RELEASE-MANIFEST.json").read_text(encoding="utf-8"))
source_name = next(row["path"] for row in manifest["artifacts"] if row["role"] == "SOURCE_REPOSITORY")
with tempfile.TemporaryDirectory(prefix=".reviewer-work-", dir=ROOT) as directory:
    scratch = Path(directory)
    with zipfile.ZipFile(ROOT / "release" / source_name) as archive:
        names = set()
        for member in archive.infolist():
            path = PurePosixPath(member.filename)
            if member.is_dir():
                continue
            mode = (member.external_attr >> 16) & 0o170000
            if (path.is_absolute() or ".." in path.parts or "\\\\" in member.filename
                    or member.filename in names or mode not in {0, 0o100000}):
                raise SystemExit("REVIEWER_SOURCE_ARCHIVE_UNSAFE")
            names.add(member.filename)
            target = scratch.joinpath(*path.parts).resolve()
            if not target.is_relative_to(scratch):
                raise SystemExit("REVIEWER_SOURCE_ARCHIVE_BOUNDARY")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(member))
    source = scratch / f"semcrys-core-{manifest['version']}"
    asset_root = source / "assets" / "legends"
    asset_root.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "release" / "ULTRA_FAMILY.mleg", asset_root / "ULTRA_FAMILY.mleg")
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(source / "src")
    env["TEMP"] = str(scratch)
    env["TMP"] = str(scratch)
    completed = subprocess.run([sys.executable, "-B", "tools/run_publication_court.py"], cwd=source, env=env)
raise SystemExit(completed.returncode)
'''


def source_entries(dist: Path) -> list[tuple[str, bytes]]:
    paths = {
        "docs/DOCUMENTATION_MANIFEST.json": ROOT / "docs" / "DOCUMENTATION_MANIFEST.json",
        "evidence/LINUX-STANDALONE-COURT.json": ROOT / "evidence" / "LINUX-STANDALONE-COURT.json",
        "evidence/PUBLICATION-COURT.json": ROOT / "evidence" / "PUBLICATION-COURT.json",
        "evidence/SECURITY-PROJECTION-COURT.json": ROOT / "evidence" / "SECURITY-PROJECTION-COURT.json",
        "evidence/ULTRA-SEEKABLE-METALEGEND-COURT.json": ROOT / "evidence" / "ULTRA-SEEKABLE-METALEGEND-COURT.json",
        "evidence/WINDOWS-STANDALONE-COURT.json": ROOT / "evidence" / "WINDOWS-STANDALONE-COURT.json",
        "release/RELEASE-MANIFEST.json": dist / "RELEASE-MANIFEST.json",
        "release/RELEASE_CONTRACT.json": ROOT / "RELEASE_CONTRACT.json",
        "release/ULTRA_FAMILY.mleg": dist / "ULTRA_FAMILY.mleg",
        "release/semcrys-core-0.1.0-source.zip": dist / "semcrys-core-0.1.0-source.zip",
        "release/semcrys-core-0.1.0.pyz": dist / "semcrys-core-0.1.0.pyz",
        "release/semcrys_core-0.1.0-py3-none-any.whl": dist / "semcrys_core-0.1.0-py3-none-any.whl",
        "release/semcrys_core-0.1.0-py3-none-win_amd64.whl": dist / "semcrys_core-0.1.0-py3-none-win_amd64.whl",
    }
    rows = [
        entry("README.md", reviewer_readme()),
        entry("RUN-COURT.BAT", b"@echo off\r\npython -B run_reviewer_court.py\r\nexit /b %errorlevel%\r\n"),
        entry("VERIFY.BAT", b"@echo off\r\npython -B verify_reviewer_bundle.py\r\nexit /b %errorlevel%\r\n"),
        entry("run_reviewer_court.py", court_source()),
        entry("verify_reviewer_bundle.py", verifier_source()),
    ]
    for name, path in paths.items():
        require(path.is_file(), "REVIEWER_INPUT_MISSING:" + name)
        rows.append(entry(name, path.read_bytes()))
    return sorted(rows)


def build_bytes(dist: Path) -> tuple[bytes, dict]:
    rows = source_entries(dist)
    manifest = {
        "schema": "semcrys.reviewer-bundle-contents.v0.3",
        "standing": "REPLACEMENT_CANDIDATE_AWAITING_HUMAN_PUBLICATION_AUTHORIZATION",
        "version": VERSION,
        "publication_authorized": False,
        "ultra_asset": "release/ULTRA_FAMILY.mleg",
        "ultra_sha256": sha256((dist / "ULTRA_FAMILY.mleg").read_bytes()),
        "logical_ultra_sha256": "4e837160f1d0f3ccf1d568e01592286dbe0d982f862f0191db1d570f7b36d6b4",
        "runner_required_paths": [
            "README.md", "VERIFY.BAT", "verify_reviewer_bundle.py",
            "RUN-COURT.BAT", "run_reviewer_court.py",
            "release/RELEASE-MANIFEST.json", "release/RELEASE_CONTRACT.json",
            "release/semcrys-core-0.1.0-source.zip", "release/ULTRA_FAMILY.mleg",
        ],
        "artifacts": [
            {"path": name, "bytes": len(data), "sha256": sha256(data)}
            for name, data in rows
        ],
        "authority_effect": "NONE",
    }
    manifest["manifest_root"] = sha256(canonical(manifest))
    rows.append(entry("REVIEWER-CONTENTS.json", json.dumps(
        manifest, indent=2, sort_keys=True
    ).encode("utf-8") + b"\n"))
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, data in sorted(rows):
            info = zipfile.ZipInfo(f"{PREFIX}/{name}", FIXED_TIME)
            info.create_system = 3
            info.external_attr = 0o644 << 16
            archive.writestr(
                info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9
            )
    return output.getvalue(), manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "release-inputs" / "reviewer"
    )
    args = parser.parse_args(argv)
    release_manifest = json.loads(
        (args.dist / "RELEASE-MANIFEST.json").read_text(encoding="utf-8")
    )
    require(release_manifest.get("publication_authorized") is False, "PUBLICATION_MUST_BE_HELD")
    court = json.loads(
        (ROOT / "evidence" / "PUBLICATION-COURT.json").read_text(encoding="utf-8")
    )
    require(court.get("status") == "PASS", "PUBLICATION_COURT_NOT_PASS")
    first, manifest = build_bytes(args.dist)
    second, repeated = build_bytes(args.dist)
    require(first == second and manifest == repeated, "REVIEWER_BUILD_NOT_REPRODUCIBLE")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    archive = args.output_dir / f"{PREFIX}.zip"
    archive.write_bytes(first)
    sidecar = archive.with_name(archive.name + ".sha256")
    archive_root = sha256(first)
    sidecar.write_text(
        f"{archive_root}  {archive.name}\n", encoding="ascii", newline="\n"
    )
    boundary_body = {
        "schema": "codex.exact-artifact-boundary.v1",
        "boundary_id": f"semcrys-core-{VERSION}-reviewer-candidate-{REVISION.lower()}-20261105",
        "artifacts": [{
            "source_path": f"release-inputs/reviewer/{archive.name}",
            "destination_path": archive.name,
            "sha256": archive_root,
            "required_by": "reviewer:replacement-candidate",
        }],
        "runner_required_paths": [archive.name],
        "allow_extra_artifacts": False,
        "policy": {
            "maximum_transfers": 1,
            "maximum_invocations": 1,
            "maximum_retries": 0,
            "preserve_prior_custody": True,
            "terminal_capture": ["archive_sha256", "court_result"],
        },
        "publication_authorized": False,
        "authority_effect": "NONE",
    }
    boundary_body["manifest_root"] = sha256(canonical(boundary_body))
    boundary = args.output_dir / f"{PREFIX}.boundary.json"
    boundary.write_text(
        json.dumps(boundary_body, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(json.dumps({
        "status": "PASS",
        "archive": str(archive),
        "sha256": archive_root,
        "bytes": len(first),
        "contents_root": manifest["manifest_root"],
        "boundary": str(boundary),
        "byte_reproducible": True,
        "publication_authorized": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, RuntimeError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, indent=2))
        raise SystemExit(1)
