# Wikipedia qualification fixture

This directory defines a reproducible, bounded comparison against an official
English Wikipedia multistream dump. It does not contain Wikipedia article data.

`SOURCE-MANIFEST.json` pins the 2026-10-01 parent object, official SHA-1,
HTTP range, derived fixture SHA-256, expanded SHA-256, and page boundaries. The
fixture is the first 717,512 compressed bytes: the dump header stream followed
by one complete article stream containing 100 indexed pages. It expands to
2,763,849 bytes. Because it is a stream prefix, it is intentionally not a
complete well-formed XML dump.

## Reproduction

```powershell
python -B tools\fetch_wikipedia_fixture.py --output-dir "$env:TEMP\semcrys-wikipedia" --max-compressed-bytes 1048576
$env:PYTHONPATH = "$PWD\src"
python -B tools\benchmark_wikipedia.py "$env:TEMP\semcrys-wikipedia\enwiki-20261001-pages-articles-multistream1.xml-p1p41242-prefix-717512.bz2" --manifest benchmarks\wikipedia\SOURCE-MANIFEST.json --output evidence\WIKIPEDIA-BENCHMARK.json
python -B tools\verify_wikipedia_evidence.py
```

The fetcher requires the official server to honor the pinned byte range and
fails closed on identity mismatch. Network access is only needed to reproduce
the fixture. SemCrys Core remains offline and standard-library-only at runtime.

## What is measured

Wikipedia is one input to the general configuration court described in
`docs/CONFIGURATION_COURT.md`. The qualification restores and verifies the exact
release-bound Ultra legend, then measures:

- direct RAW, BZ2 levels 1/9, and XZ presets 0/6/9 controls;
- SemCrys RAW, self-contained, Ultra pre-shared, and Ultra longitudinal-delta
  recipes under NONE, LZMA, and BZ2-9;
- byte-exact decode for every SemCrys candidate and every compressed control;
- cold and warm custody at exact reuse horizons 1, 2, 4, 8, 16, and 32;
- separate unconstrained, SemCrys, integerized, full-integerization, and
  shared-legend winners.

`FULL_INTEGERIZATION` means complete lexical integerization under this compiler
profile, not externally adjudicated word-sense identity. Profitable
integerization may leave unprofitable units literal. Both remain exactly
reversible.

## Claim boundary

The evidence is one fixture on one host. It proves an optimum only among the
enumerated candidates for this exact source, custody state, horizon, and
capability lane. It does not support claims about all of Wikipedia, all
machines, unseen corpora, or complete Memory Vault workloads. The official BZ2
stream also has a different delivery contract than a SemCrys artifact carrying
integerization state.

The source content remains under its stated CC BY-SA 3.0 and GFDL terms. Only
identity metadata and measurements are published here; corpus bytes are not.
