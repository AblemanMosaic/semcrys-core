# Candidate legend library and measured selection

This document describes the original one-root-per-member v0.1 surface. The
successor v0.2 stack library deduplicates roots shared by versioned base/delta
stacks and is documented in CONFIGURATION_SELECTION.md. Neither replaces or
silently rewrites the other.

This is a local control-plane interface. `.crys`, binary `.leg`, `.gly` and
packed/glyph encodings are unchanged. Library/selection JSON is not a new wire
codec, encryption mechanism, permission grant or admitted selector.

`library build library.json --member union UNION union.leg --member medical DOMAIN medical.leg`
creates canonical UTF-8 JSON with exactly schema (`semcrys.legend-library.v0.1`),
standing (`CANDIDATE_ONLY`), unit_identity (`LOCAL_TRANSPORT_UNITS_NOT_GTK_SENSES`),
members and library_root. Members are sorted by unique ID and contain exactly
id, family (UNION/ULTRA/DOMAIN), legend_sha256, legend_bytes, entry_count. A member
is one exact binary v0.2 BASE legend, not a mutable path or implicit delta chain.
Names/families are caller labels, not proof of coverage, semantic identity or
optimality. Multiple members may reference one root; acquisition counts it once.
Paths are supplied separately at use time with `--legend`, so relocation does not
change identity. Frozen legacy JSON tables require explicit migration; renaming
them is not valid. Use the explicit `legend import-ordered-v01` command for the
historical packed ordered-table schema; source identity and original order are
retained. Large-legend quality and adaptive projection remain separate questions.

`select source.txt selection.json --library library.json --legend union.leg
--legend medical.leg --accounting WARM --receiver-root SHA256 --outer-codec LZMA`

compiles a rooted selection Instance Constitution before any candidate encode.
After validating UTF-8 eligibility it measures RAW, self-contained local, and each library member's pre-shared and
TOTAL-delta profiles on the entire frozen source. Projection is explicitly PACKED.
One chosen outer codec applies to every alternative. Progress events go to stderr;
the final result/receipt goes to stdout. No statistical performance prediction or
hidden corpus-class classifier is involved. `WARM` makes external profiles
unavailable unless every external root is explicitly declared receiver-known.
Local presence never implies receiver possession. This is caller declaration,
not a remote attestation. `COLD` allows acquiring missing roots and counts their
exact uncompressed binary `.leg` file bytes once. Already-acknowledged roots cost
zero acquisition in either mode. Embedded delta bytes are already in `.crys`.

Score = complete `.crys` bytes + missing external `.leg` bytes. Ties use recipe ID.
The local library manifest and selection receipt are not transmitted and excluded;
if a protocol chooses to send them, it must add those bytes. The container already
includes actual control/receipt framing. No transport-envelope cost is invented.
Acquisition compression, projected reuse horizons and second-pass projections
remain separately unintegrated; the record says exactly what was counted.

`encode-selected source.txt selection.json chosen.crys --library library.json
--legend union.leg --legend medical.leg`

validates the rooted library, source root/size, receiver prerequisites, exact
recipe sequence, typed cost ledger and minimum selection, then reruns the chosen
recipe. Its bytes, full Instance Constitution and realization receipt must match
the measured row before publication. It does not reexecute all alternatives or
authenticate an untrusted party's measurement claims. Every selected encode also
executes the existing full reconstruction check. It never modifies a receiver
cache, append-only shared relationship, existing legend, or canonical CSIL/GTK.

Control JSON is at most 1 MiB; library at most 16 members (34 candidate recipes);
source at most 64 MiB; unique legend files at most 1 GiB. Source and legend snapshots
are bounded while reading. These are current application limits, not mathematical
limits. Trials run serially and each temporary `.crys` is removed after measurement;
source/legend snapshots and disk-backed lookup indexes still require disk space.
No hard OS-wide disk/RSS/CPU quota is claimed. Reading large legends and repeating
encodes may be expensive. There is no claim that search time beats direct encoding.

The finite exact-source minimum is not a global compression optimum. Old folded
front/capacity/shape evidence remains external candidate context, not silently
treated as a selector for this different implementation. The short-archive
negative boundary motivates actual complete-cost measurement and retaining local
baselines; it does not license extrapolating future reuse.
