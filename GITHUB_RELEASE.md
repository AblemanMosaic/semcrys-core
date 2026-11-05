# GitHub Release v0.1.0

## Repository presentation

- **Repository slug:** `semcrys-core`
- **GitHub About description:** Competitive lossless compression and full
  semantic integerization with reusable legends, adaptive cross-document
  composition, exact replay, and offline Windows/Linux CLIs.
- **Release title:** `SemCrys Core v0.1.0`
- **Tag:** `v0.1.0`

Tag the exact publication commit as `v0.1.0` and attach the files emitted under
`dist/`. The primary offline asset is
`semcrys-core-0.1.0-offline-bundle.zip`; it carries the source archive,
zipapp, wheels, release manifest, and exact `ULTRA_FAMILY.mleg` asset.

Also attach `semcrys-0.1.0-windows-x64.zip`,
`semcrys-0.1.0-linux-x64.tar.gz`, their SHA-256 sidecars, the reviewer archive,
its boundary, and its sidecar. Publish `RELEASE-MANIFEST.json` beside the assets.
The manifest binds the seven primary payload artifacts; adjacent sidecars verify
their named files. The reviewer archive is companion reviewer evidence and is
verified by its own boundary and sidecar rather than represented as a core
manifest row. It is not independent successor acceptance unless a separately
identified reviewer returns an exact-artifact replay bound to these bytes.

Publish `PUBLICATION-ASSET-INDEX.json` and its sidecar last. This non-cyclic
index binds the core manifest, every attached payload and sidecar, the offline
bundle, and the reviewer companions. It explicitly excludes GitHub's two
tag-generated source snapshots, whose custody boundary is the tagged commit.
Build and verify it with:

```powershell
python -B tools/build_publication_asset_index.py
python -B tools/verify_publication_asset_index.py
```

The release notes must preserve these boundaries:

- base runtime dependencies: none beyond Python 3.11+ standard library;
- secure profile dependency: `cryptography>=42`;
- optional native acceleration does not change container bytes;
- Standard v0.3 defaults to full eligible integerization and profit-governed
  local/cross-document composition, retains the individual/group-legend control,
  and reads Standard v0.2 archives;
- group legends pool records across related artifacts; recursive metalegends
  represent one ordered legend and restore its exact original bytes;
- the seekable Ultra `.mleg` reduces its 54,102,082-byte logical legend by
  56.3179%; its independently rooted frames cost 818,671 bytes (3.5884%) over
  the smaller whole-stream control and 693,053 bytes (3.0212%) over the former
  `.crys` transport in exchange for targeted integer lookup, frame verification,
  and cache promotion; the former `.crys` remains the faster full-restore control;
- Lite supplies keyed frequency-balanced aliases, independent position
  projection, protected moving legends, declared count/size padding, and
  `homophonic` / `homophonic-positional` / `maximum-concealment` presets; Full
  can protect complete group legends, indexes, bespoke legends,
  and recursive metalegends through an explicit bounded AEAD envelope;
- protected artifact writes fail closed on existing destinations and key
  rotation preserves source identity without re-encoding it;
- the Windows standalone carries the native ABI-2 kernel;
- the Linux standalone uses the byte-identical pure-Python fallback and requires
  the glibc floor recorded in its internal and release manifests;
- standalone packages bundle pinned third-party runtimes inventoried in
  `BUNDLED-RUNTIME.json`; “no dependencies” means no separate installation;
- formal external certification is not claimed;
- universal compression superiority and a complete protocol security proof are
  not claimed.

The security projection court is builder qualification, not independent
cryptanalysis. Release notes must separate homophony, position projection, and
length padding. Position projection suppresses bigram/trigram mutual information
to the court's shuffled-null bound on its declared fixture; this does not prove
universal concealment or cover endpoints, timing, access patterns, traffic
analysis, or the selected padding class.

Link public readers to `docs/SEMCRYS-COMPRESSION-MODEL.md`. Release notes should
state the bounded Wikipedia result and the adaptive-composition continuum:
small structures can lose after legend and manifest costs, while sufficiently
reused large structures can win; the exact realized candidate set decides.
Also link `docs/SYSTEM-ARCHITECTURE.md` as the single map of the eighteen
release subsystems and their explicit nonclaims.

The project owner authorized GitHub history, tag, and release replacement on
2026-11-05. `PUBLICATION_DECISION.json` records that effect. The executable
standing remains `PUBLICATION_CANDIDATE`; publication does not grant semantic
identity, production admission, formal certification, or protocol-security
standing.
