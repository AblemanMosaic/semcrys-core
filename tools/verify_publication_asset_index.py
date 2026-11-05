from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

from build_publication_asset_index import INDEX_NAME, SCHEMA, canonical, sha256


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def parse_sidecar(path):
    parts = path.read_text(encoding="ascii").strip().split(None, 1)
    require(len(parts) == 2, f"SIDECAR_FORMAT:{path.name}")
    return parts[0], parts[1].strip()


def verify(index_path):
    base = index_path.parent
    index = json.loads(index_path.read_text(encoding="utf-8"))
    require(index.get("schema") == SCHEMA, "INDEX_SCHEMA")
    subject = dict(index)
    claimed = subject.pop("index_root")
    require(hashlib.sha256(canonical(subject)).hexdigest() == claimed, "INDEX_ROOT")

    sidecar = index_path.with_name(index_path.name + ".sha256")
    require(sidecar.is_file(), "INDEX_SIDECAR_MISSING")
    sidecar_hash, sidecar_name = parse_sidecar(sidecar)
    require(sidecar_name == INDEX_NAME, "INDEX_SIDECAR_NAME")
    require(sidecar_hash == sha256(index_path), "INDEX_SIDECAR_HASH")

    rows = []
    seen = set()
    for group in index["asset_groups"]:
        for row in group["artifacts"]:
            name = row["path"]
            pure = PurePosixPath(name)
            require(
                len(pure.parts) == 1 and name not in {"", ".", ".."},
                f"UNSAFE_ASSET_PATH:{name}",
            )
            require(name not in seen, f"DUPLICATE_ASSET:{name}")
            seen.add(name)
            path = base / name
            require(path.is_file(), f"MISSING_ASSET:{name}")
            require(path.stat().st_size == row["bytes"], f"ASSET_SIZE:{name}")
            require(sha256(path) == row["sha256"], f"ASSET_HASH:{name}")
            rows.append(row)

    row_by_name = {row["path"]: row for row in rows}
    manifest_path = base / index["core_manifest"]["path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    require(
        manifest["manifest_root"] == index["core_manifest"]["manifest_root"],
        "CORE_MANIFEST_ROOT",
    )
    require(sha256(manifest_path) == index["core_manifest"]["sha256"], "CORE_MANIFEST_HASH")
    for manifest_row in manifest["artifacts"]:
        indexed = row_by_name.get(manifest_row["path"])
        require(indexed is not None, f"MANIFEST_ASSET_UNINDEXED:{manifest_row['path']}")
        require(indexed["sha256"] == manifest_row["sha256"], f"MANIFEST_HASH_DRIFT:{manifest_row['path']}")
        require(indexed["bytes"] == manifest_row["bytes"], f"MANIFEST_SIZE_DRIFT:{manifest_row['path']}")

    for name, row in row_by_name.items():
        if not name.endswith(".sha256"):
            continue
        target_name = name[: -len(".sha256")]
        target = row_by_name.get(target_name)
        require(target is not None, f"SIDECAR_TARGET_UNINDEXED:{name}")
        sidecar_hash, sidecar_name = parse_sidecar(base / name)
        require(sidecar_name == target_name, f"SIDECAR_TARGET_NAME:{name}")
        require(sidecar_hash == target["sha256"], f"SIDECAR_TARGET_HASH:{name}")

    excluded = index.get("excluded_host_generated_assets", [])
    require(excluded, "HOST_GENERATED_BOUNDARY_MISSING")
    return {
        "status": "PASS",
        "index_root": claimed,
        "indexed_assets": len(rows) + 2,
        "core_manifest_root": manifest["manifest_root"],
        "authority_effect": "NONE",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Verify every locally staged SemCrys publication asset."
    )
    parser.add_argument(
        "index", type=Path, nargs="?", default=Path("dist") / INDEX_NAME
    )
    args = parser.parse_args(argv)
    try:
        result = verify(args.index.resolve())
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
