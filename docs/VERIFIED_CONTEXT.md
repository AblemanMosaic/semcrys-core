# Verified legend context — candidate v0.1

The artifact ABI and encoding Instance Constitution are unchanged. The execution
configuration now explicitly uses an ephemeral verified context: hash/copy each
exact legend into private temporary storage, validate its binary structure and
sparse index once, build a disk-backed unique lookup once, retain its digest and
verified reader, then share that context across configuration, body generation
and exact post-write reconstruction. Every operation checks complete legend and
lookup hashes before reuse and before publication. File timestamps alone never
authorize reuse. Lookup SQL connections are read-only after construction.

Base-plus-delta stacks use an ordered overlay with cumulative ID offsets. A
cross-stack duplicate check scans the smaller member of every pair; it does not
reinsert millions of base entries to accommodate a tiny delta. The original
source files and pre-shared relationship state are never updated by this cache.

`encode` and `decode` get the context automatically within one invocation.
For reuse over multiple documents in a single process:

```text
semcrys batch-encode NEW_DIRECTORY --source first.txt --source second.txt --profile T:PRESHARED_TOKEN --legend union.leg --outer-codec LZMA
```

This emits `000000.crys`, `000001.crys`, ... and `BATCH_RECEIPT.json` into a new
directory only after every document reconstructs exactly. The batch receipt
binds source roots, dependency roots, chosen profile, outer codec, resource
limits, operation sequence and each individual artifact/receipt. Progress goes
to stderr. Existing directories are refused; no replacement option exists.
There is no implied longitudinal delta adoption or group legend. All three
token profiles, RAW and the already-supported glyph option remain available.

Python callers may pass a live `VerifiedLegendContext` as `legend_context` to
`encode_file`/`decode_file`. The owning process is trusted. Context handles may
not be deserialized from manifests, forged from cache files or used after close.
Any failed operation invalidates the context. Private snapshots disappear on
close. Callers may optionally supply a persistent lookup-cache root. The cache
stores a rooted, hash-checked SQLite derivative under the exact legend SHA-256.
It is a disposable performance hint, never decoder state or semantic authority.
Every operation retains full snapshot and lookup hash guards, and mandatory
postwrite reconstruction remains the final correctness proof. Missing, corrupt,
or structurally invalid cache entries are rebuilt. Cold context creation must
still be measured separately from warm reuse. This is not new authority,
confidentiality, optimality or production-readiness evidence.

Default total snapshotted legend budget: 1 GiB; maximum context members: 1024.
Batch: at most 256 source files and 1 GiB source bytes by default. A lookup index
also uses temporary disk space; its bytes are not wire bytes or legend identity.
Per-connection SQLite page cache is bounded. These bounds do not claim a fixed
RSS across every possible configuration or a disk-quota guarantee. Hash guards
detect changed content, not an adversary controlling the owning process, OS,
or making undetected transient changes between guards. Directory publication
and observed-exception rollback are not power-loss durability guarantees.

## Sparse-block lookup cache

The binary legend reader retains at most one parsed sparse block per reader:
up to 1 MiB of serialized block data and 4,096 record-offset pairs. Offset
metadata, temporary parsing buffers, and returned values have additional memory
cost; this is not a 1 MiB process-RSS ceiling. Larger blocks use the original
direct reader. The block cache does not materialize the entire Ultra legend. A
separately configured persistent lookup cache may materialize its derived unique
lookup.

Every lookup still validates the path snapshot and an opened descriptor,
including cache hits. These are separate checks on Windows: descriptor change
time can detect a same-size rewrite even if modification time is restored.
The cache removes repeated block parsing, not custody checks. It changes no
legend identity, encoded byte, configuration choice, ABI, or receiver state.
The cache is internal and disposable, never transmitted as decoder data.

Private snapshot and SQLite filenames are compact per-context ordinals. Full
SHA-256 roots remain the lookup keys and verified identities; filenames do not
establish identity. This avoids unnecessary 64-character path expansion under
long Windows temporary parents. It is not a claim that every arbitrary path
length or platform-specific filesystem limit is supported.

## Court044 aggregate cache and cleanup contract

A verified context owns one LRU across its readers. The defaults are 8MiB of
retained serialized block payload and 32,768 retained span records, with the
existing per-block ceilings of 1MiB and 4,096 spans also enforced. Eviction
drops only disposable cached blocks. Zero cache budgets use direct reads.
Path and opened-descriptor custody checks remain on every cache hit. These
bounds exclude Python object overhead, returned values and transient parsing.

The Python context accepts max_lookup_cache_bytes, max_lookup_cache_entries,
and sqlite_cache_budget_kib; all appear in its rooted effective configuration.
The default aggregate SQLite page-cache target is 16,384KiB. Before each lookup
builder opens, existing connections and the builder receive an equal target
capped at 2,048KiB each. This is a SQLite suggested page-cache allowance, NOT a
hard process-RSS bound. Connection overhead, temporary storage and SQLite
allocations outside that page cache remain separate resource obligations.
Contexts are single-owner-thread objects, not concurrently shared caches.

Execution receipts expose exact retained/reserved block counters and aggregate
SQLite targets. These runtime controls do not change container/legend bytes,
legend order, admission or pre-shared relationship state.

Owned temporary legend/cache files are cleaned on observed BaseException paths
when the filesystem permits cleanup. A failed context cleanup returns
HELD_CONTEXT_CLEANUP_INCOMPLETE and the private path; the context stays unusable,
but close() may be retried after the external lock/failure is removed.
This is not automatic post-crash recovery or power-loss durability. Filesystem
fault injections are not measurements on a physically exhausted disk.

## Adaptive physical lookup

`AUTO` is the high-level selection default. Within the declared payload budget,
it prefers RAM, then bounded memory mapping, then disk. These are physical
realizations of the same exact lookup and do not change `.crys` bytes. The RAM
payload estimate is not a hard RSS limit. Naive per-document process fan-out is
therefore not enabled: each Ultra-backed worker could replicate roughly 216 MiB
of estimated lookup payload on the qualification host. Batch encoding instead
reuses one verified context across documents.
