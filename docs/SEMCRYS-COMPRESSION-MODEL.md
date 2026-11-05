# SemCrys compression model

This is the normative v0.1 compression model for public explanation, agents,
Standard archive selection, and future optimization work. It prevents the model
from being reduced to either "a dictionary codec" or "one integer per word."

## The representation

For eligible UTF-8, SemCrys losslessly separates lexical units, punctuation,
and whitespace. A legend stores distinct units. Occurrences are transported as
unsigned variable-length local integer IDs in packed bytes, not decimal text or
fixed-width machine integers. Conventional outer codecs may then compress the
legend and reference stream.

Transport IDs do not become CSIL IDs by compilation. CSIL is the Canonical
Semantic Integer Layer: a CSIL integer has identity only in an exact rooted
registry. A GTI is an index that connects terms and occurrences to those CSIL
integers. GTK and bound-term relations remain higher governed bindings.

## The reuse continuum

SemCrys does not divide recurrence into fixed word, phrase, and blob classes.
It evaluates a continuum:

1. Repeated exact units can become local integer references.
2. Byte-identical chunks are stored once.
3. Equal legend records can be pooled across containers through group legends.
4. One ordered legend can be represented recursively as an exact `.mleg` recipe.
5. Adjacent event pairs can be composed recursively into larger transport
   structures, including recurring phrases, boilerplate, code fragments, or
   long document passages.
6. Related unique UTF-8 payloads can share one bounded collection stream so
   local and cross-document recurrence are visible to the same exact court.

Every extra structure has a cost. A special entry for a few words repeated a
few times can increase delivery size because its definition, references,
legend, manifest, container, and dependency custody outweigh its body savings.
A large block repeated many times can repay the same investment decisively.

## Standard admission

Standard `semantic` and `portable` modes use `composition=auto` by default:

1. Inventory and hash logical files.
2. Split bounded chunks and remove byte-identical duplicates.
3. Fully integerize each unique eligible UTF-8 control payload.
4. Pool individual controls through group legends.
5. Run a bounded repeated-pair census over related unique UTF-8 payloads.
6. If the census upper bound reaches the declared invocation floor, realize a
   shared collection integer stream and the recursive second-pass candidates.
7. Compare complete segment delivery, including transported manifest evidence.
8. Keep the control on ties or whenever composition does not repay itself.
9. Build semantic occurrence indexes over the original logical payloads and
   file boundaries, then replay every source byte before atomic publication.

The census is a scheduling predictor only. Hash-bucket collisions can cause
extra work but cannot admit a candidate. The realized complete-byte court is
the authority for selection. `--composition off` is an advanced ablation.

Collection payloads concatenate only already-unique eligible bytes. Exact
manifest offsets preserve chunk and file boundaries. Decode verifies the
collection root, each member root, every logical file root, and the source-tree
root. Composed IDs remain transport structures with no semantic identity effect.

## Accounting and claims

Standard reports exact chunk savings, group-legend pooling, composition groups
considered and selected, cache reuse, and net complete-segment savings as
separate fields. It does not add overlapping savings twice. A negative
composition result is retained as a valid control decision, not hidden.

`MIN_DELIVERY` and Standard segment admission are exact only over their declared
candidate set. They are not proofs of global compression optimality. Shared
legend results must state cold or warm custody. Compression and integerization
do not imply confidentiality. Security claims remain profile-specific.

## Workload expectations

Likely beneficiaries include repeated documentation, legal or policy
boilerplate, related source trees, generated reports, structured text, logs,
versioned prose, and archives containing recurring logical payloads. Already
compressed media, encrypted data, high-entropy binaries, and tiny unrelated
files may receive little or negative SemCrys-specific gain; measured controls
must be allowed to win.

