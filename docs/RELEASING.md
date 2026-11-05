# Release process

Run every source-tree command below from the repository root with `src`
available to Python. Establish that environment once before beginning:

```powershell
$env:PYTHONPATH = "$PWD\src"
```

```sh
export PYTHONPATH="$PWD/src"
```

1. Run `python -B tools/build_payload_manifest.py` after any Full component
   source change, then verify that the resulting root is expected.
2. Run `python -B tools/build_native.py` on each supported build platform.
3. Confirm `native-status` binds the expected ABI, binary hash, and build root.
4. Run `python -B tools/qualify_seekable_metalegend.py`; require deterministic
   `.mleg` rebuild, exact logical `.leg` inverse, and complete accounting against
   both the whole-stream metalegend and incumbent `.crys` controls.
5. Run `python -B tools/run_security_projection_court.py`; require exact inverse,
   bounded balanced-alias spread, sample-adjusted alias-correlation acceptance,
   independent position projection, bigram/trigram shuffled-null gates,
   padding-class behavior, tamper/wrong-key refusal, protected group-artifact
   recovery, and source-preserving key rotation.
6. Run `python -B tools/verify_wikipedia_evidence.py` against the checked-in
   rooted result. Reproduce the fixture and benchmark when compiler behavior or
   the claim changes.
7. Run `python -B tools/verify_integerization_performance_evidence.py`.
8. Run `python -B -m unittest tests.test_standard_archive -v`; confirm the
   small-composition rejection, large-composition admission, exact collection
   replay, ablation, deterministic archive, cache, and GTI courts.
9. Run `python -B tools/run_publication_court.py`.
10. Confirm zero failures and no unexpected skips.
11. On Windows, run `python -B tools/qualify_standalone.py windows`.
12. On Linux x86-64, run `python -B tools/qualify_standalone.py linux`; preserve
   its declared glibc floor and copy the qualified artifact into the final
   assembler's ignored `release-inputs/` directory.
13. Confirm both platform courts report two byte-identical builds and an exact
    pack/verify/unpack rehearsal.
14. Run `python -B tools/build_release.py` twice.
15. Confirm both combined builds produce identical artifact hashes.
16. Run `python -B tools/verify_release.py dist/RELEASE-MANIFEST.json` on both
    Windows and Linux. The host platform must execute its standalone; the other
    platform must pass structure and custody verification.
17. Confirm pure-wheel fallback and native-wheel selection rehearsals both pass.
18. Verify the exact artifact envelope and fresh extraction.
    Build the rooted candidate receipt with `tools/build_release_receipt.py`;
    it must bind both deterministic inventories, the staged envelope, packaged
    execution rehearsals, publication court, and preserved prior custody.
19. Perform independent review from the complete offline bundle.
20. Record the independent result and make the human publication decision.
21. Only after that decision, change candidate standing/publication fields and
    rebuild every affected artifact; prior publication authority does not cover
    changed source roots.
22. Run `python -B tools/build_reviewer_bundle.py`. Require its two in-memory
    builds to be byte-identical and retain the generated archive, boundary, and
    sidecar under `release-inputs/reviewer/`. Then run
    `python -B tools/build_publication_asset_index.py`.
23. Run `python -B tools/verify_publication_asset_index.py`; require every
    uploaded local asset to be present, hash-exact, and assigned to an explicit
    verification group before upload.
24. Build the release receipt after the index; the receipt must record both the
    core release verification and the wider publication-index verification.
25. Attach `PUBLICATION-ASSET-INDEX.json` and its sidecar last. GitHub's two
    tag-generated source snapshots are intentionally outside this index and are
    bound by the tagged commit.

Generated files under `dist/` are outputs, never source-of-truth. Publication must not silently promote unresolved semantic identities or broaden `RELEASE_CONTRACT.json` security claims.
The distribution directory and offline bundle each carry the exact hash-bound
Ultra asset; release verification must not borrow it from the source tree.
`RELEASE-MANIFEST.json` is the executable-payload contract.
`PUBLICATION-ASSET-INDEX.json` is the wider GitHub-release inventory and binds
the manifest, all uploaded payloads and sidecars, the offline bundle, and the
reviewer companion envelope without creating a self-hash cycle.

