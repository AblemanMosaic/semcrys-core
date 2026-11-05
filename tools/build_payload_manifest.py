from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
PACKAGES = ("semcrys", "streaming_app", "streaming_legend")
OUTPUT = SRC / "semcrys" / "PAYLOAD_MANIFEST.json"


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()


def main() -> int:
    rows = []
    for package in PACKAGES:
        directory = SRC / package
        for path in sorted(directory.iterdir(), key=lambda item: item.name):
            if path.name == "__pycache__" or (package == "semcrys" and path.name == OUTPUT.name):
                continue
            if not path.is_file():
                raise RuntimeError(f"HELD_DISTRIBUTION_UNDECLARED_DIRECTORY:{package}/{path.name}")
            data = path.read_bytes()
            rows.append(
                {
                    "package": package,
                    "path": path.name,
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
    manifest = {
        "schema": "semcrys.payload-manifest.v0.1",
        "files": rows,
        "payload_root": hashlib.sha256(canonical(rows)).hexdigest(),
    }
    OUTPUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": "PASS", "files": len(rows), "payload_root": manifest["payload_root"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
