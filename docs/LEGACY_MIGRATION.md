# Explicit historical migration

    semcrys legacy import old_sc new.crys --format SC_TEXT --expected-source-sha256 HASH --legacy-glyph old.gly
    semcrys legacy import old_sc new.crys --format SC_TEXT --expected-source-sha256 HASH --legacy-glyph old.gly --legacy-legend shared.sclegend
    semcrys legacy import old_scb new.crys --format SC_PACKED --expected-source-sha256 HASH

The expected hash is SHA-256 of the exact input file, not its decoded content.
SC_TEXT accepts historical §SC1 text frames with header v1/v2, fixed or
terminal/continuation variable codes. Supply the exact historical semcrys.gly.v1
registry. Embedded legends or explicitly named raw/shared .sclegend dictionaries
are validated against the header's legacy entry hash. No neighboring sidecar or
registry is discovered implicitly. SC_PACKED accepts SCB1 with its embedded unit
list. Unknown formats, member archives, sealed/encrypted wrappers and extra header
fields fail closed. These types are not silently parsed as current .crys.

The old source bytes are decoded privately and checked against the original
header's SHA-256 before current encoding. The selected current profile defaults
to C:SELF_CONTAINED_TOKEN. RAW, pre-shared and longitudinal profiles are explicit
choices; --legend supplies CURRENT binary legends, not old .sclegend dictionaries.
--outer-codec NONE/LZMA has its normal meaning. Current decode must reproduce the
same source root. No old file is changed; no old code ID is promoted to canonical
CSIL identity or silently treated as the new tokenizer's ID.

Receipts preserve exact old container/legend/registry roots, the legacy header,
the migration IC, current encoding configuration and inverse evidence. Use
--receipt to retain one. Existing output requires --replace; original inputs,
sidecars, registries and current legends are protected by publication alias checks.
This uses the existing aggregate scratch and journaled file-publication machinery.

Source and individual metadata caps: 64 MiB. Decoded output cap: 128 MiB.
Metadata JSON is bounded materialization, not a constant-RAM claim. The body is
decoded incrementally with bounded UTF-8/code carry, output limits and canonical
varints. --max-scratch-bytes governs logical scratch/native capacity and subsequent
publication; it is not an OS memory quota or a power-loss guarantee.

This is decoded-byte migration, not preservation of historical compression ratios,
local code numbering, encryption claims or all historical archive variants.
Candidate standing and original source custody are unchanged.
