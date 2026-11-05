# Fixtures

`sample.txt` is the shared synchronization sample.

`accounting-size-stub.crys` and `accounting-size-stub.leg` exist so that
`semcrys synchronize account` has artifacts whose **sizes** it can read. That
surface stats files; it does not decode them.

The stub is **not a decodable container**. Its configuration declares
`fixture_kind: SIZE_STUB_NOT_DECODABLE`, and attempting to decode it refuses with
`HELD_CONFIGURATION_FIELDS`. That refusal is correct behaviour, not a defect.

Nothing here is evidence. These files deliberately live outside `evidence/` so
that no artifact under `evidence/` implies a capability it does not have.
