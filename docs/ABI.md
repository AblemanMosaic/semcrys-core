# SemCrys candidate ABI and profile contract

Documentation reviewed: 2026-08-31 for SemCrys 0.1.0rc1. This is not a
public release date.

`semcrys formats` emits the rooted, machine-readable ABI/profile registry.
`ABI_REGISTRY.json` is its packaged snapshot; `capabilities` binds the same
registry root. This document and registry consolidate the implemented v0.1
application, whose container and binary legend formats are version 0.2.
Candidate stability is not independent release acceptance.

## Interpretation boundary

A `.leg` is not identified by its suffix alone. Binary legends use
`SCLEG\r\n\x1a`, version 0.2 and a canonical UTF-8 JSON header. Fold projections
use `SCFOLD\x1a\n`, with a different header and signal grammar. The exact bytes,
including the header, define the referenced SHA-256; local integer IDs are
one-based positions within that rooted ordered artifact, not canonical CSIL IDs.

The raw structural legend reader may preserve an unknown unit mode as opaque
data. The execution reader accepts only TOKEN, ASSEMBLY_EVENTS_V1,
ASSEMBLY_EVENTS_COMPACT_V1, COMPOSED_EVENTS_V1 and META_RECORDS_V1. A pool is
still not an ordinary token table: ordinary encoding/decoding refuses it, and
fold construction now requires literal TOKEN. Unknown modes cannot acquire
semantics by falling through to literal interpretation.

## Framing

`.crys`: big-endian `>8sHHI` prologue: magic, major, minor, header-byte count.
Sections use `>4sHHQ32s`: type, flags, reserved, payload length, SHA-256.
Critical bit 1 means an unknown type refuses; unknown noncritical payloads are
still bounded and hashed. Required ICFG precedes optional dependency sections,
BODY, optional RCPT, and the rooted DONE manifest. Exact ordering and fields are
enforced by the format reader. Hashes establish integrity, not sender identity.

Binary `.leg`: same prologue shape, then canonical header and length-prefixed
stored values (canonical unsigned 64-bit LEB128). A sparse index uses big-endian
u64 offsets. The `>4sQQ32s32s` LEND footer binds index position, length and
separate value/index digests. Original index stride is part of file identity.

`.gly`: canonical UTF-8 JSON; exact ordered scalar alphabet, kind and bindings.
TEMPLATE supports token-ID projection; BOUND is representable but its dictionary
semantics are not inferred or executable through the current token adapter.

## Configuration variants

Current registry: 14 critical Instance Constitution variants.

| Registry ID | Instance schema | Interpretation / body | Dependency condition |
|---|---|---|---|
| ORDINARY | semcrys.instance-constitution.v0.2 | Raw or ordinary token; RAW2 / SPV2 | none / embedded / exact shared / append-only delta |
| GLYPH | semcrys.instance-constitution.v0.3 | Glyph token projection; SGY1 | exact TEMPLATE alphabet; embedded or external |
| INTEGER | semcrys.instance-constitution.v0.10 | Canonical inspectable integer/literal projection; SIT1 | token profiles; local rooted legend-stack IDs |
| FOLD_EMBEDDED | semcrys.instance-constitution.v0.4 | Embedded folded front; SPV2 | one TOKEN base; embedded rich/compact projection |
| FOLD_EXTERNAL | semcrys.instance-constitution.v0.5 | External folded front; SPV2 | exact base and projection roots; explicit accounting |
| FORM_TAGGED | semcrys.instance-constitution.v0.6 | Tagged form programs; SPV2 | explicit form ABI, local integer namespace |
| FORM_COMPACT | semcrys.instance-constitution.v0.7 | Compact/mixed form programs; SPV2 | explicit form-family ABI, exact program expansion |
| COMPOSED | semcrys.instance-constitution.v0.8 | Composed single-file events; SPP1 | one embedded composed legend; event and source roots |
| ORDINARY_EXTENDED_OUTER_CODEC | semcrys.instance-constitution.v0.9 | Ordinary PACKED profiles with explicit XZ/BZ2 algorithm configuration | exact source and legend roots; rooted codec/framing/level/dictionary/order |
| COMPOSED_TOPK | semcrys.instance-constitution.v0.11 | Configurable hot-set composed events; SPP1 | explicit positive hot_k; exact event/source inverse |
| GROUP_LEGEND_ARCHIVE (`META_ARCHIVE` legacy ID) | semcrys.metalegend-instance.v0.1 | Group archive; historical schema name; SMA1 | exact group pool; original-artifact inventory root |
| GROUP_LEGEND_BUNDLE (`META_BUNDLE` legacy ID) | semcrys.metalegend-bundle-instance.v0.1 | Complete group bundle; historical schema name; XZ_CRYS | exact v0.1 inner archive and inventory roots |
| GROUP_LEGEND_ARCHIVE_AUX (`META_ARCHIVE_AUX` legacy ID) | semcrys.metalegend-instance.v0.2 | Typed group archive; historical schema name; SMA1 | exact GLYPH/FOLD auxiliary roots and v0.2 inventory |
| GROUP_LEGEND_BUNDLE_AUX (`META_BUNDLE_AUX` legacy ID) | semcrys.metalegend-bundle-instance.v0.2 | Typed group bundle; historical schema name; XZ_CRYS | exact v0.2 inner archive and inventory roots |
| SEEKABLE_METALEGEND | semcrys.seekable-metalegend.v0.1 | One ordered legend in independently rooted recipe superframes; SCMLEG2 | exact original `.leg`, direct local-ID lookup, cache promotion |
| WHOLE_STREAM_METALEGEND | semcrys.recursive-metalegend.v0.1 | One ordered legend in one compressed recipe stream; SCMLEG1 | exact original `.leg`; compact compatibility control |

The registry contains each exact top-level field set. SPP1 is distinct from
SMA1: within-document event composition is not cross-document legend pooling.
The source root in ordinary containers denotes decoded bytes; the legacy group
container's decoded root denotes its canonical inventory, whose entries bind
the exact original files. Use `group-legend unpack` (or the v0.1 compatibility
alias `metalegend unpack`), not ordinary `decode`.

LZMA means preset-6 LZMA2 in XZ framing on BODY. With the historical-schema
group-bundle IC, that BODY contains the entire byte-exact self-contained inner
group archive, including its pool and control fields. The outer envelope
remains uncompressed. Only an EMBEDDED/NONE group inner archive
is allowed; arbitrary or recursive wrapper input refuses. Its exact bytes,
configuration root and inventory root must match after bounded decompression.
External audit dossiers remain separate and are not made free by this layout.

## Compiler funnel and compatibility

S is the declared phase space. CM1 checks whether a configuration can function
with its actual formats, dependencies and limits. CM2 selects according to a
declared objective and accounting state; Union/Ultra selection is an optimization,
not the definition of functional admissibility. IC freezes the selected inputs
and operations; IR records the realized bytes and checks. No phase grants authority.

Known critical features require exact implementations. No silent schema downgrade,
suffix renaming, unknown-mode fallback or implicit legacy conversion is permitted.
Explicit migration decodes the declared historical representation and re-encodes
its exact source bytes; it does not preserve old local integer IDs or reinterpret
old bytes as a current container. Frozen historical artifacts remain unchanged.

## Explicit legacy compatibility

| Registry policy | Value | Public operation |
|---|---|---|
| legacy_json_legend | EXPLICIT_MIGRATE_V01 | legend migrate-v01 |
| legacy_ordered_legend | EXPLICIT_IMPORT_ORDERED_V01 | legend import-ordered-v01 |
| legacy_sc_codec | EXPLICIT_LEGACY_IMPORT_SC_TEXT_V1_V2_AND_SCB1 | legacy import |

`legacy import` supports declared SC_TEXT v1/v2 and SC_PACKED (SCB1) inputs,
with the exact expected source root, explicit glyph registry and sidecar where
required. No ambient legend discovery, suffix-only selection or automatic
conversion occurs. Historical member archives remain held; unknown wrappers and
unsupported compositions refuse. See `LEGACY_MIGRATION.md` for exact switches
and format limits, and `RELEASE_SCOPE.json` for the current held-mechanism list.

## Qualification limits

The historical 48-cell/eight-variant matrix and subsequent ninth-variant bundle
extension are lineage evidence, not the current inventory. The reviewed dev65
baseline has 54 byte-identical Windows/Linux ABI witnesses across the current
twelve variants, plus installed legacy and auxiliary-layout checks. Those are
bounded profile/placement/codec cases, not proof of the whole Cartesian product.
External GLYPH/FOLD group-legend auxiliaries are implemented by the explicit v0.2
variants below. Form-plus-glyph/fold and recursive metalegend composition remain
held; typed support here does not enable those separate combinations.

The registry declares parser and feature limits, not an operating-system memory
or crash certificate. Process measurements and negative cases remain separate
evidence. Existing Windows/Ubuntu-WSL qualification is not all-platform or
independently provisioned clean-machine coverage. Power-loss durability and
cryptographic confidentiality are not proved. Release acceptance is recorded
by the enclosing review evidence, never inferred from this registry or guide.

## Typed group-legend auxiliary variants

`GROUP_LEGEND_ARCHIVE_AUX` uses the historical wire schema
`semcrys.metalegend-instance.v0.2` and adds exactly
`auxiliary_contract_root` to the prior top-level configuration. Its limits add
`auxiliaries: 64`; inventory schema is `semcrys.restored-artifacts.v0.2`, with
typed GLYPH/FOLD artifacts after containers and ordinary legends. Auxiliaries
are sorted by (kind, root), unique, nonempty in this variant, and bounded in total.
The SMA1 physical grammar remains unchanged; auxiliary bytes are literal spans.

`GROUP_LEGEND_BUNDLE_AUX` uses the historical wire schema
`semcrys.metalegend-bundle-instance.v0.2`, with the same
field set as the prior bundle but strictly requiring a v0.2 auxiliary inner
archive. v0.1 and v0.2 inner/outer mixing is refused. Old readers refuse these
critical schemas. See `META_AUXILIARIES.md` and the shipped rooted contract.
