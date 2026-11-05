# Contributing

SemCrys changes must preserve exact reconstruction, typed refusal, format
compatibility, and the claim boundaries in `RELEASE_CONTRACT.json`.

Before opening a pull request:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -B -m unittest discover -s tests -v
python -B tools\verify_wikipedia_evidence.py
python -B tools\verify_integerization_performance_evidence.py
python -B tools\run_publication_court.py
```

Changes to codecs, manifests, native kernels, Ultra identity, security
profiles, or benchmark claims must include corresponding tests and regenerated
rooted evidence. Do not commit generated `dist/`, `release-work/`, cache, or
credential material.
