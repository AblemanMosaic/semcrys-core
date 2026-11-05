from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .core import (
    OCCURRENCE_MODES,
    PADDING_POLICIES,
    PADDING_NONE,
    PADDING_COUNT_AND_SIZE,
    POSITION_POLICIES,
    POSITION_PRESERVE,
    POSITION_CONCEAL,
    OCC_VISIBLE,
    OCC_HOMOPHONIC,
    OCC_UNIQUE,
    OUTER_CODECS,
    PLACEMENT_EXTERNAL,
    PLACEMENT_NONE,
    PLACEMENTS,
    ENVELOPES,
    ENVELOPE_BINARY,
    BODY_REPRESENTATIONS,
    BODY_PACKED_VARINT,
    ID_ORDERS,
    ORDER_FREQUENCY,
    PROFILES,
    LiteHold,
    build_legend,
    build_word_legend,
    build_assembly_legend,
    account_document,
    legend_disclosure,
    ladder_rungs,
    ladder_position,
    ladder_report,
    account_corpus,
    FIT_SELF,
    FIT_EXTERNAL,
    assembly_bytes,
    load_assembly_bytes,
    _base_events,
    PROFILE_WORD,
    canonical_bytes,
    decode_bytes,
    encode_bytes,
    rotate_protected_container,
    explain_container,
    inspect_container,
    legend_bytes,
    load_legend_bytes,
    write_atomic,
)
from .pedagogy import compare_bytes, demo_report


def _key(args: argparse.Namespace, *, required: bool = False) -> bytes | None:
    if getattr(args, "key_file", None):
        return args.key_file.read_bytes()
    name = getattr(args, "key_env", None)
    if name:
        value = os.environ.get(name)
        if value is None:
            if required:
                raise LiteHold("HELD_RUNTIME_KEY_ENV_MISSING", name)
            return None
        return value.encode("utf-8")
    return None


def _legend(path: Path | None) -> dict | None:
    return load_legend_bytes(path.read_bytes()) if path else None


def _moving(path: Path | None) -> dict | None:
    if path is None:
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as error:
        raise LiteHold("HELD_MOVING_LEGEND_MALFORMED", "INVALID_UTF8") from error
    except json.JSONDecodeError as error:
        raise LiteHold("HELD_MOVING_LEGEND_MALFORMED", "INVALID_JSON") from error
    if not isinstance(value, dict):
        raise LiteHold("HELD_MOVING_LEGEND_MALFORMED", "NOT_OBJECT")
    return value


def _emit(value: dict) -> None:
    print(canonical_bytes(value).decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="semcrys-lite", description="SemCrys-Lite candidate universal byte-to-integer reference codec")
    sub = parser.add_subparsers(dest="command", required=True)

    enc = sub.add_parser("encode")
    enc.add_argument("source", type=Path)
    enc.add_argument("output", type=Path)
    enc.add_argument("--profile", choices=PROFILES, default=PROFILES[0])
    enc.add_argument("--legend", type=Path)
    enc.add_argument("--legend-out", type=Path)
    enc.add_argument("--moving-legend-out", type=Path)
    enc.add_argument("--legend-placement", choices=PLACEMENTS)
    enc.add_argument("--legend-order", choices=ID_ORDERS, default=ORDER_FREQUENCY)
    enc.add_argument("--assembly-legend", type=Path)
    enc.add_argument("--body-representation", choices=BODY_REPRESENTATIONS, default=BODY_PACKED_VARINT)
    enc.add_argument("--envelope", choices=ENVELOPES, default=ENVELOPE_BINARY)
    enc.add_argument("--occurrence", choices=OCCURRENCE_MODES, default=OCCURRENCE_MODES[0])
    enc.add_argument("--alias-limit", type=int, default=1)
    enc.add_argument("--padding", choices=PADDING_POLICIES, default=PADDING_NONE)
    enc.add_argument("--padding-bucket", type=int)
    enc.add_argument("--position", choices=POSITION_POLICIES, default=POSITION_PRESERVE)
    enc.add_argument("--security-preset", choices=(
        "standard", "homophonic", "homophonic-positional", "maximum-concealment",
        "private-balanced", "private-maximum",
    ))
    enc.add_argument("--outer", choices=OUTER_CODECS, default=OUTER_CODECS[0])
    enc.add_argument("--key-file", type=Path)
    enc.add_argument("--key-env", default="SEMCRYS_LITE_KEY")
    enc.add_argument("--receipt", type=Path)

    dec = sub.add_parser("decode")
    dec.add_argument("source", type=Path)
    dec.add_argument("output", type=Path)
    dec.add_argument("--legend", type=Path)
    dec.add_argument("--moving-legend", type=Path)
    dec.add_argument("--assembly-legend", type=Path)
    dec.add_argument("--key-file", type=Path)
    dec.add_argument("--key-env", default="SEMCRYS_LITE_KEY")
    dec.add_argument("--receipt", type=Path)

    rot = sub.add_parser("rotate-key", help="Rewrap a protected moving legend without recompressing source data")
    rot.add_argument("source", type=Path)
    rot.add_argument("moving_legend", type=Path)
    rot.add_argument("output", type=Path)
    rot.add_argument("moving_legend_out", type=Path)
    rot.add_argument("--old-key-file", type=Path)
    rot.add_argument("--old-key-env", default="SEMCRYS_LITE_OLD_KEY")
    rot.add_argument("--new-key-file", type=Path)
    rot.add_argument("--new-key-env", default="SEMCRYS_LITE_NEW_KEY")
    rot.add_argument("--receipt", type=Path)

    ins = sub.add_parser("inspect")
    ins.add_argument("source", type=Path)
    ins.add_argument("--body", action="store_true", help="include the decoded logical JSON event body")

    exp = sub.add_parser("explain")
    exp.add_argument("source", type=Path)

    sub.add_parser("demo")

    cmp = sub.add_parser("compare")
    cmp.add_argument("source", type=Path)
    cmp.add_argument("--key-file", type=Path)
    cmp.add_argument("--key-env", default="SEMCRYS_LITE_KEY")

    leg = sub.add_parser("legend")
    leg.add_argument("output", type=Path)
    leg.add_argument("--source", type=Path)
    leg.add_argument("--universal-bytes", action="store_true")
    leg.add_argument("--words", action="store_true")
    leg.add_argument("--order", choices=ID_ORDERS, default=ORDER_FREQUENCY)

    lad = sub.add_parser("ladder")
    lad.add_argument("--container", type=Path)
    lad.add_argument("--source", type=Path)
    lad.add_argument("--legend", type=Path)
    lad.add_argument("--assembly-legend", type=Path)
    lad.add_argument("--key-file", type=Path)
    lad.add_argument("--key-env", default="SEMCRYS_LITE_KEY")

    dis = sub.add_parser("disclosure")
    dis.add_argument("legend", type=Path)
    dis.add_argument("--source", type=Path)

    acct = sub.add_parser("account")
    acct.add_argument("source", type=Path)
    acct.add_argument("--legend", type=Path, required=True)
    acct.add_argument("--assembly-legend", type=Path)
    acct.add_argument("--self-fitted", action="store_true")

    corp = sub.add_parser("corpus")
    corp.add_argument("--legend", type=Path, required=True)
    corp.add_argument("--assembly-legend", type=Path)
    corp.add_argument("--document", type=Path, action="append", required=True)
    corp.add_argument("--self-fitted", action="store_true")

    asm = sub.add_parser("assembly")
    asm.add_argument("output", type=Path)
    asm.add_argument("--base", type=Path, required=True)
    asm.add_argument("--corpus", type=Path, action="append", required=True)
    asm.add_argument("--max-rules", type=int, default=65536)

    args = parser.parse_args(argv)
    try:
        if args.command == "ladder":
            if args.container:
                _emit(ladder_position(args.container.read_bytes()))
            elif args.source and args.legend:
                _emit(ladder_report(
                    args.source.read_bytes(),
                    legend=load_legend_bytes(args.legend.read_bytes()),
                    assembly=load_assembly_bytes(args.assembly_legend.read_bytes()) if args.assembly_legend else None,
                    key=_key(args),
                ))
            else:
                _emit(ladder_rungs())
            return 0
        if args.command == "disclosure":
            _emit(legend_disclosure(
                load_legend_bytes(args.legend.read_bytes()),
                args.source.read_bytes() if args.source else None,
            ))
            return 0
        if args.command in {"account", "corpus"}:
            base = load_legend_bytes(args.legend.read_bytes())
            asm_value = load_assembly_bytes(args.assembly_legend.read_bytes()) if args.assembly_legend else None
            provenance = FIT_SELF if args.self_fitted else FIT_EXTERNAL
            if args.command == "account":
                _emit(account_document(args.source.read_bytes(), legend=base, assembly=asm_value, fit_provenance=provenance))
            else:
                _emit(account_corpus([p.read_bytes() for p in args.document], legend=base, assembly=asm_value, fit_provenance=provenance))
            return 0
        if args.command == "assembly":
            base = load_legend_bytes(args.base.read_bytes())
            streams = [_base_events(path.read_bytes(), PROFILE_WORD, base)[0] for path in args.corpus]
            value = build_assembly_legend(streams, base, max_rules=args.max_rules)
            write_atomic(args.output, assembly_bytes(value))
            _emit({"status": "PASS", "assembly_root": value["assembly_root"], "entries": value["entry_count"],
                   "base_legend_root": value["base_legend_root"], "fitted_stream_count": value["fitted_stream_count"],
                   "relationship": value["relationship"], "standing": value["standing"]})
            return 0
        if args.command == "legend":
            if args.universal_bytes == (args.source is not None):
                raise LiteHold("HELD_LEGEND_BUILD_MODE", "choose exactly one of --source or --universal-bytes")
            if args.words:
                if args.universal_bytes:
                    raise LiteHold("HELD_LEGEND_BUILD_MODE", "--words requires --source")
                value = build_word_legend(args.source.read_bytes(), id_order=args.order)
            else:
                value = build_legend(b"" if args.universal_bytes else args.source.read_bytes(), universal=args.universal_bytes)
            write_atomic(args.output, legend_bytes(value))
            _emit({"status": "PASS", "legend_root": value["legend_root"], "kind": value["kind"], "entries": value["entry_count"], "standing": value["standing"]})
            return 0
        if args.command == "inspect":
            _emit(inspect_container(args.source.read_bytes(), include_body=args.body))
            return 0
        if args.command == "explain":
            _emit(explain_container(args.source.read_bytes()))
            return 0
        if args.command == "demo":
            _emit(demo_report())
            return 0
        if args.command == "compare":
            _emit(compare_bytes(args.source.read_bytes(), key=_key(args)))
            return 0
        if args.command == "encode":
            if args.security_preset:
                if (args.occurrence != OCC_VISIBLE or args.padding != PADDING_NONE
                        or args.padding_bucket is not None or args.alias_limit != 1
                        or args.position != POSITION_PRESERVE):
                    raise LiteHold("HELD_SECURITY_PRESET_CONFLICT", "do not combine preset with occurrence/padding/alias overrides")
                if args.security_preset == "homophonic":
                    args.occurrence = OCC_HOMOPHONIC
                    args.alias_limit = 8
                elif args.security_preset == "homophonic-positional":
                    args.occurrence = OCC_HOMOPHONIC
                    args.position = POSITION_CONCEAL
                    args.alias_limit = 8
                elif args.security_preset == "maximum-concealment":
                    args.occurrence = OCC_UNIQUE
                    args.padding = PADDING_COUNT_AND_SIZE
                elif args.security_preset == "private-balanced":
                    args.occurrence = OCC_HOMOPHONIC
                    args.padding = PADDING_COUNT_AND_SIZE
                    args.alias_limit = 8
                elif args.security_preset == "private-maximum":
                    args.occurrence = OCC_UNIQUE
                    args.padding = PADDING_COUNT_AND_SIZE
            key = _key(args, required=True) if args.occurrence != "REPETITION_VISIBLE" else None
            container, external_base, moving, receipt = encode_bytes(
                args.source.read_bytes(), profile=args.profile, legend=_legend(args.legend),
                legend_placement=args.legend_placement, occurrence_mode=args.occurrence, id_order=args.legend_order,
                assembly=load_assembly_bytes(args.assembly_legend.read_bytes()) if args.assembly_legend else None,
                body_representation=args.body_representation, envelope=args.envelope,
                alias_limit=args.alias_limit, key=key, outer_codec=args.outer,
                padding_policy=args.padding, padding_bucket=args.padding_bucket,
                position_policy=args.position,
            )
            if external_base is not None:
                if args.legend_out is None:
                    raise LiteHold("HELD_LEGEND_OUTPUT_REQUIRED")
                write_atomic(args.legend_out, legend_bytes(external_base))
            if moving is not None:
                if args.moving_legend_out is None:
                    raise LiteHold("HELD_MOVING_LEGEND_OUTPUT_REQUIRED")
                write_atomic(args.moving_legend_out, canonical_bytes(moving) + b"\n")
            write_atomic(args.output, container)
            if args.receipt:
                write_atomic(args.receipt, canonical_bytes(receipt) + b"\n")
            _emit(receipt)
            return 0
        if args.command == "rotate-key":
            def key_from(file_path: Path | None, env_name: str) -> bytes:
                if file_path is not None:
                    return file_path.read_bytes()
                value = os.environ.get(env_name)
                if value is None:
                    raise LiteHold("HELD_RUNTIME_KEY_ENV_MISSING", env_name)
                return value.encode("utf-8")
            rotated, new_moving, receipt = rotate_protected_container(
                args.source.read_bytes(),
                _moving(args.moving_legend),
                old_key=key_from(args.old_key_file, args.old_key_env),
                new_key=key_from(args.new_key_file, args.new_key_env),
            )
            write_atomic(args.output, rotated)
            write_atomic(args.moving_legend_out, canonical_bytes(new_moving) + b"\n")
            if args.receipt:
                write_atomic(args.receipt, canonical_bytes(receipt) + b"\n")
            _emit(receipt)
            return 0
        if args.command == "decode":
            restored, receipt = decode_bytes(args.source.read_bytes(), legend=_legend(args.legend), moving_legend=_moving(args.moving_legend), key=_key(args), assembly=load_assembly_bytes(args.assembly_legend.read_bytes()) if args.assembly_legend else None)
            write_atomic(args.output, restored)
            if args.receipt:
                write_atomic(args.receipt, canonical_bytes(receipt) + b"\n")
            _emit(receipt)
            return 0
        raise LiteHold("HELD_COMMAND_UNSUPPORTED", str(args.command))
    except (LiteHold, FileNotFoundError, PermissionError) as error:
        hold = error if isinstance(error, LiteHold) else LiteHold("HELD_IO", f"{type(error).__name__}:{error}")
        _emit(hold.record())
        return 1
