# Standard SemCrys CLI

`semcrys` is the turnkey file and folder interface. It is offline, uses only the
packaged runtime, and never modifies an input. It is a reversible archive and
integerization tool, not an encryption claim.

## Fast path

```powershell
semcrys PATH
semcrys PATH PATH -o NAME.crys
semcrys list NAME.crys
semcrys verify NAME.crys
semcrys unpack NAME.crys NEW_DIRECTORY
```

An existing path in command position is equivalent to `semcrys pack PATH`.
The default output is a sibling `.crys` file; multiple inputs use a rooted bundle
name in the current directory. Existing destinations are never replaced.

## Standard policy

The default `semantic` mode performs this ordered workflow:

1. Inventory regular files and directories; refuse symlinks and reparse points.
2. Hash each logical file and bind path, size, mode, and nanosecond mtime.
3. Split large files into bounded chunks without changing logical file identity.
4. Reuse identical chunks by SHA-256 and byte length.
5. Fully integerize each eligible UTF-8 chunk through the self-contained token profile.
6. Measure every packaged outer-codec candidate and retain the smallest exact result.
7. Pool groups of selected containers through the group-legend optimizer as the control.
8. Census recurring events across bounded groups of unique eligible payloads.
9. When the upper bound can repay invocation, realize a shared collection stream
   and recursive composition candidates, then compare complete segment plus
   manifest bytes against the control. The control wins ties.
10. Optionally build semantic streams and a candidate GTI from the original logical payloads.
11. Bind a canonical manifest, replay every logical file, and publish atomically.

`semcrys explain-default` emits the rooted policy. The winner is exact only among
the declared candidate set; it is not a global compression-optimality claim.

The text body uses packed unsigned variable-length local IDs rather than
repeating every source spelling. Standard also deduplicates exact chunks and
pools equal legend records. Adaptive phrase/event composition is now part of the
Standard operation sequence for `semantic` and `portable` input. Its census is
only a scheduling predictor; `MIN_DELIVERY` and final segment admission charge
the new legend, body, container, manifest representation, and declared
dependencies rather than admitting every discoverable sequence.

`--composition auto` is the recommended default. `--composition off` preserves
the individual-container/group-legend control as an advanced ablation. Composed
transport IDs do not acquire CSIL or other semantic identity.

## Modes

| Mode | Contract |
|---|---|
| `semantic` | Recommended. Full eligible local integerization, self-contained replay, measured outer codec. |
| `portable` | Compatibility alias for the self-contained semantic policy. |
| `smallest` | Measures profitable token and raw-byte families; raw may win. This can reduce indexability. |

Local legend IDs and document-local semantic IDs are not CSIL. **CSIL is the
Canonical Semantic Integer Layer**, and a CSIL ID is an integer in an exact
registry. When `--registry` is supplied, Standard can embed a candidate **Global
Term Index (GTI)** mapping the caller's CSIL integers, keys, surfaces, and exact
occurrences. The caller registry has no canonical identity effect by compilation.

## Resume and parallelism

The CLI defaults to a verified per-user cache under local application data.
Every cached chunk container is inverse-decoded and checked against its source
root before reuse. Completed cache entries survive interruption; rerunning the
same command resumes at the next unknown chunk. Expensive collection-composition
candidates are separately keyed by their ordered member roots, compiler policy,
and codec set; they too are inverse-decoded before reuse. Use `--cache-root PATH` to move
custody or `--no-cache` to disable it. An unavailable cache degrades to an
uncached run and is reported as `cache_write_failures`; it does not invalidate a
verified archive.

`--workers 0` selects up to four process workers. Results are reordered by the
deterministic source/chunk inventory before manifests are built. `--chunk-bytes`
accepts 1 through 67,108,864 bytes; the default is 33,554,432.

## Progress and automation

Progress is stderr; the final rooted result is one JSON object on stdout.

| Option | Audience |
|---|---|
| `--progress human` | Default concise phase and count lines. |
| `--progress full` | Complete JSONL events for agents and observability. |
| `--progress summary` | Compact JSONL stages. |
| `--progress quiet` | No progress output. |

`semcrys --help-json` emits the installed parser-derived capability surface.
`semcrys pack ... --dry-run` inventories and emits a no-write plan. Exit status
is `0` for PASS, `1` for a typed hold or I/O/value refusal, `2` for invalid CLI
syntax, and `130` for interruption.

Publication is atomic: before the final rename, the destination is absent; after
it, the destination has passed complete inverse verification. Cache checkpoints
are not publication and may remain after interruption.

## Custody boundaries

- Output and cache locations inside an input directory are refused.
- Existing outputs, extraction directories, symlinks, reparse points, unsafe
  archive paths, unknown members, and reconstruction drift fail closed.
- Extraction uses a private stage and publishes only after exact replay.
- `--only PATH` selectively restores exact named manifest paths.
- Standard archives are self-contained and declare no confidentiality. Secure
  legend profiles are separate advanced capabilities with separate key custody.

## Search boundary

`semcrys search ARCHIVE QUERY` performs exact lookup by CSIL integer string,
semantic key, or surface in the embedded candidate GTI. Results include file,
chunk, and token positions. Alias traversal, phrase/blob sense inference,
authority adjudication, ranking, and graph retrieval remain higher integrations.

## Composition observability

Full progress includes `STANDARD_COMPOSITION_CENSUS`, second-pass arm events,
and `STANDARD_SEGMENT_SELECTED`. The terminal result and inspection surface
report groups considered, groups selected, cross-document selections, held or
unprofitable groups, verified composition-cache hits, and net complete-segment
bytes saved. These fields are non-overlapping admission measurements; they are
not added to exact-chunk or group-legend savings as though the layers were
independent.

See [the normative compression model](SEMCRYS-COMPRESSION-MODEL.md) and
[the architecture decision](ADR-0001-STANDARD-ADAPTIVE-COMPOSITION.md).

