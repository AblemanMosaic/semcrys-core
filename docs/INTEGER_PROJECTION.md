# Integer-token projection — candidate feature contract

`encode --projection INTEGER` is a human-inspectable projection of the same
lossless token events used by PACKED. It applies to self-contained, pre-shared,
and longitudinal-delta token profiles. It does not apply to raw bytes, form
assemblies, folded fronts, configurable XZ/BZ2 v0.9 profiles, or second-pass
input. Those unqualified combinations refuse rather than silently falling back.

The critical Instance Constitution is `semcrys.instance-constitution.v0.10`.
Its physical BODY schema is `semcrys.integer-token.v0.1`, with magic `SIT1\n`.
Each subsequent LF-terminated line is exactly one event:

```text
I:1
I:203
L:48656c6c6f
```

`I:` is a one-based, no-leading-zero decimal ID in the exact rooted and ordered
legend stack. `L:` is a nonempty, even-length lowercase hexadecimal literal.
CRLF, uppercase hex, missing final LF, unknown tags, out-of-range IDs, and
noncanonical decimals refuse. The decoder reconstructs canonical SPV2 first,
then uses the ordinary legend/token inverse and verifies the source root.

These integers are local transport addresses. They are not canonical CSIL IDs,
not stable after legend reordering, and not a security mechanism. INTEGER is
larger than PACKED in ordinary byte accounting; its declared purpose is manual
inspection, teaching, historical/archaic interchange, and external-tool
debugging. Optional legacy `LZMA` may wrap the INTEGER body. The receipt reports
identifier/literal/event counts, packed bytes, projected bytes, and the exact
pre-outer-codec body root.

Standing is `CANDIDATE_ONLY`; the projection has no admission, release,
authority, semantic-identity, or confidentiality effect.
