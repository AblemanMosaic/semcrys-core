# Security boundary and measured concealment properties

SemCrys-Lite makes no native confidentiality claim.

- `KEYED_PERMUTATION` changes labels but preserves the public equality graph.
- `BOUNDED_ALIAS` limits how often a public alias repeats and moves the alias
  reduction map into an external moving legend. Its public body still exposes
  bounded recurrence topology.
- `FREQUENCY_BALANCED_HOMOPHONIC` uses a fresh salt-bound alias namespace for
  each encoding and balances public frequency within each base value's alias
  pool. By itself it does not conceal source order or cross-position language
  structure.
- `KEYED_FEISTEL_PERMUTATION` is an independent position policy for bounded or
  homophonic aliases. It exactly restores order from protected state while
  leaving exact event count public when count padding is disabled.
- `FULL_UNIQUE_MESSAGE_LEGEND` exposes only the event count/range in the body
  and moves the ordered base-event sequence into the moving legend.
- Bytes move; they do not disappear. The moving legend becomes message-bearing.
- Every message-bearing moving legend is sealed with AES-256-GCM using
  HKDF-SHA256,
  a fresh salt, fresh nonce, and a fresh opaque artifact ID. The public
  container binds the randomized sealed artifact, never the deterministic
  plaintext legend root.
- The source digest and plaintext legend root remain inside the authenticated
  sealed artifact for receiver-side verification.
- Protected-mode public receipts redact exact source length, source digest,
  true event count, and unpadded moving-state length. Padding filler is fresh,
  sampled from real alias emissions, and interspersed with the keyed position
  permutation rather than appended as a deterministic suffix.
- The runtime key must contain at least 32 bytes. HKDF is not a password-hard
  KDF; users must supply high-entropy key material and govern key distribution,
  rotation, storage, and deletion outside this reference package.
- Bell-number partition growth is descriptive combinatorics, not a security
  reduction and not proof against language priors, cribs, known plaintext,
  chosen plaintext, partial legends, traffic analysis, or longitudinal state.
- Public source hashes are omitted in concealment profiles. Two encodes of the
  same plaintext under full-unique mode produce distinct public containers.
  This closes the deterministic public commitment used by the rc1
  guess-confirmation and whole-container equality tests.
- Full-unique still reveals event count unless count padding is active, plus
  container metadata, timing, and traffic behavior. Bounded aliases still
  reveal their bounded public pattern.
- `KEYED_PERMUTATION` uses a keyed reconstruction tag but remains deterministic
  and equality-preserving; it is not an encryption mode.
- AES-GCM is an established primitive, but this integration has not received
  independent cryptanalysis or an end-to-end protocol security proof.

The package proves exact reconstruction, randomized concealment artifacts,
authenticated refusal on wrong/tampered companions, and typed failure on
bounded fixtures. Its position court measures bigram and trigram mutual
information against deterministic shuffled nulls on one declared fixture.
That is regression evidence for those attack metrics, not a universal proof
that order or co-occurrence cannot be inferred. Independent cryptanalysis is
not claimed.

## Legend disclosure is measured

Holding the legend alone exposes the entire vocabulary of the document. That is
unavoidable: the legend is the map. Two further axes are ordering artifacts and
can be removed, and `semcrys-lite disclosure` measures all three against the
source rather than reading the declared `id_order`:

- **vocabulary** — every content unit, under every ordering. Not removable.
- **introduction order** — the sequence in which units first appeared.
- **frequency rank** — how often each unit was used.

`LEXICAL` ordering removes the second and third at a cost of roughly 4.5% in
output size. `FREQUENCY` ordering is smallest but discloses usage rank.
`FIRST_APPEARANCE` discloses both.

Rank correlation on a small vocabulary is noisy, so the metric computes its own
standard error, widens its decision threshold accordingly, and reports whether
the sample supports a confident determination.

## The ladder and shareability

Climbing the ladder moves repetition structure out of the public body. Byte size
does not track it — concealment can and does cost bytes, and both series are
reported so the two are never conflated. At the top rung the moving legend is
the message and can never be a corpus asset; accounting refuses message-specific
configurations with `HELD_ACCOUNTING_LEGEND_NOT_SHAREABLE` rather than
publishing a break-even number that cannot exist.

None of this is a confidentiality claim. `security_claim` remains `NONE`.
