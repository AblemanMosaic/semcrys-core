# Composed second pass — candidate application feature

The public command `semcrys second-pass input.crys output.crys` works on an
already validated packed-token container. Supply every external input legend
with repeated `--legend`. Self-contained, pre-shared, and longitudinal
packed containers, including tagged/compact form programs, are inputs.
Glyph, folded-front and already composed input are explicitly unavailable.

Standard v0.3 also invokes this mechanism internally after exact chunk
deduplication. It compares a bounded shared UTF-8 collection candidate against
the individual-container plus group-legend control. Manifest offsets retain the
original logical boundaries. This is a transport composition and has no CSIL
identity effect. See `SEMCRYS-COMPRESSION-MODEL.md`.

S: token/event relabel, pair fractionation, statistical outer coding and
multi-document group legends are distinct mechanisms.
CM1: exact complete input dependencies, valid inverse, bounded source/event/
legend sizes, lossless terminal composition, acyclic pair references.
CM2: unchanged original, composed identity, all-pair and configurable-hot-symbol
fractionation. Choose by `--selection MIN_DELIVERY` (default),
`MIN_DISPERSION`, `IDENTITY`, `ALL`, `TOP3` or `TOPK`. Original wins ties.
Relabel is a diagnostic null, not a routable option.
IC: rooted input identities, ordered operations, accounting, limits and
selection policy before execution; final container has an explicit v0.8 IC.
IR: receipt with each candidate's body/legend/container/delivery bytes,
event counts, dispersion, and verified reconstruction.

`--accounting COLD` counts all external original input legends once.
`WARM` means the caller declares those exact original legends already
available. The composed candidates embed a single complete legend and need
no external decode dependency. If the original wins, its bytes and dependency
requirements remain unchanged; discard is then NOT warranted.
This is a measured choice on this input, not a predictive optimum.
Audit receipts are separate and their delivery is not included or called free.

Default 400 rounds, minimum overlapping pair count 10, deterministic
first-occurrence tie order and left-to-right non-overlapping replacement.
TOP3 fixes its hot set at three initial-frequency symbols and preserves the
frozen critical v0.8 constitution. `--hot-k N` with positive `N != 3` exposes
the historical configurable scope through a new critical v0.11 TOPK
constitution; selection must then name TOPK rather than TOP3. Encoding bounds are
64 MiB input container, 64 MiB combined input legend bytes, 64 MiB decoded
source, one million input events and total entries, 400 rounds.
Pair expansion is at most 1 MiB and depth below 64. Selection includes each
terminal form program's existing reference depth when deciding which additional
pair edges are admissible (Court039 repair). Court045 streams event IDs through
private little-endian uint32 spools (64 KiB read blocks); pair counts are disk-backed
SQLite with at most 4,096 distinct pairs buffered per batch. Equal counts retain
first-occurrence order. A 128 MiB database-page ceiling fails closed; the 2 MiB
SQLite cache setting is a target, not a total-RSS or temporary-sort-disk bound.
These private spools do not change any transported format. Court046 moves terminal
program payloads and literal interning into a private SQLite database (256 MiB
page ceiling; 2 MiB cache target). Size/depth metadata uses uint32/uint8 arrays:
at most 5,000,000 logical bytes per set, two sets during fractionation, excluding
allocator overhead. Payloads stream from the table into the unchanged legend ABI.
Memoized reference depths are checked against the final combined-depth ceiling.
Archive container payloads now stream through bounded spans and disk-backed
record pooling. Court049's aggregate scratch scope applies to group-legend
pack/unpack, including their nested second-pass decoding. Court050 adds a
standalone second-pass transform scope: `--max-scratch-bytes` (default 4 GiB,
valid integer range 0 through 1 TiB) reserves logical file growth before writes
and each native SQLite page capacity before allocation. Ranking scans rows
with bounded top-k selection; unaccounted SQLite temporary sort plans refuse.
The resource IC is emitted before private allocation and accompanies the
rooted local receipt. Transform usage is captured before publication. The
transform-only Python API does not own transaction receipts or backups;
the public CLI adds the publication phase described below. Physical
filesystem overhead and RAM are not counted. This is not
whole-application streaming, a process-RAM ceiling, or Ultra-scale proof.
The selection IC records the resource policy; the transported v0.8 IC is unchanged.

Streams of at most 250,000 events use the deterministic in-memory fractionator;
larger streams retain the disk-backed spool and SQLite realization. The arms,
tie order, pair rules, limits, emitted legends, bodies, inverse checks, and
selection objective are identical. This is a performance realization choice,
not a format or semantic change. The composed decoder validates stored programs
from one sequential load bounded by the 64 MiB legend limit, a byte-array
cycle/depth pass, and a 128-entry expansion cache. This avoids repeated sparse
file lookups without introducing an unbounded expanded-value cache, while
preserving cycle, depth, expansion, and backward-pair checks.

Court051 coalesces four sequential sinks (private event spools, composed packed
body output, ordinary decode and composed decode) into writes of at most 64 KiB.
Each block still traverses the unchanged reserve-before-write quota kernel.
Unflushed pending bytes are bounded additional memory and discarded on failure;
they are not disk allocation and are not counted as such. Final flush failure
refuses publication. Seekable writers, native database limits, inverse checks,
IDs, ordering, bytes and transported configurations are unchanged. Coalescing
alone does not extend quota scope or establish an RSS limit.

Court052 extends the CLI's same --max-scratch-bytes limit through publication.
Its publication IC is compiled before temporary directories are created. The
transform must return a valid matching local resource receipt after closing its
private scope. The publication phase retains the selected staged artifact and
reserves exact receipt bytes plus every replacement backup before any auxiliary
write. Receipt size includes its own accounting fields, using a bounded
fixed-point calculation over deterministic UTF-8/LF JSON. Backup writes cannot
exceed their reservation; changed lengths and short writes refuse.

The combined peak is max(transform peak, staged artifact + receipt + backups
+ reserved recovery-journal capacity),
not a sum of disjoint phases. Original existing destinations are not newly
allocated scratch. Backup copies are. All reservations stay live through commit
or observed-exception rollback. Each destination retains staging beside its
own parent, including a receipt in another directory. If rollback itself fails,
private recovery copies are retained and their paths reported.

The receipt's publication.scratch section carries the new instance and exact
phase accounting. Its transform receipt_sha256 still covers the underlying
transform result, excluding the outer publication/application metadata as
before. Encoded containers and transported ICs are unchanged. This is neither
an OS quota nor a RAM bound, concurrent-writer isolation, actual disk-full
qualification or power-loss atomicity. Court053 adds a 64 KiB-capped recovery
journal before commit and explicit process-interruption recovery; see
RECOVERY.md for its schema, CLI and residual gaps. Other CLI commands retain
their explicitly documented resource scopes.

## Additive executable grammar

The existing binary .leg v0.2 envelope declares unit_mode COMPOSED_EVENTS_V1.
Terminal form programs use the existing compact form encoding, with local
references rebased into the concatenated original stack. They retain the
actual spelling operations, not merely their expanded strings.
FF 03 + ULEB(left) + ULEB(right) is a pair of earlier event IDs.
FF 04 + literal is an original escaped-literal event; it stays distinct from
an equal-spelling indexed event. Pairs may share an expanded spelling without
merging their event identity. This is scoped transport identity, not CSIL.

Body: SPP1 + ULEB(original_event_count) + ULEB(final_event_count) + event IDs.
The rooted IC binds terminal boundaries, pair counts, input packed-body SHA,
input container SHA and original source SHA. Decode verifies BOTH exact
original packed-event bytes and exact original source bytes. Literal events
recreate their original zero/length/data frames.
Old application readers refuse the critical unknown IC.

After successful composed output verification, first-pass body and legend
ARTIFACTS are unnecessary for decode. Their terminal information and form
programs survive inside the composed legend. The operation never deletes
inputs or updates shared relationship state. It does not recreate the exact
original legend FILE serialization or its audit dossier from nothing.

The earlier Adams Court013 raw-byte and dispersion gains, legend growth,
and XZ negative boundary remain historical evidence. This application uses
its current scanner, framing, and LZMA2/XZ preset 6, so its measurements are
new integration observations, not replacements for Court013's preset-9
packet measurements. No dispersion/encoding result proves confidentiality.
Group legends are a separate application layer; see GROUP_LEGEND.md.
