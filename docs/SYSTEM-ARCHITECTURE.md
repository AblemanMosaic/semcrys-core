# SemCrys system architecture

SemCrys Core v0.1.0 is one offline, lossless representation system with several
cooperating realizations. It combines archive construction, exact chunk reuse,
legend-based integerization, measured cross-document composition, optional
semantic bindings, optional protected custody, deterministic replay, and
release qualification. This document is the architectural front door to those
parts. Specialized documents remain normative for individual formats and
commands.

The ordinary user-facing path is intentionally smaller than the complete
capability surface:

```text
files or directory
  -> inventory and exact chunk deduplication
  -> eligible UTF-8 integerization
  -> individual and group-legend controls
  -> profit-governed local/cross-document composition
  -> optional caller-bound semantic occurrence index
  -> outer-codec selection
  -> exact reconstruction proof
  -> atomic .crys publication and receipt
```

Security projections, explicit legend construction, migration, transport
control, and configuration courts are advanced surfaces. They are never
silently implied by the default archive workflow.

## Realization map

```text
                         SemCrys Core facade
                                  |
            +---------------------+---------------------+
            |                     |                     |
     Standard archive        Full compiler       Lite reference codec
            |                     |                     |
   files/chunks/indexes     legends/assemblies     compact codec and
   adaptive composition    group/metalegends      security projections
            |                     |                     |
            +---------------------+---------------------+
                                  |
                    exact replay and qualification
                                  |
             source / wheels / zipapp / standalones
```

Full and Lite are release siblings with separate ABIs. The facade detects their
signatures and reports their combined capability surface without renaming or
silently converting either format. Standard composes bounded Full operations
into the recommended multi-file workflow.

## Subsystem inventory

### 1. Standard archive composer

**Purpose:** provide the turnkey `semcrys files-or-folder` experience.

Standard inventories logical files, preserves paths and selected metadata,
chunks large payloads, removes exact duplicate chunks, realizes eligible text
candidates, builds optional indexes, verifies every reconstructed file, and
publishes one `.crys` archive. Its default semantic mode fully integerizes
eligible UTF-8 payloads while retaining measured controls. `--mode smallest`
allows raw bytes to win when delivery size matters more than integer coverage.

**Primary commands:** `pack`, path-first shorthand, `list`, `inspect`, `verify`,
`unpack`, and `search`.

**Read next:** [Standard CLI](STANDARD_CLI.md) and the
[compression model](SEMCRYS-COMPRESSION-MODEL.md).

### 2. Full compiler

**Purpose:** realize the release's broad legend and assembly model.

Full owns `.crys` 0.2 containers, binary `.leg` 0.2 legends, `.gly` 0.1 glyph
registries, packed integer events, local/preshared/longitudinal profiles,
assemblies, folds, second-pass composition, group legends, recursive
metalegends, and configuration selection. It is the high-capability engine used
by Standard for eligible payloads.

**Boundary:** Full transport IDs are local to an exact legend stack and do not
create semantic identity.

**Read next:** [ABI](ABI.md), [assembly events](ASSEMBLY_EVENTS.md), and
[configuration selection](CONFIGURATION_SELECTION.md).

### 3. Lite reference codec

**Purpose:** provide a compact, independently bounded codec and the executable
security-projection ladder.

Lite owns CRYS-LITE 0.3 binary/text formats, ordinary whole-word and byte
profiles, keyed permutation, bounded aliases, frequency-balanced homophonic
aliases, independent position projection, protected moving legends, and
count/size padding. Full and Lite are not interchangeable by filename.

**Read next:** [Lite security](SECURITY-LITE.md) and [security and custody](SECURITY.md).

### 4. Legend system

**Purpose:** replace repeated stored units with compact reversible integer
references under explicit dependency custody.

The family includes local legends, the shared Ultra base, domain or
longitudinal deltas, assembly/form legends, group legends, glyph registries,
folded fronts, and recursive metalegends. A shared legend saves delivered bytes
only when the receiver's exact held root is declared and the applicable cold or
warm accounting supports the claim.

**Boundary:** equal stored records establish byte equality, not equivalent
meaning.

**Read next:** [legend resources](LEGEND_RESOURCES.md), [library format](LIBRARY_FORMAT.md),
and [longitudinal assembly](LONGITUDINAL_ASSEMBLY.md).

### 5. Seekable Ultra metalegend

**Purpose:** transport the large release Ultra legend compactly while allowing
bounded direct integer lookup.

`ULTRA_FAMILY.mleg` represents the exact ordered 54,102,082-byte logical Ultra
legend in independently rooted recipe frames. The 23,632,901-byte release asset
reduces the raw legend by 56.3179%. A narrow lookup restores only the required
frame. Broad workloads can promote a fully restored, hash-verified legend into
a local cache. The seekable form costs more bytes and restores the complete
legend more slowly than the prior opaque `.crys` control; that is an explicit
portability/access trade-off.

**Read next:** [metalegends](METALEGEND.md) and [Ultra configuration](ULTRA_CONFIGURATION.md).

### 6. Adaptive composition

**Purpose:** discover and admit profitable repeated multi-event structures.

The recursive second pass counts adjacent integer-event pairs, composes
selected pairs, and can progressively represent larger recurring structures.
A short phrase repeated a few times can lose after definition and manifest
costs. A large recurring passage can win decisively. Standard retains a
candidate only when its complete segment plus manifest realization is strictly
smaller than the individual/group-legend control; the control wins ties.

Composition IDs are transport structures. They have no CSIL, GTI, GTK,
authority, or security effect.

**Read next:** [second pass](SECOND_PASS.md) and
[ADR-0001](ADR-0001-STANDARD-ADAPTIVE-COMPOSITION.md).

### 7. Group-legend optimizer

**Purpose:** pool exact legend records across related artifacts without losing
their original local namespaces.

A group legend stores a shared record pool and per-artifact local-ID maps. It
can preserve the original container and legend bytes and compare embedded,
external, body-only, and whole-bundle realizations. It is distinct from a
metalegend: a group legend shares records among artifacts; a metalegend
represents one ordered legend recursively.

**Read next:** [group legends](GROUP_LEGEND.md).

### 8. Semantic integerization

**Purpose:** provide complete integer addressability without manufacturing
semantic meaning.

Eligible tokenizer events receive either a caller-assigned semantic integer or
a deterministic document-local integer. Ambiguous surfaces remain local unless
the caller supplies an exact occurrence binding. The release-local product
contract uses CSIL for the externally governed canonical integer layer, GTI for
an index over those identities, and GTK for a disambiguated bound-term key.
Registry identity must accompany integers across namespaces or versions.

**Boundary:** full integer coverage and resolved semantic coverage are separate
measurements.

**Read next:** [semantic identity](SEMANTIC_IDENTITY.md) and
[GTK analysis](GTK_ANALYSIS.md).

### 9. Search and index surface

**Purpose:** expose rooted occurrence retrieval over the exact archive contents.

Standard can embed a candidate index over caller-supplied registry IDs,
semantic keys, exact surfaces, file boundaries, and occurrences. Local fallback
IDs preserve unbound events. Higher systems may add governed aliases, typed
relations, embeddings, access policy, and sense adjudication; the codec does
not infer those layers.

**Primary command:** `search`.

**Boundary:** this is an executable candidate GTI surface, not a grant of
canonical semantic identity or a complete semantic search engine.

### 10. Compression-selection court

**Purpose:** select among declared candidates by measured complete cost and
required capability.

The court compares raw storage, BZ2, LZMA2/XZ, profitable integerization, full
integerization, shared legends, and other enumerated realizations. It separates
cold delivery from warm receiver custody and reports capability-constrained
winners. A winner is exact only over the declared candidate set, not a proof of
global compression optimality.

**Read next:** [configuration court](CONFIGURATION_COURT.md),
[codec selection](CODEC_SELECTION.md), and [archive selection](ARCHIVE_SELECTION.md).

### 11. Security-projection system

**Purpose:** optionally reduce selected disclosure surfaces and protect
reconstruction state.

The ladder includes keyed ID permutation, bounded aliases,
frequency-balanced homophonic aliases, independently selectable keyed position
projection, count/size padding, protected moving legends, complete protected
artifact envelopes, and key rotation. AES-256-GCM and HKDF-SHA256 come from the
optional `cryptography>=42` secure profile.

The homophonic control that preserves position correctly reports
`position_and_cooccurrence_concealed: false`; the separate position-enabled
profile is measured independently. The security court's bigram/trigram and
alias-correlation results are fixture-bounded tests, not universal concealment
or a protocol-security proof.

**Read next:** [security and custody](SECURITY.md).

### 12. Optional native acceleration

**Purpose:** reduce CPU cost in measured hot loops without changing container
bytes, policy, or identity.

The ABI-2 kernel accelerates buffered unsigned-varint packing/unpacking, packed
event parsing, and assembly-pair folding. `AUTO` crosses the native boundary
only for sufficiently large runs; `OFF` uses the Python reference; `REQUIRED`
refuses when the exact compatible kernel is unavailable. Windows standalone
ships the qualified kernel. Linux v0.1 uses the byte-identical pure-Python
fallback.

**Read next:** [native acceleration](NATIVE_ACCELERATION.md).

### 13. Resources, transaction, and recovery

**Purpose:** bound temporary work and prevent incomplete output from appearing
as a completed artifact.

Operations account declared scratch capacity, stream or spool bounded
intermediates, lock publication targets, stage output, verify the inverse, and
publish only after checks pass. Recovery journals support explicit inspection
and root-bound rollback after process interruption. The release does not claim
power-failure atomicity, OS sandboxing, or concurrent-writer support.

**Read next:** [application resources](APPLICATION_RESOURCES.md),
[publication safety](PUBLICATION_SAFETY.md), and [recovery](RECOVERY.md).

### 14. Transport-control surface

**Purpose:** bind an explicitly requested transfer arrangement to exact peer,
codec, projection, security-mode, and legend-custody declarations.

It validates peer capability records, negotiates exact ordered root chains or
self-contained delivery, and emits rooted sidecar frames. It is not a network
stack, does not transfer files, and does not treat registry references as proof
that a peer possesses a legend.

**Read next:** [transport control](TRANSPORT_CONTROL.md).

### 15. Legacy and migration workbench

**Purpose:** preserve explicit compatibility and refusal behavior for historical
SemCrys artifacts.

Supported imports require exact source custody and preserve decoded bytes.
Unknown wrappers, member archives, or implicit registries fail closed. The
workbench exposes rooted dispositions for qualified, superseded, partial,
research-only, and unavailable historical surfaces; a disposition does not make
an unavailable capability executable.

**Read next:** [legacy migration](LEGACY_MIGRATION.md), [ordered import](ORDERED_IMPORT.md),
and [migration workbench](MIGRATION_WORKBENCH.md).

### 16. Observability and agent interface

**Purpose:** make long operations and machine integration inspectable without
turning progress text into evidence.

Humans receive ordinary help, phase progress, and explanation commands. Agents
receive `--help-json`, stable exit/refusal codes, JSONL progress, final rooted
results, capability manifests, and explicit dependency disclosures. Progress
and final stdout are separate channels. Receipts and verified artifacts, not
terminal animation, establish completion.

**Read next:** [agent API](AGENT_API.md) and [Standard CLI](STANDARD_CLI.md).

### 17. Integrity and qualification system

**Purpose:** establish exact bounded claims and fail closed on release drift.

Courts cover codec inverses, Standard replay, security projections, Ultra
metalegend restoration and lookup, Wikipedia configuration comparison,
integerization performance, native/reference equivalence, Windows and Linux
standalones, archive extraction safety, double-build reproducibility, and
release-manifest closure. Hashes and rooted manifests establish artifact
correspondence; they do not authenticate a publisher when an attacker can
replace both payload and checksum.

**Read next:** [release candidate](RELEASE_CANDIDATE.md),
[releasing](RELEASING.md), and [Wikipedia qualification](WIKIPEDIA_OPTIMIZATION.md).

### 18. Delivery system

**Purpose:** make the same qualified functionality available through several
offline installation and review boundaries.

The release emits source, a Python zipapp, pure and Windows-native wheels,
Windows x64 and Linux x64 standalones, the Ultra metalegend, an offline custody
bundle, manifests, checksums, and reviewer evidence. Standalones bundle an
inventoried Python runtime and require no separate interpreter, browser, cloud
service, font service, or network access.

`RELEASE-MANIFEST.json` binds executable payloads. The wider
`PUBLICATION-ASSET-INDEX.json` binds the uploaded payloads, sidecars, offline
bundle, and reviewer companions without attempting a self-hash cycle.

## Capability boundaries

SemCrys Core does not include or silently claim:

- Mosaic Lineage Archive or Transtemporal version-lineage deduplication;
- Mosaic Memory Vault, filesystem watching, freshness launching, or vault UI;
- canonical semantic authority or automatic global sense adjudication;
- a network transport implementation;
- UCM enforcement, Pippi host mediation, or a bound external executor;
- universal compression superiority;
- a complete cryptographic protocol proof; or
- publication, admission, or authority effects from a successful court.

Those systems may consume SemCrys through explicit contracts. They do not
redefine its formats, evidence, or claim boundaries.

## Choosing the right entry point

| Need | Recommended surface |
|---|---|
| Compress or fully integerize files/folders | Standard path-first CLI or `pack` |
| Inspect, verify, search, or restore an archive | `list`, `inspect`, `verify`, `search`, `unpack` |
| Minimize measured delivery size | Standard `--mode smallest` or configuration court |
| Preserve complete eligible integer addressability | Standard semantic mode / Full total profile |
| Share exact legend records across related artifacts | Group legend |
| Reduce custody size of one large legend | Seekable metalegend |
| Extend an exact shared base over time | Domain/longitudinal delta |
| Bind caller-resolved semantic identities | Semantic registry plus occurrence bindings |
| Reduce public frequency/order/length disclosures | Explicit Lite security profile |
| Protect a complete legend or index artifact | `security protect` envelope |
| Integrate an agent | `--help-json`, `--progress full`, and rooted final results |
| Import historical SemCrys material | Explicit legacy migration/workbench commands |

The recommended default remains the Standard archive workflow. The advanced
surfaces exist so applications and agents can select a more precise capability
without weakening exact reconstruction or silently broadening claims.
