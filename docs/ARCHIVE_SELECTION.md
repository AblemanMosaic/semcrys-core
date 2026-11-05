# Exact archive selection — current candidate contract

This is a measured minimum over a bounded, explicit configuration set, not a
learned prediction or claim of optimal SemCrys. It operationalizes the known
signal-amortization boundary: small files must not inherit an expensive front
just because it helped a larger archive.

1. Build a front on designated calibration material with `fold build`.
2. Use `fold prefix full.leg zero.leg --front-cap 0`, and optionally additional
   capacities, to retain the same calibration ordering without retraining.
   The prefix receipt binds its parent. The artifact keeps original calibration
   provenance; base-dependent semantic validation still occurs at use.
3. Run `archive select choice.json --source one.txt --source two.txt
   --legend base.leg --fold-front zero.leg --fold-front full.leg
   --accounting COLD --horizon 1`.
4. Run `archive encode-selected choice.json result-directory --source one.txt
   --source two.txt --legend base.leg --fold-front zero.leg --fold-front full.leg`.

The candidate set always includes raw and local self-contained containers,
the unchanged pre-shared base with its normal scanner, and embedded/external
placement of each provided folded front. At least one zero front is required.
Base-only is distinct from the folded zero front because the scanners and
constituent fallback differ. Failed functional preconditions are typed
UNAVAILABLE cells; unexpected corruption or runtime failure halts the court.

Each candidate realizes and inverse-checks every exact ordered source. The
selector retains compact roots and byte ledgers, not every trial container.
It chooses minimum `H * sum(container_bytes) + missing_dependency_bytes`,
then lexical stable recipe ID. The outer codec is explicit NONE or LZMA2/XZ6;
it is not silently switched. One to eight supplied fronts, one to 32 source
files, at most 512 candidate-document realizations, up to 64 MiB source bytes
and 1 GiB dependency bytes are admitted by this interface.

H is 1..32 repetitions of **this identical workload**, with fixed dependency
availability. It is not a prediction of differently shaped future letters,
recipient fanout, adaptive updates, or unseen archives. No repeat contents
are deduplicated beyond the selected codec. H does not cause encode-selected
to create H copies: it creates one delivery plus missing dependency artifacts,
and reports the separately modeled horizon cost.

COLD charges the exact full bytes of dependencies not named with repeatable
`--receiver-root`. WARM permits only candidates whose external dependencies
are all declared available. An embedded front requires only its base externally;
an external front requires both. Declarations must name roots in the candidate
set; local presence is not receiver attestation. No relationship state changes.

The new result directory contains numbered .crys files and, when required,
one copy of each missing .leg under dependencies/. LOCAL_REPLAY_RECEIPT.json
is local evidence, not billed transport. Local selection/replay receipts and
unmeasured OS/network/session framing are excluded explicitly. Actual delivered
container/dependency bytes are separately reported from horizon costs.

Selected replay checks every selected container's bytes and IC root against
the frozen ledger, then checks custody before publishing a new directory.
It does not rerun other candidates or authenticate a self-rehashed ledger.
Roots establish correspondence, not publisher identity. Existing profiles and
container ABIs remain unchanged. No security, admission or release claim.

Open work: selection across multiple Union/domain bases in this archive mode,
new-data calibrated prediction, aggregated archive framing, morphology/event
projection, second pass, group legends, and independent release qualification.
# Court034 accounting clarification

Compact v0.2 fronts are accepted alongside rich v0.1 fronts. Candidate costs
charge actual executable artifacts, not separate provenance dossiers. This is
execution-only delivery selection. See COMPACT_PROJECTION.md for explicit
audit-inclusive acquisition accounting; do not infer an audit-inclusive optimum.
