# Longitudinal assembly deltas — candidate application

The legend history remains append-only. Factoring a delta creates a new artifact;
rebasing it onto an equivalent transformed parent creates a new branch, not a
silent update of a receiver's old history. Old containers retain their exact
original dependency roots.

## New letter, existing history

```text
semcrys assembly encode-longitudinal letter.txt letter.crys --rules rules.json --legend base.leg --legend prior-delta.leg --receipt audit.json
semcrys decode letter.crys restored.txt --legend base.leg --legend prior-delta.leg
semcrys legend extract letter.crys next-delta.leg --binding-index 2
```

Only after explicitly adopting the extracted delta does the caller supply it
as an additional --legend for the next letter. The application never edits a
relationship registry or existing legend. The receipt provides the exact next
binding index, delta root and parent root.

The encoder realizes ordinary and factored TOTAL missing-unit deltas against
the same exact external history. MIN_CONTAINER chooses the smaller complete
container, ordinary on ties. ASSEMBLY is an explicit forced representation and
may cost more. Selection concerns this letter, not predicted future reuse.
External dependency costs are equal between these two candidates; cold history
acquisition and audit receipts are separate costs, never declared free.

Compact and tagged form encodings use the existing opcodes and IC versions.
The packed BODY and its global stack ID order are preserved. A rule pack is an
encoder input and audit source, not a decoder dependency.

## Explicit migration of a delta's parent

```text
semcrys assembly build-delta old-delta.leg new-delta.leg --rules rules.json --source-parent old-base.leg --target-parent new-base.leg --receipt rebase.json
```

Both parent chains must be complete from their root base, equal in length, and
each corresponding member must expand to exactly the same ordered byte values.
Not merely the same set, labels, or concept names. Every parent link and
cross-member value uniqueness is checked. The input delta must be a TOKEN
legend whose parent is the last source-parent root. The new delta names the
last target-parent root.

For a second delta, supply both complete old and new two-member histories.
An assembly delta itself is not refactored directly: expand it first to a
TOKEN artifact if needed. Expansion preserves its *current* parent root; it
does not automatically reconstruct a former parent root or migrate old letters.
Creating replacement containers requires explicit encoding against the new
history. Source, rules, parents and prior containers remain unchanged.

## Scope and limits

- Source text: at most 64 MiB for encode-longitudinal.
- Explicit rule pack: at most 16 MiB and 65,536 declared forms.
- Parent chain: at most 1,023 members; total snapshot budget is explicit
  (default/max 1 GiB, including candidate legends in the verification context).
- Program expansion/depth: existing 4,096-byte / 32-step bounds.
- Program references are local to their own delta. A base present only in
  an ancestor is inlined, not treated as a new cross-ancestor reference opcode.
- Binary .leg remains ABI 0.2. Tagged/compact assembly families and IC 0.6/0.7
  are unchanged; Court036 decoders can read these resulting containers.
- Glyph/fold composition, second pass, group legends, cross-ancestor
  operands, complete disk/crash/platform qualification and final release
  remain separate unfinished work.

S > CM1 > CM2 > IC > IR is recorded in LONGITUDINAL_ASSEMBLY_CONTRACT.json:
phase space; actual parent/function prerequisites; measured representation
choice; rooted effective inputs; verified realized container and explicit delta
extraction. CANDIDATE_ONLY, no admission, authority or cryptographic claim.

