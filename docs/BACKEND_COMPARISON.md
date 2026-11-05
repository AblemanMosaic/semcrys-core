# Historical dev69 evidence: physical legend lookup comparison

This document records the bounded dev69 backend experiment. It is retained as
historical evidence, not as the current application version or release state.

No legend identity, container grammar, source semantics, standing, or security
claim changes. Disk-backed lookup remains the public CLI default. New backends
are explicitly experimental **low-level context API** choices, not automatic
CM2 routing and not public CLI switches:

```python
from streaming_app.legend_context import VerifiedLegendContext
from streaming_app.core import encode_file, decode_file
with VerifiedLegendContext(lookup_backend='RAM') as context:
    encode_file(source, output, profile='T:PRESHARED_TOKEN',
                external_legends=[legend], legend_context=context)
    decode_file(output, restored, external_legends=[legend],
                legend_context=context)
```

DISK: existing verified private snapshot, SQLite value-to-ID database, sparse
ID-to-value reader and bounded caches. MMAP: same verified database, explicit
SQLite mapping plus read-only mapped legend and dense immutable offset array.
RAM: same verified database copied to query-only in-memory SQLite, immutable
legend bytes and dense immutable offset array. New backends only accept plain
TOKEN legends; assembly/fold execution is not silently reinterpreted. Retain all
source/snapshot/database hash guards and reconstruction checks.

Preparation includes validation, uniqueness-index creation, and backend load.
RAM is not a dictionary of four million Python strings. The binary legend is
~54 MB, but the reverse lookup index and offsets require additional memory.
The payload budget includes offset-construction storage and database file size,
not SQLite heap/page overhead; it is **not** a hard RSS guarantee. Mapping is
virtual addressability, not guaranteed physical RAM residency. Existing process
trust limits apply; memory and OS compromise are not defended by hashes here.

Comparison: two repetitions, forward and reversed backend order, separate fresh
processes, real four-million-entry Ultra, historical small-source witness plus
declared synthetic broad-ID/hot-vocabulary fixtures. OS caches are not flushed.
No other test workload is deliberately run alongside timed measurements.
Fresh-process startup is not called cold-device I/O. Report startup separately
from encode/decode with an already prepared context. Count all startup when
evaluating one-shot use. Retain wall, CPU, RSS, byte roots, and full context ICs.

Distribution compares original .leg, XZ preset 6, and C:RAW_BYTES + LZMA .crys.
Both compressed forms must restore the exact binary legend root. This is outer
compression, **not** semantic legend factoring, second-pass fractionation, or
multi-document group-legend pooling. It does not alter already-shared warm wire
bytes and does not prove confidentiality. Those other mechanisms are preserved,
not replaced or asserted inferior by this test.
