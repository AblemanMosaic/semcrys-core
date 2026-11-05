# Glyph-token projection, candidate feature contract

The `.crys` envelope framing and binary `.leg` remain ABI v0.2. This successor
enables the existing `glyph_binding` header branch and registered `GLYP`
section, previously unavailable in the v0.2 application. It is an explicit
feature extension, not a claim that an old implementation reads new glyph files.
Old applications must and do refuse them; old packed outputs remain byte-identical.
No prior frozen schema or evidence was edited. Public release format acceptance
still requires the release court.

`glyph_binding` is null for packed/raw. For glyph projection it is exactly
`{mode: EMBEDDED|EXTERNAL, sha256: lowercase-root, schema: semcrys.glyph-registry.v0.1}`.
EMBEDDED requires exactly one critical GLYP section after legends and before
BODY; its exact payload hash must match. EXTERNAL forbids GLYP and requires the
caller to supply that exact registry. Registry JSON is bounded to 4 MiB and
65,536 unique scalar glyphs. General registry inspection permits BOUND; this
token projection requires TEMPLATE and at least two glyphs.

The glyph IC is `semcrys.instance-constitution.v0.3`, with the old fields plus
projection, glyph_registry_sha256, glyph_placement, glyph_codec, glyph_radix,
glyph_literal_escape, glyph_width and glyph_legend_entries. Packed IC remains
v0.2. Decoder checks registry, count, width, escape, schema, profile and roots;
none can be changed merely by rehashing an inconsistent configuration.

Given B glyphs in their declared order and M entries across the rooted legend
stack, w is the smallest positive integer with B^w >= max(1,M). A positive
legend ID i is written as exactly w base-B digits for i-1, with leading zero
digits. No delimiter is needed between fixed-width codes. A code >= M is invalid.
The ID remains local to that legend stack; no CSIL/GTK identity is invented.

BODY before an optional outer codec is UTF-8 `SGY1\n` followed by symbols and
literal frames. The escape is the first absent glyph among `~`, `^`, `|`, then
ascending scalars from U+E000. It never overlaps a symbol digit. A literal is:

    escape decimal-byte-length : lowercase-hex-of-bytes ;

Length is 1..max_unit_bytes (at most 4096), without leading zero. Decoder reads
exactly twice that many hex characters and a semicolon. Uppercase hex, spacing,
bad/truncated UTF-8, missing delimiters and unknown digits are refused. Original
literal bytes may themselves contain the escape, punctuation or newlines.

Streaming conversion is between packed token EVENTS and glyph codes. It does
not map individual varint bytes to glyphs. After inverse projection the regular
token decoder resolves the same IDs and literals through the same legend stack.
Both output budgets and intermediate expansion budgets apply. One source byte
can correspond to at most 256 glyph bytes (64 digits × four UTF-8 bytes); a
separate bound applies to literal frames and the five-byte header.

SFTIR addresses in `GLYPH_PROFILE_CONTRACT.json` refer to the already rooted
SemCrys-A control bridge. `SDO:EMIT_GLYPH_PROJECTION` is the domain realization;
this work does not promote a codec operation into a new SFTIR primitive.
