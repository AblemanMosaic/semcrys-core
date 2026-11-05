# Lite → full SemCrys crosswalk

| Semantic role | Lite | Full | Boundary |
|---|---|---|---|
| Lossless unit | byte or word/separator token | raw byte or `UNICODE_CATEGORY_LOSSLESS_V1` unit | Tokenizers correspond; spans and bytes differ. |
| Event body | packed varint (default) or JSON events | packed varint/binary body | Same role, different ABI. |
| Vocabulary | local/pre-shared word or byte `.leg` | binary Union/Ultra/domain/delta `.leg` | Never silently interchangeable. |
| Composition | adjacent-pair assembly | local/form/fold/second-pass families | Related mechanism class, not identity. |
| Accounting | exact `.crys` + exact `.leg` bytes | exact realized dependency artifacts | Same rule, distinct formats. |
| Disclosure | source-conditioned measurement | `synchronize disclosure` | Observational, not a security theorem. |
| Recurrence placement | L0–L3 ladder | occurrence-topology successor | Candidate correspondence, not merged implementation. |

The shared contract is `shared/EVENT_MODEL_CONTRACT.json` in the synchronization
package. Neither dialect decodes the other, and the crosswalk grants no release,
admission, compression-superiority, or confidentiality claim.
