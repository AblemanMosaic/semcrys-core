# Fold-front application bridge — candidate v0.1

Apache-2.0 implementation. No release, admission, canonical CSIL identity or confidentiality claim.

## Commands

```text
semcrys fold build calibration.txt front.leg --legend base.leg --front-cap 4096 --receipt build.json
semcrys plan letter.txt --profile T:PRESHARED_TOKEN --legend base.leg --fold-front front.leg
semcrys encode letter.txt letter.crys --profile T:PRESHARED_TOKEN --legend base.leg --fold-front front.leg --outer-codec LZMA
semcrys decode letter.crys restored.txt --legend base.leg
semcrys fold extract letter.crys recovered-front.leg
semcrys inspect front.leg
```

Additional ordered calibration documents: repeat `--calibration FILE`. The caller designates calibration; the compiler does not know which files are research holdouts. Never supply evaluation documents to this builder when claiming held-out selection. It records every calibration snapshot hash. Builder limit: 512 documents, 64 MiB aggregate by default, configurable up to 1 GiB. Front cap: 0–65,536 entries. The API supports a VerifiedLegendContext; batch-encode supports --fold-front and guards its root across the batch.

## S → CM1 → CM2 → IC → IR

S: immutable-base move-to-front and concatenation projections; encoding, inverse realization and cost accounting.
CM1: current implemented composition requires exactly one root-qualified binary .leg v0.2 base with no parent, T:PRESHARED_TOKEN, PACKED output, fixed historical folded scanner and bounded projection. NONE or LZMA outer codec both work. Other profile/glyph/delta compositions refuse; they are not silently substituted.
CM2: the caller chooses front capacity. Ordering is calibration count descending, first occurrence ascending. Zero front retains constituent fallback with unchanged base order. No automatic scale/reuse-horizon selection yet; bigger fronts are not assumed better.
IC: base root, projection root, ordered calibration roots in projection, scanner identity, codec, resource bounds, source root, candidate standing.
IR: actual packed body, critical projection section, exact reconstruction, custody checks, root-bound receipt and byte accounting.

SFTIR remains external control notation, not the byte codec. This realization implements the previously evidenced domain operations: decompose folded miss, construct calibration-only macro front, reconstruct frozen tail, emit projection signal. These are SDO domain operations, not newly invented SFM primitives. This is no new proof of shared semantic identity or SFTIR predictive power.

## .leg projection ABI

An ordinary binary base legend still begins SCLEG CR LF SUB. A projection uses distinct 8-byte magic `SCFOLD\x1a\n`, then big-endian uint32 canonical-header length, canonical UTF-8 JSON, then compact signal. Old binary legend readers refuse the new magic; a projection is not a replacement base dictionary.

Header exact fields: schema=semcrys.legend.fold-projection.v0.1; standing=CANDIDATE_ONLY; base_legend_sha256; base_entries; front_entries; macro_entries; projected_entries; signal_sha256; signal_codec=MOVE_BASE_OR_CONCAT_TWO_BASE_ULEB128_V1; tokenizer=HISTORICAL_WORDMODE_FOLD_BOUNDED_V1; max_unit_bytes=4096; front_cap; ordering=CALIBRATION_COUNT_DESC_FIRST_SEEN_ASC; candidate_policy=OBSERVED_UNITS_PLUS_LONGEST_SEPARATOR_COMPONENTS_V1; calibration_roots (ordered, repetition significant).

Signal: canonical unsigned LEB128 front_count; each entry tag byte 0 + base_rank, or tag byte 1 + first_base_rank + second_base_rank. Ranks are positive and within the exact base. A tag-1 expansion concatenates a base prefix and a declared common separator, and must not already exist in the base. Duplicate moved ranks, duplicate macros, duplicate expansions, malformed varints, wrong counts, unknown fields, changed hashes or trailing bytes refuse.

Front ranks are 1..F. The tail is the original base order excluding moved base entries. The full virtual size is base_count + macro_count. Lookup uses the existing disk-backed base index plus the bounded front, not a second four-million-entry dictionary. Inverse tail lookup uses order statistics on sorted moved ranks. Transport ranks are not canonical CSIL identities.

Limits: artifact 4 MiB, header 64 KiB, 65,536 front entries, 4,096 bytes per front expansion, 16 MiB total expanded front. Construction and base-dependent validation remain separate. Inspect without the base checks structure, not the truth of base-dependent expansions.

## .crys bridge

Container prologue/header/manifest stay v0.2. New critical singleton FRNT section follows legends and precedes BODY. Its bytes are the exact projection artifact. ICFG v0.4 binds its SHA-256, schema, EMBEDDED placement, base SHA-256, front count and projected cardinality. Missing, noncritical, duplicate, unknown or mismatched features refuse. Older readers refuse FRNT as unknown-critical.

Body physical schema semcrys.folded-front-packed.v0.1 begins SFP1. Integers address the virtual rank view. Zero introduces length + literal bytes. A folded miss can emit two constituent IDs from that entire view, including existing front macros. Each macro still expands to two base ranks, so this does not introduce recursive legend definitions. IC records fold_fallback=FULL_PROJECTED_VIEW_CONSTITUENT_LOOKUP_V1. The decoder never interprets this body as ordinary SPV2.

The historical scanner preserves internal hyphen/underscore/apostrophe/dot/slash only when flanked by historical word characters; retains its original asymmetric CJK regex behavior; folds only the frozen common separator list. Oversize runs become bounded literal chunks. This bounded oversize policy is an explicit departure from unbounded historical unit segmentation, not a silent claim of whole-input token identity.

## Accounting and limits of the result

Receipt exposes signal bytes, full projection artifact bytes, physical body bytes and outer-body bytes. Result exposes full .crys warm wire size and cold acquisition plus wire size. Projection is embedded in EVERY container in this first bridge; it is not free and not amortized by the execution cache. Base acquisition is separate. Extraction does not change that accounting.

LZMA here means LZMA2 in XZ framing, preset 6. The original Court016 used preset 9. Its XZ measurements must not be silently compared as the same configuration. No new global compression superiority follows from byte-exact reconstruction.

Remaining: external/shared front placement; calibrated scale/horizon selector; composed morphology/assembly/second pass/group legends; full platform, corruption, release and independent-review courts. This bridge advances the full release-readiness goal, not completes it.

## Historical candidate-pool correction

The initial integration trial searched all base entries while building the front.
That yielded 21,068 entries, 184 more than the frozen 20,884, and failed the
preregistered signal-identity gate before evaluation replay. The failed attempt
is retained. Candidate selection is now explicitly
OBSERVED_UNITS_PLUS_LONGEST_SEPARATOR_COMPONENTS_V1: observed calibration units,
plus the prefix and separator from their longest matching common suffix. The
builder does not silently substitute full-base membership for that pool.

Encoding is a separate policy: FULL_PROJECTED_VIEW_CONSTITUENT_LOOKUP_V1, recorded in IC.
The original research harness limited fallback lookups to a combined evaluation
candidate pool; this application does not require other documents to encode one
letter. The replay therefore separately checks original body inverse compatibility
and the application's unrestricted-base emitted stream. Any byte differences are
reported, never hidden as historical encoder equivalence. No threshold is tuned
against evaluation results.

Attempt002 reproduced the exact signal but exposed ten fallback unit types whose
prefix was already a front macro (for example Captain + newline, followed by
another newline). Restricting fallback constituents to base entries discarded
this composition. The implementation now queries the entire projected view;
the second failed attempt and a focused regression retain that attribution.
# Historical dev32 addition: shared projection placement

The default embedded mode and its bytes are unchanged. Explicit
`--fold-placement EXTERNAL` uses IC v0.5 and one **critical FREF** section:
`{"schema":"semcrys.fold-reference.v0.1","binding":{...}}`.
Its canonical binding contains exactly schema, sha256, mode=EXTERNAL,
base_legend_sha256, front_entries, projected_entries. A reader must refuse
unknown critical FREF; FREF and FRNT are mutually exclusive singleton sections.
The projection .leg itself and SFP1 body are unchanged.

Decode requires both `--legend base.leg` and `--fold-front front.leg`.
The latter is loaded with a 4 MiB bound, root/schema checked, privately
snapshotted, then expanded against the exact base. Missing/wrong dependencies
refuse before output publication. Inspect without dependencies reports
EXTERNAL_NOT_RESOLVED, not proof of reconstruction. Fold extraction refuses
external references because the container does not contain that artifact.

External encoding and planning require explicit `--accounting COLD|WARM`.
Repeat `--receiver-root SHA256` for each dependency the receiver already has:
base and, when external, projection. WARM refuses unless all external roots
are declared present. COLD charges each missing complete binary artifact.
Local presence is never treated as remote possession.

The rooted **transfer IC** is local accounting evidence, separate from the
serialized realization IC. Changing only receiver state leaves container bytes
unchanged. Accounted bytes = exact .crys bytes + missing uncompressed dependency
artifact bytes. This excludes local JSON reporting receipts, OS/network framing
and acknowledgments; no network delivery or authentication is asserted.
For an explicit batch each missing dependency is charged **once**, with repeated
documents each charged as a container. Per-document standalone receipts must
not be summed as the batch acquisition total. Batch execution does not adopt
legend updates or mutate pre-shared relationship state.

Shared projection is not automatically optimal: the base/front acquisition,
reference/control framing, archive size, reuse horizon and outer codec all
matter. Scale-aware front selection remains unimplemented. The rest of this
document describes the inherited embedded mode and mechanism.
# Court034 additive format: compact projection

See COMPACT_PROJECTION.md and semcrys/COMPACT_PROJECTION_CONTRACT.json for the
explicit v0.2 compact schema and independently rooted audit dossier. The v0.1
specification below remains valid; default rich output and old bytes are unchanged.
