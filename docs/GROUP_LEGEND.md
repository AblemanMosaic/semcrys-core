# Group legends

A **group legend** pools byte-identical stored legend records across a related
set of verified SemCrys artifacts. It retains an exact local-ID-to-group-ID map
for each original legend, preserves each local namespace, restores every
original container and legend byte for byte, and verifies decoded source roots.

This is horizontal reuse across artifacts. It is not recursive compression of
one legend; that operation is a [metalegend](METALEGEND.md).

## Commands

```text
semcrys group-legend pack OUTDIR --source a.crys --source b.crys
semcrys group-legend unpack archive.crys OUTDIR [--meta pool.leg]
```

The historical `metalegend pack` and `metalegend unpack` spellings remain
byte-compatible aliases in v0.1. New automation should use `group-legend`.
Likewise, the existing `semcrys.metalegend-instance.*` and
`semcrys.metalegend-bundle-instance.*` strings are frozen wire-schema names,
not the canonical conceptual name. Python integrations use
`semcrys.group_legend`, `semcrys.group_bundle`, and
`semcrys.group_auxiliary`; the old `meta_*` modules are compatibility imports.

The packer measures a pooled realization against a verbatim control and can
place the pool internally or externally. Cold accounting charges every missing
dependency once; warm accounting requires the caller to declare the exact roots
already held. Ties remain with the control. Record identity is exact stored
bytes, not semantic identity, CSIL identity, confidentiality, or authority.

The canonical machine contract is `src/semcrys/GROUP_LEGEND_CONTRACT.json`.
