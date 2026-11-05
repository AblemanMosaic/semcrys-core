# Historical ordered legend import

`legend import-ordered-v01 old.json new.leg --expected-source-sha256 ROOT`
explicitly imports the historical `semcrys.packed.legend.v0.1` ordered transport
table. It is distinct from `legend migrate-v01`, which handles the earlier
`semcrys.legend.v0.1` artifact schema. Renaming never implies migration.

The accepted top-level field sequence is exactly schema, ordering, cap, entries,
id2unit, occurrences, train, lineage. This is an explicit historical serialization
contract, not a general JSON dictionary importer. Ordering must be
`frequency_desc_first_seen_ties`. JSON whitespace and ordinary JSON string escapes
are accepted; the UTF-8 source's exact byte root is mandatory. Invalid/trailing
JSON, alternate/duplicate fields, wrong schemas/types, invalid Unicode, empty
units, inconsistent counts, negative occurrence values and duplicates are refused.

Each `id2unit` entry is emitted in original array order: local ID = position + 1.
No sorting, renumbering, normalization, case folding, vocabulary merging or sense
binding is performed. Occurrences are validated and summed but not materialized.
Training metadata and lineage are retained in the import receipt. They are source
claims, not newly verified facts about the training corpus.

The source is copied and hash-verified once into a private snapshot. The streaming
parser feeds the binary writer, whose uniqueness check is disk-backed. It consumes
and validates the entire occurrence vector and metadata before final publication.
An ordered content hash of big-endian u64 byte length followed by entry bytes is
computed while importing and recomputed across every entry in the generated
binary legend. Counts and hashes must agree. The binary legend's own whole-file
and sparse-index validation remains active. Its legend_id includes the source
artifact root. The output remains `CANDIDATE_ONLY`, never canonical CSIL/GTK.

Defaults/caps: source 1 GiB; entries/cap 10 million; decoded unit 16 MiB; parser
chunk 65,536 Unicode scalars; incomplete JSON token buffer bounded by six times
unit limit plus one chunk. These bounds do not imply constant total process RSS:
SQLite, Python, filesystem cache and OS allocations must be measured separately.
CPU time and scratch disk are not hard OS quotas. One snapshot, the new binary
legend, and disk-backed uniqueness/index state require free disk space.

Progress events include the rooted import Instance Constitution, each 250,000
units, and full ordered-correspondence verification. CLI progress goes to stderr;
the result and optional `--receipt` go to stdout/file. Public transactional output
preserves the original source and existing output on tested failures.

Imported transport words/blobs do not acquire GTK identities. Original training
occurrences are not a model of current source distribution. Runtime tokenization,
folded compatibility projections, adaptive ordering, compression quality, and
receiver pre-sharing remain separately governed choices; successful import alone
proves none of their performance or security claims.
