# Directory resource integration

`fold compact`, `batch-encode`, `archive encode-selected`, `group-legend pack`
and `group-legend unpack` accept
`--max-scratch-bytes` (default 4 GiB). Their public Python entry is
`semcrys.directory_application.run(operation, source, output, **options)`;
BATCH_ENCODE takes `source=None` and explicit `sources`.

One rooted Instance Constitution is emitted before work. Temporary source and
legend copies, native database capacity, nested encoding/decoding, all final
payloads and existing local receipts share one owner. The completed directory is
checked for unowned files, size drift, nonregular entries and open resources.
Files are flushed, a rooted recovery journal is written and fsynced, hashes are
rechecked, and the complete directory is renamed only to an absent destination.
There is no replacement mode.

The additional `LOCAL_RESOURCE_RECEIPT.json` is local audit metadata, not a decoder
dependency. It records the input/output-manifest root, resource instance, final
logical bytes and peak reservations; a fixed-point serialization includes the
receipt's own byte cost. All original `.crys`, `.leg`, `.gly` and provenance bytes
are preserved. Batch and archive replay receipts contain context-creation timings;
the batch receipt also contains per-document timings. Their hashes therefore vary
between runs. Validate each root and compare the remaining fields separately;
do not claim byte-identical local observation receipts.

The receipt is prepared before publication, not a claim of crash-durable commit.
A 262,144-byte journal capacity is reserved before any work, in addition to
native database reservations. Its dedicated bounded writer is charged through
that reservation, not charged twice as a tracked payload file. The receipt's
native_capacity_bytes includes this full journal cap; reserved_bytes includes
it even though the journal is removed after successful publication.

## Interrupted directory publication

    semcrys recovery directory-inspect PATH/DIRECTORY_RECOVERY.json
    semcrys recovery directory-quarantine PATH/DIRECTORY_RECOVERY.json --output EXACT_OUTPUT --expected-journal-root ROOT

DIRECTORY_PREPARED and DIRECTORY_PUBLISHED progress events identify the journal
and root. A prepared exception retains the private directory, journal and
payload. Successful completion removes its private journal. Process termination
can interrupt either path. Inspect is read-only; it verifies the full manifest,
typed paths, regular files, directory structure and journal root, then reports
PREPARED (private stage), PUBLISHED (destination), or NEITHER_PRESENT.

Quarantine requires the caller's exact output path and inspected journal root.
The original process must be stopped and concurrent writers prevented first.
If PUBLISHED, it renames the verified destination back to the absent private
stage. If already PREPARED, it makes no change. All payload bytes and the journal
are retained; no recursive deletion, payload copy or automatic cleanup occurs.
Interrupted quarantine is repeatable. NEITHER_PRESENT is not successful recovery.
Unexpected/changed content, journal aliases/reparse points, both trees present, malformed
or oversized journals and wrong target/root bindings refuse without a bypass.

The journal is bounded at 256 KiB, 2,048 files and 2,048 directories, with an
exact manifest and typed sibling paths. It is local observation/recovery state,
not a transported decoder dependency, identity, signature or authority grant.
Hash roots establish correspondence, not sender authentication.
The entry cap accommodates the existing group-legend envelope of 32 containers,
1,024 legends, up to 64 typed glyph/fold auxiliaries and local receipts; the byte
cap still applies independently. This capacity statement is not a combined-maxima
or physical-filesystem-exhaustion test result.
Public pack/unpack return a new receipt_sha256 covering final resource/recovery
metadata. realization_receipt_sha256 identifies the unchanged-format internal
META_RECEIPT.json or UNPACK_RECEIPT.json. Do not compare the two as one receipt.
Caller output spellings (including Windows 8.3 short paths) are resolved before
being journaled or compared for authorization. The journal itself must contain
canonical paths. Inventory limits are enforced while walking, before descent
into a directory or hashing an additional over-limit file.

An interruption before journal preparation can still leave unjournaled scratch.
Do not delete directories based only on their names. No automatic orphan
recovery, power-loss atomicity or concurrent-writer safety is established.

This is logical-file/native-capacity accounting, not a physical disk or RSS limit.
Directory entries/filesystem allocation overhead and stdout are not charged as
disk payload. Existing source/legend/document limits remain independently active.
No new compression claim, security claim, legend adoption or canonical mutation.
