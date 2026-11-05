from __future__ import annotations

import argparse
import json
from pathlib import Path

from semcrys.configuration_court import CONTROL_CODECS, run
from streaming_app.core import REQUESTABLE_OUTER_CODECS


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the general bounded SemCrys configuration court.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--legend", action="append", type=Path, required=True)
    parser.add_argument("--semcrys-codec", action="append", choices=REQUESTABLE_OUTER_CODECS)
    parser.add_argument("--control-codec", action="append", choices=CONTROL_CODECS)
    parser.add_argument("--horizon", action="append", type=int)
    parser.add_argument("--receiver-root", action="append", default=[])
    parser.add_argument("--label", default="UNSPECIFIED_EXACT_WORKLOAD")
    parser.add_argument("--lookup-cache-root", type=Path)
    args = parser.parse_args()
    result = run(
        args.source,
        args.output,
        library_path=args.library,
        legends=args.legend,
        semcrys_codecs=args.semcrys_codec or ("NONE", "LZMA", "BZ2_9"),
        control_codecs=args.control_codec or CONTROL_CODECS,
        horizons=args.horizon or (1, 2, 4, 8, 16, 32),
        receiver_roots=args.receiver_root,
        qualification_label=args.label,
        lookup_cache_root=args.lookup_cache_root,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
