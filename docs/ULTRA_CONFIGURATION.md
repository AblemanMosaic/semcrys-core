# Ultra legend: configuration and measured results

The Ultra family legend is distributed as a seekable one-level recursive
`.mleg`. It may be queried directly by local legend integer or restored before
use. The metalegend operates on logical ordered legend records, not opaque
`.leg` bytes.

    semcrys metalegend restore ULTRA_FAMILY.mleg ultra.leg

| property | value |
|---|---|
| seekable metalegend sha256 | `e39a0067bd1285f521ece7b401edd827e2cca851a10fed2cec5df2fcdfd93e9a` |
| seekable metalegend bytes | 23,632,901 |
| whole-stream control bytes | 22,814,230 |
| restored legend bytes | 54,102,082 |
| restored legend sha256 | `4e837160f1d0f3ccf1d568e01592286dbe0d982f862f0191db1d570f7b36d6b4` |
| reduction from raw legend | 56.317945% |
| seekability cost over whole-stream control | 818,671 bytes (3.588423%) |
| data frames | 8 (128 recipe blocks per frame) |

The extra 818,671 bytes purchase bounded targeted inflation, direct local-ID
lookup, per-frame corruption isolation, decoded-frame caching, and verified
promotion to the exact full legend. The whole-stream form remains a supported
control for custody contexts that value the final 3.59% more than access speed.

## The outer codec is not applied by default

Encoding against a pre-shared legend does **not** apply an outer codec unless
one is requested. On Pride and Prejudice (717,602 bytes, sha256
`441e778a4297bfc944dc254810e8ded3134cfb0e36d73eef6bb312b4ffd74d6a`) under `T:PRESHARED_TOKEN`:

| configuration | container bytes | ratio |
|---|---|---|
| default (`--outer NONE`) | 416,852 | 0.581 |
| `--outer LZMA` | **200,520** | **0.279** |
| `xz -6` on the source | 210,860 | 0.294 |

Both round-trip byte-identically. The published 200,520 figure — a 4.9%
improvement on the baseline — is the `--outer LZMA` configuration. The default
configuration loses to the baseline by 98%.

    semcrys encode book.txt book.crys \
        --profile T:PRESHARED_TOKEN --legend ultra.leg --outer LZMA

## Hash provenance

Every digest on this page was read from `sha256sum` output on the actual
artifact, not transcribed from a truncated display. The container digest
published before this revision was wrong: it shared only its first four bytes
with the real value, because the remainder had been filled in rather than
measured. The payload was never affected — the container's internal roots,
`verify-self`, and the restored-legend digest were all correct and
self-consistent throughout — but a published integrity claim was not.

The Ultra metalegend is a release-bound asset. `verify-self` checks its physical
root and the logical legend identity declared in its header. The full court also
restores and hashes all 54,102,082 bytes; an envelope check is not substituted
for that inverse proof.

## Reporting rule

No ratio is published without the configuration that produced it. A figure
quoted without its `--outer` setting, legend root, and profile is not a claim
this project makes.
