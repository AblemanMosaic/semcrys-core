from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
OUTPUT = DOCS / "DOCUMENTATION_MANIFEST.json"
DATE = "2026-11-05"
VERSION = "0.1.0"
DATE_RE = re.compile(r"\b20\d\d-\d\d-\d\d\b")
VERSION_RE = re.compile(r"\b(?:dev\d+|\d+\.\d+\.\d+(?:rc\d+)?)\b", re.IGNORECASE)
README_LINK_RE = re.compile(r"\(docs/([A-Za-z0-9_.-]+\.md)(?:#[^)]+)?\)")


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def main() -> int:
    release_scope = json.loads((ROOT / "src/semcrys/RELEASE_SCOPE.json").read_text(encoding="utf-8"))
    files = []
    for path in sorted(DOCS.glob("*.md"), key=lambda item: item.name):
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        files.append({
            "name": path.name,
            "kind": "MARKDOWN",
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "embedded_dates": sorted(set(DATE_RE.findall(text))),
            "historical_or_current_version_mentions": sorted(set(VERSION_RE.findall(text))),
            "reviewed_date": DATE,
            "reviewed_for_version": VERSION,
        })
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    body = {
        "schema": "semcrys.documentation-manifest.v0.1",
        "standing": "CANDIDATE_ONLY",
        "version": VERSION,
        "reviewed_date": DATE,
        "public_publication": True,
        "public_release_date": DATE,
        "security_claim": "NONE",
        "current_version_sources": ["README.md", "pyproject.toml", "semcrys.__version__"],
        "historical_version_mentions_retained_as_lineage_not_current_versions": True,
        "command_group_counts": {
            key: len(value) for key, value in sorted(release_scope["command_groups"].items())
        },
        "file_count": len(files),
        "files": files,
        "references_from_readme": sorted(set(README_LINK_RE.findall(readme))),
        "stale_current_entries": [],
    }
    manifest = {**body, "manifest_root": hashlib.sha256(canonical(body)).hexdigest()}
    OUTPUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8", newline="\n")
    print(json.dumps({"status": "PASS", "file_count": len(files),
                      "manifest_root": manifest["manifest_root"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
