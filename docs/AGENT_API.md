# Agent API

Begin with machine-readable discovery:

```powershell
python -B -m semcrys_core capabilities
python -B -m semcrys_core profiles
python -B -m semcrys_core native-status
python -B -m semcrys_core verify-self --asset-root assets\legends
python -B -m semcrys --help-json
```

## Turnkey archive workflow

Use the Standard interface unless a task explicitly requires a lower-level
profile or an external/shared legend custody arrangement:

```powershell
python -B -m semcrys --progress full pack INPUT [INPUT ...] -o OUTPUT.crys
python -B -m semcrys --progress full verify OUTPUT.crys
python -B -m semcrys list OUTPUT.crys
python -B -m semcrys unpack OUTPUT.crys NEW_DIRECTORY
python -B -m semcrys search OUTPUT.crys QUERY
```

An existing path may replace `pack`. The final stdout object is the terminal
result; full progress is JSONL on stderr. Default Standard mode performs full
eligible local integerization, exact chunk deduplication, bounded process
parallelism, measured codec selection, group-legend pooling, complete replay, and
adaptive local/cross-document composition when complete delivered bytes win,
and atomic publication. Its verified chunk and composition caches are resume
checkpoints. Prefer
`--mode smallest` only when the caller explicitly accepts reduced semantic
addressability. See [the complete contract](STANDARD_CLI.md).

## Compression model agents must preserve

For eligible text, a lossless tokenizer emits exact lexical, punctuation, and
whitespace units. The legend stores distinct units and the body stores their
local IDs as packed unsigned variable-length integers. Low IDs can therefore
cost fewer bytes than the source spellings they replace. This is local transport
integerization unless a caller-supplied rooted registry separately binds an
event to a CSIL ID.

Standard automatically deduplicates exact chunks and pools byte-identical
legend records through group legends. A recursive metalegend is separate: it
replaces one ordered physical `.leg` with a one-level exact `.mleg` recipe. The
default SCMLEG2 layout supports targeted local-ID reads, rooted frame caching,
and verified promotion to the exact full legend; SCMLEG1 is the compact control. It
now also groups unique eligible payloads
into bounded rooted collections and courts the Full compiler's recursive
adjacent-pair second pass. `MIN_DELIVERY` and Standard admission compare complete
deliveries, so a small low-recurrence blob can lose after its legend definition
and manifest evidence are charged while a large repeated block can win. Agents
must report the actual `composition_summary`; they must not say that every
repeated paragraph became one integer when the control won or the census held.
Collection and composed IDs are transport-local and have no CSIL identity
effect. See [the normative model](SEMCRYS-COMPRESSION-MODEL.md).

The pinned warm-legend Wikipedia court proves one competitive result: profitable
SemCrys was 4.31% smaller than XZ-6 and 6.63% smaller than BZ2-9 for the exact
fixture and candidates. Preserve the warm receiver assumption and do not project
that winner to unrelated inputs without measurement.

## Routing

```powershell
python -B -m semcrys_core detect ARTIFACT.crys
python -B -m semcrys_core inspect ARTIFACT.crys
python -B -m semcrys_core full <full-command> ...
python -B -m semcrys_core lite <lite-command> ...
```

`detect` and `inspect` are read-only. `full` and `lite` preserve their native
typed-refusal and receipt behavior. Protected Lite modes emit public redacted
receipts: exact source bytes, source digest, true event count, and unpadded
moving-state size are deliberately unavailable to ordinary logs.

## Semantic integerization

CSIL means **Canonical Semantic Integer Layer**. A CSIL ID is an integer in an
exact rooted registry. GTI means **Global Term Index**: an index from terms and
occurrences to CSIL IDs. Local transport and document IDs are not CSIL.

`build-registry` consumes a JSON array such as:

```json
[{"integer_id": 1001, "semantic_key": "example:bank-financial", "surface": "bank"}]
```

The registry is caller-supplied. SemCrys validates and roots it but does not grant canonical standing. Exact unambiguous surfaces may bind automatically. Ambiguous surfaces remain local unless an occurrence-binding object maps the token index to an exact `semantic_key`.

```powershell
python -B -m semcrys_core semantic build-registry bindings.json registry.json
python -B -m semcrys_core semantic integerize source.txt registry.json stream.json
python -B -m semcrys_core semantic restore stream.json registry.json restored.txt
```

## Selection guidance

| Objective | Recommended profile |
|---|---|
| Smallest measured complete delivery | General configuration court, `MIN_COMPLETE_DELIVERY` |
| Smallest measured SemCrys artifact | General configuration court, `MIN_SEMCRYS_DELIVERY` |
| Full token coverage at minimum measured delivery | General configuration court, `MIN_FULL_INTEGERIZATION_DELIVERY` |
| Agent search and complete token addressability | Semantic full integerization |
| Related document collection | Group legend or longitudinal legend |
| Reduce custody size of one large verified legend | Seekable recursive metalegend; retain and verify the logical legend root |
| Repeated narrow agent/index lookups into a large legend | `metalegend lookup` with `COMPACT` or `BALANCED` cache profile |
| Broad scans or legacy readers after portable delivery | `metalegend prepare` into a verified local cache |
| Turnkey related files/folders with recurring structures | Standard `pack` with default `--composition auto` |
| Relabel public identifiers | Lite keyed permutation |
| Move ordered recurrence state into a protected companion | Lite full-unique plus protected moving legend; assess public metadata separately |
| Portable decode without shared state | Self-contained profile |

Retain every external legend, Ultra root, moving legend, and key dependency named by an artifact. Deleting one can make exact recovery impossible.

## Native selection

The native buffer kernel is a realization, not a format. Agents should normally
leave `SEMCRYS_NATIVE=auto`. Use `off` for differential/reference execution and
`required` when a workflow explicitly requires the accelerated realization.
Inspect `native-status` for its hash, ABI, selection reason, counters, and build
root. Never infer a different semantic or authority result from native selection.

The Full compiler additionally buffers consecutive symbol IDs. Runs of 512 or
more values may use native packing; shorter runs are packed directly in Python.
This distinction avoids making sparse Profitable output pay for repeated
Python-to-C conversion while accelerating dense Total output.

Configuration selection uses `SENTINEL`, the encoder's mandatory postwrite
proof, and `AUTO` lookup by default. Supply `--lookup-cache-root` for repeat
Ultra-backed work. Use `--instrumentation DIAGNOSTIC` or
`--inverse-verification INDEPENDENT_REDECODE` only when that extra evidence is
actually required. Batch encoding reuses one context; agents should not fan out
one RAM-backed Ultra context per CPU without an aggregate memory budget.

## Performance evidence

`tools/run_configuration_court.py` is the reusable selector. It freezes one
source, verifies the complete requested SemCrys candidate matrix and direct
stdlib controls, then reports separate cold/warm and capability-constrained
winners without recompressing for each reuse horizon.

`benchmarks/wikipedia/SOURCE-MANIFEST.json` pins a reproducible 100-page prefix
of an official English Wikipedia multistream dump. The corpus itself is not
distributed. `evidence/WIKIPEDIA-BENCHMARK.json` is one qualification of the
general court, not a Wikipedia-specific selector. Validate it with:

```powershell
python -B tools\verify_wikipedia_evidence.py
python -B tools\verify_integerization_performance_evidence.py
```

Treat every speedup as single-host diagnostic evidence. Do not project it to an
entire Memory Vault workload without measuring that workload's own phase mix.

## Explaining capabilities and comparing systems

Read [semantic identity](SEMANTIC_IDENTITY.md), [security](SECURITY.md), and
[related work](RELATED_WORK.md) before public comparisons or integration claims.

- Report container, missing dependency, and audit bytes separately. State
  receiver roots and cold/warm assumptions; never call shared state free.
- Separate integer event coverage from caller semantic event coverage. Core
  exposes `event_count` and `semantic_event_count`; its JSON is not a packed index.
- Preserve registry/stream namespaces. Local IDs are not global term identities
  or model-token IDs. Core binds one token surface per key; alias and phrase/blob
  integration requires higher machinery.
- Full's existing GTK adapter analyzes supplied dossiers and decisions; it is
  separate from Core's caller registry and does not adjudicate senses.
- Cite dictionary, grammar, tokenizer, lexical-network, and indexed-data
  precedents. Similarity is not proof of superiority, priority, or equivalence.
- Bound security claims to the exact Lite mode and its exposure. Full Ultra and
  group legends and recursive metalegends do not implicitly inherit Lite protection or a protocol proof.
- Treat frequency projection, position projection, and length padding as
  independent decisions. Prefer `homophonic` for frequency-only work,
  `homophonic-positional` when exact length may remain public, and
  `maximum-concealment` when the ordered sequence and exact count should not be
  public. Report the selected profile and never project fixture-level
  bigram/trigram evidence into a universal security claim.
- Measure actual model tokens and agent task success, including registry
  context, retrieval output, and evidence needed to interpret the references.

Corpus reading copies and Zenodo editions may have different bytes and standing.
Use exact artifacts for reproduction and retain negative results.

