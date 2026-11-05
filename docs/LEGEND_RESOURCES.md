# Legend workflow resource contract

Candidate-only. Public `legend build`, `legend migrate-v01`,
`legend import-ordered-v01`, `legend extract`, `glyph build`, `glyph export`
and `library build` accept `--max-scratch-bytes` (default 4 GiB; integer 0..1 TiB).
The installed `LEGEND_RESOURCE_CONTRACT.json` enumerates exactly these seven
operations. It does not silently enroll fold/assembly/selection/batch commands.

The resource IC is emitted before private allocation. One owned scope includes
snapshots, count/rank databases, uniqueness checks, index spools, captured
embedded legends, pending outputs and any nested glyph reconstruction decoder.
The immutable input and pre-existing output are not charged; temporary copies
are. File growth is reserved before writes. Native SQLite files reserve their
declared page capacity (default 256 MiB each), which is not measured disk or RAM.

After realization closes its scope, publication uses the same limit for the
staged output, exact JSON receipt, every replacement backup and the full 64 KiB
recovery-journal capacity. The combined peak is the maximum of the two phases,
not their sum. Insufficient quota refuses; it does not choose a different
legend, drop evidence, change IDs, suppress backups or alter shared state.

```text
python semcrys.pyz legend build union-source.txt union.leg --policy TOTAL --max-scratch-bytes 4294967296 --receipt union-build.json
python semcrys.pyz legend import-ordered-v01 old.json migrated.leg --expected-source-sha256 ROOT --max-scratch-bytes 4294967296 --receipt migration.json
python semcrys.pyz library build library.json --member union UNION union.leg --receipt library-build.json
```

`ROOT` means the exact 64-hex SHA256 of the old source, not a placeholder accepted
by the CLI. Migration and ordered import remain different formats. Canonical
JSON v0.1 migration reads at most 64 MiB of source into memory and is **not**
streaming. The ordered packed-legend importer streams and retains its explicit
source/entry/value limits and exact source-root requirement. Parent-root remaps
are not inferred. Count statistics in the Python build result now use the same
array shape as its JSON receipt.

Extraction snapshots its source before validating and selecting an embedded
legend; extracting an external binding still refuses. Glyph export validates
source reconstruction under the same scope before exporting glyph text.
Library families remain caller labels, not evidence of coverage or optimality.
Nothing changes .leg/.gly/container bytes or turns local IDs into canonical
CSIL/GTK identities. New legend adoption remains explicit.

Python: `semcrys.application.run(OPERATION, source_or_None, output, **options)`
provides the realization phase. Use `transaction.publish` with the matching
`resource_operation` and same limit to include receipts/backups. `GLYPH_BUILD`
and `LIBRARY_BUILD` take None as source and explicit glyph/member parameters.
Low-level artifact functions inherit an existing scope; they are not stand-alone
quota APIs. Resource receipts are local, not free wire bytes.

Boundaries: no whole-application, RAM, physical-allocation, actual disk-full,
power-loss, concurrent-writer, cryptographic-security or release claim. Existing
larger resource/platform/profile/release requirements remain open.
