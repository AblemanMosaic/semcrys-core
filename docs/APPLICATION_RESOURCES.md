# Primary encode/decode temporary-storage contract

Candidate-only. `encode` and `decode` default to `--max-scratch-bytes
4294967296` (4 GiB); explicit integer limits range from zero through 1 TiB.
The same limit covers two sequential phases, so the combined peak is their
maximum, not their sum:

1. Realization: source snapshots, private legend snapshots and lookups,
   local count/rank databases, intermediate bodies, embedded controls,
   reconstruction checks and the staged result. Nested decoders share the
   same quota. File growth is reserved before writes; native SQLite databases
   reserve their page capacity before opening. Closed databases remain charged
   at their actual size until removal.
2. Publication: staged output, exact UTF-8/LF receipt (including its own length),
   every replacement backup and the recovery journal's full 64 KiB capacity.
   All auxiliaries are reserved before receipt/backup writes. Observed failures
   preserve prior destinations; process-interruption recovery uses RECOVERY.md.

The implementation reuses the existing file quota and SQL-plan guards. Local
legend selection reads immutable counts and writes an explicit ordered primary
B-tree keyed by negative frequency and exact bytes. This preserves the prior
legend ordering without an unaccounted SQL temporary sort.

The installed model is `APPLICATION_RESOURCE_CONTRACT.json`. Resource ICs are
rooted and emitted on stderr before scoped I/O. The final local JSON receipt
contains `scratch_instance`, `scratch_budget` and `publication.scratch`.
These resource controls are not added to transported container identity.

Example (a prepared, exact pre-shared base remains an input, not a new legend):

```text
python semcrys.pyz encode letter.txt letter.crys --profile T:PRESHARED_TOKEN --legend union.leg --max-scratch-bytes 4294967296 --receipt encode.json
python semcrys.pyz decode letter.crys restored.txt --legend union.leg --max-scratch-bytes 4294967296 --receipt decode.json
```

Low limits produce `HELD_SCRATCH_BUDGET` before forbidden growth. A small text
may require a large reservation because native database capacity is reserved,
not because that many bytes were physically written. Inputs and pre-existing
targets are not charged, but newly created copies of them are. Limits do not
silently select another codec, legend, security mechanism or cheaper output.

Python callers use `semcrys.application.encode/decode` for the bounded
realization phase. They can compose `semcrys.transaction.publish` with the
same limit and `resource_operation='ENCODE'` or `'DECODE'` for receipt/backup
accounting. Shared external contexts and nested top-level scopes refuse;
composite internals use `streaming_app` with their existing explicit scope.

Boundaries: not a process-RAM cap, physical-filesystem allocation cap, OS
sandbox, power-loss guarantee or concurrent-writer isolation. Other top-level
commands are not silently enrolled. Quota refusal tests are not actual disk
exhaustion tests. No new compression advantage, security or release claim.