from __future__ import annotations

import argparse
import bz2
import hashlib
import json
import platform
import tempfile
from pathlib import Path

from semcrys.configuration_court import CONTROL_CODECS, load as load_court, run as run_court
from semcrys.configuration_selection import build_library
from semcrys.recursive_metalegend import restore as restore_metalegend


ROOT = Path(__file__).resolve().parent.parent
CHUNK = 1024 * 1024


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(CHUNK):
            digest.update(block)
    return digest.hexdigest()


def decompress(source: Path, target: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    total = 0
    with bz2.open(source, "rb") as incoming, target.open("wb") as outgoing:
        while block := incoming.read(CHUNK):
            outgoing.write(block)
            digest.update(block)
            total += len(block)
    return total, digest.hexdigest()


def scenario(court: dict, accounting: str, horizon: int) -> dict:
    return next(
        row for row in court["scenarios"]
        if row["accounting"] == accounting and row["reuse_horizon"] == horizon
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Qualify the general SemCrys configuration court on pinned Wikipedia data.")
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ultra-asset", "--ultra-container", dest="ultra_asset", type=Path,
                        default=ROOT / "assets" / "legends" / "ULTRA_FAMILY.mleg")
    parser.add_argument("--profile-bytes", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    expected = manifest["fixture"]
    release = json.loads((ROOT / "RELEASE_CONTRACT.json").read_text(encoding="utf-8"))
    ultra_contract = release["ultra"]
    if args.fixture.stat().st_size != expected["bytes"] or hash_file(args.fixture) != expected["sha256"]:
        raise RuntimeError("HELD_WIKIPEDIA_FIXTURE_IDENTITY")
    if args.ultra_asset.stat().st_size != ultra_contract["asset_bytes"] or hash_file(args.ultra_asset) != ultra_contract["asset_sha256"]:
        raise RuntimeError("HELD_WIKIPEDIA_ULTRA_ASSET_IDENTITY")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="semcrys-wikipedia-court-", dir=args.output.parent) as name:
        work = Path(name)
        source = work / "source.xml"
        source_bytes, source_sha256 = decompress(args.fixture, source)
        if source_bytes != expected["expanded_bytes"] or source_sha256 != expected["expanded_sha256"]:
            raise RuntimeError("HELD_WIKIPEDIA_EXPANDED_IDENTITY")

        ultra_legend = work / "ultra.leg"
        restored = restore_metalegend(args.ultra_asset, ultra_legend)
        if (
            ultra_legend.stat().st_size != ultra_contract["logical_legend_bytes"]
            or restored["source_legend_sha256"] != ultra_contract["logical_legend_sha256"]
            or hash_file(ultra_legend) != ultra_contract["logical_legend_sha256"]
        ):
            raise RuntimeError("HELD_WIKIPEDIA_ULTRA_LEGEND_IDENTITY")

        library = work / "library.json"
        built = build_library(library, [("ULTRA", "ULTRA", 0, ultra_legend)])
        court_path = work / "court.json"
        run_court(
            source,
            court_path,
            library_path=library,
            legends=[ultra_legend],
            semcrys_codecs=("NONE", "LZMA", "BZ2_9"),
            control_codecs=CONTROL_CODECS,
            horizons=(1, 2, 4, 8, 16, 32),
            receiver_roots=[ultra_contract["logical_legend_sha256"]],
            qualification_label="PINNED_ENWIKI_20261001_100_PAGE_STREAM_PREFIX",
        )
        court = load_court(court_path)

    result = {
        "schema": "semcrys.wikipedia-qualification.v0.2",
        "standing": "SINGLE_HOST_BOUNDED_CONFIGURATION_COURT_EVIDENCE",
        "fixture_manifest_sha256": hashlib.sha256(canonical(manifest)).hexdigest(),
        "fixture": expected,
        "runtime": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "system": platform.system(),
            "machine": platform.machine(),
        },
        "source_bytes": source_bytes,
        "source_sha256": source_sha256,
        "official_fixture_ratio": round(expected["bytes"] / source_bytes, 8),
        "ultra": {
            **ultra_contract,
            "library_root": built["library_root"],
        },
        "configuration_court": court,
        "headline_scenarios": {
            "cold_horizon_1": scenario(court, "COLD", 1),
            "warm_horizon_1": scenario(court, "WARM", 1),
            "cold_horizon_32": scenario(court, "COLD", 32),
            "warm_horizon_32": scenario(court, "WARM", 32),
        },
        "method_notes": [
            "The fixture is a bounded prefix of complete bzip2 streams, not a well-formed complete XML dump.",
            "The general court measures exact SemCrys RAW, self-contained, Ultra pre-shared, and Ultra longitudinal-delta candidates under NONE, LZMA, and BZ2_9.",
            "Direct RAW, BZ2 levels 1/9, and XZ presets 0/6/9 are exact-recovery controls.",
            "Cold scenarios charge the decoded Ultra legend once; warm scenarios require its exact root and charge no acquisition bytes.",
            "Every SemCrys candidate is decoded and hash-verified before it is eligible for selection.",
            "Full integerization is a capability constraint, so its winner is reported separately from the unconstrained minimum-byte winner.",
            "Reuse horizons repeat this exact frozen source and do not predict future Wikipedia pages or other corpora.",
        ],
        "claim_boundary": "One pinned 100-page stream prefix on one host; enumerated-candidate optimality only, with no whole-Wikipedia, cross-corpus, or global-optimality claim.",
        "authority_effect": "NONE",
    }
    result["evidence_root"] = hashlib.sha256(canonical(result)).hexdigest()
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({
        "status": "PASS",
        "evidence_root": result["evidence_root"],
        "court_root": court["court_root"],
        "output": str(args.output),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
