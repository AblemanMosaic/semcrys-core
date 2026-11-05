# General configuration court

The configuration court applies the repository's CM2 byte objective to one
frozen exact workload without treating a benchmark corpus as the court itself.
`CM2` here is the implementation label recorded by SemCrys contracts; this
document does not assign a broader canonical semantic identity to that label.

The court first invokes the verified legend-stack configuration selector once.
That selector realizes the exact RAW, self-contained, pre-shared, and
longitudinal-delta recipes crossed with the requested outer codecs, then decodes
every executable container to the frozen source hash. The court also creates and
round-trip verifies direct standard-library RAW, BZ2, and XZ controls.

The resulting measurements are rescored without recompression across:

- cold custody, where every missing legend root is charged once;
- warm custody, where a legend-backed candidate is eligible only when the
  caller declares every exact root already present;
- exact reuse horizons from 1 through 1024;
- unconstrained delivery, SemCrys-only delivery, any integerization, full
  integerization, and shared-legend capability lanes.

The byte objective is:

`container_bytes * exact_reuse_horizon + unique_missing_legend_bytes`

Capability constraints are applied before byte minimization. This prevents a
plain XZ control from being presented as the answer to a request for complete
integerization and prevents profitable integerization from silently standing in
for full coverage.

Run a court over any exact source and rooted legend-stack library:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -B tools\run_configuration_court.py SOURCE `
  --library STACKS.json --legend ULTRA.leg `
  --receiver-root EXACT_ULTRA_ROOT `
  --semcrys-codec NONE --semcrys-codec LZMA --semcrys-codec BZ2_9 `
  --horizon 1 --horizon 8 --horizon 32 `
  --output COURT.json --label MY_EXACT_WORKLOAD
```

The output is rooted, binds the source, library, measurement selection, complete
candidate rows, scenarios, and lane winners, and keeps
`future_prediction: false`, `global_optimality: false`,
`security_claim: NONE`, and `authority_effect: NONE`.

The court does not yet make a multi-document group-legend decision. Collections
must first be represented as an exact ordered workload and evaluated by the
archive/group-legend selectors; their complete delivered bytes can then enter a
successor court as additional candidates.
