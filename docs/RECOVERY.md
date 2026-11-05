# Publication recovery — candidate v0.1

## Deterministic interruption testing

Existing low-level progress callbacks expose `PUBLICATION_PREPARED` after the
journal is fsynced, `PUBLICATION_TARGET_COMMITTED` after each target commit,
and `RECOVERY_TARGET_ROLLED_BACK` after each reverse mutation. A test-only
subprocess can block on these events while its parent terminates that exact
child, then exercises the public recovery CLI against the retained journal.
Do not confuse an exception (which invokes in-process cleanup) with abrupt
process death. No CLI crash option or environment fault switch is provided.
Directory publication likewise exposes `DIRECTORY_PREPARED` and
`DIRECTORY_PUBLISHED`; its recovery operation is quarantine, not file rollback.
These tests cover selected process-interruption states, not sudden power loss.

SemCrys file publication stages an output and optional receipt beside their
respective destinations. After all staging and replacement backups are ready,
it writes and fsyncs RECOVERY.json in the output's private semcrys-publish-*
directory before the first target rename. Backups are also fsynced before
that journal is written. Successful publication/observed rollback removes the
private directories as before. Process death can leave them for inspection.

The journal is local runtime state, never .crys/.leg content, a legend, security
credential or authority grant. It is capped at 65,536 UTF-8 bytes. Second-pass
CLI publication reserves this whole cap (not just actual journal length)
alongside the staged output, exact receipt and backup copies. Other commands
do not thereby acquire whole-operation resource accounting.

## Explicit recovery

    semcrys recovery inspect PATH/RECOVERY.json
    semcrys recovery rollback PATH/RECOVERY.json --expected-journal-root ROOT --output OUTPUT --receipt RECEIPT

Omit --receipt only when the journal contains no receipt target. Inspect is
read-only. Rollback requires the exact inspected root and exact caller-named
destinations; it does not take destination authority from the journal alone.
The caller must first stop the original process; recovery does not discover or
kill processes. Explicit rollback takes the same nonblocking parent-directory
OS locks as file publication, then revalidates the journal and caller-named
targets while holding those locks. A cooperating owner already holding a parent
lock causes `HELD_PUBLICATION_BUSY`, without waiting or mutating target content.
Inspection remains read-only and does not claim a locked snapshot.

## Coordination contract

The following fields mirror `PUBLICATION_CONCURRENCY_CONTRACT.json`:

| Field | Value |
|---|---|
| lock_scope | RESOLVED_OUTPUT_PARENT |
| lock_file | .semcrys-publication.lock |
| lock_lifecycle | PERSISTENT_INODE_KERNEL_HANDLE_RELEASE_ON_EXIT |
| contention | REFUSE_WITHOUT_WAIT |
| scope | COOPERATING_LOCAL_SEMCRYS_FILE_DIRECTORY_PUBLICATION_AND_EXPLICIT_RECOVERY |

The zero-byte lock file persists after successful operations; the kernel-held
lock is released when its handle closes or its process exits. Do not remove the
file while writers may run. Coordinate each target parent within one supported
local OS lock domain. Prevent noncooperating external writers; hostile writers,
cross-OS or network coordination and power-loss guarantees are not covered.
See `PUBLICATION_SAFETY.md` for platform support and exact exclusions.

## Recovery behavior

Inspect reports ALL_OLD, MIXED or ALL_NEW after validating the rooted schema,
typed paths and existing files. These are content states, not claims about
which syscall ran. Drift, unexpected files, changed backup/stage content,
missing needed backups or unrecognized target contents refuse. There is no
force or bypass option.

Rollback validates every row before its first mutation, then restores in reverse
order. A target already equal to its old state is unchanged. A new target with
no old predecessor is removed; otherwise its verified backup replaces it.
Checks repeat between mutations. If recovery itself is interrupted, the same
command can resume from the newly observed content state. The journal and any
unused private files remain for review; recovery performs no recursive cleanup.

Before mutation, a rooted recovery Instance Constitution is emitted. The final
JSON records initial states, changed roles, final ALL_OLD state and retained
journal. The recovery code copies no payload and requires no new temporary
payload allocation. Results on stdout can be redirected explicitly by the user.

## Journal schema

Top-level exact keys: schema=semcrys.publication-recovery-journal.v0.1;
standing=CANDIDATE_ONLY; intent=EXPLICIT_ROLLBACK_TO_PRIOR_TARGETS;
rows=array of one OUTPUT then optional RECEIPT; power_failure_atomicity=false;
concurrent_writers_supported=false; journal_root=SHA256 of canonical JSON
(sorted keys, no whitespace, UTF-8, ensure_ascii=false) excluding journal_root.

Row exact keys: role; target (absolute canonical local path); stage (absolute
path new+target suffix beneath its own semcrys-publish-* directory beside the
target); backup (same private directory/previous or null); old (fingerprint
or null); new (fingerprint). Fingerprint={bytes:nonnegative integer,
sha256:64 lowercase hex}. Old and backup are null together. The journal itself
must be RECOVERY.json in the first row's staging directory. Unknown keys,
duplicate keys, aliases, foreign path layouts and unexpected directory members
refuse. A hash detects mismatch against the expected root; it is not a signature.

## Boundaries

This enables explicit process-interruption recovery in tested file-publication
paths. It does not make a pair of renames atomic. It does not prove power-loss
durability, universal disk-exhaustion safety, hostile-writer isolation, recovery
of legacy unjournaled staging, or automatic cleanup of pre-journal leftovers.
Directory-based publication is a separate path: `DIRECTORY_RESOURCES.md` defines
explicit quarantine for journaled fold-compact, batch-encode, archive-selected
and group-legend pack/unpack outputs. A process
killed during final cleanup can leave partial housekeeping after complete
publication; do not infer journal presence or absence alone proves completion.
No automatic startup rollback, source deletion, release, admission, standing
change, canonical CSIL/GTK mutation or cryptographic confidentiality.
