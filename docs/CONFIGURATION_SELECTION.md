# Versioned legend-stack and codec selection - v0.2 release-candidate contract

Reviewed 2026-08-31. The implementation originated in dev87; this is the
current release-candidate contract, not a public release date.

`library build-stacks` creates a rooted `semcrys.legend-stack-library.v0.2`
control artifact. Every member names a stack, a typed family label, a zero-based
ordinal and an exact binary `.leg`. Ordinals must be contiguous and every parent
must be the preceding root. Shared base roots are described once in `artifacts`
and referenced from multiple stacks, so the manifest itself does not duplicate
their bytes or identity.

Supported labels are UNION, ULTRA, DOMAIN, SPARSE_EXTENSION, LONGITUDINAL and
HYBRID. They describe the caller's proposed role only. They do not prove corpus
coverage, GTK identity, fitness, optimality, receiver possession or admission.
Every legend remains a scoped local transport mapping.

`configuration select` freezes one exact source, stack library, supplied artifact
set, codec set, COLD/WARM receiver declarations and reuse horizon. It compiles the
complete RAW/local plus stack-preshared/stack-delta cross-product, materializes
every executable complete `.crys`, decodes every one to the source root, and
records complete container bytes, BODY bytes, missing-root acquisition bytes,
wall time and CPU time. `SENTINEL` is the default and does not enable
`tracemalloc`; `DIAGNOSTIC` records Python-traced peak allocation when explicitly
requested. The encoder's mandatory postwrite reconstruction is the default
inverse proof. An additional independent re-decode is opt-in diagnostic work.

The decision objective is:

`score_bytes = container_bytes * exact_reuse_horizon + unique_missing_legend_bytes`

Timing and traced memory are observations, not decision inputs. Exact byte ties
use canonical candidate ID. The memory field is Python `tracemalloc` only—not
process RSS, native-library allocation or an OS-wide bound. Reuse means repetitions
of this exact frozen source workload, not prediction of unseen documents.

The high-level selector defaults to `AUTO` physical lookup with a 512 MiB
estimated payload budget and accepts an optional rooted persistent lookup-cache
directory. Cache state is not part of the selected format or receiver custody.
Corrupt cache entries are ignored and rebuilt; exact reconstruction still gates
publication.

WARM makes a stack candidate unavailable unless every required root is present in
the caller's receiver-root set. COLD charges each missing artifact root once even
when roots are shared across stacks. Receiver declarations are accounting inputs,
not remote attestations. RAW/local candidates remain available without legends.
Non-UTF-8 input makes token candidates unavailable while retaining RAW. ZSTD cells
remain explicitly typed unavailable; no package install or codec substitution occurs.

`configuration encode-selected` revalidates the rooted library and selection,
source root/length/UTF-8 state, every artifact binding and lineage, selected full
configuration, receipt, bytes and reconstruction before publication. It refuses
drift rather than selecting again. The record binds application payload and runtime
identity but does not authenticate an untrusted measurement party.

Limits: 16 stacks, 64 unique artifacts, 256 candidate cells, 64 MiB source,
1 GiB aggregate supplied legends, 4 MiB control record and horizons 1..1024.
These are bounded application limits, not universal scale or optimality claims.
Control records are not transmitted unless another protocol chooses to send them.
No result establishes confidentiality, global compression optimality, future
workload performance, canonical CSIL/GTK mutation, release or production routing.

The outer codec is not applied by default; see `ULTRA_CONFIGURATION.md` for the
measured effect on pre-shared-legend encodes.
