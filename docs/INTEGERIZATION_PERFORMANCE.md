# Integerization performance qualification

This qualification isolates the Full compiler on the exact pinned Wikipedia
fixture and release-bound Ultra legend. All records are rooted JSON under
`evidence/`. Verify their roots and invariant container identities with:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -B tools\verify_integerization_performance_evidence.py
```

## Measured result

| Path | Ultra preparation | Encode plus mandatory postwrite proof |
|---|---:|---:|
| Original disk lookup | 65.107 s | 170.244 s |
| Memory-mapped lookup | 65.554 s | 97.223 s |
| RAM lookup before batching | 64.810 s | 25.756 s |
| AUTO, batched Python parser | 65.050 s | 13.561 s |
| AUTO, ABI-2 C parser | 70.863 s | 13.164 s |
| Rooted cache, cold | 66.690 s | 11.939 s |
| Rooted cache, warm | 12.300 s | 12.403 s |
| Full integerization, warm cache | 12.558 s | 8.612 s |

For profitable integerization, the comparable untraced disk path fell from
170.244 seconds to 13.164 seconds, a 92.27% reduction. Warm cache reuse reduced
Ultra preparation by 81.56%. The ABI-2 parser supplied about 2.93% beyond the
already-batched Python path on this fixture. The major gain came from adaptive
physical lookup, batched resolution, larger bounded caches, eliminating default
diagnostic tracing, and avoiding a redundant independent decode.

Every profitable record produced the same 671,046-byte container with SHA-256
`e0d424b3aa7265bcbd4d8a60eb8da5f4655bbae02fc194d669e6eb0630d4a43c`.
The full-integerization record produced the established 724,782-byte container
with SHA-256
`c0d3e93008358f758530bb54572edbc004456159a452774d281a9b92e5cdffce`.

## Governance and parallelism

`SENTINEL` keeps phase durations and exact proof state without Python allocation
tracing. `DIAGNOSTIC` enables `tracemalloc`; an independent second re-decode is
also opt-in. Neither changes the selected container.

Single-file token reconstruction remains ordered. Batch jobs reuse one verified
adaptive context instead of opening one Ultra lookup per document. A process
pool is intentionally deferred until it can enforce an aggregate memory budget:
the RAM realization estimated about 216 MiB of lookup payload per Ultra-backed
worker on this host, so naive multicore fan-out could trade latency for memory
exhaustion. GPU/CUDA is not justified by the measured phase mix; parsing and
irregular lookup are control-heavy, while stdlib compression already runs in
native code.

These are single-host, single-fixture observations. They do not establish
cross-corpus throughput, a hard RSS ceiling, or global optimality.
