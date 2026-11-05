from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parent.parent


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def require(condition, code):
    if not condition:
        raise RuntimeError(code)


def rooted(value: dict, field: str) -> dict:
    return {**value, field: hashlib.sha256(canonical(value)).hexdigest()}


def inventory(directory: Path, version: str, *, names: set[str] | None = None) -> dict:
    rows = [
        {"name": path.name, "bytes": path.stat().st_size, "sha256": digest(path)}
        for path in sorted(directory.iterdir(), key=lambda item: item.name)
        if path.is_file() and (names is None or path.name in names)
    ]
    return {"schema": "semcrys.release-build-inventory.v0.1", "version": version, "artifacts": rows}


def validate_boundary(path: Path, stage: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(value.get("schema") == "codex.exact-artifact-boundary.v1", "BOUNDARY_SCHEMA")
    rows = value.get("artifacts")
    require(type(rows) is list and rows, "BOUNDARY_ARTIFACTS")
    expected = {}
    evidence = []
    for row in rows:
        relative = PurePosixPath(row["destination_path"])
        require(not relative.is_absolute() and ".." not in relative.parts, "BOUNDARY_PATH")
        name = relative.as_posix()
        require(name not in expected, "BOUNDARY_DUPLICATE")
        source = Path(row["source_path"])
        if not source.is_absolute():
            source = ROOT / source
        require(source.is_file() and digest(source) == row["sha256"], "BOUNDARY_SOURCE")
        target = stage.joinpath(*relative.parts)
        require(target.is_file() and digest(target) == row["sha256"], "BOUNDARY_STAGE")
        expected[name] = row["sha256"]
        evidence.append({
            "destination_path": name,
            "sha256": row["sha256"],
            "bytes": target.stat().st_size,
        })
    required = value.get("runner_required_paths")
    require(required == [row["destination_path"] for row in rows], "BOUNDARY_REQUIRED_SET")
    observed = sorted(
        path.relative_to(stage).as_posix() for path in stage.rglob("*") if path.is_file()
    )
    require(value.get("allow_extra_artifacts") is False and observed == sorted(expected), "BOUNDARY_STAGE_LAYOUT")
    envelope = {
        "boundary_id": value["boundary_id"],
        "artifacts": sorted(evidence, key=lambda row: row["destination_path"]),
    }
    return {
        "status": "PASS",
        "boundary_id": value["boundary_id"],
        "artifact_count": len(rows),
        "manifest_sha256": digest(path),
        "envelope_root": hashlib.sha256(canonical(envelope)).hexdigest(),
        "source_phase": "PASS",
        "staged_phase": "PASS",
    }


def verify_release(manifest: Path) -> dict:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-B", str(ROOT / "tools" / "verify_release.py"), str(manifest)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    require(completed.returncode == 0, "PACKAGED_VERIFICATION_EXECUTION")
    value = json.loads(completed.stdout)
    require(value.get("status") == "PASS", "PACKAGED_VERIFICATION_RESULT")
    return value


def verify_publication_index(index: Path) -> dict:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            str(ROOT / "tools" / "verify_publication_asset_index.py"),
            str(index),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    require(completed.returncode == 0, "PUBLICATION_INDEX_VERIFICATION_EXECUTION")
    value = json.loads(completed.stdout)
    require(value.get("status") == "PASS", "PUBLICATION_INDEX_VERIFICATION_RESULT")
    return value


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first-build-inventory", type=Path, required=True)
    parser.add_argument("--stage-root", type=Path, required=True)
    parser.add_argument("--prior-custody", type=Path, required=True)
    parser.add_argument("--prior-version", default="0.2.0rc4")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    require(not args.output.exists(), "RECEIPT_OUTPUT_EXISTS")

    first = json.loads(args.first_build_inventory.read_text(encoding="utf-8-sig"))
    require(type(first.get("artifacts")) is list, "BUILD_INVENTORY_ARTIFACTS")
    first = {**first, "artifacts": sorted(first["artifacts"], key=lambda row: row["name"])}
    core_names = {row["name"] for row in first["artifacts"]}
    require(len(core_names) == len(first["artifacts"]), "BUILD_INVENTORY_DUPLICATE")
    second = inventory(ROOT / "dist", "0.1.0", names=core_names)
    require(first.get("schema") == second["schema"] and first.get("version") == second["version"], "BUILD_INVENTORY_SCHEMA")
    require(len(second["artifacts"]) == len(core_names), "BUILD_INVENTORY_CORE_SET")
    require(first == second, "DETERMINISTIC_BUILD_MISMATCH")
    inventory_root = hashlib.sha256(canonical(first)).hexdigest()

    manifest_path = ROOT / "dist" / "RELEASE-MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    claimed = manifest.get("manifest_root")
    subject = {key: value for key, value in manifest.items() if key != "manifest_root"}
    require(claimed == hashlib.sha256(canonical(subject)).hexdigest(), "RELEASE_MANIFEST_ROOT")
    require(manifest.get("version") == "0.1.0", "RELEASE_VERSION")
    require(manifest.get("publication_authorized") is True, "PUBLICATION_AUTHORITY_BOUNDARY")
    decision = json.loads((ROOT / "PUBLICATION_DECISION.json").read_text(encoding="utf-8"))
    require(decision.get("decision") == "AUTHORIZED_FOR_GITHUB_PUBLICATION",
            "PUBLICATION_DECISION")
    require(manifest.get("publication_decision_root") == decision.get("decision_root"),
            "PUBLICATION_DECISION_ROOT")
    require(manifest.get("verification_status") in {
        "SELF_VERIFYING_EXTERNAL_REPLAY_PENDING",
        "SELF_VERIFYING_AND_INDEPENDENTLY_REPRODUCED",
    }, "VERIFICATION_STATUS")
    require(manifest.get("formal_external_certification") == "NOT_CLAIMED", "CERTIFICATION_BOUNDARY")

    court = json.loads((ROOT / "evidence" / "PUBLICATION-COURT.json").read_text(encoding="utf-8"))
    require(court.get("status") == "PASS", "PUBLICATION_COURT")
    contract = json.loads((ROOT / "RELEASE_CONTRACT.json").read_text(encoding="utf-8"))
    qualification_courts = {}
    for label, path, contract_root in (
        (
            "security_projection",
            ROOT / "evidence" / "SECURITY-PROJECTION-COURT.json",
            contract["security_projection"]["court_root"],
        ),
        (
            "seekable_metalegend",
            ROOT / "evidence" / "ULTRA-SEEKABLE-METALEGEND-COURT.json",
            contract["ultra"]["qualification_court_root"],
        ),
    ):
        value = json.loads(path.read_text(encoding="utf-8"))
        claimed_court_root = value.pop("court_root")
        require(value.get("status") == "PASS", "QUALIFICATION_COURT_STATUS:" + label)
        require(claimed_court_root == hashlib.sha256(canonical(value)).hexdigest(),
                "QUALIFICATION_COURT_ROOT:" + label)
        require(claimed_court_root == contract_root,
                "QUALIFICATION_COURT_CONTRACT:" + label)
        qualification_courts[label] = {
            "status": "PASS",
            "court_root": claimed_court_root,
            "authority_effect": "NONE",
        }
    boundary = validate_boundary(ROOT / "evidence" / "EXACT-ARTIFACT-BOUNDARY.json", args.stage_root)
    packaged = verify_release(manifest_path)
    publication_index = verify_publication_index(
        ROOT / "dist" / "PUBLICATION-ASSET-INDEX.json"
    )
    prior = inventory(args.prior_custody, args.prior_version)

    receipt = rooted({
        "schema": "semcrys.release-candidate-receipt.v0.1",
        "standing": "PUBLIC_RELEASE_AUTHORIZED_ENGINEERING_EVIDENCE",
        "version": "0.1.0",
        "deterministic_build": {
            "status": "PASS",
            "build_count": 2,
            "inventory_root": inventory_root,
            "artifact_count": len(first["artifacts"]),
        },
        "publication_court": {
            "status": "PASS",
            "court_root": court["court_root"],
            "source_root": court["source_root"],
        },
        "qualification_courts": qualification_courts,
        "release_manifest": {
            "status": "PASS",
            "manifest_root": claimed,
            "sha256": digest(manifest_path),
        },
        "exact_artifact_boundary": boundary,
        "packaged_verification": packaged,
        "publication_asset_index": publication_index,
        "prior_custody": {
            "version": args.prior_version,
            "status": "PRESERVED",
            "inventory_root": hashlib.sha256(canonical(prior)).hexdigest(),
            "artifact_count": len(prior["artifacts"]),
        },
        "security_claim": "BOUNDED_IMPLEMENTED_PROFILE_NO_PROTOCOL_SECURITY_PROOF",
        "publication_authorized": True,
        "publication_decision_root": decision["decision_root"],
        "verification_status": manifest["verification_status"],
        "formal_external_certification": "NOT_CLAIMED",
        "authority_effect": "NONE",
    }, "receipt_root")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({
        "status": "PASS",
        "receipt_root": receipt["receipt_root"],
        "manifest_root": claimed,
        "boundary_envelope_root": boundary["envelope_root"],
        "output": str(args.output),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, RuntimeError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, indent=2, sort_keys=True))
        raise SystemExit(1)
