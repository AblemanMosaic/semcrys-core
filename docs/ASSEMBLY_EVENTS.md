# Assembly-event legends — candidate application

An event integer is scoped to one exact legend. It is not the CSIL address of
`plural`, a sense identity, or a grammatical judgment. A form such as `friends`
can be stored as `friend` + the explicitly chosen spelling operation `+s`.
Several occurrences still emit the same one integer each. The event definition
is stored once in the legend. The ordinary surface legend is not also required
by the decoder.

## Public workflow

1. Prepare an ordinary binary `.leg` and an explicit JSON form-rule pack.
2. `semcrys assembly build surface.leg forms.leg --rules rules.json --receipt audit.json`
3. `semcrys assembly inspect forms.leg`
4. `semcrys encode letter.txt letter.crys --profile T:PRESHARED_TOKEN --legend forms.leg`
5. `semcrys decode letter.crys restored.txt --legend forms.leg`
6. `semcrys assembly expand forms.leg restored-surface.leg`

The last step reproduces the original root-base TOKEN legend byte for byte,
including its ID order and sparse-index stride. It is an explicit new output,
not a mutation of the source. Rule pack and build receipt are audit material,
not hidden decoder inputs. The current build receipt is not the rich folded
projection dossier format, nor a universal installed audit library.

Example rule pack:

```json
{"schema":"semcrys.assembly-rule-pack.v0.1","standing":"CANDIDATE_ONLY","jurisdiction":"ENGLISH_EXPLICIT_SURFACE_FORMS","source_refs":["caller-owned-proposal"],"rules":[{"surface":"friends","base":"friend","operator":"EN_PLURAL_OR_3SG_S"}]}
```

Only exact supplied rules are used. A validated spelling transform is not
proof that its result is grammatical or has the base's meaning. `EXPLICIT_REPLACE`
stores the replacement literally for irregular forms; it is not free compression.
Unmatched rules are counted. Unmatched entries remain literal programs. Missing
base entries are inlined; existing bases use local event references, including
forward references. Nested unary programs are allowed within the fixed depth
limit, while cycles and duplicate expanded values refuse.

## Format and operating costs

The binary `.leg` envelope remains 0.2. Its explicit `unit_mode` is
`ASSEMBLY_EVENTS_V1`; entries contain programs rather than literal execution
values. The raw binary reader verifies storage; the execution reader verifies
and evaluates programs. The exact source artifact root binds the resulting
disk-backed lookup. A new rooted IC schema 0.6 declares the ordered assembly
legend roots and assembly ABI. Older applications refuse that IC; no legacy
decoder is asked to interpret programs as ordinary text.

The binary envelope, index, program tags, inline bases and exact roots all cost
bytes. The packed body is unchanged if source and ID ordering are unchanged;
this is dictionary factoring, not a new body compression result. The existing
library selector can compare a surface and assembly legend with COLD or WARM
accounting, including unchanged raw/local competitors. It selects the measured
whole delivery, not the most attractive name. Audit-source acquisition and
receipts remain separate and must not be called free.

`A:LONGITUDINAL_TOKEN_DELTA` can use the assembly base, then append normal TOTAL
delta legends. The caller explicitly retains/extracts deltas; no relationship
state is mutated. Batch encoding may reuse a verified assembly context but is
not group-legend processing. Glyph and folded-front combinations with assembly
programs currently refuse. Second pass, group legends and broad resource/platform qualification
remain unfinished release requirements.

The shipped ASSEMBLY_PROFILE_CONTRACT.json fixes the operator table, program
grammar, limits and S→CM1→CM2→IC→IR boundaries. SFTIR addresses describe external
control obligations; the domain spelling operators are not new SFTIR primitives.
No grammar, GCNL identity, confidentiality, admission or release claim follows.

## Compact records and self-contained files (dev36)

The original tagged build remains the default and byte-compatible. Opt in with
`assembly build surface.leg compact.leg --rules rules.json --encoding COMPACT --policy SHORTER`.
The compact mode stores ordinary literal bytes without a tag; leading FF is
escaped as FF 00, and FF 01/02 identify reference/inline programs. The existing
length-delimited envelope makes this unambiguous, including arbitrary bytes.
SHORTER uses a program only when its complete length-prefixed record is smaller
than the literal record. This is not a whole-file optimization guarantee.

For a file with no pre-shared legend:

`semcrys assembly encode letter.txt letter.crys --rules rules.json --outer-codec LZMA --receipt audit.json`

This builds ordinary and compact-assembly self-contained candidates, verifies
both inverses, and chooses the smaller complete container (ordinary on ties).
Use `--selection ASSEMBLY` to explicitly force the assembly candidate for
inspection; it may be larger. The source budget is 64 MiB. The decoder is the
ordinary `semcrys decode` command and needs no rule pack or external legend.
The rule pack is supplied, never inferred; an invalid pack refuses rather than
silently falling back. Duplicate JSON keys now refuse at every rule-pack level.

Compact and mixed tagged/compact stacks use assembly family ABI 0.2 and IC 0.7;
old tagged-only stacks retain ABI 0.1 and IC 0.6. Older applications fail closed
on the new IC. Shared and longitudinal PACKED paths can consume compact bases.
No packed-body ID is changed; savings or losses are in legend and metadata cost.
Audit receipts and source provenance remain separately accounted, not hidden
inverse dependencies. The full contract is COMPACT_LOCAL_ASSEMBLY_CONTRACT.json.

Dev37 adds explicit delta rebasing and cost-aware longitudinal encoding. See
LONGITUDINAL_ASSEMBLY.md. Existing histories are not silently reparented.
# Rule-pack diagnostics

Per-rule refusals retain their original typed code and identify `rules[N]`,
where N is a zero-based index in the submitted `rules` array. This includes
operator/precondition failures. No surface/base text is echoed by this context.
Pack-level parse/schema errors do not invent an index. The current rule limit
is 65,536; the separate `source_refs` list is limited to 512.
