from __future__ import annotations

import argparse
import bz2
import codecs
import hashlib
import json
import urllib.request
from pathlib import Path

DEFAULT_DATE = "20261001"
DEFAULT_SHARD = "pages-articles-multistream1.xml-p1p41242"
DEFAULT_LIMIT = 16 * 1024 * 1024
CHUNK = 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(CHUNK):
            digest.update(block)
    return digest.hexdigest()


def fetch(url: str) -> tuple[bytes, dict[str, str]]:
    request = urllib.request.Request(url, headers={"User-Agent": "SemCrys-Core-Benchmark/0.2"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read(), {key.lower(): value for key, value in response.headers.items()}


def fetch_range(url: str, boundary: int, output: Path) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        headers={
            "Range": f"bytes=0-{boundary - 1}",
            "User-Agent": "SemCrys-Core-Benchmark/0.2",
        },
    )
    partial = output.with_suffix(output.suffix + ".partial")
    with urllib.request.urlopen(request, timeout=120) as response:
        headers = {key.lower(): value for key, value in response.headers.items()}
        if response.status != 206:
            raise RuntimeError("HELD_WIKIMEDIA_RANGE_NOT_HONORED")
        content_range = headers.get("content-range", "")
        if not content_range.startswith(f"bytes 0-{boundary - 1}/"):
            raise RuntimeError("HELD_WIKIMEDIA_RANGE_MISMATCH")
        with partial.open("wb") as target:
            while block := response.read(CHUNK):
                target.write(block)
    if partial.stat().st_size != boundary:
        partial.unlink(missing_ok=True)
        raise RuntimeError("HELD_WIKIMEDIA_RANGE_SIZE")
    partial.replace(output)
    return {
        "content_range": content_range,
        "etag": headers.get("etag"),
        "last_modified": headers.get("last-modified"),
        "parent_bytes": int(content_range.rsplit("/", 1)[1]),
    }


def expanded_identity(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    total = 0
    with bz2.open(path, "rb") as source:
        while block := source.read(CHUNK):
            decoder.decode(block, final=False)
            digest.update(block)
            total += len(block)
    decoder.decode(b"", final=True)
    return total, digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch a bounded, complete-stream English Wikipedia benchmark fixture.")
    parser.add_argument("--dump-date", default=DEFAULT_DATE)
    parser.add_argument("--shard", default=DEFAULT_SHARD)
    parser.add_argument("--max-compressed-bytes", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    stem = f"enwiki-{args.dump_date}-{args.shard}"
    base = f"https://dumps.wikimedia.org/enwiki/{args.dump_date}/"
    parent_name = stem + ".bz2"
    index_name = stem.replace("multistream", "multistream-index").replace(".xml-", ".txt-") + ".bz2"
    sums_name = f"enwiki-{args.dump_date}-sha1sums.txt"
    index_data, _ = fetch(base + index_name)
    sums_data, _ = fetch(base + sums_name)

    rows = []
    for line in bz2.decompress(index_data).decode("utf-8").splitlines():
        offset, page_id, title = line.split(":", 2)
        rows.append((int(offset), int(page_id), title))
    offsets = sorted({row[0] for row in rows})
    boundaries = [offset for offset in offsets if 0 < offset <= args.max_compressed_bytes]
    if not boundaries:
        raise RuntimeError("HELD_WIKIMEDIA_FIXTURE_LIMIT_TOO_SMALL")
    boundary = max(boundaries)
    covered = [row for row in rows if row[0] < boundary]

    parent_sha1 = None
    for line in sums_data.decode("ascii").splitlines():
        value, name = line.split(None, 1)
        if name.strip() == parent_name:
            parent_sha1 = value
            break
    if parent_sha1 is None:
        raise RuntimeError("HELD_WIKIMEDIA_PARENT_CHECKSUM_ABSENT")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    fixture = args.output_dir / f"{stem}-prefix-{boundary}.bz2"
    manifest_path = args.output_dir / "SOURCE-MANIFEST.json"
    if not args.replace and (fixture.exists() or manifest_path.exists()):
        raise RuntimeError("HELD_WIKIMEDIA_FIXTURE_EXISTS")
    http = fetch_range(base + parent_name, boundary, fixture)
    expanded_bytes, expanded_sha256 = expanded_identity(fixture)
    manifest = {
        "schema": "semcrys.wikipedia-fixture.v0.1",
        "standing": "REPRODUCIBLE_BENCHMARK_INPUT",
        "project": "English Wikipedia",
        "dump_date": args.dump_date,
        "parent": {
            "url": base + parent_name,
            "bytes": http["parent_bytes"],
            "sha1": parent_sha1,
            "etag": http["etag"],
            "last_modified": http["last_modified"],
        },
        "index_url": base + index_name,
        "fixture": {
            "filename": fixture.name,
            "derivation": "HTTP_RANGE_PREFIX_ENDING_BEFORE_NEXT_COMPLETE_BZIP2_STREAM",
            "content_range": http["content_range"],
            "bytes": fixture.stat().st_size,
            "sha256": sha256(fixture),
            "expanded_bytes": expanded_bytes,
            "expanded_sha256": expanded_sha256,
            "utf8": True,
            "complete_article_streams": len({row[0] for row in covered}),
            "index_rows": len(covered),
            "first_page": {"id": covered[0][1], "title": covered[0][2]},
            "last_page": {"id": covered[-1][1], "title": covered[-1][2]},
            "redistributed": False,
        },
        "source_documentation": [
            "https://meta.wikimedia.org/wiki/Data_dumps/What%27s_available_for_download",
            "https://meta.wikimedia.org/wiki/Data_dumps/Dump_format",
            "https://meta.wikimedia.org/wiki/Research:Data",
        ],
        "content_license": ["CC-BY-SA-3.0", "GFDL"],
        "claim_boundary": "Benchmark input identity only; no SemCrys performance claim.",
        "authority_effect": "NONE",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
