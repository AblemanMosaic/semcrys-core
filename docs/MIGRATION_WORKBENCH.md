# Migration and release-disposition workbench

Documentation reviewed: 2026-08-31. This is a release-candidate review date,
not a public release date.

`semcrys workbench status` is a read-only compact view of the v9-to-v0.1
migration and current release gates. Add `--rows` for complete dispositions.
`semcrys workbench export` emits the complete deterministic artifact.

The packaged status accounts for all 79 inventoried legacy parameters and
invariants. Each receives exactly one disposition: qualified current candidate,
optional research preserved, typed unavailable, proposal-only, superseded by a
current rooted contract, or partial successor with legacy parity explicitly not
claimed. It separately reports whether a current surface is available.

The status root binds every row and the exact `RELEASE_SCOPE.json` bytes. The
loader checks the root, exact row schema, sorted unique slugs, disposition
counts, evidence-reference types, release-scope hash, and historical blocker
count. `verify-self` additionally checks the package inventory.

Historical disposition closure is not release acceptance. A nonblocking row
means the old item was not silently lost; it may still be unavailable or only
partially represented. Release-gate blockers are counted separately.

Both commands have no canonical CSIL/GTK effect, relationship-state effect,
authority, admission, security, or publication effect. `CANDIDATE_ONLY` remains
the standing of every row.
