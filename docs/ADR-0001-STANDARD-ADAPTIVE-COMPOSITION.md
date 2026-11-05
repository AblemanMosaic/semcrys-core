# ADR-0001: Adaptive composition in Standard

Status: accepted for the v0.1 publication candidate.

## Decision

Standard enables bounded local and cross-document event composition by default
for full-integerization modes. It does not feed completed `.crys` bytes back
through the deduplicator. Exact chunk deduplication runs first; composition then
operates over canonical logical UTF-8 bytes and their lossless event stream.

The existing individual-container plus group-legend realization remains the
control. A shared collection candidate is published only when its complete
segment bytes plus manifest representation are strictly smaller. Original wins
ties. File boundaries are offsets over a rooted concatenation and remain exact.

## Why

This exposes recurring structures larger than one token, including recurrence
across related files, while retaining the established exact replay, custody,
semantic-index, and conventional-codec controls. It also preserves the central
economic rule: discoverability does not imply admission.

## Consequences

- Standard v0.3 readers understand `INTEGER_COLLECTION` and
  `COMPOSED_COLLECTION` segments and continue to read v0.2 archives.
- `--composition off` provides an explicit ablation.
- A fixed-size collision-safe census avoids obviously fruitless courts. The
  exact realized-byte comparison still decides publication.
- Bounded streams use deterministic in-memory fractionation; larger streams
  retain the disk-backed realization. Transport bytes and selection semantics
  are unchanged by that realization choice.
- Composition candidates can be reused only from an inverse-verified,
  hash-bound cache entry.
- Composition IDs have no CSIL, GTI, GTK, bound-term, authority, or security
  effect.

