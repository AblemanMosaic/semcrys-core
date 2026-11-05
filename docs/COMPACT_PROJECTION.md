# Compact execution projection and rooted provenance

Candidate Apache-2.0 application. Explicit opt-in; no release or security claim.

`fold build` and `fold prefix` still emit byte-compatible rich v0.1 artifacts.
`fold compact rich.leg bundle-dir` creates a new directory containing:

- `front.leg`: v0.2 executable projection, unchanged packed signal and base root.
- `provenance.json`: canonical dossier with the entire source header, source
  artifact root and compaction operation sequence.
- `LOCAL_RECEIPT.json`: local configuration and cost receipt, not wire data.

The compact header replaces ordering, calibration roots and candidate policy
with `provenance_sha256`. Cardinalities, signal codec/root, tokenizer, unit limit
and front cap remain. This is smaller executable framing, not a claim of a
theoretically minimal serialization. The rich original is not deleted or changed.

`fold audit bundle-dir/front.leg --provenance bundle-dir/provenance.json` verifies
the dossier root, strict canonical schema and exact rich-source reconstruction.
`fold restore-rich bundle-dir/front.leg restored.leg --provenance bundle-dir/provenance.json`
recreates the original rich artifact byte for byte. Then prefix and recompact
if a smaller cap is needed. Prefixing a compact front without its dossier refuses.

Use the compact `front.leg` with existing `--fold-front`, embedded or external.
The old rich format remains readable; old readers fail closed on the new schema.
Neither a renamed extension nor an unknown schema is an implicit migration.
The SFP1 body is unchanged; container identity changes because its projection
binding changes. Decoding uses the exact base and signal, not the dossier.
Inspection explicitly reports an unresolved provenance root until a separate
audit is requested. It does not fetch a file or network resource automatically.

## Accounting

Execution-only transport can omit the dossier: the recipient can decode, but
cannot reconstruct or audit calibration provenance from the root alone.
Sender/source evidence should retain the dossier. No claim of authentication or
truth follows from hashing a self-consistent dossier.

`fold delivery-cost bundle-dir/front.leg --policy EXECUTION_ONLY`
charges the missing external projection once. `--policy EXECUTION_AND_AUDIT
--provenance bundle-dir/provenance.json` additionally verifies and charges the
missing dossier. `--receiver-root` explicitly declares exact artifacts present;
unknown/duplicate roots refuse. `--container-bytes N --horizon H` adds H identical
deliveries of the caller-declared container bytes. This calculator does not
measure those containers, attest receiver state, transmit data, or charge the
base legend; include a missing base separately. H is 1–32 identical repetitions.

Existing encode/batch/archive costs charge executable containers and external
legend/projection dependencies, **not** the separate audit dossier. Archive
selection is therefore an execution-only objective. Full audit-inclusive
archive optimization remains explicit future work; do not call that selector
optimal for an audit-delivery objective. Both sizes are reported by compaction
and audit. A complete cold audit bundle can be larger than the rich original.
The provenance was relocated and rooted, not made free or discarded.

No new SFTIR primitive, semantic-discrimination, compression superiority,
cryptographic confidentiality, admission, or production claim is made.

## Versioned contract reading

FOLD_PROFILE_CONTRACT.json retains the v0.1 rich-builder/standalone-profile
contract. COMPACT_PROJECTION_CONTRACT.json is its additive compact specialization;
ARCHIVE_PROFILE_CONTRACT.json defines exact-workload selection above standalone
encoding. A legacy standalone `NOT_YET_INTEGRATED` selector field must not be
read as overriding the separate archive feature or the installed catalogue.
Consolidating these versioned descriptions is a remaining release-documentation
task; versioned evidence is not silently rewritten as an earlier claim.
