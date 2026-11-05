# SemCrys 0.1.0rc1 — release candidate

The separately rooted synchronization successor adds read-only Lite/full
event-model measurement surfaces; see `SYNCHRONIZATION.md`. It does not change
the rc1 container or legend ABI and is not an independent release acceptance.

Documentation reviewed: 2026-08-31. This date records the candidate review;
it is not a public release date.

SemCrys is a legend-centered, lossless encoding application for file compression,
pre-shared transport, and growing correspondence legends. It uses an explicit
S > CM1 > CM2 > IC > IR configuration funnel. Apache-2.0 covers application
code, not external datasets or legends.

This is a technically qualified release candidate, not an independently accepted
or authorized public release. RELEASE_SCOPE.json, also returned by `capabilities`, retains the eight
release obligations and separates implemented workflows, unavailable mechanisms,
and unproved properties. Historical development notes are not the current guide.

## Run or install

Requires Python >=3.12 with standard-library sqlite3, lzma, and bz2; Python is not
bundled. There are no third-party Python runtime dependencies. No network service,
LLM, Ollama, private legend, or old workspace is required.

```text
python semcrys.pyz --help
python semcrys.pyz verify-self
python semcrys.pyz capabilities
python semcrys.pyz formats
python -m pip install --no-index --no-deps semcrys-0.1.0rc1-py3-none-any.whl
```

After installation use `semcrys` or `python -m semcrys`. SEMCRYS.cmd is the
portable Windows helper. `verify-self` checks the embedded manifest, not publisher
authenticity if an attacker can replace both files. Builds use
build_distribution.py and offline setuptools/wheel; unstaged source builds refuse
missing rooted payload preparation. RUNTIME_INVENTORY.json records dependencies.

## Formats and profiles

Application v0.1 uses .crys container ABI 0.2, binary .leg ABI 0.2, and JSON .gly
ABI 0.1. Fold/assembly legends declare critical variants. `formats` describes
fourteen critical Instance Constitution variants. Renaming old files is not migration.

| Profile | Input and legend behavior |
| --- | --- |
| C:RAW_BYTES | Arbitrary bytes; no token legend. |
| C:SELF_CONTAINED_TOKEN | Strict UTF-8; current-document legend travels with it. |
| T:PRESHARED_TOKEN | Strict UTF-8; exact root-bound external legend chain. |
| A:LONGITUDINAL_TOKEN_DELTA | Strict UTF-8; prior chain plus embedded missing-unit delta. |

Legend supply order: **encoding** requires parent-ordered base then deltas.
For **decoding**, required external legend files may be supplied in any order;
the container declares chain order and files are selected by their exact roots.
This does not relax missing-root, lineage, or duplicate-value checks.

Progress presentation: `semcrys --progress summary encode ...` emits compact
stderr stage events; `--progress quiet` suppresses progress. The default is
`full` for compatibility. Put this global option before the command.
Machine-readable stdout, typed refusal outcomes, and the full configuration
in operation results / requested `--receipt` files are unchanged.

Small files can be larger as `.crys` than plain XZ because the container carries
rooted configuration, section manifests, framing, and sometimes embedded legends.
There is no universal 3,129-byte minimum. `semcrys inspect FILE.crys` reports
`byte_accounting`: BODY, embedded legend payload, other section payload, and
framing/header/manifest bytes; their sum equals the container's size. This is
physical delivery accounting, not a compression-superiority or security claim.

Pre-shared Union/domain/Ultra legends are the intended computer-use pathway;
no universal best legend ships with the application. Explicit longitudinal deltas
can extend that base. No automatic adoption or transmission of private state occurs.

Commands below follow `python semcrys.pyz` (or installed `semcrys`):

```text
encode book.txt book.crys --profile C:SELF_CONTAINED_TOKEN --outer-codec LZMA --receipt book.receipt.json
decode book.crys book.restored.txt
encode photo.bin photo.crys --profile C:RAW_BYTES --outer-codec LZMA
legend build union.txt union.leg --policy TOTAL
encode letter.txt letter.crys --profile T:PRESHARED_TOKEN --legend union.leg --outer-codec LZMA
decode letter.crys restored.txt --legend union.leg
inspect letter.crys
```

LZMA selects LZMA2 in XZ framing, preset 6, not a separate competitor to XZ.
NONE omits it. The frozen NONE/LZMA spellings retain dev73 configuration and
byte behavior. Explicit successor profiles `LZMA2_XZ_0`, `LZMA2_XZ_6`,
`LZMA2_XZ_9`, `BZ2_1`, and `BZ2_9` bind algorithm, framing, level, dictionary
mode, and order in a v0.9 Instance Constitution. ZSTD names are visible but
fail with `HELD_OPTIONAL_CODEC_ADAPTER_NOT_PACKAGED`; there is no silent fallback.
Tokenization preserves bytes, punctuation and line endings; units
over 4096 bytes stay literal. TOTAL prioritizes coverage; PROFITABLE is a raw-cost
heuristic, not a compressed-size guarantee. Uncovered pre-shared units remain
explicit literals; coverage is not fabricated.

## Configuration and accounting

`profiles` lists the installed model. `plan INPUT --profile PROFILE ...` exposes
the effective configuration. S is declared phase space; CM1 is functional
admissibility; CM2 is explicit choice or measured desirability; IC binds the
selected inputs/options; IR records realization and inverse. Encoding verifies
reconstruction before publication.

```text
library build library.json --member union UNION union.leg --member medicine DOMAIN medicine.leg
select input.txt choice.json --library library.json --legend union.leg --legend medicine.leg --accounting COLD --outer-codec LZMA
encode-selected input.txt choice.json output.crys --library library.json --legend union.leg --legend medicine.leg
```

Selection measures declared candidates on the exact source, retains a baseline,
and counts dependencies. It does not predict unseen workloads or prove global
optimality. WARM accounting needs explicit `--receiver-root SHA256` declarations
for known dependencies. Local availability is not remote possession.
Cold acquisition, warm transfer, and audit-inclusive delivery are separate;
omitting audit bytes does not prove its evidence passed. See LIBRARY_FORMAT.md
and ARCHIVE_SELECTION.md. Progress is stderr; rooted JSON results are stdout.

Versioned stacks extend this exact-source court without duplicating shared base
artifacts in the control manifest:

```text
library build-stacks stacks.json --stack-member union UNION 0 union.leg --stack-member hybrid HYBRID 0 union.leg --stack-member hybrid HYBRID 1 sparse-delta.leg
configuration select input.txt choice.json --library stacks.json --legend union.leg --legend sparse-delta.leg --codec NONE --codec LZMA --accounting COLD --horizon 8
configuration encode-selected input.txt choice.json output.crys --library stacks.json --legend union.leg --legend sparse-delta.leg
```

This surface compares RAW/local baselines and each exact Union, Ultra, domain,
sparse-extension, longitudinal or hybrid stack across explicit codecs. It verifies
every executable inverse, counts each missing root once, multiplies exact container
delivery by the declared identical-workload horizon, and uses candidate ID—not
runtime timing—to break byte ties. Family names are typed caller labels, not proof
of coverage or semantic fitness. See CONFIGURATION_SELECTION.md.

Outer-codec selection is a separate exact-source court:

```text
codec select input.txt codec-choice.json --profile C:SELF_CONTAINED_TOKEN --accounting COLD
codec encode-selected input.txt codec-choice.json output.crys
```

It creates every available complete `.crys`, verifies every inverse, charges
missing legend dependencies under COLD accounting, and selects the smallest
measured total with caller order as the tie-break. The rooted record identifies
the application payload/runtime and gives every candidate an explicit codec,
framing, level, dictionary and operation-order descriptor. It does not predict another
file or claim a globally optimal codec. See CODEC_SELECTION.md.

## Growing correspondence and batching

```text
encode letter1.txt letter1.crys --profile A:LONGITUDINAL_TOKEN_DELTA --legend base.leg
legend extract letter1.crys delta1.leg --binding-index 1
encode letter2.txt letter2.crys --profile A:LONGITUDINAL_TOKEN_DELTA --legend base.leg --legend delta1.leg
decode letter2.crys restored.txt --legend base.leg --legend delta1.leg
batch-encode new-directory --source first.txt --source second.txt --profile T:PRESHARED_TOKEN --legend union.leg --outer-codec LZMA
```

Extraction indices are zero-based positions in the inspected full stack; only
embedded legends are extractable. Deltas bind exact parents. Adoption means
explicitly supplying a delta later, not mutating the base. Batch encoding reuses
verified contexts and publishes separate numbered containers plus a receipt;
it is not automatic history adoption or a group legend.

## Additional explicit workflows

| Workflow | Entry points and detailed contract |
| --- | --- |
| Glyph projection | glyph build/export, encode --projection GLYPH; GLYPH_FORMAT.md |
| Integer projection | encode --projection INTEGER; INTEGER_PROJECTION.md |
| SemCrys-A control profiles | archaic profiles/plan; SEMCRYS_A.md |
| Transport control | transport capabilities/negotiate/frame/verify-frame; TRANSPORT_CONTROL.md |
| Read-only GTK analysis | gtk capabilities/analyze/vocabulary/verify-vocabulary; GTK_ANALYSIS.md |
| Migration/release inspection | workbench status/export; MIGRATION_WORKBENCH.md |
| Folded fronts | fold build/prefix/extract, encode --fold-front; FOLD_FORMAT.md |
| Audit/execution separation | fold compact/audit/restore-rich/delivery-cost; COMPACT_PROJECTION.md |
| Exact archive selection | archive select/encode-selected; ARCHIVE_SELECTION.md |
| Exact outer-codec selection | codec select/encode-selected; CODEC_SELECTION.md |
| Legend-stack × codec selection | library build-stacks, configuration select/encode-selected; CONFIGURATION_SELECTION.md |
| Explicit form assemblies | assembly build/inspect/expand/encode; ASSEMBLY_EVENTS.md |
| Longitudinal assemblies | assembly build-delta/encode-longitudinal; LONGITUDINAL_ASSEMBLY.md |
| Single-container second pass | second-pass; SECOND_PASS.md |
| Multi-document group legends | group-legend pack/unpack; GROUP_LEGEND.md, META_AUXILIARIES.md |
| Recursive legend-of-a-legend | metalegend build/inspect/verify/restore; METALEGEND.md |
| Ordered historical legends | legend import-ordered-v01; ORDERED_IMPORT.md |
| Explicit historical containers | legacy import; LEGACY_MIGRATION.md |
| File/directory recovery | recovery inspect/rollback/directory-inspect/directory-quarantine; RECOVERY.md, DIRECTORY_RESOURCES.md |

Glyph registries and folded fronts may be embedded or externally root-bound.
Wrong or missing dependencies refuse substitution. Group-legend archives support
explicit external auxiliaries through repeatable pack --glyph/--fold-front.

Form rules are supplied, not inferred; assembly IDs are local transport
projections, not canonical CSIL identities. Second pass composes one event
stream and proves discard of intermediate artifacts; group legends pool records
across documents. Neither is universally smaller; second pass may lose after
XZ. MIN_DELIVERY retains the smaller declared complete delivery.

`second-pass --hot-k N` exposes the bounded initial-frequency hot-set size.
The frozen default `N=3` retains the v0.8 TOP3 container. Any other positive
value uses the new critical v0.11 TOPK constitution, records `hot_k`, and still
requires both event-stream and source-byte inverses. Dispersion remains an
observational objective, never a confidentiality claim.

Legacy import requires explicit historical format, exact source hash and
dependencies, then decodes/re-encodes rather than reinterpreting old IDs.
JSON legend migration is separate. Unknown wrappers and unsupported
compositions remain typed refusals, not guessed compatibility.

## Resources and publication

Producing workflows have separate resource models and a default 4 GiB logical
temporary-storage budget (--max-scratch-bytes). See APPLICATION_RESOURCES.md,
LEGEND_RESOURCES.md, COMPOSITE_RESOURCES.md and DIRECTORY_RESOURCES.md for exact
operation limits/exclusions. This is not a RAM cap or proof of all maxima
combined. Numeric 1 TiB reader caps do not mean 1 TiB inputs were qualified.
Large legends use binary storage and sparse disk lookup; disposable .legidx
caches are not transported identity. VERIFIED_CONTEXT.md defines custody reuse.

Existing file/receipt targets require --replace; new-directory operations refuse
existing destinations. Publication and explicit recovery coordinate cooperating
processes via nonblocking parent locks in one supported local OS lock domain.
Atomic no-replace preserves targets created after preflight. Rollback checks
committed identity/root and retains evidence on disagreement.

The persistent zero-byte .semcrys-publication.lock is local metadata; do not
remove it while writers run. Output and receipt are not a crash-atomic pair.
Arbitrary external in-place writers, hostile directories, network locking,
power-loss durability and Windows/WSL shared-target safety are not qualified.
Use one OS owner per output parent. See PUBLICATION_SAFETY.md.
Recovery inspection is read-only; mutation is explicit and root-bound.

## Qualification and boundaries

The v0.1.0rc1 source qualification ran 916 applicable predecessor tests, one
documented environment skip, 250 predecessor subtests, 81 successor tests, and
21 successor subtests. Thirteen dev73 assertions tied to that frozen build's
version, package path, documentation, command denominator, or ABI denominator
were replaced by successor assertions rather than counted as current failures.
See RELEASE_CANDIDATE.md and the packaged release-qualification receipt.

The predecessor dev64 qualified Windows CPython 3.12 and Ubuntu/WSL CPython 3.14:
893 Windows passes plus one environment skip, 97 Linux publication/recovery
passes, 54 byte-identical cross-platform ABI cases and four actual bounded tmpfs
disk-full cases. The 1/64 MiB repeated-record probes are not universal memory or
large-vocabulary proof. These are inherited facts; the enclosing dev65 report
records fresh tests rather than assuming successor acceptance.

Unavailable mechanisms remain explicit: form+glyph/fold; second-pass
glyph/fold/already-composed input; recursive group-legend archives; ancestor
assembly operands; shared composed-second-pass placement; BOUND/GCNL dictionary
glyph semantics; historical member archives; delegated encryption. Listing
them does not make them executable or erase a release obligation.

Independent whole-application acceptance is not self-awarded. Technical release-
candidate qualification does not authorize public publication. Encoding,
withheld legends, shuffles, hashes and second passes
alone do not establish cryptographic confidentiality. No encryption adapter,
canonical CSIL/GTK mutation, admission, production routing or public release
is implied. Local tests never change candidate standing.

Transport negotiation is read-only and transport-independent. The caller must
request the exact pathway, codec, projection and ordered legend chain (or an
explicit self-contained disposition). It can root/verify a
sidecar frame over exact `.crys` bytes. Legend version, supersession,
compatibility, and acquisition locations are advisory repair information, never
an executable substitute for `HELD` custody of an exact root. Peer capability
records, the realized Instance Constitution, and the negotiation document are
all hash-bound into the frame. No socket, remote attestation,
relationship-state mutation, encryption, keyed shuffle, or homophonic adapter
is packaged. See TRANSPORT_CONTROL.md.

GTK analysis is independently rooted and read-only. It distinguishes GTK
bound-term dossier identity, local legend transport IDs, and unassigned model
token IDs; measures semantic coverage separately from exact legend exposure;
fails closed on unresolved GCNL senses; and never corrects source text. Explicit
vocabulary export requires acknowledgement that it discloses legend contents.
See GTK_ANALYSIS.md.

The outer codec is not applied by default; see `ULTRA_CONFIGURATION.md` for the
measured effect on pre-shared-legend encodes.
