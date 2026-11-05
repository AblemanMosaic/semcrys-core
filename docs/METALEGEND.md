# Recursive metalegends

A SemCrys **metalegend** is a legend of a legend. It represents the ordered
logical records of a `.leg` as bounded reconstruction recipes and can restore
the original physical legend byte for byte. The original `.leg` does not need
to remain in custody after the `.mleg` has passed exact verification.

This is vertical recursion. Pooling records across a collection is a separate
horizontal operation called a [group legend](GROUP_LEGEND.md).

## Commands

```text
semcrys metalegend build SOURCE.leg OUTPUT.mleg
semcrys metalegend inspect OUTPUT.mleg
semcrys metalegend lookup OUTPUT.mleg ID [ID ...]
semcrys metalegend prepare OUTPUT.mleg --cache-root CACHE
semcrys metalegend verify OUTPUT.mleg
semcrys metalegend restore OUTPUT.mleg RESTORED.leg
```

For v0.1 compatibility, `semcrys metalegend pack` and `unpack` remain aliases
for `group-legend pack` and `unpack`. Existing group archive schemas and bytes
are unchanged.

## Representation

The v0.1 recursive profiles read verified logical legend entries in their exact
order. Entries are divided into bounded blocks. Each block begins with one
literal anchor; later records store a prefix length against the preceding
record and the exact remaining bytes. The recipe stream also carries the small
original prologue/header and sparse-index/footer envelope required for exact
physical reconstruction.

`--layout seekable` is the default. It groups recipe blocks into independently
compressed superframes, roots every compressed and decoded frame, and commits a
deterministic frame directory. `lookup` seeks to one frame for a requested local
legend integer. `--layout whole` preserves the original globally compressed
control, which is smaller but must inflate the complete recipe stream. Both
layouts court declared LZMA presets and publish only when strictly smaller than
the source `.leg`; `--allow-expansion` is an explicit research ablation.

This is not LZMA applied blindly to opaque `.leg` bytes: the transform operates
on logical record boundaries and its receipt exposes entry count, block count,
shared-prefix bytes, recipe bytes, codec candidates, and both physical and
logical roots.

## Invariants

- Recursion depth is exactly one in v0.1; `.mleg` input is refused.
- The restored `.leg` must match the original byte count and SHA-256.
- Block references cannot cross their anchor boundary.
- Frame offsets, compressed bytes, decoded recipes, the complete payload, and
  the frame directory are independently hash-bound.
- Truncation, trailing bytes, malformed recipes, decompression overflow, and
  physical or logical root drift are refused.
- The transform changes no local integer IDs and claims no CSIL, GTI,
  confidentiality, or authority effect.
- A consumer may restore the exact legend and use every existing SemCrys
  decoder unchanged.

## Cache and deployment profiles

The `.mleg` is the portable custody artifact. A local cache is derivable state,
never part of semantic identity. `COMPACT` retains few frames and recommends
full promotion only after broad access; `BALANCED` keeps a bounded decoded-frame
working set; `THROUGHPUT` promotes earlier. Every disk-cached frame is checked
against its recipe root. A promoted `.leg` is accepted only when its byte count
and SHA-256 equal the source identity committed by the metalegend.

For installation, keep the `.mleg` as the authoritative portable asset. Run
`metalegend prepare` when a workload will scan much of the vocabulary or needs
legacy readers. Narrow agent/index queries should remain on seekable frames.

## Ultra result

The release seekable Ultra metalegend reconstructs the 54,102,082-byte Ultra legend at
SHA-256 `4e837160f1d0f3ccf1d568e01592286dbe0d982f862f0191db1d570f7b36d6b4`.
Its exact size, physical root, control comparison, timings, and proof status are
recorded in `evidence/ULTRA-SEEKABLE-METALEGEND-COURT.json`; the release manifest, not
this prose, is the publication identity authority.

## Limits

The current recipe is deliberately narrow. It does not claim globally optimal
factorization, recursive depth beyond one, constant-time random lookup, semantic
equivalence between different legend records, or encryption. More elaborate
fragment dictionaries may be introduced only as separately versioned profiles
with exact inverse, corruption, resource, and complete-cost courts.
