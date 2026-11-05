# Wikipedia qualification and optimization dossier

This dossier interprets the rooted evidence in
`evidence/WIKIPEDIA-BENCHMARK.json`. Wikipedia is one qualification lane for
the general configuration court in `docs/CONFIGURATION_COURT.md`; it is not the
court's objective or a Wikipedia-specific codec mode.

The evidence covers one pinned 100-page English Wikipedia stream prefix on one
Windows AMD64 host. It proves enumerated-candidate optimality only. It makes no
whole-Wikipedia, cross-corpus, or global-optimality claim.

## Court result

| Representation | Bytes | Reduction from expanded XML | Difference from fresh BZ2-9 |
|---|---:|---:|---:|
| Expanded XML | 2,763,849 | 0.00% | +284.54% |
| Official multistream fixture | 717,512 | 74.04% | -0.16% |
| Fresh stdlib BZ2-9 | 718,692 | 74.00% | baseline |
| Fresh stdlib XZ-6 | 701,272 | 74.63% | -2.42% |
| SemCrys raw carrier + LZMA | 703,472 | 74.55% | -2.12% |
| SemCrys self-contained profitable + BZ2-9 | 873,818 | 68.38% | +21.58% |
| SemCrys Ultra profitable + LZMA | 671,046 | 75.72% | -6.63% |
| SemCrys Ultra full integerization + LZMA | 724,782 | 73.78% | +0.85% |

All 18 enumerated candidates were decoded and byte-exactly matched to the
2,763,849-byte expanded source before admission to the court.

When the receiver already holds the release-bound Ultra legend, the complete
delivery winner is `T:PRESHARED_TOKEN` with LZMA at 671,046 bytes. It is 30,226
bytes (4.31%) smaller than fresh XZ-6 and 47,646 bytes (6.63%) smaller than
fresh BZ2-9. This result was hidden by the previous self-contained-only court.

Full integerization selects `A:LONGITUDINAL_TOKEN_DELTA` with LZMA at 724,782
bytes. It costs 53,736 bytes (8.01%) more than profitable Ultra integerization,
and only 6,090 bytes (0.85%) more than fresh BZ2-9, while retaining total token
coverage and a parent-bound delta.

## Custody and reuse

Cold delivery must account for the 54,102,082-byte restored Ultra legend. For
one artifact, fresh XZ-6 therefore wins the unconstrained complete-delivery
lane at 701,272 bytes. A held Ultra legend changes the result immediately: the
warm winner is SemCrys Ultra profitable + LZMA.

The measured horizons 1, 2, 4, 8, 16, and 32 do not amortize a new Ultra
acquisition against this small repeated fixture. At the measured per-artifact
gap, the simple equal-workload break-even is about 1,790 artifacts. This is an
illustrative calculation, not a prediction for unlike corpora. A Memory Vault
that already holds Ultra is a warm receiver and should not charge the legend
again.

## Ultra evolution and the learned delta

The full-integerization run produced a 98,869-byte, 9,121-entry binary delta,
SHA-256 `6f6f77bd2c225128b88c9da63b1bf32f752471e020d021b9dd51bfd7bad113fe`,
parent-bound to Ultra root
`4e837160f1d0f3ccf1d568e01592286dbe0d982f862f0191db1d570f7b36d6b4`.
Diagnostic inspection found strong Wikipedia/MediaWiki/XML locality, alongside
ordinary alphabetic, numeric, and non-ASCII terms.

That delta is useful evidence that Ultra can continue to evolve. The entire
delta should first remain an exact Wikipedia/domain child legend. Promotion
into a successor Ultra requires recurrence, stability, cross-corpus utility,
and measured delivery benefit. Otherwise source-specific IDs, names, and markup
would make a universal asset larger without general benefit.

## Performance finding

The size configuration is now clear, but the full compiler remains slow on this
fixture. Approximate exact-verification wall times recorded by the court were:

| Configuration | Verification wall time |
|---|---:|
| Fresh XZ-6 control | 0.96 s |
| SemCrys raw + LZMA | 1.67 s |
| Ultra profitable + LZMA | 578.05 s |
| Ultra full + LZMA | 704.52 s |

These original court timings included diagnostic `tracemalloc` and an independent
decode after the encoder's mandatory postwrite reconstruction. They remain valid
historical integration observations, but they are not fast-lane throughput.
Phase-separated untraced evidence and the completed optimization are in
`docs/INTEGERIZATION_PERFORMANCE.md`.

## Next optimization priorities

1. Add an aggregate-memory-governed document worker pool only where repeated
   contexts or per-document work outweigh process coordination.
2. Accelerate token traversal only after pinning the current UTF-8 and Unicode
   classification contract.
3. Retain and compare domain deltas across multiple unlike corpora, then propose
   only recurrent entries for Ultra promotion.
4. Expand the court with repeated isolated timing trials across unlike corpora;
   encode, decode, preparation, filesystem, and verification are now separated.
5. Exercise related-document batches so group-legend and shared-delta benefits are
   measured rather than inferred from a single stream.
6. Repeat on larger and structurally different corpora before changing default
   selection policy.

## Acceptance targets

- preserve byte-exact recovery for every admitted candidate;
- keep cold and warm custody accounting explicit;
- retain XZ and BZ2 controls in every corpus qualification;
- require a capability lane before preferring full integerization;
- never promote a workload delta into Ultra from one corpus alone;
- make timing claims only from repeated isolated distributions.
