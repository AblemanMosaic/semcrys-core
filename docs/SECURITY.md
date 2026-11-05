# Security, protected legends, and custody

SemCrys separates public vocabulary, local identifiers, and private
reconstruction state. These are useful capabilities with different exposure
and assurance properties. The release claim remains
`BOUNDED_IMPLEMENTED_PROFILE_NO_PROTOCOL_SECURITY_PROOF`.

## Implemented profiles

Occurrence modes belong to `src/semcrys_lite/core.py`. Complete Full, Ultra,
group-legend, recursive-metalegend, and application-index artifacts can be
protected explicitly through `semcrys security`; protection is never inferred
from compression or integerization.

| Mode | Implemented behavior | Exposure / boundary |
|---|---|---|
| Ordinary compression/integerization | Reversible public mappings and events. | No confidentiality; dependencies permit reconstruction. |
| `KEYED_PERMUTATION` | HMAC-SHA256-derived ordering relabels local IDs with a secret key. | Repeated values retain repeated labels; equality and frequency remain. |
| `BOUNDED_ALIAS` | Caps reuse of public aliases; inverse mapping is in a protected moving legend. | Bounds label repetition; length, linkage, and inference still need analysis. |
| `FREQUENCY_BALANCED_HOMOPHONIC` | Creates a bounded alias pool per stable ID, permutes the public alias namespace per encoding, and key-shuffles a schedule whose alias frequencies differ by at most one. | Flattens frequency within each pool; position and co-occurrence remain unless the independent position policy is enabled. |
| Keyed position projection | Applies an invertible salt-bound Feistel permutation to aliased public events independently of count padding. | The tested bigram/trigram signals fall within the declared shuffled-null bound; exact event count, endpoints, timing, access patterns, and untested inference remain. |
| `FULL_UNIQUE_MESSAGE_LEGEND` | Public body is an event-count range; ordered base events are in a protected moving legend. | Source-bearing state is in the companion; an exact count or padded count class remains public. |
| Count/size padding | Buckets public event counts and/or sealed moving-state plaintext. Alias filler is fresh per encoding, sampled from that encoding's real alias emissions, and interspersed through a salt-bound keyed position permutation. | Reveals the selected bucket and does not conceal timing, filenames, endpoints, or access patterns. No traffic-analysis proof is claimed. |
| Protected artifact envelope | Authenticates and encrypts a complete group legend, semantic index, bespoke legend, recursive metalegend, or generic artifact. Exact source length and SHA-256 remain inside authenticated ciphertext. | The envelope role, padded size, envelope-specific key identifier, and ciphertext metadata remain public. |

The optional `cryptography>=42` backend provides AES-256-GCM and HKDF-SHA256.
The moving-legend path uses a fresh 16-byte salt, 12-byte nonce, purpose-derived
subkeys, and opaque artifact identifier. Alias, schedule, filler, position,
encryption, and key-identifier domains are separated. Associated data binds declared artifact
and profile context. Missing backend, wrong bindings, and authentication
failures are refused. The [backend's AEAD documentation](https://cryptography.io/en/latest/hazmat/primitives/aead/)
describes the primitive's requirements, including nonce discipline.

Public protect/encode receipts redact exact source length, source digest, and
true event count for protected modes. Full reconstruction checks remain inside
authenticated decryption. Treat private diagnostic measurements as protected
material rather than copying them into logs or evidence.

Keys need at least 32 high-entropy bytes. Length checking does not strengthen a
weak password. Key bytes can be supplied through a file or environment handle
and are never placed in receipts. Key rotation rewraps protected state without
recompressing the source. Password hardening, distribution, escrow, revocation,
hardware-backed custody, and memory zeroization remain outside this implementation.

The complete-artifact envelope is an in-memory operation bounded to a
512 MiB padded plaintext class. It refuses an existing destination instead of
silently replacing it. Larger collections should be partitioned into separately
rooted artifacts and composed by a manifest; this release does not imply a
streaming encrypted-container protocol.

Lite padding is likewise bounded: at most 8,388,608 public padded events and a
512 MiB sealed moving-state plaintext. A requested class beyond either bound is
a typed refusal, not an attempted allocation. These are implementation safety
limits, not security-strength measurements.

## Why a scrambled shared legend is interesting

A shared vocabulary can be public while a deployment keeps the correspondence
between that vocabulary and transported local IDs private. Possessing public
Ultra alone does not supply a keyed correspondence. Bespoke legends can also
benefit from separating the base from its private mapping.

This is meaningful custody dependence, but static permutation alone is not
encryption. Known text, frequency/equality structure, reuse, or oracle access
may help infer a mapping. Rotating labels does not establish forward secrecy
or unlinkability.

Protected modes instead put source-bearing mappings or sequences in an
authenticated encrypted companion. Homophony distributes recurrence over
several aliases without mutating stable semantic IDs. Full-unique removes the
ordered source sequence from the public body. Padding can replace exact public
counts with declared classes. Position projection can be selected without
padding when order/co-occurrence reduction matters but exact length may remain
public. These are concrete mechanisms to investigate,
not a new cipher or protocol proof. Companion and padding bytes still count: a
tiny public range is not evidence of tiny total delivery.

Full's binary Ultra asset is not a Lite legend by renaming it. Collection-level
protection therefore wraps the exact realized group legend, index, bespoke
legend, or metalegend. Callers should protect every disclosure-bearing copy;
leaving a plaintext group pool beside its protected envelope defeats that
boundary. Seekable encrypted artifacts may still reveal frame access locality.

## Evidence and remaining exposure

Lite and protected-artifact tests exercise exact reconstruction, balanced alias
counts, independent position projection, count-class padding, randomized
protected companions, key rotation, wrong-key and tamper refusal,
missing/mismatched dependencies, and occurrence behavior.
`evidence/SECURITY-PROJECTION-COURT.json` records a tie-aware, sample-adjusted
alias-correlation gate and bigram/trigram mutual-information gates against
deterministic shuffled nulls. This is bounded builder qualification on one
declared fixture, not proof that position or co-occurrence is universally
concealed and not independent cryptanalysis. The AEAD primitive is established;
its SemCrys integration still needs broader adversarial analysis.

Public fields can reveal mode, profile, dependency identities, exact count or
count/size classes, and envelope-specific identifiers. File names, unprojected
positions and co-occurrence, access patterns, execution timing, endpoints, and
unprotected application indexes can reveal more. Protect manifests and indexes explicitly when the
application requires it; a moving legend does not cover other copies.

[RFC 7457, section 2.6](https://www.rfc-editor.org/rfc/rfc7457.html#section-2.6)
documents compression side channels in TLS/HTTP. It is relevant prior work when
designing systems that combine attacker-controlled data, secrets, and observable
compressed lengths. It is a review target, not a demonstrated SemCrys exploit.

The release establishes no complete protocol security proof, independent
cryptanalysis, endpoint security, traffic-analysis resistance, forward secrecy,
or leakage-free semantic search. Exact replay does not prove these properties.

## Custody and integrity

Retain the exact key, moving legend or protected envelope, and all external
base/delta/assembly dependencies. Loss can make artifacts unrecoverable. Keep
recovery material and custody records backed up under an appropriate separate
access policy, run `security verify` or an exact decode rehearsal, and verify a
rotated copy before removing source material or retiring an old key.

SemCrys does not log supplied key bytes. Callers must keep them out of shell
history, command-line arguments, diagnostics, issues, and agent context. A
vocabulary export may disclose private legend contents. Unkeyed hashes detect
drift relative to trusted roots; they do not authenticate a publisher that can
be impersonated by replacing both an object and its checksum.

## Help stress-test and harden SemCrys

Useful adversarial work includes:

- known/chosen-plaintext and chosen-input attacks on permutations and aliases;
- cross-artifact linkage, frequency inference, and metadata leakage;
- companion/context swaps, nonce/salt handling, tampering, and malformed input;
- decode resource exhaustion and partial-publication/recovery behavior;
- custody loss, backup restoration, rotation/revocation, and endpoint boundaries.

Report vulnerabilities privately to **ableman.research@gmail.com**. Include a
minimal synthetic reproduction, exact version/profile, attacker knowledge,
observable fields, and expected/observed behavior. Use generated test keys;
do not send real keys, private legends, or third-party secrets. Public issues
can discuss redacted research and compression/semantic evaluations.

The [SemCrys-Secure paper](https://doi.org/10.5281/zenodo.20374735) describes the
wider direction. Executable modes, exposure, and measured evidence remain the
basis for claims about this release.

