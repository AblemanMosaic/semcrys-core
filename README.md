# SemCrys Core

**Competitive lossless compression and full integerization with reusable
legends, cross-document group legends, recursive metalegends, and explicit
semantic bindings.**

SemCrys stores recurring material in legends and represents its occurrences with
compact references. A shared Ultra base, domain and longitudinal deltas,
reusable forms, and pooled group legends let that representation extend across
artifacts. Recursive metalegends can then represent a legend itself as bounded,
independently compressed recipe frames without retaining the original physical
legend. Targeted readers inflate only the frame containing a requested integer;
verified caches can promote broad workloads to the exact original legend. The
same system can prioritize minimum delivered bytes or complete
integer addressability for indexing and agent applications. Optional protected
legend custody controls access to reconstruction state.

Start with the [system architecture](docs/SYSTEM-ARCHITECTURE.md) for one
end-to-end map of the eighteen release subsystems, their boundaries, commands,
formats, and deeper documentation.

SemCrys is a real compression option, not only a semantic-indexing experiment.
On the release's pinned warm-legend Wikipedia fixture, its profitable profile
produced a result **4.31% smaller than stdlib XZ-6 and 6.63% smaller than stdlib
BZ2-9**, with byte-exact reconstruction. That is a bounded proof of superiority
for the tested source, candidates, and receiver custody state, not a claim that
SemCrys wins on every corpus. Its strongest opportunities arise when vocabulary,
structures, chunks, or legend state recur within or across related artifacts.

The release seekable Ultra metalegend is 23,632,901 bytes and restores the exact
54,102,082-byte Ultra legend. That is a **56.3179% reduction** from the raw
legend. Seekability costs 818,671 bytes (3.5884%) over the 22,814,230-byte
whole-stream control. Against the incumbent 22,939,848-byte `.crys` transport,
it costs 693,053 bytes (3.0212%). The seekable form provides targeted access,
independently rooted frames, bounded materialization, and verified cache
promotion; it is slower than `.crys` when the entire legend must be restored.
This is a bounded trade-off for this exact ordered legend and profile.

This tree targets **SemCrys v0.1.0, the first public release line**. The current
replacement is authorized for GitHub publication by the recorded human
decision. Its bounded technical claims are
established by deterministic construction, byte-exact replay, rooted evidence,
and exact replay. The predecessor release was independently reproduced; exact
external replay of this replacement envelope remains pending. Formal external
certification is not claimed or required for publication.

## Downloads

Download the appropriate asset from the GitHub release. Both standalone
applications are offline, carry the release-bound Ultra metalegend and a pinned
Python runtime, and do not require a separately installed Python interpreter.

| Release asset | Use it for | Start here |
| --- | --- | --- |
| `semcrys-0.1.0-windows-x64.zip` | Windows 64-bit standalone application | Extract, then run `semcrys.exe` or `START.BAT`. |
| `semcrys-0.1.0-linux-x64.tar.gz` | Linux x86-64 standalone application | Extract, then run `./semcrys-linux-x64/semcrys` or `START.sh`. |
| `semcrys-core-0.1.0-offline-bundle.zip` | Complete offline custody set | Includes both standalones, source, wheels, zipapp, Ultra, manifest, and checksums. |
| `semcrys-core-0.1.0-source.zip` | Source review, development, and court replay | Requires a compatible Python interpreter; see [Releasing](docs/RELEASING.md). |
| `ULTRA_FAMILY.mleg` | Release-bound shared Ultra vocabulary | Seekable one-level metalegend; supports direct integer lookup and restores the exact logical `.leg`. |

Start verification with `PUBLICATION-ASSET-INDEX.json`. Its rooted groups bind
the release manifest and every uploaded payload, sidecar, offline bundle, and
reviewer companion. The index and its own adjacent sidecar deliberately exclude
GitHub's two tag-generated source snapshots, whose custody boundary is the
tagged commit. `RELEASE-MANIFEST.json` remains the narrower executable-payload
contract used by the release verifier.

## Turnkey CLI

The `semcrys` command chooses the recommended self-contained workflow. A path
in command position is shorthand for `pack`:

```powershell
semcrys report.txt
semcrys project-folder
semcrys file1.txt file2.json -o research.crys
semcrys list research.crys
semcrys verify research.crys
semcrys unpack research.crys restored
```

The Standard default fully integerizes eligible UTF-8 content, measures the
declared exact-codec candidates, chunks large logical files, reuses duplicate
chunks, pools related containers through group legends, and adaptively courts
local and cross-document event composition. Composition is retained only when
its complete segment plus manifest representation is strictly smaller than the
individual/group-legend control. The workflow then verifies complete replay and
atomically publishes the `.crys` file. Verified chunk and composition caches
make interrupted and repeated work resumable. `--mode smallest` is an explicit
semantic-capability trade: it may choose raw bytes when that is smaller;
`--composition off` is an advanced ablation.

Use `semcrys --help`, `semcrys pack --help`, and `semcrys explain-default` for
human orientation. Agents should use `semcrys --help-json` and
`--progress full`; the final stdout record and progress JSONL are separate.
[The Standard CLI contract](docs/STANDARD_CLI.md) defines modes, custody,
progress, exit codes, limits, and the embedded candidate Global Term Index.
[The normative compression model](docs/SEMCRYS-COMPRESSION-MODEL.md) fixes the
reuse continuum, profitability rule, semantic boundary, and claim limits.

## Why use it?

- **Reuse knowledge across files.** A receiver holding the exact shared legend
  can receive references instead of acquiring that legend again.
- **Keep new vocabulary incremental.** Parent-bound deltas extend a known base
  without replacing it or silently adopting private material.
- **Share structure across a collection.** Group legends pool exact stored legend
  records; adaptive shared streams can expose profitable recurring event
  structures across related logical payloads while preserving file boundaries.
- **Compress legend state recursively.** A metalegend replaces one ordered
  physical legend with bounded recipes that restore the exact original legend;
  seekable frames avoid paying full restoration cost for narrow reads.
- **Make content addressable.** Integer events support occurrence indexes;
  caller-supplied semantic keys can connect them to disambiguated senses.
- **Choose by evidence.** The configuration court verifies reconstruction and
  reports different winners for compression, integerization, and cold/warm delivery.

### Where SemCrys tends to help

| Workload | Expected fit | Why |
|---|---|---|
| Related prose, policies, contracts, reports, and documentation | Strong | Words, punctuation, boilerplate, and sometimes whole passages recur. |
| Source code, JSON/XML, logs, and generated records | Strong | Syntax, names, schemas, templates, and structural fragments repeat heavily. |
| Versioned or overlapping collections | Strong | Exact files and chunks can be stored once; shared legend state is amortized. |
| Large natural-language corpora with an already-held Ultra/domain legend | Strong to mixed | Warm shared vocabulary can replace repeated spellings with compact references. |
| Novel text or heterogeneous small files sent to a new receiver | Mixed | Integerization remains useful, but cold legend and container costs may dominate. |
| Raw executables and uncompressed binary data | Mixed | Exact chunk reuse may help; lexical legendization usually needs a typed adapter. |
| JPEG/PNG, MP3/AAC, MP4, ZIP, XZ/BZ2, or other already-compressed data | Usually weak | Their redundancy has largely been removed before SemCrys sees the bytes. |
| Encrypted or high-entropy data | Weak | Deliberately concealed recurrence leaves little compressible structure. |

Raw-byte profiles preserve arbitrary files even when SemCrys is not the size
winner. The Standard `smallest` mode can choose raw bytes instead of paying for
unprofitable integerization. Interpreting an image or compiled program still
requires an application to supply appropriate metadata or structure.

## How legends produce compression

A legend is an explicit reversible mapping between stored units and local
integer IDs. For eligible UTF-8 input, the lossless tokenizer separates words,
punctuation, and whitespace runs without discarding source bytes. A distinct
unit is stored in the legend; its occurrences in the body become integer
references.

Those references are serialized as unsigned variable-length integers in a
packed binary byte stream. They are not decimal text, and SemCrys does not
reserve a fixed machine word for every ID. Frequently used units can receive
small IDs that occupy fewer packed bytes, while larger IDs expand only as
needed. The outer codec then compresses the reference stream and legend. The
gain is representational: repeated source spellings no longer have to be emitted
in full at every occurrence.

SemCrys also works above the single-token level:

- Standard archives automatically store each byte-identical file chunk once.
- Group legends pool byte-identical legend records across verified containers.
- Recursive metalegends encode an ordered legend as one-level block-local
  recipes. The default seekable layout groups those recipes into independently
  rooted frames; the original physical `.leg` may be discarded after exact
  verification and rematerialized into a local acceleration cache when needed.
- Explicit assembly legends can represent supplied reusable forms.
- The second pass can discover repeated adjacent integer-event pairs,
  recursively compose them into progressively larger sequences, measure
  complete delivered size, and retain the composed result only under the
  selected policy.
- Standard automatically courts that mechanism over bounded groups of unique
  eligible payloads after exact chunk deduplication. The existing individual
  container plus group-legend route remains the control and wins ties.

This is a profitability continuum, not a fixed phrase/blob category. A short
sequence repeated only a few times can lose because its new legend definition
costs more than its references save. A large block repeated many times can repay
that definition decisively. Under `MIN_DELIVERY`, the second pass compares the
complete original delivery with exact composed candidates, including body,
legend, container, and declared dependency costs for the selected cold/warm
accounting basis. An unprofitable composition loses; it is not published merely
because it was discoverable.

Consequently, repeated disclaimer text can benefit token by token; an exact
repeated chunk is reused as one stored payload; and the second-pass machinery
can reduce a recurring multi-token passage to a much shorter composed integer
sequence, potentially a single composed ID when its recurrence, depth, and size
fit the bounded optimizer. Standard now invokes this court automatically for
bounded eligible groups, but it does **not** promise that every repeated phrase
or paragraph becomes one integer. The census may decline an uneconomic court,
and the fully realized individual/group-legend or conventional-codec control may
still be smaller and therefore win.

Savings must exceed the cost of legends, references, containers, and missing
dependencies. Warm results assume the receiver already holds the exact declared
shared legend; cold results charge it.

| Layer | Role in SemCrys |
|---|---|
| Local legend | Carries the units needed for a self-contained artifact. |
| Ultra/shared base | Reuses an exact, already available vocabulary across artifacts. |
| Domain or longitudinal delta | Adds missing units and binds their exact parent stack. |
| Form/assembly legend | Represents explicitly supplied reusable structure. |
| Group legend | Pools identical stored legend records across verified artifacts; maps recover their original local namespaces. |
| Recursive metalegend | Represents one ordered legend through bounded recipes; seekable frames provide direct integer lookup and restore the original `.leg` byte for byte. |
| Adaptive collection | Courts one rooted integer stream across unique related UTF-8 payloads; manifest offsets preserve exact logical boundaries. |
| Outer codec | Applies conventional compression such as LZMA2/XZ or BZ2 to the representation. |

These layers address different scopes of repetition: occurrences within a
document, shared vocabulary across documents, and repeated legend records across
containers. Pooling equal bytes does not assert equivalent meaning. Additional
layers can cost more than they save, so measured selection retains controls.
`PROFITABLE` is a raw-cost heuristic, not a compressed-size guarantee. See
[group legends](docs/GROUP_LEGEND.md), [recursive metalegends](docs/METALEGEND.md),
and [the configuration court](docs/CONFIGURATION_COURT.md).

## Relationship to established systems

Shared dictionaries, integer IDs, and reusable grammars have substantial prior
work. SemCrys's contribution is their particular integration with explicit
dependency custody, multiple legend levels, reversible artifacts, semantic
binding interfaces, and measured capability-aware selection.

| Adjacent work | Established capability | What to examine in SemCrys |
|---|---|---|
| [Zstandard dictionaries](https://github.com/meta/zstd/blob/dev/README.md#the-case-for-small-data-compression) | Trained dictionaries reused for related inputs. | Exact shared stacks, deltas, and accounting for missing receiver state. |
| [Brotli](https://www.rfc-editor.org/rfc/rfc7932.html#section-8) | Static dictionary references and transformations. | Explicit legend families and reusable cross-artifact legend records. |
| [Re-Pair](https://avadeaux.net/larsson.dogma.net/dcc99.pdf) | Dictionary/grammar compression through repeated pair replacement. | Supplied assemblies and exact multi-document namespace reconstruction. |
| [SentencePiece](https://aclanthology.org/D18-2012/) | Reusable subword models, token IDs, and detokenization. | Archive-byte reconstruction, legend custody, and separately assigned sense bindings. |
| [HDT](https://www.w3.org/submissions/HDT/) | Compact dictionary IDs and graph structures with indexed access. | General artifact representation and an interface for higher semantic indexes. |
| [Arrow](https://arrow.apache.org/docs/format/Columnar.html#dictionary-encoded-layout) / [Parquet](https://parquet.apache.org/docs/file-format/data-pages/encodings/#dictionary-encoding-plain_dictionary--2-and-rle_dictionary--8) | Typed dictionary arrays, compact indices, and column-oriented encoding. | Artifact-wide legends, exact dependency custody, and optional semantic bindings. |
| [WordNet](https://wordnet.princeton.edu/) / [BabelNet](https://aclanthology.org/P10-1023/) | Sense distinctions, lexical relations, and multilingual concept networks. | Connecting reversible occurrence identities to governed external bindings. |

These are architectural comparisons. The release has not benchmarked superiority
over these systems or established priority for every part of the composition.
The [related-work dossier](docs/RELATED_WORK.md) records sources, differences,
counterexamples, and experiments needed for stronger claims.

## Compression or full integerization?

**Profitable integerization** favors compact delivery and can leave unprofitable
units literal. **Full/Total integerization** prioritizes eligible lexical coverage
within the Full compiler's profile limits. The Core semantic helper separately
gives every UTF-8 tokenizer event an externally assigned semantic integer or a
document-local integer. Complete integer coverage and resolved semantic coverage
are different measurements.

Full integerization lets an application build occurrence indexes, compare rooted
sequences, retrieve selected passages, and connect them to a semantic registry.
This reusable addressability is valuable alongside byte reduction. A compressed
file alone is not a finished search engine; its IDs are not automatically an
LLM's tokenizer vocabulary.

### CSIL, GTI, GTK, and bound-terms

The broader architecture connects occurrences to **bound-terms**: disambiguated
word, phrase, or other named concept bindings. Financial-bank and river-bank
bindings remain separate even when their spelling is identical. Governed aliases
and relations can connect appropriate names without conflating competing senses.

**CSIL is the Canonical Semantic Integer Layer.** A CSIL ID is an integer in an
exact, versioned canonical registry. The registry identity must accompany the
integer when data can cross registry versions or jurisdictions. **GTI is the
Global Term Index**: the lookup structure that connects spellings, aliases,
occurrences, and other indexed views to CSIL IDs. **GTK is the Global Term Key**
used for a governed bound-term: a disambiguated word, phrase, blob, or other
named concept. Definitions and wider typed relations remain linked structures,
not properties manufactured by an integer alone. See [the GTK
paper](https://github.com/AblemanMosaic/ableman-corpus/tree/main/papers/current/AC-0091-global-term-key-constitutional-lexical-identity-thro).

Some earlier corpus reading copies use older CSIL wording and a layered RPZ
shorthand. This public release follows the corrected product terminology above
without claiming that generated documentation alters the upstream corpus.

**Available in v0.1:** a rooted registry of caller-assigned keys, exact unambiguous
token bindings, explicit occurrence bindings for ambiguity, and lossless local-ID
fallback. Standard archives can embed a candidate GTI over caller-supplied
registry IDs, exact surfaces, keys, and occurrences. Full also has a read-only
GTK dossier analysis adapter. None of these grants canonical identity. Automatic
multiword/blob sense resolution, alias expansion, and authoritative global
semantic search require higher integration.
[Semantic identity and indexing](docs/SEMANTIC_IDENTITY.md) explains the current
schema, coverage denominators, and integration boundaries.

## A measured example

The qualification uses one pinned **100-page Wikipedia stream prefix**, expanding
to 2,763,849 bytes. All 18 enumerated candidates passed exact reconstruction.

| Representation | Delivered bytes | Condition |
|---|---:|---|
| Fresh stdlib BZ2-9 | 718,692 | No external legend |
| Fresh stdlib XZ-6 | 701,272 | No external legend |
| SemCrys Ultra profitable + LZMA | 671,046 | Receiver holds the exact Ultra root |
| SemCrys Ultra full + LZMA | 724,782 | Same warm base; includes its longitudinal delta |

On that warm-receiver basis, profitable SemCrys is **4.31% smaller than XZ-6**
and **6.63% smaller than BZ2-9**. Full integerization costs **8.01% more than
profitable SemCrys**, or **0.85% more than BZ2-9**, while retaining the full
compiler profile's integerization capability.

For a new receiver, the court charges the 54,102,082-byte restored Ultra
dependency; XZ-6 wins the one-artifact unconstrained cold-delivery comparison.
The replacement transports Ultra as a 23,632,901-byte seekable `.mleg`. The
incumbent 22,939,848-byte `.crys` remains an explicit performance and size
control, not a release asset. Transport size and the court's restored-legend
accounting basis are distinct. Shared state must be counted explicitly rather
than called free.

The result establishes a winner among the enumerated candidates for this source
and custody state. Whole-Wikipedia and cross-corpus superiority remain untested.
Source roots and reproduction are in the [Wikipedia dossier](docs/WIKIPEDIA_OPTIMIZATION.md).

Phase-separated single-host measurements also reduced profitable encoding plus
mandatory postwrite proof from 170.244 s to 13.164 s with identical output bytes.
Most of that gain came from lookup and batching improvements; the native parser
added about 2.93% beyond batched Python on this fixture. See
[performance evidence](docs/INTEGERIZATION_PERFORMANCE.md).

## What belongs to SemCrys

- The Full compiler and its `.crys` 0.2, binary `.leg` 0.2, and `.gly` 0.1 formats.
- The Lite reference codec and its CRYS-LITE 0.3 format.
- Ultra, local, delta, longitudinal, assembly, group-legend, and recursive-metalegend families.
- Profitable and full integerization profiles.
- Explicit semantic-key bindings and a lossless local-integer fallback.
- Keyed permutation, bounded aliases, frequency-balanced homophonic aliases,
  independent keyed position projection, protected moving legends, and
  count/size padding profiles.
- Authenticated protected-artifact envelopes for group legends, semantic
  indexes, bespoke legends, and recursive metalegends.
- Profitable omission of only deterministically reconstructible single spaces.
- Configuration measurement, exact reconstruction, integrity receipts, and typed refusal.
- Optional hash-bound native acceleration for buffered varints and assembly folding.
- Reproducible, non-redistributing Wikipedia `.bz2` qualification evidence.

Full and Lite are release siblings. `semcrys-core` detects their signatures and
dispatches inspection while preserving their separate ABIs.

## Requirements

The ordinary compiler, integerization, compression, inspection, and metadata
surfaces use only Python's standard library.

Protected moving legends use the optional `secure` profile and require
`cryptography>=42` for AES-256-GCM and HKDF-SHA256. SemCrys does not replace
that implementation with an improvised cipher. Install it only when needed:

```powershell
python -m pip install ".[secure]"
```

The complete offline release bundle carries the exact Ultra `.mleg` artifact as a
release-bound asset. Ultra is not silently downloaded.

Source checkouts use `assets\legends` by default. A packaged or independently
mounted Ultra asset can be selected explicitly with `--asset-root` or the
`SEMCRYS_ULTRA_ASSET_ROOT` environment variable.

The ordinary distribution remains usable without a compiler or native binary.
On supported platforms, a separate native wheel adds a dependency-free C ABI
for high-volume buffer operations. `AUTO` selects it only for sufficiently
large workloads and otherwise retains the Python reference implementation.

The standalone applications are a different delivery profile: they carry a
pinned Python runtime and their exact bundled binary components, hashes, and
available redistribution notices. They require no separately installed Python.
`BUNDLED-RUNTIME.json` and `THIRD-PARTY-NOTICES.txt` distinguish bundled code
from external runtime requirements.

## Quick start

```powershell
$env:PYTHONPATH = "$PWD\src"
python -B -m semcrys project-folder -o project.crys
python -B -m semcrys verify project.crys
python -B -m semcrys unpack project.crys restored
python -B -m semcrys_core capabilities
python -B -m semcrys_core native-status
python -B -m semcrys_core verify-self --asset-root assets\legends
python -B -m semcrys metalegend inspect assets\legends\ULTRA_FAMILY.mleg
python -B -m semcrys metalegend lookup assets\legends\ULTRA_FAMILY.mleg 1 1000000
python -B -m semcrys metalegend prepare assets\legends\ULTRA_FAMILY.mleg --cache-root .semcrys-cache
python -B -m semcrys metalegend verify assets\legends\ULTRA_FAMILY.mleg
python -B -m semcrys_core inspect example.crys
python -B -m semcrys_core full capabilities
python -B -m semcrys_core lite demo
```

Windows users can instead extract `semcrys-0.1.0-windows-x64.zip` and invoke
`semcrys.exe` directly. It carries a pinned Python runtime, the optional native
kernel, complete self-integrity inventory, license/notice, and the release Ultra
asset. No Python installation, network access, font service, or browser is
required. `START.BAT` displays the human command guide; `semcrys.exe --help-json`
is the agent-facing discovery surface.

Linux x86-64 users can extract `semcrys-0.1.0-linux-x64.tar.gz` and invoke
`./semcrys-linux-x64/semcrys`. Its internal manifest and release notes declare
the exact minimum glibc symbol version established by the build. The v0.1.0
Linux artifact uses the pure-Python native-kernel fallback; that affects speed,
not container bytes. `START.sh` displays help and `--help-json` exposes the same
agent contract as Windows.

Build a semantic-key registry and losslessly integerize UTF-8 text:

```powershell
python -B -m semcrys_core semantic build-registry bindings.json registry.json
python -B -m semcrys_core semantic integerize source.txt registry.json source.sit.json
python -B -m semcrys_core semantic restore source.sit.json registry.json restored.txt
```

Every token is represented by an integer. A token receives an externally
assigned semantic integer only when the registry supplies an unambiguous exact
binding or the caller supplies an occurrence binding. Other tokens receive
document-local integers, preserving exact reconstruction without manufacturing meaning.

## Verification and release construction

```powershell
python -B tools\run_publication_court.py
python -B tools\build_release.py
python -B tools\verify_release.py dist\RELEASE-MANIFEST.json
```

The release assembler emits deterministic source, zipapp, wheel, standalone
Windows, standalone Linux, and complete offline-bundle artifacts. Platform
standalones are each built twice and qualified on their own operating system
before final assembly. It excludes caches, temporary files, Git internals,
platform staging inputs, and prior build output. Both platform courts launch the
frozen executable without `PYTHONPATH`/`PYTHONHOME`, pack and verify a fixture,
restore it, and compare exact bytes. Foreign-platform verification still proves
archive safety, internal-manifest closure, runtime custody, and declared files,
but reports execution as structure-only.

Build and benchmark the optional native kernel:

```powershell
python -B tools\build_native.py
$env:PYTHONPATH = "$PWD\src"
python -B tools\benchmark_native.py
```

Set `SEMCRYS_NATIVE=off` for the reference path, `auto` for adaptive selection,
or `required` to refuse an operation when a compatible hash-bound kernel cannot
be loaded. `SEMCRYS_NATIVE_THRESHOLD` controls the minimum event count.

Run the general bounded configuration court over any exact workload:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -B tools\run_configuration_court.py SOURCE --library STACKS.json --legend ULTRA.leg --receiver-root ULTRA_ROOT --output COURT.json
```

The court separates cold and warm custody, exact reuse horizons, natural-codec
controls, and capability-constrained winners. See
`docs/CONFIGURATION_COURT.md`.

Qualify that same court on the bounded Wikipedia fixture without adding a
runtime dependency:

```powershell
python -B tools\fetch_wikipedia_fixture.py --output-dir "$env:TEMP\semcrys-wikipedia" --max-compressed-bytes 1048576
$env:PYTHONPATH = "$PWD\src"
python -B tools\benchmark_wikipedia.py "$env:TEMP\semcrys-wikipedia\enwiki-20261001-pages-articles-multistream1.xml-p1p41242-prefix-717512.bz2" --manifest benchmarks\wikipedia\SOURCE-MANIFEST.json --output evidence\WIKIPEDIA-BENCHMARK.json
python -B tools\verify_wikipedia_evidence.py
python -B tools\verify_integerization_performance_evidence.py
```

The fetch is optional qualification work. SemCrys does not download anything at
runtime, and the Wikipedia corpus is not redistributed in this repository.

## Security boundary

A public Ultra legend supplies no secrecy by itself. A keyed permutation gives
local IDs a private correspondence, so the public legend alone no longer supplies
that mapping. The principle also applies to bespoke legends. The implemented
Lite permutation preserves equality/frequency patterns, however, and is not a
confidentiality protocol.

Stronger Lite modes use bounded aliases, keyed frequency-balanced homophonic
aliases, an independently selectable keyed position projection, or move the
ordered reconstruction sequence into a **protected moving legend**.
AES-256-GCM with HKDF-SHA256 protects the companion. Every protected encoding
receives a fresh salt-bound public alias permutation. Homophony alone flattens
each base value's public alias frequency within a declared bound while leaving
order visible; the homophonic court's negative position flag describes this
position-preserved control. `homophonic-positional` additionally permutes public event
positions without adding filler or hiding exact length. `maximum-concealment`
moves the sequence into protected state and exposes only an event-count class.
Recovery requires the key, companion, and declared base dependencies.

Count and sealed-state padding expose a bucket rather than an exact count or
plaintext size. Fresh filler is drawn from the encoding's real alias emissions
and placed through a keyed interspersal permutation rather than a deterministic
tail. Position projection is a separate control: it can hide tested order and
co-occurrence signals without padding, while padding remains necessary to hide
exact event count within a declared class. Public protected-mode receipts redact exact source metrics. The
`semcrys security` commands protect complete group legends,
semantic indexes, bespoke legends, or metalegends so a plaintext dependency is
not silently left outside the protected state. Exact source length and digest
are encrypted, while role, padded size, ciphertext metadata, and an
envelope-specific key identifier remain public. Key rotation rewraps protected
state without changing semantic identities or recompressing source events.

These are concrete strengths to investigate: separating public vocabulary from
secret reconstruction state, reducing public-label recurrence, and authenticating
the protected companion. Bounded tests demonstrate exact recovery, randomized
companions, and wrong/tampered-input refusal. Public metadata, size, timing,
endpoint exposure, access patterns, and inference still matter. Protection of
Full/group/metalegend artifacts is an explicit envelope operation, never a
silent implication of compression.

The release claim is `BOUNDED_IMPLEMENTED_PROFILE_NO_PROTOCOL_SECURITY_PROOF`.
Independent cryptanalysis and a complete protocol security argument remain open.
We invite known/chosen-plaintext analysis, cross-artifact inference, malformed
input testing, and custody/recovery audits. See the detailed
[security strengths, exposure, and limits](docs/SECURITY.md).

```powershell
# Protect a complete group-legend archive without exposing the key on argv.
$env:SEMCRYS_SECURE_KEY = '<32+ high-entropy bytes supplied by a secret provider>'
semcrys security protect related-group.crys related-group.scp `
  --role GROUP_LEGEND_ARCHIVE --padding POWER_OF_TWO
semcrys security verify related-group.scp
semcrys security unprotect related-group.scp related-group-restored.crys

# Lite frequency, position, and maximum-disclosure-reduction presets.
semcrys-lite encode source.bin source.crys --moving-legend-out source.moving.json `
  --security-preset homophonic
semcrys-lite encode source.bin source.crys --moving-legend-out source.moving.json `
  --security-preset homophonic-positional
semcrys-lite encode source.bin source.crys --moving-legend-out source.moving.json `
  --security-preset maximum-concealment
```

Environment variables are convenient but are not a universal secret manager;
applications should prefer protected key files or operating-system/provider
handles appropriate to their deployment.

## What the evidence establishes

| Claim | Evidence and scope |
|---|---|
| Reversible supported representations | Exact source reconstruction in shipped tests and the configuration court. |
| Detectable dependency/integrity failures | Root checks and typed refusal; hashes alone do not authenticate a publisher. |
| Compression gains | Pinned candidate measurements with explicit cold/warm accounting. |
| Protected, homophonic, and positional behavior | Implemented AEAD integration, balanced-alias, position/co-occurrence null-model, and padding courts, plus protected dependency envelopes; no whole-protocol proof. |
| Semantic addressability | Rooted caller bindings and integer events; sense correctness remains the supplier's obligation. |
| Better agent retrieval, fewer model tokens, or improved reasoning | Research opportunities requiring task-level comparisons and suitable model integration. |

The papers describe a larger research program. A proposed integration does not
become an executable release feature through citation alone.

## Research and collaboration

Useful contributions include unlike-corpus compression trials, trained-dictionary
controls, multi-document group-legend measurements, recursive-legend controls,
ambiguity-aware retrieval
evaluations, protected-mode cryptanalysis, and parser/resource fuzzing. Include
exact versions, reproducible inputs, dependency roots, custody assumptions, and
negative results. The [research agenda](docs/RELATED_WORK.md#evaluation-and-collaboration-agenda)
sets out useful comparisons and acceptance criteria.

Report potential vulnerabilities privately to **ableman.research@gmail.com**.
Public research issues should use synthetic or redacted reproductions. Keep
keys and private legends out of issues and receipts. The aim is to turn apparent
strengths into reproducible results, including results favoring an established
alternative.

## Papers and corpus

Read the [Ableman research corpus](https://github.com/AblemanMosaic/ableman-corpus)
or its [human-facing corpus](https://ablemanmosaic.github.io/ableman-corpus/site-bridge/).
Corpus reading copies and Zenodo editions are separate artifacts with their own
standing; the paper links are research context, not software security certification.

| Paper | Corpus reading copy | Zenodo record |
|---|---|---|
| Constitutional Legends | [AC-0118](https://github.com/AblemanMosaic/ableman-corpus/tree/main/papers/current/AC-0118-constitutional-legends) | [10.5281/zenodo.20330324](https://doi.org/10.5281/zenodo.20330324) |
| SemCrys0 | [AC-0119](https://github.com/AblemanMosaic/ableman-corpus/tree/main/papers/current/AC-0119-semcrys0) | [10.5281/zenodo.20370117](https://doi.org/10.5281/zenodo.20370117) |
| SemCrys: Toward a Tokenizer-Native Semantic Substrate for Machine Cognition | [AC-0120](https://github.com/AblemanMosaic/ableman-corpus/tree/main/papers/current/AC-0120-semcrys-toward-a-tokenizer-native-semantic-substrate) | [10.5281/zenodo.20374559](https://doi.org/10.5281/zenodo.20374559) |
| SemCrys-Secure | [AC-0121](https://github.com/AblemanMosaic/ableman-corpus/tree/main/papers/current/AC-0121-semcrys-secure-toward-governed-semantic-transport-an) | [10.5281/zenodo.20374735](https://doi.org/10.5281/zenodo.20374735) |
| Semantic Coordinate Identity Tokenization (SCIT) | [AC-0127](https://github.com/AblemanMosaic/ableman-corpus/tree/main/papers/current/AC-0127-semantic-coordinate-identity-tokenization-scit) | [10.5281/zenodo.20532070](https://doi.org/10.5281/zenodo.20532070) |
| Global Term Key: Constitutional Lexical Identity Through Disambiguated Semantic Binding | [AC-0091](https://github.com/AblemanMosaic/ableman-corpus/tree/main/papers/current/AC-0091-global-term-key-constitutional-lexical-identity-thro) | No DOI recorded in corpus metadata |
| Global Term Key: Identity Primitives in Governed Knowledge Systems | [AC-0102](https://github.com/AblemanMosaic/ableman-corpus/tree/main/papers/current/AC-0102-global-term-key-identity-primitives-in-governed-know) | No DOI recorded in corpus metadata |

See `docs/AGENT_API.md`, `docs/ARCHITECTURE.md`, `docs/COMPATIBILITY.md`,
`docs/CONFIGURATION_COURT.md`,
`docs/NATIVE_ACCELERATION.md`, `docs/INTEGERIZATION_PERFORMANCE.md`,
`docs/SECURITY.md`, `docs/WIKIPEDIA_OPTIMIZATION.md`, and `docs/RELEASING.md`.

License: Apache-2.0. See `LICENSE` and `NOTICE`.
