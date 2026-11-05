# Architecture

SemCrys Core is one system with several internal realizations.

This document is the compact implementation map. Read
[SemCrys system architecture](SYSTEM-ARCHITECTURE.md) for the complete public
inventory of all eighteen subsystems, their end-to-end flow, boundaries,
commands, formats, and specialized references.

1. **Full compiler** provides streaming `.crys`, binary legends, integer projections, folds, assemblies, configuration selection, group legends, recursive metalegends, recovery, and publication controls.
2. **Lite reference codec** provides a compact implementation, whole-word and byte profiles, keyed permutation, bounded aliases, and protected moving legends.
3. **Core facade** detects Full or Lite artifacts by signature, reports the combined capability manifold, verifies release-bound assets, and routes operations without rewriting either ABI.
4. **Semantic integerization** maps explicitly assigned semantic keys to stable integers and gives every remaining token a deterministic local integer.
5. **Ultra** is a release-bound, separately hashed data asset used by preshared profiles. It is part of the release but not Python source code.
6. **Native buffer kernel** optionally accelerates varint packing, varint
   unpacking, and assembly folding through a versioned C ABI. Python owns policy,
   validation fallback, metrics, custody, and all transported format decisions.
7. **Qualification harnesses** bind public-corpus identities and local evidence
   without putting network access or third-party corpus bytes in the runtime.

Full and Lite are complementary realizations under one release contract. Migration between them is decode-and-reencode over verified source bytes, never suffix renaming or implicit reinterpretation.

Application integrations such as Archive Composer and Memory Vault sit outside the codec boundary. They may select configurations, store receipts, and combine SemCrys with other deduplication layers, but do not redefine SemCrys formats.

Native acceleration is deliberately below the constitutional and semantic
layers. Selection changes execution cost, never artifact meaning or identity.
The Full encoder accumulates bounded symbol runs and crosses the native ABI only
when the run is large enough to justify conversion. Recovery remains Python in
ABI 2; canonical packed-event parsing is native-qualified while legend lookup
remains the next measured optimization boundary.

