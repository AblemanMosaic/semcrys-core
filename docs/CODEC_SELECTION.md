# Exact outer-codec selection — v0.1 release-candidate contract

Reviewed 2026-08-31. The implementation originated in dev87; this is the
current release-candidate contract, not a public release date.

`codec select` measures an ordered codec set on one exact source, profile,
legend stack, and legend policy. It writes a rooted candidate record. Every
available candidate must produce a complete `.crys` container and decode to the
exact source root before it can participate in selection.

```text
semcrys codec select SOURCE CHOICE.json --profile C:SELF_CONTAINED_TOKEN --accounting COLD
semcrys codec encode-selected SOURCE CHOICE.json OUTPUT.crys
```

The default executable set is `NONE`, legacy `LZMA`, explicit
`LZMA2_XZ_0/6/9`, and `BZ2_1/9`. Repeat `--codec` to set another ordered subset.
`ZSTD` and `ZSTD_DICT` are requestable typed-unavailable cells in this package;
they refuse rather than install a dependency or substitute another codec.

The objective is the minimum exact complete-container bytes plus missing
external-legend dependency bytes. COLD charges legend roots not declared at the
receiver. WARM requires every external root in `--receiver-root` and charges no
legend acquisition. Receiver declarations are accounting inputs, not remote
attestation. Caller candidate order breaks exact byte ties.

The record binds source root/length, profile, ordered legend roots, normalized
legend policy, ordered codecs, accounting mode, receiver roots, budgets, every
container root/length, BODY payload length, full effective configuration and
receipt, and the selected result. Every measured cell—including frozen `NONE`
and `LZMA`—has an explicit algorithm/framing/level/dictionary/order descriptor.
The selector also binds the application payload, application version, Python
runtime, platform and standard-library adapter identities that performed the
measurement. `codec encode-selected` rejects source,
legend, configuration, receipt, or output-byte drift.

This is exact-source measurement only. It proves neither future-workload
prediction nor global codec optimality. Extended profiles currently compose
only with ordinary PACKED realizations; glyph, fold, and assembly combinations
remain typed unqualified. No compression result implies confidentiality.
