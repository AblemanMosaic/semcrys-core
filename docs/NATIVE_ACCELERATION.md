# Native acceleration

SemCrys keeps its semantic, constitutional, security, and observability policy
in Python. The optional native kernel accelerates bounded buffer transforms that
have a simple exact correspondence with the Python reference implementation.

## ABI 2 operations

- unsigned 63-bit varint packing;
- unsigned 63-bit varint unpacking;
- canonical packed token-event parsing into ID/literal descriptors;
- repeated left-to-right assembly-pair folding.

The kernel is a standalone C ABI loaded with Python's standard-library `ctypes`.
It does not link to CPython and therefore avoids a per-Python-version extension
ABI. The packaged binary is accepted only when its adjacent build manifest,
SHA-256, platform, machine, and ABI all agree.

## Policy

- `SEMCRYS_NATIVE=auto`: use a compatible kernel above the adaptive threshold;
- `SEMCRYS_NATIVE=off`: always execute the Python reference path;
- `SEMCRYS_NATIVE=required`: refuse accelerated operations if the kernel is unavailable.

The default threshold is 128 events and can be changed with
`SEMCRYS_NATIVE_THRESHOLD`. Small operations remain in Python because conversion
cost can exceed native execution savings.

The Full compiler applies a second integration threshold: it buffers symbol
runs and calls the native packer only at 512 values or more. This is independent
of the kernel's general threshold and prevents fragmented Profitable streams
from repeatedly crossing the ABI. Dense Total streams can still be emitted in
bounded batches of at most 8192 IDs.

## Invariants

Native selection does not alter container bytes, event sequences, roots,
security claims, semantic identity, or authority. Differential tests compare
both realizations. Runtime counters remain out of transported containers so
timing and realization cannot make deterministic artifacts diverge.

UTF-8 token scanning is not native in ABI 2. A future scanner must pin Unicode
classification behavior and prove corpus-wide boundary equivalence before it
can enter `AUTO` selection.

The packed-event parser is bounded to bodies no larger than 64 MiB in the Full
compiler. It performs canonical varint and literal-boundary checks and falls
back to the same Python refusal path on malformed input. On the pinned fixture,
the C parser improved the already-batched Python path by about 2.9%. It is a
useful bounded kernel, not the source of the larger end-to-end gain.

The isolated 500,000-event ABI-2 differential benchmark measured the parser at
51.2x the Python reference loop, while pack, unpack, and assembly fold measured
4.29x, 4.75x, and 8.61x respectively. Those microbenchmarks explain kernel
capacity, not application-wide speedup. The rooted record is
`evidence/NATIVE-BENCHMARK-ABI2.json`.

## Corpus qualification

The pinned Wikipedia harness compares `OFF` and `AUTO` using identical Full
configuration bytes, verifies one container from each legend policy by exact
decode, and records a call-level profile on a deterministic 1 MiB prefix. It is
a diagnostic court, not a universal throughput promise. See
`benchmarks/wikipedia/README.md` and `evidence/WIKIPEDIA-BENCHMARK.json`.
The phase-separated optimization evidence is documented in
`docs/INTEGERIZATION_PERFORMANCE.md`.
