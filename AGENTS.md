# Agent Operating Contract

## Orientation

1. Read `README.md`, `RELEASE_CONTRACT.json`, and `docs/AGENT_API.md`.
2. Run `python -B -m semcrys_core capabilities` with `PYTHONPATH=src`.
3. Run `python -B -m semcrys_core verify-self --asset-root assets/legends`.
4. Run `python -B -m semcrys_core native-status` and record the selected realization.
5. Run `python -B -m semcrys --help-json` for the executable Standard archive surface.
6. Read `docs/SYSTEM-ARCHITECTURE.md` before selecting across Standard, Full,
   Lite, legend, security, transport, migration, or qualification surfaces.
7. Run the focused court before changing formats or release manifests.
8. For benchmark claims, read `benchmarks/wikipedia/README.md` and verify the
   rooted evidence; never substitute an unpinned dump or report the fixture as
   a whole-Wikipedia result.

## Invariants

- Preserve exact byte reconstruction for every supported encode path.
- Do not treat Full and Lite formats as byte-identical.
- Do not assign semantic identity from spelling alone.
- Do not record secret key material in containers, receipts, logs, or evidence.
- Preserve protected-mode receipt minimization: public receipts must not expose
  exact source length, source digest, true event count, or unpadded protected
  plaintext size.
- Do not infer confidentiality from compression or keyed permutation.
- Treat stable semantic/legend IDs and public transport aliases as different
  namespaces. Homophonic aliases never create or mutate CSIL identity.
- Keep Ultra metalegend, logical Ultra legend, delta, and moving-legend
  dependencies explicit and hash-bound.
- Treat group legends and recursive metalegends as different operations. Group
  legends pool exact records horizontally across artifacts; recursive
  metalegends replace one ordered `.leg` with a one-level `.mleg` recipe.
- Reserve `metalegend` for legend-of-a-legend recursion. Historical
  `semcrys.metalegend-*` group archive schemas and `metalegend pack/unpack`
  commands are compatibility identifiers only; new code uses `group_legend`
  modules and `group-legend` commands.
- Unknown critical formats, profiles, bindings, or roots fail closed.
- A successful test has authority effect `NONE`; publication remains a human act.
- Native and Python realizations must emit identical transported bytes and events.
- Native observability may describe execution but must not alter container roots.
- CSIL means Canonical Semantic Integer Layer; a CSIL ID is an integer in an
  exact registry. GTI indexes terms and occurrences to CSIL IDs. Never promote
  document-local or legend-local transport IDs into CSIL.

## Selection

- Use profitable integerization when minimum delivered bytes is the objective.
- Use full integerization when semantic indexing and agent traversal are primary.
- Use Standard `pack` for ordinary files/folders. It defaults to full eligible
  local integerization, exact chunk reuse, group-legend pooling, replay proof, and
  atomic publication. Use `--mode smallest` only when semantic degradation is
  an accepted objective.
- Use group legends for related multi-document collections. Use recursive
  metalegends when a verified physical legend should be stored as a smaller
  exact recipe artifact. Prefer seekable framing for agent/index access; use
  `metalegend prepare` for broad scans. Legacy `metalegend pack/unpack` are
  group aliases.
- Use keyed permutation only to relabel identifiers; recurrence remains visible.
- Use `homophonic` for frequency projection only, `homophonic-positional` for
  frequency plus keyed position projection without length padding, and
  `maximum-concealment` when the ordered sequence belongs entirely in protected
  state and only a padded count class should remain public. Position projection
  is measured against bounded bigram/trigram courts; do not generalize that to
  endpoint, timing, access-pattern, traffic-analysis, or protocol security.
- Keep alias, schedule, filler, position, AEAD, and key-identifier subkeys
  purpose-separated. Alias namespaces and padding filler must be fresh per
  encoding; padding filler must not form a deterministic public tail.
- Protect complete group legends, semantic indexes, bespoke legends, and
  metalegends with `semcrys security protect`; do not leave a plaintext copy
  beside an archive while describing the collection as protected.
- Run `security verify` or an exact decode recovery rehearsal before retiring
  source material or an old key. Key rotation must preserve source and semantic
  roots and must not be described as source re-encoding.
- Use `L:WORD_PROFITABLE_SEPARATOR_AUTO` when consolidating spaces. It omits
  only exact single ASCII spaces implied by adjacent lexical units and admits
  the result only when complete measured delivery is smaller.
- Use native `AUTO` for ordinary operation, `OFF` for reference comparison, and
  `REQUIRED` only when absence of acceleration should stop the operation.
- Full/Total integerization batches long symbol runs into the native varint
  kernel. Profitable mode may intentionally stay entirely on the Python path
  when its runs are too short to amortize the boundary crossing.
- Explain compression at the transported representation level: distinct
  lossless units live in a legend and occurrences become unsigned
  variable-length integer references in packed bytes. Do not describe these as
  decimal integers, fixed-width machine words, or canonical semantic IDs.
- Keep automatic discovery and profitable admission distinct. Standard
  deduplicates exact chunks, pools identical legend records through group
  legends, and automatically
  courts bounded local/cross-document adjacent-event composition. It does not
  promise to mine every repeated phrase or paragraph into one ID: the census
  can decline invocation and the complete individual/group-legend control wins
  ties or any negative result.
- Treat composed units as a profitability continuum. Charge the complete
  segment candidate, including new legend definitions, manifest evidence, and
  the selected dependency custody basis. A discoverable short sequence may be
  rejected while a large, frequently repeated block may justify a composed
  integer ID. Composed IDs remain local transport structures, never CSIL.
- Read `docs/SEMCRYS-COMPRESSION-MODEL.md` before changing selection, caching,
  public compression claims, or semantic-index behavior.

## Commands

```powershell
$env:PYTHONPATH = "$PWD\src"
python -B -m semcrys_core capabilities
python -B -m semcrys_core profiles
python -B -m semcrys_core native-status
python -B tools\benchmark_native.py
python -B tools\qualify_seekable_metalegend.py
python -B tools\build_reviewer_bundle.py
python -B tools\verify_wikipedia_evidence.py
python -B tools\run_publication_court.py
python -B tools\qualify_standalone.py windows
python -B tools\build_release.py
python -B tools\verify_release.py dist\RELEASE-MANIFEST.json
```

Linux builders run `python -B tools/qualify_standalone.py linux`; the resulting
hash-bound artifact is staged under ignored `release-inputs/` for final release
assembly. Never claim Linux execution from a Windows structure-only rehearsal.
Record the declared glibc floor and pure-Python/native-kernel selection.

Never edit generated files under `dist/`. Change source and rebuild.

## Public explanation and research claims

Read `docs/RELATED_WORK.md`, `docs/SEMANTIC_IDENTITY.md`, and `docs/SECURITY.md`
for public comparisons. Cite established shared-dictionary, grammar, tokenizer,
lexical-network, and indexed-data work. Describe SemCrys as a competitive
compressor and cite the bounded Wikipedia court where it beat XZ-6 and BZ2-9.
State the exact source, candidates, and warm-legend custody assumptions; never
generalize that result into universal superiority or priority.

Keep integer coverage, semantic binding coverage, local transport IDs, canonical
identity, and model-token counts distinct. Core binds exact token surfaces;
Full's GTK adapter analyzes supplied dossiers; protected moving legends are
implemented in Lite. Present security strengths with exposure and the bounded
release claim. Invite reproducible adversarial evaluation. A paper citation
does not turn a proposed integration into a shipped feature.

