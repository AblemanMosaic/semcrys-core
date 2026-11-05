from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import sys
import tempfile
from pathlib import Path

from standalone_custody import canonical, sha256
from verify_release import (
    safe_extract_tar,
    safe_extract_zip,
    verify_linux_bundle,
    verify_windows_bundle,
)

ROOT = Path(__file__).resolve().parent.parent
VERSION = "0.1.0"


def require(condition, code):
    if not condition:
        raise RuntimeError(code)


def rooted(value, field):
    return {**value, field: hashlib.sha256(canonical(value)).hexdigest()}


def load_internal(path: Path, platform_name: str, temp_root: Path) -> dict:
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as directory:
        root = Path(directory)
        if platform_name == "linux":
            safe_extract_tar(path, root)
            manifest = root / "semcrys-linux-x64" / "LINUX-MANIFEST.json"
        else:
            safe_extract_zip(path, root)
            manifest = root / "semcrys-windows-x64" / "WINDOWS-MANIFEST.json"
        return json.loads(manifest.read_text(encoding="utf-8"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("platform", choices=("windows", "linux"))
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "release-inputs"
    )
    parser.add_argument(
        "--work-root", type=Path, default=ROOT / "release-work" / "qualification"
    )
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args(argv)
    expected = "Windows" if args.platform == "windows" else "Linux"
    require(platform.system() == expected, "HELD_QUALIFICATION_PLATFORM")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.work_root.mkdir(parents=True, exist_ok=True)
    suffix = "windows-x64.zip" if args.platform == "windows" else "linux-x64.tar.gz"
    outputs = [
        args.work_root / f"semcrys-{VERSION}-{args.platform}-A.{suffix.split('.', 1)[1]}",
        args.work_root / f"semcrys-{VERSION}-{args.platform}-B.{suffix.split('.', 1)[1]}",
    ]
    results = []
    if args.platform == "windows":
        from build_windows_executable import build

        for output in outputs:
            results.append(build(output))
        runtime_smoke = verify_windows_bundle(outputs[1])
        schema = "semcrys.windows-standalone-court.v0.2"
    else:
        from build_linux_executable import build

        for index, output in enumerate(outputs):
            results.append(build(output, args.work_root / f"linux-work-{index}"))
        runtime_smoke = verify_linux_bundle(outputs[1])
        schema = "semcrys.linux-standalone-court.v0.2"

    require(outputs[0].read_bytes() == outputs[1].read_bytes(), "BUILD_NOT_REPRODUCIBLE")
    require(runtime_smoke == "PACK_VERIFY_UNPACK_PASS", "RUNTIME_SMOKE")
    internal = load_internal(outputs[1], args.platform, args.work_root)
    destination = args.output_dir / f"semcrys-{VERSION}-{suffix}"
    shutil.copyfile(outputs[1], destination)
    court = rooted(
        {
            "schema": schema,
            "standing": "INTERNAL_SELF_QUALIFICATION",
            "status": "PASS",
            "version": VERSION,
            "platform": internal["platform"],
            "builds": [
                {
                    "label": label,
                    "bytes": output.stat().st_size,
                    "sha256": sha256(output),
                }
                for label, output in zip(("A", "B"), outputs)
            ],
            "byte_reproducible": True,
            "manifest_root": internal["manifest_root"],
            "runtime_root": internal["bundled_runtime"]["runtime_root"],
            "runtime_smoke": runtime_smoke,
            "toolchain": internal["build_identity"],
            "glibc_floor": (
                internal["glibc"]["required"] if args.platform == "linux" else None
            ),
            "native_acceleration": internal["native_acceleration"],
            "security_claim": internal["security_claim"],
            "authority_effect": "NONE",
        },
        "court_root",
    )
    evidence = args.evidence or (
        ROOT
        / "evidence"
        / ("WINDOWS-STANDALONE-COURT.json" if args.platform == "windows" else "LINUX-STANDALONE-COURT.json")
    )
    evidence.write_text(
        json.dumps(court, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "artifact": str(destination),
                "sha256": sha256(destination),
                "court_root": court["court_root"],
                "evidence": str(evidence),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, RuntimeError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, indent=2, sort_keys=True))
        raise SystemExit(1)
