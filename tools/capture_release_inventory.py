from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--version", default="0.1.0")
    args = parser.parse_args()
    rows = [
        {"name": path.name, "bytes": path.stat().st_size, "sha256": digest(path)}
        for path in sorted(args.directory.iterdir(), key=lambda item: item.name)
        if path.is_file()
    ]
    value = {
        "schema": "semcrys.release-build-inventory.v0.1",
        "version": args.version,
        "artifacts": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": "PASS", "artifacts": len(rows), "output": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
