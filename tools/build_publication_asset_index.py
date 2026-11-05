from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


SCHEMA = "semcrys.publication-asset-index.v0.1"
INDEX_NAME = "PUBLICATION-ASSET-INDEX.json"


def canonical(value):
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode()


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact(path, role):
    return {
        "path": path.name,
        "role": role,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def write_sidecar(path):
    sidecar = path.with_name(path.name + ".sha256")
    sidecar.write_text(f"{sha256(path)}  {path.name}\n", encoding="ascii", newline="\n")
    return sidecar


def stage_reviewers(reviewer_dir, dist):
    if not reviewer_dir.is_dir():
        raise RuntimeError(f"REVIEWER_DIRECTORY_MISSING:{reviewer_dir}")
    files = sorted(path for path in reviewer_dir.iterdir() if path.is_file())
    zips = [path for path in files if path.suffix == ".zip"]
    boundaries = [path for path in files if path.name.endswith(".boundary.json")]
    if len(zips) != 1 or len(boundaries) != 1:
        raise RuntimeError("REVIEWER_ENVELOPE_INCOMPLETE")
    zip_sidecar = zips[0].with_name(zips[0].name + ".sha256")
    if zip_sidecar not in files:
        raise RuntimeError("REVIEWER_SIDECAR_MISSING")
    staged = []
    for source in (boundaries[0], zips[0], zip_sidecar):
        destination = dist / source.name
        shutil.copyfile(source, destination)
        staged.append(destination)
    return staged


def build_index(dist, reviewer_dir):
    dist.mkdir(parents=True, exist_ok=True)
    manifest_path = dist / "RELEASE-MANIFEST.json"
    manifest_sidecar = dist / "RELEASE-MANIFEST.json.sha256"
    if not manifest_path.is_file() or not manifest_sidecar.is_file():
        raise RuntimeError("RELEASE_MANIFEST_ENVELOPE_MISSING")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = manifest["version"]

    manifest_payloads = []
    for row in manifest["artifacts"]:
        payload = dist / row["path"]
        sidecar = payload.with_name(payload.name + ".sha256")
        if not payload.is_file() or not sidecar.is_file():
            raise RuntimeError(f"MANIFEST_PAYLOAD_ENVELOPE_MISSING:{row['path']}")
        manifest_payloads.extend(
            (artifact(payload, row["role"]), artifact(sidecar, "SHA256_SIDECAR"))
        )

    bundle = dist / f"semcrys-core-{version}-offline-bundle.zip"
    bundle_sidecar = bundle.with_name(bundle.name + ".sha256")
    if not bundle.is_file() or not bundle_sidecar.is_file():
        raise RuntimeError("OFFLINE_BUNDLE_ENVELOPE_MISSING")

    reviewers = stage_reviewers(reviewer_dir, dist)
    subject = {
        "schema": SCHEMA,
        "version": version,
        "release_tag": f"v{version}",
        "core_manifest": {
            "path": manifest_path.name,
            "manifest_root": manifest["manifest_root"],
            "sha256": sha256(manifest_path),
        },
        "asset_groups": [
            {
                "group": "release_control",
                "verification": "ROOTED_MANIFEST_AND_ADJACENT_SIDECAR",
                "artifacts": [
                    artifact(manifest_path, "RELEASE_MANIFEST"),
                    artifact(manifest_sidecar, "SHA256_SIDECAR"),
                ],
            },
            {
                "group": "manifest_bound_payloads",
                "verification": "RELEASE_MANIFEST_ROWS_AND_ADJACENT_SIDECARS",
                "artifacts": manifest_payloads,
            },
            {
                "group": "offline_custody_bundle",
                "verification": "ADJACENT_SIDECAR_AND_EMBEDDED_RELEASE_MANIFEST",
                "artifacts": [
                    artifact(bundle, "OFFLINE_BUNDLE"),
                    artifact(bundle_sidecar, "SHA256_SIDECAR"),
                ],
            },
            {
                "group": "reviewer_companion_evidence",
                "standing": "COMPANION_EVIDENCE_WITH_OWN_BOUNDARY_AND_SIDECAR",
                "verification": "REVIEWER_BOUNDARY_AND_ADJACENT_SIDECAR",
                "artifacts": [
                    artifact(path, "REVIEWER_COMPANION") for path in reviewers
                ],
            },
        ],
        "self_binding": {
            "index": INDEX_NAME,
            "sidecar": INDEX_NAME + ".sha256",
            "rule": "INDEX_ROOT_PLUS_ADJACENT_SIDECAR",
        },
        "excluded_host_generated_assets": [
            {
                "names": ["Source code (zip)", "Source code (tar.gz)"],
                "reason": "GitHub generates these snapshots from the release tag; the tag commit is their custody boundary.",
            }
        ],
        "authority_effect": "NONE",
    }
    subject["index_root"] = hashlib.sha256(canonical(subject)).hexdigest()
    output = dist / INDEX_NAME
    output.write_text(
        json.dumps(subject, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    sidecar = write_sidecar(output)
    return output, sidecar, subject


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build the non-cyclic index for every SemCrys GitHub release asset."
    )
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument(
        "--reviewer-dir", type=Path, default=Path("release-inputs/reviewer")
    )
    args = parser.parse_args(argv)
    output, sidecar, index = build_index(args.dist.resolve(), args.reviewer_dir.resolve())
    print(
        json.dumps(
            {
                "status": "PASS",
                "index": str(output),
                "sidecar": str(sidecar),
                "index_root": index["index_root"],
                "authority_effect": "NONE",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
