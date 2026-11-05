# Profiles and orthogonal axes

Base profiles:

- `L:BYTE_DIRECT`: byte values are integer events `0..255`; no base legend.
- `L:BYTE_LOCAL_DENSE`: encountered bytes receive dense IDs in a local legend.
- `L:BYTE_PRESHARED`: encoding requires an exact root-bound external legend.
- `L:WORD_DIRECT`: lossless word/separator units use a shareable word legend.
- `L:WORD_ASSEMBLY`: a separately rooted adjacent-pair assembly composes over
  the word legend and expands exactly before source reconstruction.

Body and envelope axes:

- `PACKED_VARINT` (default) or inspectable `JSON_EVENTS`
- `BINARY` (default) or inspectable `TEXT`

Legend placement:

- `NONE`, `SELF_CONTAINED`, or `EXTERNAL`, as constrained by the profile.

Occurrence projection:

- `REPETITION_VISIBLE`
- `KEYED_PERMUTATION`
- `BOUNDED_ALIAS`
- `FULL_UNIQUE_MESSAGE_LEGEND`

The last two modes require a minimum 32-byte runtime key and the optional
`cryptography` backend. They emit randomized AES-256-GCM sealed moving legends.
The key is present in the Instance Configuration only as a boolean capability;
its value is never recorded.

Outer physical codec:

- `NONE`
- deterministic stdlib `LZMA` over the selected physical body carrier.

These axes are recorded independently. Compression desirability never implies
recurrence concealment, and recurrence concealment plus an established AEAD
primitive does not by itself prove an end-to-end secure protocol.
