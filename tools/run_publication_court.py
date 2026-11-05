from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "evidence" / "PUBLICATION-COURT.json"
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
COURT_TEMP = ROOT / "release-work" / "publication-court-temp"


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()


def source_root():
    rows = []
    for path in sorted(ROOT.rglob("*")):
        relative = path.relative_to(ROOT)
        # Exclude by lexical repository path before touching the filesystem.
        # WSL virtual environments can contain Windows-inaccessible symlinks.
        if path.name in EXCLUDED_FILES or any(part in EXCLUDED for part in relative.parts):
            continue
        if not path.is_file():
            continue
        if relative.parts and ROOT_TEMP_DIRECTORY.fullmatch(relative.parts[0]):
            continue
        if relative.as_posix() in {
            "evidence/PUBLICATION-COURT.json",
            "evidence/EXACT-ARTIFACT-BOUNDARY.json",
            "evidence/EXACT-ARTIFACT-BOUNDARY-RECEIPT.json",
        } or path.suffix in {".pyc", ".pyo"}:
            continue
        rows.append({"path": relative.as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size})
    return hashlib.sha256(canonical(rows)).hexdigest(), rows


def run(arguments):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["TEMP"] = str(COURT_TEMP)
    env["TMP"] = str(COURT_TEMP)
    env["TMPDIR"] = str(COURT_TEMP)
    completed = subprocess.run([sys.executable, "-B", *arguments], cwd=ROOT, env=env, capture_output=True, text=True)
    recorded_arguments = []
    for argument in arguments:
        try:
            relative = Path(argument).resolve().relative_to(ROOT)
            recorded_arguments.append("<repo>/" + relative.as_posix())
        except (OSError, ValueError):
            recorded_arguments.append(argument)
    return {
        "command": ["<python>", "-B", *recorded_arguments],
        "returncode": completed.returncode,
        "stdout_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(completed.stderr.encode()).hexdigest(),
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-4000:]
    }


def main():
    COURT_TEMP.mkdir(parents=True, exist_ok=True)
    root, inventory = source_root()
    checks = [
        run(["-m", "unittest", "discover", "-s", "tests", "-v"]),
        run(["-m", "semcrys_core", "capabilities"]),
        run(["-m", "semcrys_core", "native-status"]),
        run(["tools/benchmark_native.py", "--events", "250000", "--repeats", "2"]),
        run(["tools/verify_wikipedia_evidence.py"]),
        run(["tools/verify_integerization_performance_evidence.py"]),
        run(["tools/verify_seekable_metalegend_evidence.py"]),
        run(["-m", "semcrys_core", "verify-self", "--asset-root", str(ROOT / "assets" / "legends")]),
        run(["-m", "semcrys", "--progress", "quiet", "metalegend", "verify", str(ROOT / "assets" / "legends" / "ULTRA_FAMILY.mleg")]),
        run(["-m", "semcrys", "verify-self"]),
        run(["-m", "semcrys_lite", "demo"])
    ]
    court = {
        "schema": "semcrys.publication-court.v0.1",
        "standing": "INTERNAL_SELF_QUALIFICATION",
        "source_root": root,
        "inventory_count": len(inventory),
        "checks": checks,
        "status": "PASS" if all(check["returncode"] == 0 for check in checks) else "FAIL",
        "authority_effect": "NONE",
        "publication_effect": "NONE",
        "formal_external_certification": "NOT_CLAIMED"
    }
    court["court_root"] = hashlib.sha256(canonical(court)).hexdigest()
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(court, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": court["status"], "court_root": court["court_root"], "source_root": root}, indent=2, sort_keys=True))
    return 0 if court["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
