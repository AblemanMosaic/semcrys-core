# GTK analysis adapter — candidate contract

Documentation reviewed: 2026-08-31. This is a candidate review date, not a
public release date.

The GTK adapter is read-only. It reports lexical coverage, bound-term sense
resolution, and actual SemCrys legend exposure as three independent facts. It
never changes source bytes, a dossier, canonical CSIL/GTK, a legend, or shared
relationship state.

## Identity boundary

- A GTK bound term is a disambiguated sense identified by the dossier's
  `identity.bound_term_csil` and exact `dossier_root`.
- A SemCrys transport ID is local to an ordered, exact-root legend stack. It is
  not canonical CSIL and is not a sense identity.
- A model-token ID is outside this adapter. Exporting a vocabulary does not
  claim a model tokenizer, vocabulary fit, or token-count saving.

The adapter accepts the candidate
`hyperpedia.gtk-bound-term-dossier.v0.1.candidate` format and binds the exact
schema-contract file hash. Candidate provenance remains candidate provenance.
`PROPOSED` decisions never satisfy a lookup. `REVIEWED` and
`CANDIDATE_BACKED` decisions bind the selected bound-term CSIL and dossier root.
The dossier-set root also binds the exact schema-contract hash.

## Analysis

```text
gtk capabilities
gtk analyze input.txt --schema-contract GTK_SCHEMA_CONTRACT.json \
  --dossier bank-river.json --dossier bank-finance.json \
  --decisions decisions.json --pathway GCNL --sense-binding SENSE_KEYED \
  --sense-unresolved HOLD --force-csil FLAG --legend union.leg
```

`NL` requires `sense-binding=NONE`. `GCNL` requires `SENSE_KEYED`. A
polysemous surface without an accepted decision refuses under `HOLD`. The
explicit legacy-compatible `SPINE` option chooses the lowest candidate CSIL but
records `SPINE_GUESS`; it is not promoted to resolved evidence. A per-type
decision can be overridden by a source-bound `unit_index` decision.

`force-csil=OFF` makes no coverage hold, `FLAG` exposes unknown lexical units,
and `HOLD` refuses them. None of these modes corrects text. Normalization remains
a proposal-only, pre-encoding workflow and is not packaged in this build.

When exact legends are supplied, `wire_state` is calculated from their actual
expanded values. An unknown GTK term is not automatically a literal, and a
known GTK term is not automatically encoded: semantic coverage and wire
exposure are separate ledgers. The report retains source, schema, dossier-set,
decision and legend roots, bounded per-unit annotations, and a bounded
clarification queue with only dossier-backed candidates/glosses.

Type-default decisions may carry `source_sha256: null` and can therefore be
reused against another source while retaining their dossier-set root.
Occurrence overrides always require the exact source hash and declare
`UNICODE_CATEGORY_LOSSLESS_V1`; changing either source or tokenizer refuses.
Analysis runs over a bounded source snapshot and uses the same ephemeral,
disk-backed verified legend context and parent-chain checks as encoding. It does
not materialize an Ultra legend as a Python dictionary.

## Vocabulary export

```text
gtk vocabulary vocab.jsonl --legend union.leg --acknowledge-legend-disclosure
gtk verify-vocabulary vocab.jsonl --legend union.leg
```

The JSONL vocabulary maps ordered-stack local IDs to exact unit bytes and is
verified against every supplied legend value before publication. Export is
refused without the disclosure acknowledgement because publishing it reveals
those legend values. The file is an external-tokenizer interface, not a CSIL
table and not a security mechanism.

All outputs remain `CANDIDATE_ONLY` with `security_claim: NONE`. No LLM,
training, WordNet, automatic correction, canonical mutation, admission,
authority, or release is part of this adapter.
