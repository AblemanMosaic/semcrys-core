# Exact external dependencies in group-legend archives

This document describes group legends. The `semcrys.metalegend-*` strings below
are immutable historical wire-schema identifiers, not the current name of the
cross-artifact operation. Recursive legend-of-a-legend artifacts are documented
separately in [METALEGEND.md](METALEGEND.md).

The existing source glyph and folded-front modes can now participate in a batch:

```text
semcrys group-legend pack new-bundle --source glyph.crys --source folded.crys --legend union.leg --glyph alphabet.gly --fold-front front.leg --layout AUTO
semcrys group-legend unpack new-bundle/archive.crys restored
```

Repeat `--glyph` or `--fold-front` for distinct required roots. Each is matched
to its explicit type and exact source configuration root, never by filename or
similarity. Missing, wrong, duplicate or unused dependencies refuse publication.
If an external group pool was selected, unpack also needs `--meta meta.leg`.

Auxiliaries are retained once as exact bytes in the archive inventory. They are
not pooled as token records, converted to CSIL identities, or normalized. The
restored glyph registry uses `.gly`; the folded-front artifact uses `.leg`.
The source container bytes and legend stack are restored before each actual
source decoder verifies plaintext bytes with its own exact dependencies.

The typed successor is `semcrys.metalegend-instance.v0.2` with an auxiliary
contract root and `semcrys.restored-artifacts.v0.2`. Whole-bundle LZMA2/XZ uses
`semcrys.metalegend-bundle-instance.v0.2` and must contain the matching v0.2 inner
archive. Without auxiliaries, v0.1 schemas, layouts and bytes are unchanged.
Older readers must refuse these new critical configurations, not guess.

Existing META/VERBATIM, BODY_ONLY/WHOLE_BUNDLE, pool placement, measured selection
and cold/warm pool accounting apply. Auxiliary acquisition is inside the archive;
this feature does not silently omit it based on a receiver declaration. Pre-shared
pool reuse remains explicit and is not receiver authentication. No private legend
or auxiliary is discovered or sent without being explicitly supplied to pack.

At most 64 distinct auxiliaries and 64 MiB of aggregate auxiliary bytes are
accepted, under the same logical scratch/publication budget and archive output
limits. This is not a maximum-scale RAM or power-loss certificate. Nested archives,
all-profile grammatical compositions and delegated encryption remain separate.
No encryption, confidentiality, canonical mutation, admission or release is claimed.
