# Lite/full event-model synchronization — candidate

Full SemCrys and SemCrys-Lite share semantic roles, not wire ABIs. The shared
contract defines literal, unit-reference, and assembly-reference events and
requires exact reconstruction, rooted dependencies, actual-artifact cold
accounting, and observed disclosure. Neither application silently parses the
other's `.crys` or `.leg` files.

Full SemCrys adds four read-only measurement surfaces:

```text
semcrys synchronize disclosure SOURCE LEGEND
semcrys synchronize ordering SOURCE LEGEND
semcrys synchronize compose SOURCE LEGEND --minimum-count 3
semcrys synchronize account --source A --container A.crys --legend union.leg
```

`disclosure` measures coverage and reference-frequency exposure against the
actual source. `ordering` proposes a deterministic frequency/lexical ID
permutation and estimates packed-reference savings without rewriting the rooted
legend. `compose` proposes recurring adjacent pairs only when packed reference
savings repay the definition on the observed stream; it does not infer an outer
codec gain. `account` roots actual sources, containers, and legends and reports
an observed warm/cold curve against XZ/LZMA preset 6.

All four outputs are `CANDIDATE_ONLY`, read-only, and carry
`security_claim: NONE`. A proposal is not an applied configuration, and an
observed disclosure report is not a confidentiality theorem.
