# Related systems, evidence, and research opportunities

Research reviewed: 2026-11-02. This is a primary-source comparison and an
implementation-grounded synthesis. It is not an exhaustive literature survey,
priority adjudication, or comparative benchmark. Sources are cited beside their
claims; no external implementation was added as a runtime dependency.

## Shared and trained dictionaries

[Zstandard's reference documentation](https://github.com/meta/zstd/blob/dev/README.md#the-case-for-small-data-compression)
describes dictionary training on related samples and reuse during compression
and decompression. It particularly helps small inputs. Shared training and
amortized state are established precedents for part of Ultra's rationale.
SemCrys makes exact legend stacks, deltas, and missing receiver state explicit.
Those are architectural distinctions to evaluate, not proof that its dictionary
learning or compression ratio is better.

[Brotli's format, RFC 7932 section 8](https://www.rfc-editor.org/rfc/rfc7932.html#section-8),
specifies a static dictionary with transformations. It is a counterexample to
any claim that established compressors only learn inside the current file.
SemCrys exposes additional legend families and exact record pooling. Compare
complete delivery, not a shared SemCrys stream against an unfairly untrained
competitor. Zstandard/Brotli were researched but not run in the shipped court;
their SemCrys adapters are not implied by this discussion.

## Grammars and reusable forms

N. Jesper Larsson and Alistair Moffat's
[Offline Dictionary-Based Compression (1999)](https://avadeaux.net/larsson.dogma.net/dcc99.pdf)
introduces Re-Pair's repeated-pair grammar construction and explicit dictionary
encoding. Recursive reusable structure predates SemCrys. SemCrys's supplied
assemblies, local namespaces, exact reconstruction recipes, and cross-artifact
record pools provide the relevant comparison surface. A SemCrys group legend
pools exact stored records; it does not automatically infer semantic equivalence
or implement the same algorithm as Re-Pair.

SemCrys recursive metalegends are a different comparison surface: block-local
front recipes over one ordered legend, followed by a conventional outer codec.
Front coding and delta coding are established techniques; the release claim is
the exact format, custody, admission, and measured Ultra realization, not
priority for prefix compression.

## Tokenization and reversibility

Taku Kudo and John Richardson's
[SentencePiece (2018)](https://aclanthology.org/D18-2012/)
learns reusable subword tokenization directly from raw sentences. Its
[implementation](https://github.com/google/sentencepiece) provides token IDs and
detokenization, so integer addressability and reversible tokenization alone
cannot establish SemCrys's novelty.

SentencePiece's [normalization documentation](https://github.com/google/sentencepiece/blob/master/doc/normalization.md)
also provides an identity option alongside normalization defaults. SemCrys's
archive-byte reconstruction contract is therefore a configuration-sensitive
comparison, not evidence that other tokenizers inherently cannot preserve text.
Sense binding and custody are additional SemCrys interfaces. A disk compression
result does not demonstrate fewer input tokens in an existing language model.

## Compact, queryable data and column dictionaries

[HDT's specification](https://www.w3.org/submissions/HDT/)
and [technical overview](https://www.rdfhdt.org/technical-specification/)
describe dictionary IDs and compressed RDF graph structure with indexed access.
HDT is a particularly relevant precedent for compact representation that remains
useful for search. SemCrys handles general artifact representations and offers
semantic-binding interfaces, but Core's JSON stream is not an equivalent
implemented compressed graph query engine. The W3C document is a Member
Submission, not a W3C Recommendation or endorsement.

[Apache Arrow](https://arrow.apache.org/docs/format/Columnar.html#dictionary-encoded-layout)
defines dictionary arrays, while [Parquet](https://parquet.apache.org/docs/file-format/data-pages/encodings/#dictionary-encoding-plain_dictionary--2-and-rle_dictionary--8)
encodes column values through dictionary indices and permits fallback when a
dictionary grows too large. These are strong comparisons for compact index
storage and adaptive profitability. Their scopes are typed arrays/columns;
SemCrys's relevant scope is artifact reconstruction and shared legend custody.
No format compatibility or performance advantage is established here.

## Sense inventories and semantic networks

[Princeton WordNet](https://wordnet.princeton.edu/)
already distinguishes word senses, groups synonyms, and links concepts through
typed relations. Roberto Navigli and Simone Paolo Ponzetto's
[BabelNet (2010)](https://aclanthology.org/P10-1023/)
connects multilingual concept lexicalizations using lexicographic and
encyclopedic resources. Sense identity, synonyms, and multilingual semantic
graphs therefore have substantial prior art.

The proposed CSIL/GTK addition concerns governed binding, provenance, standing,
ambiguity/refusal, and revision across representation layers. In this release,
Core accepts caller bindings and Full analyzes supplied GTK dossiers. Neither
imports WordNet/BabelNet nor automatically performs their semantic tasks. Their
resources are useful prospective baselines, subject to their licenses.

See [semantic identity](SEMANTIC_IDENTITY.md) for the exact v0.1 schema and
the layered corpus definition, including its unresolved schema relationship.

## Protection and compression side channels

The [cryptography AEAD API](https://cryptography.io/en/latest/hazmat/primitives/aead/)
provides the AES-GCM implementation used for moving legends. The security
primitive is external established work; SemCrys's contribution is its custody
and reconstruction-state arrangement. Static keyed permutation retains
equality/frequency structure. Full-unique moves the ordered sequence into an
encrypted companion; the size and exposure of that companion still matter.

[RFC 7457 section 2.6](https://www.rfc-editor.org/rfc/rfc7457.html#section-2.6)
documents compression-related inference in other protocols. It motivates tests
where an attacker can influence inputs or observe lengths, without establishing
a SemCrys exploit by analogy. [SECURITY.md](SECURITY.md) records the implemented
strengths, threat boundaries, and private reporting route.

## What is distinctive enough to investigate?

The strongest present characterization is a particular composition:

1. reversible artifact/legend representations with explicit root-bound dependencies;
2. local, Ultra/shared, domain/delta, assembly, and cross-artifact record pooling;
3. capability-constrained selection with complete cold/warm cost accounting;
4. integer occurrence identity plus explicit external semantic binding;
5. optional protected custody in the supported Lite profiles.

The demonstrated value includes exact reconstruction and measured candidate
selection. The possibility of a common representation serving storage, indexing,
and agents is the larger opportunity. Historical priority, general compression
superiority, better reasoning, and complete protocol security require further
evidence. Listing mechanisms together does not imply all their combinations
are implemented or qualified.

## Evaluation and collaboration agenda

| Question | Experiment and comparison | Evidence needed |
|---|---|---|
| Where does Ultra generalize? | Held-out prose, source, structured data, logs, and unlike domains; XZ/BZ2 plus trained Zstandard/Brotli controls when available. | Separate training/test sets, exact roots, cold/warm costs, size/time/memory distributions, and losing cases. |
| Do group legends help collections? | Related and unrelated document families; compare shared-base only, verbatim bundles, and pooled records under the same codecs. | Exact originals restored; count pool, maps, dependencies, headers, and audit bytes. |
| When does legend recursion help? | Compare raw `.leg`, conventional whole-file compression, and versioned recursive recipes across legend families. | Exact inverse, complete bytes, build/restore time, memory, random-access cost, and losing cases. |
| Is full integerization worth its cost? | Compare profitable/full representations at equal source identity and custody. | Report byte/time premium and actual integer coverage under each profile's limits. |
| Does semantic binding improve retrieval? | Ambiguous queries against lexical search, inverted indexes, graph and embedding retrieval. | Labeled sense decisions, precision/recall, index/update costs, source-bound snippets, and mistakes. |
| Does it help an agent? | Same tasks/models/tool budget with and without indexed references. | Actual tokenizer counts including registry/tool output, latency, citations, and task success. |
| How strong is protected custody? | Known/chosen-plaintext, linkage, oracle and metadata tests, malformed input and resource attacks. | Declared attacker knowledge, mode-specific observations, reproducible attacks, and documented residual leakage. |
| Can others reproduce it? | Fresh supported-platform runs and native/reference comparisons. | Exact asset roots, supported skips/refusals, byte invariance, and independent terminal results. |

Retain negative results. A zero-benefit collection or a successful inference
attack usefully narrows a claim. Proposed Ultra promotions need independent
cross-corpus recurrence/benefit evidence; one Wikipedia delta cannot establish
universal utility. Contributions may add optional evaluation dependencies without
changing the standard-library base runtime.

## Internal evidence and source custody

The README's numerical claims come from `evidence/WIKIPEDIA-BENCHMARK.json`,
`docs/WIKIPEDIA_OPTIMIZATION.md`, and the rooted phase-separated performance
records. Ultra profitable warm delivery is 671,046 bytes; full is 724,782 bytes;
fresh XZ-6 is 701,272 and BZ2-9 is 718,692. Cold accounting charges the restored
54,102,082-byte legend; the replacement transports a 23,632,901-byte seekable
`.mleg`. The incumbent 22,939,848-byte `.crys` is retained as a control and is
smaller and faster for complete restoration. The seekable form instead provides
targeted lookup, independently verified frames, bounded materialization, and
cache promotion. Different accounting representations must be declared, not
silently interchanged.

The cited corpus reading copies were inspected from public-corpus checkout
`013822bbd38b2caf2795d7d25d1fed7bc7f2ff72`. Their accession, exact Markdown
hashes, publication links, and standing are captured in `RESEARCH_SOURCES.json`.
The five Zenodo DOI links are recorded in that corpus's metadata. Direct DOI and
human-site fetches were unavailable through the research browser during this
pass; live resolver availability is not claimed. Reading copies and Zenodo
editions are not asserted to be byte-identical.

Corpus concept bindings retain their source-declared or reviewed-provisional
standing. The comparison prose is a new synthesis. References establish
provenance and comparison surfaces, not external endorsement, semantic admission,
cryptographic certification, or permission to modify the cited sources.
