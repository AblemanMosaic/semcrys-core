# Negative boundaries

- Whole input and event arrays are materialized in memory.
- No large-input streaming claim.
- No phrase, language, GTK, GCNL, morphology, or semantic-sense claim.
- No end-to-end cryptographic-confidentiality claim. AES-256-GCM integration is
  tested, but key management, protocol composition, metadata leakage, endpoint
  compromise, and independent cryptanalysis remain outside the claim.
- Full-unique reveals event count; bounded aliases reveal bounded recurrence.
- The concealment extra is not stdlib-only and must be installed separately.
- No independent cryptanalysis.
- No compression-superiority claim.
- No full-SemCrys cross-decoder compatibility claim.
- The v0.2 reader is a bounded compatibility path; the encoder emits only v0.3.
- Direct JSON events are intentionally verbose. They are not evidence about
  the full application's packed-body compression performance.
- No release, admission, production routing, or canonical mutation.
