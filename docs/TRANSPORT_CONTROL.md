# Transport control — candidate v0.2

Reviewed 2026-08-31. This is candidate documentation, not a release date.

SemCrys transport is a format and negotiation control plane, not a network
stack. `transport negotiate` intersects two strictly typed peer declarations
and selects one exact pathway, `.crys` ABI, projection, legend root, and
available noncryptographic security mode. It does not contact the peer.

```text
semcrys transport capabilities
semcrys transport negotiate LOCAL.json REMOTE.json --pathway FILE_TRANSFER --codec CRYS_V02 --projection PACKED --legend-root BASE_SHA256 --legend-root DELTA_SHA256
semcrys transport negotiate LOCAL.json REMOTE.json --pathway FILE_TRANSFER --codec CRYS_V02 --projection RAW --self-contained
semcrys transport frame FILE.crys NEGOTIATION.json
semcrys transport verify-frame FRAME.json FILE.crys NEGOTIATION.json
```

Peer JSON uses schema `semcrys.transport-peer-capabilities.v0.2` with exactly:
`schema`, `standing`, `peer_id`, sorted unique `pathways`, `codecs`,
`projections`, `security_modes`, and `legends`. Each legend record has exactly
`legend_id`, `sha256`, positive integer `version`, `custody`, sorted unique
`supersedes`, `compatible_with`, and `locations`. `custody` is either `HELD`
or `REGISTERED_REFERENCE`. Registry knowledge supplies repair information but
does not assert that a peer possesses the bytes.

Current pathways are `EXTERNAL_CHANNEL` and `FILE_TRANSFER`; they describe an
external delivery choice. Current codec negotiation is `CRYS_V02`. These labels
do not claim that HTTP, queues, USB, voice, or any other external mechanism ran.

An external-chain negotiation requires `HELD` custody of the same
caller-ordered legend SHA-256 chain at both peers. A self-contained negotiation explicitly declares that no
external root is required. Version, supersession, compatibility, and locations make a missing root
actionable, but never substitute another legend for the root committed by a
`.crys` container. Missing intersections refuse with `HELD_NO_SHARED_PATHWAY`,
`HELD_NO_SHARED_CODEC`, `HELD_NO_SHARED_PROJECTION`, or
`HELD_NO_SHARED_LEGEND`.

The frame is a rooted JSON sidecar. It binds both peer capability hashes, the
exact negotiation document, body hash, byte count, profile, realized Instance
Constitution root, ordered legend chain, projection, pathway, and codec. The body is not embedded.
Verification distinguishes a changed frame root from changed body bytes. It is
not encryption, authentication, a signature, remote attestation, or proof of
delivery.

`NONE` and `NATIVE_OPACITY` are executable, both with `security_claim: NONE`.
Native opacity is accepted only with a nonempty exact pre-shared legend chain;
it cannot label a self-contained artifact. It means only that this dependency
posture was selected and does not claim confidentiality. Public adaptive permutation, keyed local-ID shuffle,
keyed homophony, delegated AEAD, and sealed-legend execution are visible typed
holds. There is no fallback from a requested held mode. Phase/domain separation,
salt, nonce, key custody, rotation, wrong-key behavior, and tamper guarantees
remain the responsibility of a future vetted cryptographic adapter court.

SFTIR addresses `SFM:SCOPE_BIND`, `SFM:REFERENCE_RESOLVE`, and
`SFM:CONDITION_GUARD` describe this control disposition. They do not produce
bytes or make the peer/legend identities equivalent.
