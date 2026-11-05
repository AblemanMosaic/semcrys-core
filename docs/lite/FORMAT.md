# Container format

A container is one logical object with two possible serializations. The logical
object, and therefore `container_root`, is identical in both — the envelope is
transport, not meaning.

## Envelopes

`BINARY` (default). Magic `SCRYSL1\n`, two varint lengths, a canonical JSON
header, then the body payload as raw bytes.

`TEXT`. Canonical JSON with the body carried as base64, or inline when the body
is JSON and the outer codec is `NONE`.

Decode auto-detects: text containers have no magic, so they load unchanged.
The text envelope costs about one third more, because base64 needs four
characters for every three bytes. It exists so a container can be opened and
read in an editor.

## Body representations

`PACKED_VARINT` (default). Events as LEB128 varints.

`JSON_EVENTS`. Events as a JSON array of decimal integers. Readable under the
text envelope; costs roughly 6% more after LZMA.

A `RANGE` body carries no events array, so `PACKED_VARINT` falls back to
`JSON_EVENTS` for it. The fallback is recorded: the container states the
representation actually used, and the receipt states both what was requested and
what was effective.

`body_logical_sha256` binds the canonical logical body, so the digest is the
same under either representation and either envelope.

## Unit models

Byte profiles map one source byte to one event. No dictionary gain is possible
at that granularity; these are the reference floor.

Word profiles tokenize into whole words and separator runs. Hyphenated
compounds are held back and resolved last, once part frequencies are known:
each compound is bound as its own entry or composed from its parts, whichever
is measured cheaper. Composition is charged for any part it must admit to the
legend.

## Legend tiers

`BASE_WORD` maps ids to units. `ASSEMBLY` maps ids to pairs of earlier ids, so
expansion always terminates; it binds the base legend root it was fitted
against. Both are separate documents from the worked artifact.
