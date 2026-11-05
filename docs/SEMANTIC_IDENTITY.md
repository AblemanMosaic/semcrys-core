# Semantic identity and indexing

This guide distinguishes executable v0.1 surfaces from the broader research
architecture. It is a source-grounded integration explanation, not a grant of
canonical identity or an empirical claim about improved reasoning.

## Three different identities

| Identity | Scope | Use |
|---|---|---|
| Compiler transport ID | Exact ordered legend stack and encoding profile | Decode units and reusable forms. |
| Caller-assigned semantic integer | Exact Core registry root and supplied key | Refer to a caller-declared binding. |
| Document-local integer | Exact stream and its local legend | Represent unbound tokens without loss. |

Equal integers in unrelated namespaces do not establish identity. Index local
events by stream root, namespace, and ID; caller events by registry root,
namespace, and ID. Reconciliation across registry versions needs explicit
external identity mappings. Model-token IDs are a separate namespace.

## What the Core helper executes

`src/semcrys_core/semantic.py` validates a caller registry, tokenizes strict UTF-8
through the Lite tokenizer, and emits a rooted stream. Each event is
`[namespace, integer_id]`: `0` is caller-assigned semantic; `1` is document-local.
Whitespace and punctuation also remain reconstructible.

Each registry row has a unique positive integer, unique semantic key, and one
exact token surface. A surface with one candidate may bind automatically.
Competing candidates remain local until the caller supplies an occurrence
binding from token index to key. A requested binding must match that token's
exact surface or the helper refuses it.

For `bank`, separate financial-bank and river-bank keys can have different
integers and the same surface. Occurrence decisions select the intended key.
The helper checks reconstruction and registry consistency; semantic correctness
depends on the supplied registry and decisions. A registry omitting a competing
sense can remain semantically incomplete despite a valid hash.

The current schema permits one surface per unique key/ID. It does not directly
encode many aliases to one key, resolve multi-token phrases, assign code AST
roles, or infer senses for binary blobs. Those need higher registry and
span/structure adapters. Full assemblies supply reusable forms separately;
they do not infer ASTs or semantic roles.

The JSON semantic stream is an inspectable integration artifact. It is not
automatically a packed Full/Lite `.crys` body or a size-optimal search index.
Applications select its storage and index realization explicitly.

## Separate coverage denominators

The helper reports `event_count`, `semantic_event_count`,
`explicit_occurrence_binding_count`, and `full_integer_coverage`.

- Integer event coverage is complete when every tokenizer event has an ID.
- Caller semantic event coverage is `semantic_event_count / event_count` for a
  nonempty stream; an empty stream should report N/A.
- Local fallback covers the remaining events. This is exact representation,
  not adjudicated meaning.
- Word-only or unique-type coverage needs its own tokenizer/filter/denominator;
  the all-event ratio includes whitespace and punctuation.

Full's `TOTAL`/`PROFITABLE` policies have a different contract. Its documented
token-unit limit is 4096 bytes, above which units remain literal. Report actual
events and exposure rather than equating "full" with universal semantic coverage.

## Existing GTK analysis

`src/semcrys/gtk_analysis.py` is a separate read-only adapter. It consumes exact
candidate bound-term dossiers and decisions, distinguishes accepted decisions
from proposals, and can hold ambiguous occurrences. Occurrence overrides bind
the exact source and tokenizer. Lexical coverage, sense resolution, and actual
legend exposure are separate reported facts.

The adapter does not mutate a registry or repair source text. Its vocabulary
export discloses local legend values and requires an acknowledgement. See
[the adapter contract](GTK_ANALYSIS.md).

## CSIL, GTI, and GTK in the wider architecture

**CSIL means Canonical Semantic Integer Layer.** A CSIL ID is an integer assigned
by an exact canonical registry. In transport and index records, pair the integer
with the registry root or another governed registry-version identity so that an
equal number from another registry cannot be mistaken for the same concept.

**GTI means Global Term Index.** It is an index over CSIL identities, not a second
identity namespace. A mature GTI can map spellings, aliases, typed structures,
occurrences, contexts, and provenance to CSIL IDs. The Standard v0.1 candidate
implements only exact CSIL integer, semantic-key, surface, and occurrence lookup
for a caller-supplied rooted registry. It does not infer aliases or adjudicate
meaning.

**GTK means Global Term Key.** In the wider architecture it identifies the
governed bound-term view: the disambiguated word, phrase, blob, proper noun, or
many-named concept that can carry renderings and competing bindings. Definitions
and the wider typed relational manifold remain linked semantic structures.

The current [GTK reading copy](https://github.com/AblemanMosaic/ableman-corpus/tree/main/papers/current/AC-0091-global-term-key-constitutional-lexical-identity-thro)
contains older CSIL wording and an unresolved relationship between a
five-component GTK catalog and a layered formulation. This guide uses the
author-supplied corrected terminology above and does not claim to mutate or
adjudicate that upstream corpus record.
The repository's `SEMANTIC_USE_CONTRACT.json` records source identities and
mixed standing without promoting generated explanations to canonical status.

An integration can connect an occurrence to a vetted binding, then follow its
aliases and typed relations to retrieve passages under other appropriate names.
The codec preserves representation; the registry supplies identity; the
application supplies disambiguation, access control, index maintenance, and
retrieval policy. This is the route from lexical indexing to semantic retrieval.

## Agent applications and evaluation

Useful targets include exact occurrence retrieval, sense-specific search,
cross-document joins, lineage comparison, and source-bound snippets. Compare
these with grep/ripgrep, an ordinary inverted index, and graph/embedding
retrieval where appropriate. The codec alone does not execute these workflows.

Measure precision/recall on ambiguous queries, index/legend bytes, build/update
latency, and agent task success. Count actual model input tokens including
registry context and retrieved tool output. Smaller disk representation or
integers printed as text do not demonstrate model-token savings.
