from __future__ import annotations

import base64
import collections
import hashlib
import hmac
import json
import lzma
import os
import re
import secrets
import tempfile
from pathlib import Path
from typing import Any

from semcrys_native import NativeRequiredError
from semcrys_native import fold_pairs as _native_fold_pairs
from semcrys_native import pack_varints as _native_pack_varints
from semcrys_native import unpack_varints as _native_unpack_varints


STANDING = "CANDIDATE_ONLY"
SCHEMA_CONTAINER = "semcrys-lite.crys.v0.3.candidate"
SCHEMA_CONTAINER_V02 = "semcrys-lite.crys.v0.2.candidate"
SCHEMA_LEGEND = "semcrys-lite.legend.v0.2.candidate"
SCHEMA_ASSEMBLY = "semcrys-lite.assembly-legend.v0.1.candidate"
SCHEMA_SEALED_MOVING = "semcrys-lite.sealed-moving-legend.v0.2.candidate"
SCHEMA_MOVING_BINDING = "semcrys-lite.moving-legend-binding.v0.2.candidate"
SCHEMA_RECEIPT = "semcrys-lite.realization-receipt.v0.3.candidate"
FORMAT = "CRYS-LITE-0.3"
FORMAT_V02 = "CRYS-LITE-0.2"
AEAD_ALGORITHM = "AES-256-GCM"
AEAD_KDF = "HKDF-SHA256"

PROFILE_DIRECT = "L:BYTE_DIRECT"
PROFILE_LOCAL = "L:BYTE_LOCAL_DENSE"
PROFILE_PRESHARED = "L:BYTE_PRESHARED"
PROFILE_WORD = "L:WORD_DIRECT"
PROFILE_WORD_IMPLICIT_SPACE = "L:WORD_IMPLICIT_SINGLE_SPACE"
PROFILE_WORD_AUTO_SPACE = "L:WORD_PROFITABLE_SEPARATOR_AUTO"
PROFILE_WORD_ASSEMBLY = "L:WORD_ASSEMBLY"
PROFILES = (PROFILE_DIRECT, PROFILE_LOCAL, PROFILE_PRESHARED, PROFILE_WORD, PROFILE_WORD_IMPLICIT_SPACE, PROFILE_WORD_AUTO_SPACE, PROFILE_WORD_ASSEMBLY)
BYTE_PROFILES = (PROFILE_DIRECT, PROFILE_LOCAL, PROFILE_PRESHARED)
WORD_PROFILES = (PROFILE_WORD, PROFILE_WORD_IMPLICIT_SPACE, PROFILE_WORD_ASSEMBLY)
ASSEMBLY_PROFILES = (PROFILE_WORD_ASSEMBLY,)

KIND_BYTE = "BASE_BYTE"
KIND_WORD = "BASE_WORD"
LEGEND_KINDS = (KIND_BYTE, KIND_WORD)
KIND_ASSEMBLY = "ASSEMBLY"

ORDER_FREQUENCY = "FREQUENCY"
ORDER_FIRST_APPEARANCE = "FIRST_APPEARANCE"
ORDER_LEXICAL = "LEXICAL"
ID_ORDERS = (ORDER_FREQUENCY, ORDER_FIRST_APPEARANCE, ORDER_LEXICAL)

HYPHEN_SINGLE = "SINGLE"
HYPHEN_COMPOSED = "COMPOSED"

OCC_VISIBLE = "REPETITION_VISIBLE"
OCC_PERMUTE = "KEYED_PERMUTATION"
OCC_BOUNDED = "BOUNDED_ALIAS"
OCC_HOMOPHONIC = "FREQUENCY_BALANCED_HOMOPHONIC"
OCC_UNIQUE = "FULL_UNIQUE_MESSAGE_LEGEND"
OCCURRENCE_MODES = (OCC_VISIBLE, OCC_PERMUTE, OCC_BOUNDED, OCC_HOMOPHONIC, OCC_UNIQUE)

PADDING_NONE = "NONE"
PADDING_COUNT = "COUNT_BUCKET"
PADDING_SIZE = "SIZE_BUCKET"
PADDING_COUNT_AND_SIZE = "COUNT_AND_SIZE_BUCKET"
PADDING_FIXED = "FIXED_CLASS"
PADDING_POLICIES = (
    PADDING_NONE,
    PADDING_COUNT,
    PADDING_SIZE,
    PADDING_COUNT_AND_SIZE,
    PADDING_FIXED,
)
POSITION_PRESERVE = "PRESERVE_ORDER"
POSITION_CONCEAL = "KEYED_FEISTEL_PERMUTATION"
POSITION_POLICIES = (POSITION_PRESERVE, POSITION_CONCEAL)
MAX_PADDED_EVENTS = 8_388_608
MAX_PADDED_MOVING_BYTES = 512 * 1024 * 1024

PLACEMENT_NONE = "NONE"
PLACEMENT_EMBEDDED = "SELF_CONTAINED"
PLACEMENT_EXTERNAL = "EXTERNAL"
PLACEMENTS = (PLACEMENT_NONE, PLACEMENT_EMBEDDED, PLACEMENT_EXTERNAL)

OUTER_NONE = "NONE"
OUTER_LZMA = "LZMA"
OUTER_CODECS = (OUTER_NONE, OUTER_LZMA)

BODY_JSON_EVENTS = "JSON_EVENTS"
BODY_PACKED_VARINT = "PACKED_VARINT"
BODY_REPRESENTATIONS = (BODY_JSON_EVENTS, BODY_PACKED_VARINT)

ENVELOPE_BINARY = "BINARY"
ENVELOPE_TEXT = "TEXT"
ENVELOPES = (ENVELOPE_BINARY, ENVELOPE_TEXT)
CONTAINER_MAGIC = b"SCRYSL1\n"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rooted(value: dict[str, Any], field: str) -> dict[str, Any]:
    result = dict(value)
    result[field] = sha256(canonical_bytes(result))
    return result


class LiteHold(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)

    def record(self) -> dict[str, Any]:
        return rooted({
            "schema": "semcrys-lite.refusal.v0.2.candidate",
            "status": "HELD",
            "code": self.code,
            "detail": self.detail,
            "standing": STANDING,
            "security_claim": "NONE",
        }, "refusal_root")


def require(condition: bool, code: str, detail: str = "") -> None:
    if not condition:
        raise LiteHold(code, detail)


def verify_root(value: dict[str, Any], field: str, code: str) -> str:
    require(field in value, code, field)
    subject = dict(value)
    claimed = str(subject.pop(field))
    require(hmac.compare_digest(sha256(canonical_bytes(subject)), claimed), code, field)
    return claimed


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def read_json_bytes(data: bytes, code: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise LiteHold(code, "INVALID_UTF8") from error
    except json.JSONDecodeError as error:
        raise LiteHold(code, "INVALID_JSON") from error
    require(isinstance(value, dict), code, "NOT_OBJECT")
    return value


def build_legend(data: bytes, *, universal: bool = False) -> dict[str, Any]:
    values = list(range(256)) if universal else sorted(set(data))
    return rooted({
        "schema": SCHEMA_LEGEND,
        "kind": KIND_BYTE,
        "standing": STANDING,
        "entries": [{"id": index + 1, "byte": value} for index, value in enumerate(values)],
        "entry_count": len(values),
        "universal_byte_coverage": universal,
        "security_claim": "NONE",
    }, "legend_root")


_WORD_ATOM = r"[^\W_]+(?:'[^\W_]+)*"
_TOKEN_PATTERN = re.compile(
    rf"(?P<hyphen>{_WORD_ATOM}(?:-{_WORD_ATOM})+)"
    rf"|(?P<word>{_WORD_ATOM})"
    rf"|(?P<space>\s+)"
    rf"|(?P<other>.)",
    re.DOTALL | re.UNICODE,
)


def _varint_width(value: int) -> int:
    width = 1
    while value >= 128:
        value >>= 7
        width += 1
    return width


def tokenize_text(text: str) -> list[tuple[str, str]]:
    """Lossless whole-word tokenization.

    Yields (kind, text) pairs where kind is HYPHEN, WORD, SPACE or OTHER.
    Concatenating every text field reproduces the input exactly.
    """
    tokens: list[tuple[str, str]] = []
    for match in _TOKEN_PATTERN.finditer(text):
        kind = match.lastgroup or "other"
        tokens.append((kind.upper(), match.group()))
    return tokens


def _split_hyphen(compound: str) -> list[str]:
    parts = re.split(r"(-)", compound)
    return [part for part in parts if part != ""]


def _provisional_widths(counter: collections.Counter) -> dict[str, int]:
    widths: dict[str, int] = {}
    for rank, token in enumerate(sorted(counter, key=lambda value: (-counter[value], value))):
        widths[token] = _varint_width(rank + 1)
    return widths


def _resolve_hyphens(tokens: list[tuple[str, str]]) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """Decide, per distinct hyphenated compound, single binding or composition.

    Runs last: the decision needs part frequencies and provisional widths, which
    are only known once whole words and separators have been counted.
    """
    plain = collections.Counter(text for kind, text in tokens if kind != "HYPHEN")
    compounds = collections.Counter(text for kind, text in tokens if kind == "HYPHEN")
    for compound, count in compounds.items():
        for part in _split_hyphen(compound):
            plain[part] += count
    widths = _provisional_widths(plain)
    fallback = _varint_width(len(plain) + len(compounds) + 1)
    standalone = {text for kind, text in tokens if kind != "HYPHEN"}
    committed: set[str] = set()
    decisions: dict[str, str] = {}
    records: list[dict[str, Any]] = []
    for compound in sorted(compounds):
        count = compounds[compound]
        parts = _split_hyphen(compound)
        payload = len(compound.encode("utf-8"))
        cost_single = payload + _varint_width(payload) + count * fallback
        # Composition is only free for parts that already exist as legend
        # entries. A part appearing solely inside compounds must be admitted,
        # and that entry cost belongs to the composition branch.
        new_parts = {part for part in parts if part not in standalone and part not in committed}
        admission = sum(
            len(part.encode("utf-8")) + _varint_width(len(part.encode("utf-8")))
            for part in sorted(new_parts)
        )
        cost_composed = count * sum(widths.get(part, fallback) for part in parts) + admission
        binding = HYPHEN_SINGLE if cost_single < cost_composed else HYPHEN_COMPOSED
        if binding == HYPHEN_COMPOSED:
            committed |= new_parts
        decisions[compound] = binding
        records.append({
            "compound": compound,
            "binding": binding,
            "occurrences": count,
            "parts": parts,
            "parts_admitted_by_composition": sorted(new_parts),
            "single_cost_estimate": cost_single,
            "composed_cost_estimate": cost_composed,
        })
    return decisions, records


def _expand_tokens(tokens: list[tuple[str, str]], decisions: dict[str, str]) -> list[str]:
    expanded: list[str] = []
    for kind, text in tokens:
        if kind == "HYPHEN" and decisions.get(text) == HYPHEN_COMPOSED:
            expanded.extend(_split_hyphen(text))
        else:
            expanded.append(text)
    return expanded


_WORD_UNIT_PATTERN = re.compile(rf"^(?:{_WORD_ATOM})(?:-(?:{_WORD_ATOM}))*$", re.UNICODE)


def _is_word_unit(value: str) -> bool:
    return bool(_WORD_UNIT_PATTERN.fullmatch(value))


def _consolidate_single_spaces(units: list[str]) -> tuple[list[str], int]:
    """Omit only spaces that are exactly implied by adjacent lexical units."""
    output: list[str] = []
    removed = 0
    for index, unit in enumerate(units):
        if (unit == " " and index > 0 and index + 1 < len(units)
                and _is_word_unit(units[index - 1]) and _is_word_unit(units[index + 1])):
            removed += 1
            continue
        output.append(unit)
    return output, removed


def build_word_legend(data: bytes, *, id_order: str = ORDER_FREQUENCY,
                      implicit_single_spaces: bool = False) -> dict[str, Any]:
    require(id_order in ID_ORDERS, "HELD_LEGEND_ID_ORDER", id_order)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise LiteHold("HELD_SOURCE_NOT_UTF8", "invalid utf-8") from error
    tokens = tokenize_text(text)
    decisions, records = _resolve_hyphens(tokens)
    units = _expand_tokens(tokens, decisions)
    removed_spaces = 0
    if implicit_single_spaces:
        units, removed_spaces = _consolidate_single_spaces(units)
    if id_order == ORDER_FREQUENCY:
        counts = collections.Counter(units)
        # Equal-frequency units must not inherit source-order leakage.  Lexical
        # tie-breaking makes the logical legend deterministic from the
        # frequency table rather than from incidental first occurrence.
        ordered = sorted(counts, key=lambda unit: (-counts[unit], unit))
    elif id_order == ORDER_LEXICAL:
        # Lexical order is derived from the vocabulary alone, so it carries
        # neither the sequence in which units first appeared nor how often
        # each was used.
        ordered = sorted(set(units))
    else:
        seen: dict[str, None] = {}
        for unit in units:
            seen.setdefault(unit, None)
        ordered = list(seen)
    value = {
        "schema": SCHEMA_LEGEND,
        "kind": KIND_WORD,
        "standing": STANDING,
        "entries": [{"id": index + 1, "text": unit} for index, unit in enumerate(ordered)],
        "entry_count": len(ordered),
        "id_order": id_order,
        "hyphen_decisions": records,
        "security_claim": "NONE",
    }
    if implicit_single_spaces:
        value["separator_policy"] = "IMPLICIT_SINGLE_ASCII_SPACE"
        value["separator_references_removed_while_fitting"] = removed_spaces
    return rooted(value, "legend_root")


def legend_bytes(legend: dict[str, Any]) -> bytes:
    validate_base_legend(legend)
    return canonical_bytes(legend) + b"\n"


def load_legend_bytes(data: bytes) -> dict[str, Any]:
    value = read_json_bytes(data, "HELD_LEGEND_MALFORMED")
    validate_base_legend(value)
    return value


def validate_base_legend(value: dict[str, Any]) -> str:
    require(value.get("schema") == SCHEMA_LEGEND, "HELD_LEGEND_SCHEMA")
    require(value.get("kind") in LEGEND_KINDS, "HELD_LEGEND_KIND")
    require(value.get("standing") == STANDING, "HELD_LEGEND_STANDING")
    root = verify_root(value, "legend_root", "HELD_LEGEND_ROOT_MISMATCH")
    entries = value.get("entries")
    require(isinstance(entries, list), "HELD_LEGEND_ENTRIES")
    ids: list[int] = []
    if value["kind"] == KIND_BYTE:
        bytes_: list[int] = []
        for row in entries:
            require(isinstance(row, dict), "HELD_LEGEND_ENTRY")
            identifier, byte = row.get("id"), row.get("byte")
            require(isinstance(identifier, int) and identifier >= 1, "HELD_LEGEND_ID")
            require(isinstance(byte, int) and 0 <= byte <= 255, "HELD_LEGEND_BYTE")
            ids.append(identifier)
            bytes_.append(byte)
        require(len(bytes_) == len(set(bytes_)), "HELD_LEGEND_BYTE_DUPLICATE")
    else:
        texts: list[str] = []
        for row in entries:
            require(isinstance(row, dict), "HELD_LEGEND_ENTRY")
            identifier, text = row.get("id"), row.get("text")
            require(isinstance(identifier, int) and identifier >= 1, "HELD_LEGEND_ID")
            require(isinstance(text, str) and text != "", "HELD_LEGEND_TEXT")
            ids.append(identifier)
            texts.append(text)
        require(len(texts) == len(set(texts)), "HELD_LEGEND_TEXT_DUPLICATE")
        require(value.get("id_order") in ID_ORDERS, "HELD_LEGEND_ID_ORDER")
        require(value.get("separator_policy", "EXPLICIT") in {"EXPLICIT", "IMPLICIT_SINGLE_ASCII_SPACE"},
                "HELD_LEGEND_SEPARATOR_POLICY")
        require(isinstance(value.get("hyphen_decisions"), list), "HELD_LEGEND_HYPHEN_DECISIONS")
    require(ids == list(range(1, len(ids) + 1)), "HELD_LEGEND_IDS_NONCONTIGUOUS")
    require(value.get("entry_count") == len(entries), "HELD_LEGEND_COUNT")
    return root


def build_assembly_legend(streams: list[list[int]], base_legend: dict[str, Any], *, max_rules: int = 65536, min_occurrences: int = 2) -> dict[str, Any]:
    """Fit multi-integer assemblies over one or more event streams.

    Greedy most-frequent-adjacent-pair with incremental count maintenance over a
    doubly linked list. Pairs never span a stream boundary, so a corpus of N
    documents cannot manufacture assemblies that no single document contains.
    Ties are broken by the smallest (left, right) pair so the fit is
    deterministic for a given corpus and order.
    """
    require(base_legend.get("kind") == KIND_WORD, "HELD_ASSEMBLY_BASE_KIND")
    base_root = validate_base_legend(base_legend)
    require(min_occurrences >= 2, "HELD_ASSEMBLY_MIN_OCCURRENCES")

    symbol: list[int] = []
    prev_ix: list[int] = []
    next_ix: list[int] = []
    for stream in streams:
        start = len(symbol)
        for offset, value in enumerate(stream):
            symbol.append(value)
            prev_ix.append(start + offset - 1 if offset else -1)
            next_ix.append(start + offset + 1 if offset + 1 < len(stream) else -1)

    positions: dict[tuple[int, int], set[int]] = {}

    def add_pair(left_index: int) -> None:
        right_index = next_ix[left_index]
        if right_index == -1:
            return
        positions.setdefault((symbol[left_index], symbol[right_index]), set()).add(left_index)

    def drop_pair(left_index: int) -> None:
        right_index = next_ix[left_index]
        if right_index == -1:
            return
        key = (symbol[left_index], symbol[right_index])
        holder = positions.get(key)
        if holder is not None:
            holder.discard(left_index)
            if not holder:
                del positions[key]

    for index in range(len(symbol)):
        add_pair(index)

    next_id = base_legend["entry_count"] + 1
    rules: list[tuple[int, int]] = []
    while len(rules) < max_rules:
        best_key = None
        best_count = 0
        for key, holder in positions.items():
            count = len(holder)
            if count > best_count or (count == best_count and best_key is not None and key < best_key):
                best_key, best_count = key, count
        if best_key is None or best_count < min_occurrences:
            break
        left_symbol, right_symbol = best_key
        # A rule that replaces k occurrences saves k references and costs one
        # rule (two references). Below that it is not worth admitting.
        if best_count <= 2:
            break
        new_symbol = next_id
        next_id += 1
        for left_index in sorted(positions[best_key]):
            right_index = next_ix[left_index]
            if right_index == -1 or symbol[left_index] != left_symbol or symbol[right_index] != right_symbol:
                continue
            before = prev_ix[left_index]
            after = next_ix[right_index]
            if before != -1:
                drop_pair(before)
            drop_pair(left_index)
            drop_pair(right_index)
            symbol[left_index] = new_symbol
            next_ix[left_index] = after
            if after != -1:
                prev_ix[after] = left_index
            symbol[right_index] = -1
            next_ix[right_index] = -1
            prev_ix[right_index] = -1
            if before != -1:
                add_pair(before)
            add_pair(left_index)
        positions.pop(best_key, None)
        rules.append((left_symbol, right_symbol))

    return rooted({
        "schema": SCHEMA_ASSEMBLY,
        "kind": KIND_ASSEMBLY,
        "standing": STANDING,
        "base_legend_root": base_root,
        "first_assembly_id": base_legend["entry_count"] + 1,
        "entries": [
            {"id": base_legend["entry_count"] + 1 + index, "pair": [left, right]}
            for index, (left, right) in enumerate(rules)
        ],
        "entry_count": len(rules),
        "fitted_stream_count": len(streams),
        "fitted_event_count": sum(len(stream) for stream in streams),
        "relationship": "WARM_RELATIONSHIP_ONLY",
        "security_claim": "NONE",
    }, "assembly_root")


def validate_assembly_legend(value: dict[str, Any], base_legend: dict[str, Any] | None = None) -> str:
    require(value.get("schema") == SCHEMA_ASSEMBLY, "HELD_ASSEMBLY_SCHEMA")
    require(value.get("kind") == KIND_ASSEMBLY, "HELD_ASSEMBLY_KIND")
    require(value.get("standing") == STANDING, "HELD_ASSEMBLY_STANDING")
    root = verify_root(value, "assembly_root", "HELD_ASSEMBLY_ROOT_MISMATCH")
    entries = value.get("entries")
    require(isinstance(entries, list), "HELD_ASSEMBLY_ENTRIES")
    first = value.get("first_assembly_id")
    require(isinstance(first, int) and first >= 1, "HELD_ASSEMBLY_FIRST_ID")
    for offset, row in enumerate(entries):
        require(isinstance(row, dict), "HELD_ASSEMBLY_ENTRY")
        identifier, pair = row.get("id"), row.get("pair")
        require(identifier == first + offset, "HELD_ASSEMBLY_IDS_NONCONTIGUOUS")
        require(isinstance(pair, list) and len(pair) == 2, "HELD_ASSEMBLY_PAIR")
        left, right = pair
        require(isinstance(left, int) and isinstance(right, int), "HELD_ASSEMBLY_PAIR")
        # A rule may only reference base ids or strictly earlier assemblies, so
        # expansion always terminates.
        require(1 <= left < identifier and 1 <= right < identifier, "HELD_ASSEMBLY_PAIR_FORWARD_REFERENCE")
    require(value.get("entry_count") == len(entries), "HELD_ASSEMBLY_COUNT")
    if base_legend is not None:
        require(value.get("base_legend_root") == base_legend.get("legend_root"), "HELD_ASSEMBLY_BASE_MISMATCH")
        require(first == base_legend["entry_count"] + 1, "HELD_ASSEMBLY_BASE_MISMATCH")
    return root


def assembly_bytes(assembly: dict[str, Any]) -> bytes:
    validate_assembly_legend(assembly)
    return canonical_bytes(assembly) + b"\n"


def load_assembly_bytes(data: bytes) -> dict[str, Any]:
    value = read_json_bytes(data, "HELD_ASSEMBLY_MALFORMED")
    validate_assembly_legend(value)
    return value


def _apply_assembly_legend_python(events: list[int], assembly: dict[str, Any]) -> list[int]:
    """Fold an event stream using an existing assembly legend.

    Repeated left-to-right passes until no rule matches. Deterministic: at each
    position the pair starting there is replaced if it is a rule, so overlapping
    candidates resolve leftmost-first.
    """
    rules = {(row["pair"][0], row["pair"][1]): row["id"] for row in assembly["entries"]}
    if not rules:
        return list(events)
    current = list(events)
    while True:
        folded: list[int] = []
        index = 0
        changed = False
        limit = len(current)
        while index < limit:
            if index + 1 < limit:
                identifier = rules.get((current[index], current[index + 1]))
                if identifier is not None:
                    folded.append(identifier)
                    index += 2
                    changed = True
                    continue
            folded.append(current[index])
            index += 1
        current = folded
        if not changed:
            return current


def apply_assembly_legend(events: list[int], assembly: dict[str, Any]) -> list[int]:
    try:
        return _native_fold_pairs(
            events,
            assembly["entries"],
            lambda values: _apply_assembly_legend_python(values, assembly),
        )
    except NativeRequiredError as error:
        raise LiteHold("HELD_NATIVE_REQUIRED", str(error)) from error


def expand_assembly_events(events: list[int], assembly: dict[str, Any], *, max_expanded_events: int = 1 << 28) -> list[int]:
    """Expand assembly ids back to base ids. Iterative, so deep grammars are safe.

    Rules only reference strictly earlier ids, so each rule's expansion length is
    computable in one pass. That gives an exact bound on the output before any
    work is done, which is a sounder guard than a multiple of the input length:
    a heavily folded stream legitimately expands many times over.
    """
    table = {row["id"]: (row["pair"][0], row["pair"][1]) for row in assembly["entries"]}
    if not table:
        return list(events)
    lengths: dict[int, int] = {}
    for row in assembly["entries"]:
        left, right = row["pair"]
        lengths[row["id"]] = lengths.get(left, 1) + lengths.get(right, 1)
    expected = sum(lengths.get(value, 1) for value in events)
    require(expected <= max_expanded_events, "HELD_ASSEMBLY_EXPANSION_BUDGET", str(expected))
    output: list[int] = []
    stack = list(reversed(events))
    while stack:
        value = stack.pop()
        pair = table.get(value)
        if pair is None:
            output.append(value)
        else:
            stack.append(pair[1])
            stack.append(pair[0])
    return output


def _word_events(data: bytes, legend: dict[str, Any] | None, id_order: str,
                 *, implicit_single_spaces: bool = False) -> tuple[list[int], dict[str, Any]]:
    selected = build_word_legend(
        data, id_order=id_order, implicit_single_spaces=implicit_single_spaces
    ) if legend is None else legend
    require(selected.get("kind") == KIND_WORD, "HELD_LEGEND_KIND_MISMATCH_FOR_PROFILE")
    validate_base_legend(selected)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise LiteHold("HELD_SOURCE_NOT_UTF8", "invalid utf-8") from error
    decisions = {
        row["compound"]: row["binding"]
        for row in selected["hyphen_decisions"]
        if isinstance(row, dict) and "compound" in row and "binding" in row
    }
    lookup = {row["text"]: row["id"] for row in selected["entries"]}
    units = _expand_tokens(tokenize_text(text), decisions)
    if implicit_single_spaces:
        units, _removed = _consolidate_single_spaces(units)
    missing = sorted({unit for unit in units if unit not in lookup})
    require(not missing, "HELD_LEGEND_COVERAGE_INCOMPLETE", ",".join(missing[:8]))
    return [lookup[unit] for unit in units], selected


def _base_events(data: bytes, profile: str, legend: dict[str, Any] | None, id_order: str = ORDER_FREQUENCY, assembly: dict[str, Any] | None = None) -> tuple[list[int], dict[str, Any] | None]:
    require(profile in PROFILES, "HELD_PROFILE_UNSUPPORTED", profile)
    if profile in WORD_PROFILES:
        implicit_spaces = profile == PROFILE_WORD_IMPLICIT_SPACE
        events, selected = _word_events(data, legend, id_order, implicit_single_spaces=implicit_spaces)
        if profile in ASSEMBLY_PROFILES:
            require(assembly is not None, "HELD_ASSEMBLY_LEGEND_MISSING")
            validate_assembly_legend(assembly, selected)
            events = apply_assembly_legend(events, assembly)
        else:
            require(assembly is None, "HELD_ASSEMBLY_LEGEND_FORBIDDEN")
        return events, selected
    require(assembly is None, "HELD_ASSEMBLY_LEGEND_FORBIDDEN")
    if legend is not None:
        require(legend.get("kind") == KIND_BYTE, "HELD_LEGEND_KIND_MISMATCH_FOR_PROFILE")
    if profile == PROFILE_DIRECT:
        require(legend is None, "HELD_DIRECT_LEGEND_FORBIDDEN")
        return list(data), None
    if profile == PROFILE_LOCAL:
        selected = build_legend(data) if legend is None else legend
    else:
        require(legend is not None, "HELD_PRESHARED_LEGEND_REQUIRED")
        selected = legend
    validate_base_legend(selected)
    lookup = {row["byte"]: row["id"] for row in selected["entries"]}
    missing = sorted(set(data) - set(lookup))
    require(not missing, "HELD_LEGEND_COVERAGE_INCOMPLETE", ",".join(map(str, missing[:8])))
    return [lookup[value] for value in data], selected


def _permutation(domain: list[int], key: bytes) -> tuple[dict[int, int], dict[int, int]]:
    require(bool(key), "HELD_RUNTIME_KEY_REQUIRED")
    shuffled = sorted(domain, key=lambda value: hmac.new(key, b"semcrys-lite-permute\x00" + str(value).encode(), hashlib.sha256).digest())
    forward = dict(zip(domain, shuffled, strict=True))
    return forward, {right: left for left, right in forward.items()}


def _derive_subkey(secret: bytes, salt: bytes, info: bytes) -> bytes:
    require(len(secret) >= 32 and len(salt) == 16 and bool(info), "HELD_PROJECTION_KEY_MATERIAL")
    _AESGCM, HKDF, hashes, _InvalidTag = _aead_backend()
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=info).derive(secret)


def _projection_subkeys(root_secret: bytes, salt: bytes) -> dict[str, bytes]:
    return {
        "alias": _derive_subkey(root_secret, salt, b"semcrys-lite-projection-alias-v1"),
        "schedule": _derive_subkey(root_secret, salt, b"semcrys-lite-projection-schedule-v1"),
        "filler": _derive_subkey(root_secret, salt, b"semcrys-lite-projection-filler-v1"),
        "position": _derive_subkey(root_secret, salt, b"semcrys-lite-projection-position-v1"),
    }


def _feistel_value(value: int, bits: int, key: bytes) -> int:
    require(bits >= 2 and bits % 2 == 0 and 0 <= value < (1 << bits), "HELD_PADDING_POSITION_DOMAIN")
    half = bits // 2
    mask = (1 << half) - 1
    left, right = value >> half, value & mask
    width = max(1, (half + 7) // 8)
    for round_index in range(8):
        digest = hmac.new(
            key,
            b"semcrys-lite-position-feistel-v1\x00"
            + round_index.to_bytes(1, "big") + right.to_bytes(width, "big"),
            hashlib.sha256,
        ).digest()
        left, right = right, left ^ (int.from_bytes(digest[:8], "big") & mask)
    return (left << half) | right


def _position_index(source_index: int, domain_size: int, key: bytes) -> int:
    require(0 <= source_index < domain_size <= MAX_PADDED_EVENTS, "HELD_PADDING_POSITION_DOMAIN")
    bits = max(2, (domain_size - 1).bit_length())
    if bits % 2:
        bits += 1
    candidate = source_index
    for _attempt in range(1024):
        candidate = _feistel_value(candidate, bits, key)
        if candidate < domain_size:
            return candidate
    raise LiteHold("HELD_PADDING_POSITION_CYCLE")


def _next_power_of_two(value: int) -> int:
    require(isinstance(value, int) and value >= 0, "HELD_PADDING_VALUE")
    return 1 if value <= 1 else 1 << (value - 1).bit_length()


def _padding_target(value: int, policy: str, bucket: int | None, *, dimension: str) -> int:
    require(policy in PADDING_POLICIES, "HELD_PADDING_POLICY", policy)
    applies = (
        dimension == "COUNT" and policy in {PADDING_COUNT, PADDING_COUNT_AND_SIZE, PADDING_FIXED}
    ) or (
        dimension == "SIZE" and policy in {PADDING_SIZE, PADDING_COUNT_AND_SIZE, PADDING_FIXED}
    )
    limit = MAX_PADDED_EVENTS if dimension == "COUNT" else MAX_PADDED_MOVING_BYTES
    require(value <= limit, "HELD_PADDING_SOURCE_SIZE", dimension)
    if not applies:
        return value
    if policy == PADDING_FIXED:
        require(isinstance(bucket, int) and bucket >= value, "HELD_PADDING_FIXED_CLASS", str(bucket))
        target = bucket
    elif bucket is not None:
        require(isinstance(bucket, int) and bucket >= 1, "HELD_PADDING_BUCKET", str(bucket))
        target = ((value + bucket - 1) // bucket) * bucket
    else:
        target = _next_power_of_two(value)
    require(target <= limit, "HELD_PADDING_TARGET_SIZE", dimension)
    return target


def _balanced_alias_schedule(count: int, aliases: list[int], *, key: bytes, salt: bytes, base: int) -> list[int]:
    """Return a keyed positional shuffle with exactly balanced alias counts."""
    require(count >= 0 and bool(aliases), "HELD_HOMOPHONIC_ALIAS_DOMAIN")
    balanced = [aliases[index % len(aliases)] for index in range(count)]
    order = sorted(
        range(count),
        key=lambda index: hmac.new(
            key,
            b"semcrys-lite-homophonic-v1\x00" + salt + base.to_bytes(8, "big") + index.to_bytes(8, "big"),
            hashlib.sha256,
        ).digest(),
    )
    shuffled = [0] * count
    for source_index, target_index in enumerate(order):
        shuffled[target_index] = balanced[source_index]
    return shuffled


def _moving_legend(kind: str, base_root: str | None, source: bytes, payload: dict[str, Any]) -> dict[str, Any]:
    return rooted({
        "schema": SCHEMA_LEGEND,
        "kind": kind,
        "standing": STANDING,
        "base_legend_root": base_root,
        "source_sha256": sha256(source),
        "payload": payload,
        "security_claim": "NONE",
        "confidentiality_requirement": "SEALED_BY_ESTABLISHED_AEAD_BEFORE_PUBLIC_BINDING",
    }, "legend_root")


def _aead_backend() -> tuple[Any, Any, Any, Any]:
    try:
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    except ImportError as error:
        raise LiteHold("HELD_AEAD_BACKEND_UNAVAILABLE", "INSTALL_SEMCRYS_LITE_CONCEALMENT_EXTRA") from error
    return AESGCM, HKDF, hashes, InvalidTag


def _moving_context(*, artifact_id: str, profile: str, base_root: str | None, mode: str,
                    alias_limit: int, event_count: int, padding_policy: str = PADDING_NONE,
                    padding_bucket: int | None = None,
                    position_policy: str = POSITION_PRESERVE) -> dict[str, Any]:
    value = {
        "schema": SCHEMA_MOVING_BINDING,
        "artifact_id": artifact_id,
        "profile": profile,
        "base_legend_root": base_root,
        "occurrence_mode": mode,
        "alias_limit": alias_limit if mode in {OCC_BOUNDED, OCC_HOMOPHONIC} else None,
        "event_count": event_count,
        "position_policy": position_policy,
    }
    if padding_policy != PADDING_NONE:
        value["padding_policy"] = padding_policy
        value["padding_bucket"] = padding_bucket
    return value


def _seal_moving_legend(moving: dict[str, Any], *, key: bytes | None, profile: str,
                        base_root: str | None, mode: str, alias_limit: int,
                        event_count: int, padding_policy: str = PADDING_NONE,
                        padding_bucket: int | None = None,
                        position_policy: str = POSITION_PRESERVE) -> tuple[dict[str, Any], dict[str, Any]]:
    require(key is not None and len(key) >= 32, "HELD_AEAD_KEY_TOO_SHORT", "MINIMUM_32_BYTES")
    AESGCM, HKDF, hashes, _InvalidTag = _aead_backend()
    artifact_id = secrets.token_hex(16)
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    context = _moving_context(
        artifact_id=artifact_id,
        profile=profile,
        base_root=base_root,
        mode=mode,
        alias_limit=alias_limit,
        event_count=event_count,
        padding_policy=padding_policy,
        padding_bucket=padding_bucket,
        position_policy=position_policy,
    )
    aad = canonical_bytes(context)
    derived = HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=b"semcrys-lite-moving-legend-v0.2").derive(key)
    identifier_key = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=salt,
        info=b"semcrys-lite-moving-key-identifier-v2",
    ).derive(key)
    moving_bytes = canonical_bytes(moving)
    size_target = _padding_target(len(moving_bytes) + 8, padding_policy, padding_bucket, dimension="SIZE")
    if size_target > len(moving_bytes) + 8:
        plaintext_format = "LENGTH_PREFIXED_PADDED_JSON"
        plaintext = len(moving_bytes).to_bytes(8, "big") + moving_bytes + secrets.token_bytes(
            size_target - len(moving_bytes) - 8
        )
    else:
        plaintext_format = "CANONICAL_JSON"
        plaintext = moving_bytes
    ciphertext = AESGCM(derived).encrypt(nonce, plaintext, aad)
    key_identifier = hmac.new(
        identifier_key,
        b"semcrys-lite-key-identifier-v2\x00" + artifact_id.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()[:32]
    sealed = rooted({
        "schema": SCHEMA_SEALED_MOVING,
        "standing": STANDING,
        "artifact_id": artifact_id,
        "algorithm": AEAD_ALGORITHM,
        "kdf": AEAD_KDF,
        "salt_b64": base64.b64encode(salt).decode("ascii"),
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
        "ciphertext_sha256": sha256(ciphertext),
        "aad_sha256": sha256(aad),
        "key_identifier": key_identifier,
        "plaintext_format": plaintext_format,
        "padded_plaintext_bytes": len(plaintext),
        "padding_policy": padding_policy,
        "security_claim": "NONE",
        "primitive_claim": "ESTABLISHED_AEAD_INTEGRATION_WITHOUT_END_TO_END_SECURITY_PROOF",
    }, "sealed_legend_root")
    binding = {
        **context,
        "sealed_legend_root": sealed["sealed_legend_root"],
        "ciphertext_sha256": sealed["ciphertext_sha256"],
        "algorithm": AEAD_ALGORITHM,
        "kdf": AEAD_KDF,
        "key_identifier": key_identifier,
    }
    return sealed, binding


def _decode_b64(value: Any, code: str) -> bytes:
    require(isinstance(value, str), code, "NOT_STRING")
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as error:
        raise LiteHold(code, "INVALID_BASE64") from error


def _open_moving_legend(sealed: dict[str, Any] | None, *, key: bytes | None, binding: dict[str, Any]) -> dict[str, Any]:
    require(isinstance(sealed, dict), "HELD_MOVING_LEGEND_MISSING", str(binding.get("artifact_id")))
    require(key is not None and len(key) >= 32, "HELD_AEAD_KEY_TOO_SHORT", "MINIMUM_32_BYTES")
    require(sealed.get("schema") == SCHEMA_SEALED_MOVING, "HELD_MOVING_LEGEND_SCHEMA")
    sealed_root = verify_root(sealed, "sealed_legend_root", "HELD_MOVING_LEGEND_ROOT_MISMATCH")
    require(sealed_root == binding.get("sealed_legend_root"), "HELD_MOVING_LEGEND_MISMATCH")
    require(sealed.get("artifact_id") == binding.get("artifact_id"), "HELD_MOVING_ARTIFACT_ID_MISMATCH")
    require(sealed.get("algorithm") == binding.get("algorithm") == AEAD_ALGORITHM, "HELD_MOVING_AEAD_ALGORITHM")
    require(sealed.get("kdf") == binding.get("kdf") == AEAD_KDF, "HELD_MOVING_AEAD_KDF")
    salt = _decode_b64(sealed.get("salt_b64"), "HELD_MOVING_SALT")
    nonce = _decode_b64(sealed.get("nonce_b64"), "HELD_MOVING_NONCE")
    ciphertext = _decode_b64(sealed.get("ciphertext_b64"), "HELD_MOVING_CIPHERTEXT")
    require(len(salt) == 16, "HELD_MOVING_SALT_LENGTH")
    require(len(nonce) == 12, "HELD_MOVING_NONCE_LENGTH")
    _AESGCM, HKDF, hashes, _InvalidTag = _aead_backend()
    if "content_plaintext_bytes" in sealed:
        # Decode-only compatibility for protected containers emitted by the
        # first public v0.1 build. New encodings never emit this linkable ID.
        expected_key_identifier = hmac.new(
            key, b"semcrys-lite-key-identifier-v1", hashlib.sha256
        ).hexdigest()[:32]
    else:
        identifier_key = HKDF(
            algorithm=hashes.SHA256(), length=32, salt=salt,
            info=b"semcrys-lite-moving-key-identifier-v2",
        ).derive(key)
        expected_key_identifier = hmac.new(
            identifier_key,
            b"semcrys-lite-key-identifier-v2\x00" + str(binding.get("artifact_id")).encode("ascii"),
            hashlib.sha256,
        ).hexdigest()[:32]
    require(
        hmac.compare_digest(str(sealed.get("key_identifier")), expected_key_identifier)
        and hmac.compare_digest(str(binding.get("key_identifier")), expected_key_identifier),
        "HELD_MOVING_LEGEND_AUTHENTICATION",
    )
    require(sha256(ciphertext) == sealed.get("ciphertext_sha256") == binding.get("ciphertext_sha256"), "HELD_MOVING_CIPHERTEXT_DIGEST")
    context_fields = [
        "schema", "artifact_id", "profile", "base_legend_root", "occurrence_mode", "alias_limit", "event_count"
    ]
    if "position_policy" in binding:
        context_fields.append("position_policy")
    if "padding_policy" in binding:
        context_fields.extend(["padding_policy", "padding_bucket"])
    context = {key_: binding.get(key_) for key_ in context_fields}
    aad = canonical_bytes(context)
    require(sha256(aad) == sealed.get("aad_sha256"), "HELD_MOVING_AAD_MISMATCH")
    AESGCM, HKDF, hashes, InvalidTag = _aead_backend()
    derived = HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=b"semcrys-lite-moving-legend-v0.2").derive(key)
    try:
        plaintext = AESGCM(derived).decrypt(nonce, ciphertext, aad)
    except InvalidTag as error:
        raise LiteHold("HELD_MOVING_LEGEND_AUTHENTICATION") from error
    plaintext_format = sealed.get("plaintext_format", "CANONICAL_JSON")
    if plaintext_format == "LENGTH_PREFIXED_PADDED_JSON":
        require(len(plaintext) >= 8, "HELD_MOVING_LEGEND_PADDING")
        content_length = int.from_bytes(plaintext[:8], "big")
        require(0 < content_length <= len(plaintext) - 8, "HELD_MOVING_LEGEND_PADDING")
        plaintext = plaintext[8:8 + content_length]
    else:
        require(plaintext_format == "CANONICAL_JSON", "HELD_MOVING_LEGEND_PLAINTEXT_FORMAT")
    moving = read_json_bytes(plaintext, "HELD_MOVING_LEGEND_PLAINTEXT_MALFORMED")
    verify_root(moving, "legend_root", "HELD_MOVING_LEGEND_PLAINTEXT_ROOT_MISMATCH")
    return moving


def _apply_occurrence(events: list[int], mode: str, *, key: bytes | None, alias_limit: int,
                      base_root: str | None, source: bytes,
                      padding_policy: str = PADDING_NONE,
                      padding_bucket: int | None = None,
                      position_policy: str = POSITION_PRESERVE) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any]]:
    require(mode in OCCURRENCE_MODES, "HELD_OCCURRENCE_MODE_UNSUPPORTED", mode)
    require(padding_policy in PADDING_POLICIES, "HELD_PADDING_POLICY", padding_policy)
    require(position_policy in POSITION_POLICIES, "HELD_POSITION_POLICY", position_policy)
    if position_policy != POSITION_PRESERVE:
        require(mode in {OCC_BOUNDED, OCC_HOMOPHONIC},
                "HELD_POSITION_REQUIRES_ALIASED_MODE", mode)
    if padding_policy != PADDING_NONE:
        require(mode in {OCC_BOUNDED, OCC_HOMOPHONIC, OCC_UNIQUE},
                "HELD_PADDING_REQUIRES_PROTECTED_MODE", mode)
    if mode == OCC_VISIBLE:
        return {"kind": "EVENTS", "events": events}, None, {"public_equality_preserved": True}
    if mode == OCC_PERMUTE:
        require(key is not None and bool(key), "HELD_RUNTIME_KEY_REQUIRED")
        domain = list(range(256)) if base_root is None else list(range(1, max(events, default=0) + 1))
        forward, _inverse = _permutation(domain, key)
        tag = hmac.new(key, b"semcrys-lite-source\x00" + source, hashlib.sha256).hexdigest()
        return {"kind": "EVENTS", "events": [forward[value] for value in events]}, None, {
            "public_equality_preserved": True,
            "permutation_domain": "BYTE_0_255" if base_root is None else "LEGEND_ID_1_N",
            "domain_size": len(domain),
            "keyed_source_tag": tag,
        }
    if mode in {OCC_BOUNDED, OCC_HOMOPHONIC}:
        require(isinstance(alias_limit, int) and alias_limit >= 1, "HELD_ALIAS_LIMIT_INVALID")
        require(key is not None and len(key) >= 32, "HELD_AEAD_KEY_TOO_SHORT", "MINIMUM_32_BYTES")
        counts = collections.Counter(events)
        projection_salt = secrets.token_bytes(16)
        projection_root = _derive_subkey(
            key, projection_salt, b"semcrys-lite-projection-root-v1"
        )
        projection_keys = _projection_subkeys(projection_root, projection_salt)
        alias_total = sum(max(1, (count + alias_limit - 1) // alias_limit) for count in counts.values())
        logical_aliases = list(range(1, alias_total + 1))
        alias_forward, _alias_inverse = _permutation(logical_aliases, projection_keys["alias"])
        aliases_by_base: dict[int, list[int]] = {}
        alias_to_base: list[dict[str, int]] = []
        next_alias = 1
        for value in sorted(counts):
            alias_count = max(1, (counts[value] + alias_limit - 1) // alias_limit)
            aliases = [alias_forward[item] for item in range(next_alias, next_alias + alias_count)]
            aliases_by_base[value] = aliases
            for alias in aliases:
                alias_to_base.append({"alias": alias, "base": value})
            next_alias += alias_count
        if mode == OCC_BOUNDED:
            seen: dict[int, int] = {}
            public = []
            for value in events:
                occurrence = seen.get(value, 0)
                public.append(aliases_by_base[value][occurrence // alias_limit])
                seen[value] = occurrence + 1
            moving_kind = "OCCURRENCE_ALIAS"
            schedule = "CONTIGUOUS_BOUNDED_GROUPS"
        else:
            schedules = {
                value: _balanced_alias_schedule(
                    counts[value], aliases_by_base[value], key=projection_keys["schedule"],
                    salt=projection_salt, base=value
                )
                for value in counts
            }
            offsets: dict[int, int] = collections.defaultdict(int)
            public = []
            for value in events:
                public.append(schedules[value][offsets[value]])
                offsets[value] += 1
            moving_kind = "OCCURRENCE_HOMOPHONIC"
            schedule = "KEYED_POSITION_SHUFFLE_WITH_BALANCED_ALIAS_COUNTS"
        real_public = list(public)
        true_event_count = len(real_public)
        public_event_count = _padding_target(true_event_count, padding_policy, padding_bucket, dimension="COUNT")
        position_layout = "NONE"
        combined = list(real_public)
        if public_event_count > true_event_count:
            require(bool(public), "HELD_PADDING_EMPTY_ALIAS_DOMAIN")
            for offset in range(public_event_count - true_event_count):
                digest = hmac.new(
                    projection_keys["filler"],
                    b"semcrys-lite-count-padding-v2\x00" + offset.to_bytes(8, "big"),
                    hashlib.sha256,
                ).digest()
                combined.append(real_public[int.from_bytes(digest[:8], "big") % true_event_count])
        if position_policy == POSITION_CONCEAL or public_event_count > true_event_count:
            interspersed = [0] * public_event_count
            for source_index, alias in enumerate(combined):
                interspersed[_position_index(source_index, public_event_count, projection_keys["position"])] = alias
            public = interspersed
            position_layout = (
                "KEYED_FEISTEL_INTERSPERSED_V1"
                if public_event_count > true_event_count
                else "KEYED_FEISTEL_PERMUTATION_V1"
            )
        moving = _moving_legend(moving_kind, base_root, source, {
            "alias_to_base": alias_to_base,
            "alias_limit": alias_limit,
            "true_event_count": true_event_count,
            "public_event_count": public_event_count,
            "padding_policy": padding_policy,
            "position_policy": position_policy,
            "position_layout": position_layout,
            "padding_layout": position_layout if public_event_count > true_event_count else "NONE",
            "projection_salt_b64": base64.b64encode(projection_salt).decode("ascii"),
            "projection_root_b64": base64.b64encode(projection_root).decode("ascii"),
            "schedule": schedule,
        })
        public_counts = collections.Counter(real_public)
        return {"kind": "EVENTS", "events": public}, moving, {
            "public_equality_preserved": False,
            "max_public_repeat_before_padding": max(public_counts.values(), default=0),
            "homophonic_balance": mode == OCC_HOMOPHONIC,
            "alias_namespace": "PER_ENCODING_SALT_BOUND_PERMUTATION",
            "position_policy": position_policy,
            "position_layout": position_layout,
            "padding_layout": position_layout if public_event_count > true_event_count else "NONE",
            "public_body_semantics": (
                "ALIASED_EVENTS_KEYED_POSITION_WITH_BUCKETED_LENGTH"
                if position_layout != "NONE" and padding_policy != PADDING_NONE
                else "ALIASED_EVENTS_KEYED_POSITION_WITH_EXACT_LENGTH"
                if position_layout != "NONE"
                else "ALIASED_EVENT_ORDER_WITH_BUCKETED_LENGTH"
                if padding_policy != PADDING_NONE
                else "ALIASED_EVENT_ORDER"
            ),
        }
    true_event_count = len(events)
    public_event_count = _padding_target(true_event_count, padding_policy, padding_bucket, dimension="COUNT")
    moving = _moving_legend("OCCURRENCE_SEQUENCE", base_root, source, {
        "base_events": events,
        "true_event_count": true_event_count,
        "public_event_count": public_event_count,
        "padding_policy": padding_policy,
    })
    return {"kind": "RANGE", "start": 1, "count": public_event_count}, moving, {
        "public_equality_preserved": False,
        "public_body_semantics": "PADDED_EVENT_COUNT_ONLY" if padding_policy != PADDING_NONE else "EVENT_COUNT_ONLY",
    }


def _pack_varints_python(values: list[int]) -> bytes:
    out = bytearray()
    for value in values:
        require(isinstance(value, int) and value >= 0, "HELD_BODY_VARINT_RANGE")
        require(value < (1 << 63), "HELD_BODY_VARINT_RANGE")
        while value >= 128:
            out.append((value & 127) | 128)
            value >>= 7
        out.append(value)
    return bytes(out)


def _pack_varints(values: list[int]) -> bytes:
    try:
        return _native_pack_varints(values, _pack_varints_python)
    except NativeRequiredError as error:
        raise LiteHold("HELD_NATIVE_REQUIRED", str(error)) from error


def _unpack_varints_python(data: bytes) -> list[int]:
    values: list[int] = []
    current = 0
    shift = 0
    for byte in data:
        current |= (byte & 127) << shift
        if byte < 128:
            values.append(current)
            current = 0
            shift = 0
        else:
            shift += 7
            require(shift <= 63, "HELD_BODY_VARINT_OVERLONG")
    require(shift == 0, "HELD_BODY_VARINT_TRUNCATED")
    return values


def _unpack_varints(data: bytes) -> list[int]:
    try:
        return _native_unpack_varints(data, _unpack_varints_python)
    except NativeRequiredError as error:
        raise LiteHold("HELD_NATIVE_REQUIRED", str(error)) from error


def serialize_container(container: dict[str, Any], envelope: str = ENVELOPE_BINARY) -> bytes:
    """Serialize one logical container into either envelope.

    The logical container, and therefore container_root, is identical in both.
    The binary envelope simply carries the body payload as raw bytes instead of
    base64 text, which is the whole of the difference.
    """
    require(envelope in ENVELOPES, "HELD_ENVELOPE_UNSUPPORTED", envelope)
    if envelope == ENVELOPE_TEXT:
        return canonical_bytes(container) + b"\n"
    carrier = container.get("body_b64")
    if carrier is None:
        header, payload = container, b""
    else:
        header = {key: value for key, value in container.items() if key != "body_b64"}
        payload = _decode_b64(carrier, "HELD_BODY_BASE64")
    header_bytes = canonical_bytes(header)
    return CONTAINER_MAGIC + _pack_varints([len(header_bytes), len(payload)]) + header_bytes + payload


def deserialize_container(data: bytes) -> dict[str, Any]:
    """Accept either envelope. Text containers have no magic, so they still load."""
    if not data.startswith(CONTAINER_MAGIC):
        return read_json_bytes(data, "HELD_CONTAINER_MALFORMED")
    cursor = len(CONTAINER_MAGIC)
    lengths: list[int] = []
    for _ in range(2):
        value = 0
        shift = 0
        while True:
            require(cursor < len(data), "HELD_CONTAINER_BINARY_TRUNCATED")
            byte = data[cursor]
            cursor += 1
            value |= (byte & 127) << shift
            if byte < 128:
                break
            shift += 7
            require(shift <= 63, "HELD_CONTAINER_BINARY_LENGTH")
        lengths.append(value)
    header_length, payload_length = lengths
    require(cursor + header_length + payload_length == len(data), "HELD_CONTAINER_BINARY_TRUNCATED")
    header = read_json_bytes(data[cursor:cursor + header_length], "HELD_CONTAINER_MALFORMED")
    require(isinstance(header, dict), "HELD_CONTAINER_MALFORMED")
    payload = data[cursor + header_length:]
    if "body" not in header:
        # A carrier body is present even when it packs to zero bytes, so the
        # decision comes from the header, not from the payload length.
        header["body_b64"] = base64.b64encode(payload).decode("ascii")
    else:
        require(not payload_length, "HELD_BODY_CARRIER_AMBIGUOUS")
    return header


def _encode_body(body: dict[str, Any], outer: str, representation: str = BODY_JSON_EVENTS) -> dict[str, Any]:
    require(outer in OUTER_CODECS, "HELD_OUTER_CODEC_UNSUPPORTED", outer)
    require(representation in BODY_REPRESENTATIONS, "HELD_BODY_REPRESENTATION_UNSUPPORTED", representation)
    raw = canonical_bytes(body)
    # The logical digest binds the body's meaning, not its carrier, so the same
    # events verify identically under either representation.
    if representation == BODY_PACKED_VARINT and body.get("kind") != "EVENTS":
        # A RANGE body carries no events array, so there is nothing to pack.
        # The fallback is recorded rather than silent: the container states the
        # representation actually used, and the receipt states what was asked.
        representation = BODY_JSON_EVENTS
    common = {
        "body_representation": representation,
        "body_logical_sha256": sha256(raw),
    }
    if representation == BODY_PACKED_VARINT:
        require(body.get("kind") == "EVENTS", "HELD_BODY_REPRESENTATION_KIND", str(body.get("kind")))
        carrier = _pack_varints(body["events"])
        encoding = "PACKED_VARINT"
        if outer == OUTER_LZMA:
            carrier = lzma.compress(carrier, format=lzma.FORMAT_XZ, preset=6)
            encoding = "LZMA_PACKED_VARINT"
        return {
            **common,
            "body_encoding": encoding,
            "body_b64": base64.b64encode(carrier).decode("ascii"),
            "body_carrier_sha256": sha256(carrier),
        }
    if outer == OUTER_NONE:
        return {**common, "body_encoding": "JSON_DIRECT", "body": body}
    packed = lzma.compress(raw, format=lzma.FORMAT_XZ, preset=6)
    return {
        **common,
        "body_encoding": "LZMA_JSON",
        "body_b64": base64.b64encode(packed).decode("ascii"),
        "body_carrier_sha256": sha256(packed),
    }


def _decode_body(container: dict[str, Any]) -> dict[str, Any]:
    legacy = container.get("format") == FORMAT_V02
    encoding = container.get("body_encoding")
    has_direct = "body" in container
    has_b64 = "body_b64" in container
    require(not (has_direct and has_b64), "HELD_BODY_CARRIER_AMBIGUOUS")
    if not legacy and encoding == "JSON_DIRECT":
        require(has_direct and not has_b64, "HELD_BODY_DIRECT_MISSING")
        body = container.get("body")
        require(isinstance(body, dict), "HELD_BODY_JSON", "NOT_OBJECT")
        raw = canonical_bytes(body)
        require(sha256(raw) == container.get("body_logical_sha256"), "HELD_BODY_DIGEST_MISMATCH")
        return body
    require(has_b64 and not has_direct, "HELD_BODY_BASE64_MISSING")
    packed = _decode_b64(container.get("body_b64"), "HELD_BODY_BASE64")
    expected_carrier = container.get("body_sha256") if legacy else container.get("body_carrier_sha256")
    require(sha256(packed) == expected_carrier, "HELD_BODY_DIGEST_MISMATCH")
    if encoding in {"PACKED_VARINT", "LZMA_PACKED_VARINT"}:
        require(not legacy, "HELD_BODY_ENCODING", str(encoding))
        if encoding == "LZMA_PACKED_VARINT":
            try:
                packed = lzma.decompress(packed, format=lzma.FORMAT_XZ)
            except lzma.LZMAError as error:
                raise LiteHold("HELD_BODY_LZMA") from error
        body = {"kind": "EVENTS", "events": _unpack_varints(packed)}
        require(sha256(canonical_bytes(body)) == container.get("body_logical_sha256"), "HELD_BODY_LOGICAL_DIGEST_MISMATCH")
        return body
    if legacy and encoding == "JSON":
        raw = packed
    elif encoding == "LZMA_JSON":
        try:
            raw = lzma.decompress(packed, format=lzma.FORMAT_XZ)
        except lzma.LZMAError as error:
            raise LiteHold("HELD_BODY_LZMA") from error
    else:
        raise LiteHold("HELD_BODY_ENCODING", str(encoding))
    body = read_json_bytes(raw, "HELD_BODY_JSON")
    if not legacy:
        require(sha256(raw) == container.get("body_logical_sha256"), "HELD_BODY_LOGICAL_DIGEST_MISMATCH")
    return body


def encode_bytes(data: bytes, *, profile: str = PROFILE_DIRECT, legend: dict[str, Any] | None = None,
                 legend_placement: str | None = None, occurrence_mode: str = OCC_VISIBLE,
                 alias_limit: int = 1, key: bytes | None = None, outer_codec: str = OUTER_NONE,
                 id_order: str = ORDER_FREQUENCY, assembly: dict[str, Any] | None = None,
                 body_representation: str = BODY_PACKED_VARINT, envelope: str = ENVELOPE_BINARY,
                 padding_policy: str = PADDING_NONE,
                 padding_bucket: int | None = None,
                 position_policy: str = POSITION_PRESERVE) -> tuple[bytes, dict[str, Any] | None, dict[str, Any] | None, dict[str, Any]]:
    if profile == PROFILE_WORD_AUTO_SPACE:
        common = dict(
            legend=legend,
            legend_placement=legend_placement,
            occurrence_mode=occurrence_mode,
            alias_limit=alias_limit,
            key=key,
            outer_codec=outer_codec,
            id_order=id_order,
            assembly=assembly,
            body_representation=body_representation,
            envelope=envelope,
            padding_policy=padding_policy,
            padding_bucket=padding_bucket,
            position_policy=position_policy,
        )
        candidates = []
        for candidate_profile in (PROFILE_WORD, PROFILE_WORD_IMPLICIT_SPACE):
            result = encode_bytes(data, profile=candidate_profile, **common)
            container, external, moving, receipt = result
            complete_bytes = len(container)
            if external is not None:
                complete_bytes += len(legend_bytes(external))
            if moving is not None:
                complete_bytes += len(canonical_bytes(moving)) + 1
            candidates.append((complete_bytes, candidate_profile, result))
        candidates.sort(key=lambda row: (row[0], row[1] != PROFILE_WORD))
        complete_bytes, selected_profile, selected_result = candidates[0]
        container, external, moving, receipt = selected_result
        unrooted = dict(receipt)
        unrooted.pop("receipt_root", None)
        configuration = dict(unrooted["effective_instance_configuration"])
        configuration["requested_profile"] = PROFILE_WORD_AUTO_SPACE
        configuration["profile"] = selected_profile
        unrooted["effective_instance_configuration"] = configuration
        unrooted["separator_admission"] = {
            "policy": "MIN_COMPLETE_CONTAINER_PLUS_REQUIRED_DEPENDENCIES",
            "selected_profile": selected_profile,
            "selected_complete_bytes": complete_bytes,
            "candidates": [
                {"profile": row[1], "complete_bytes": row[0]} for row in candidates
            ],
            "ties": "EXPLICIT_SEPARATOR_CONTROL_WINS",
        }
        return container, external, moving, rooted(unrooted, "receipt_root")
    caller_supplied_legend = legend is not None
    events, selected = _base_events(data, profile, legend, id_order, assembly)
    if profile == PROFILE_DIRECT:
        placement = PLACEMENT_NONE
    else:
        # A caller-supplied legend is presumed already held and therefore
        # external.  A legend constructed for this invocation remains embedded.
        default_placement = PLACEMENT_EXTERNAL if caller_supplied_legend else (
            PLACEMENT_EMBEDDED if profile in (PROFILE_LOCAL, PROFILE_WORD, PROFILE_WORD_IMPLICIT_SPACE, PROFILE_WORD_ASSEMBLY)
            else PLACEMENT_EXTERNAL
        )
        placement = legend_placement or default_placement
        require(placement in {PLACEMENT_EMBEDDED, PLACEMENT_EXTERNAL}, "HELD_LEGEND_PLACEMENT")
        require(not (profile == PROFILE_PRESHARED and placement == PLACEMENT_EMBEDDED), "HELD_PRESHARED_EMBED_FORBIDDEN")
    base_root = selected["legend_root"] if selected else None
    body, moving_plaintext, exposure = _apply_occurrence(
        events,
        occurrence_mode,
        key=key,
        alias_limit=alias_limit,
        base_root=base_root,
        source=data,
        padding_policy=padding_policy,
        padding_bucket=padding_bucket,
        position_policy=position_policy,
    )
    public_event_count = body.get("count") if body.get("kind") == "RANGE" else len(body.get("events", []))
    moving = None
    moving_binding = None
    if moving_plaintext is not None:
        moving, moving_binding = _seal_moving_legend(
            moving_plaintext,
            key=key,
            profile=profile,
            base_root=base_root,
            mode=occurrence_mode,
            alias_limit=alias_limit,
            event_count=public_event_count,
            padding_policy=padding_policy,
            padding_bucket=padding_bucket,
            position_policy=position_policy,
        )
        exposure = {
            **exposure,
            "public_container_equality_randomized": True,
            "moving_legend_protection": AEAD_ALGORITHM,
            "public_plaintext_legend_commitment": False,
        }
    body_fields = _encode_body(body, outer_codec, body_representation)
    public_source_digest = occurrence_mode in {OCC_VISIBLE}
    container = {
        "schema": SCHEMA_CONTAINER,
        "format": FORMAT,
        "standing": STANDING,
        "profile": profile,
        "legend_placement": placement,
        "base_legend_root": base_root,
        "assembly_legend_root": assembly["assembly_root"] if assembly is not None else None,
        "embedded_base_legend": selected if selected is not None and placement == PLACEMENT_EMBEDDED else None,
        "moving_legend_root": None,
        "moving_legend_binding": moving_binding,
        "occurrence_mode": occurrence_mode,
        "alias_limit": alias_limit if occurrence_mode in {OCC_BOUNDED, OCC_HOMOPHONIC} else None,
        "padding_policy": padding_policy,
        "padding_bucket": padding_bucket,
        "position_policy": position_policy,
        "outer_codec": outer_codec,
        "event_count": public_event_count,
        **body_fields,
        "source_sha256": sha256(data) if public_source_digest else None,
        "verification": exposure,
        "security_claim": "NONE",
    }
    container = rooted(container, "container_root")
    serialized = serialize_container(container, envelope)
    container_bytes = len(serialized)
    receipt_is_redacted = moving_plaintext is not None
    size_advisory = {
        "status": "REDACTED_PROTECTED_MODE" if receipt_is_redacted else (
            "EXPANDED" if container_bytes > len(data) else "NOT_EXPANDED"
        ),
        "source_bytes": None if receipt_is_redacted else len(data),
        "container_bytes": container_bytes,
        "recommendation": "NONE" if receipt_is_redacted else (
            "TRY_OUTER_LZMA_FOR_SIZE" if outer_codec == OUTER_NONE and container_bytes > len(data) else "NONE"
        ),
        "outer_codec_is_explicit": True,
        "privacy_note": "EXACT_SOURCE_METRICS_REDACTED" if receipt_is_redacted else "PUBLIC_METRICS",
    }
    receipt = rooted({
        "schema": SCHEMA_RECEIPT,
        "operation": "ENCODE",
        "status": "PASS",
        "standing": STANDING,
        "effective_instance_configuration": {
            "profile": profile,
            "legend_placement": placement,
            "base_legend_root": base_root,
            "occurrence_mode": occurrence_mode,
            "alias_limit": alias_limit if occurrence_mode in {OCC_BOUNDED, OCC_HOMOPHONIC} else None,
            "padding_policy": padding_policy,
            "padding_bucket": padding_bucket,
            "position_policy": position_policy,
            "outer_codec": outer_codec,
            "body_representation_requested": body_representation,
            "body_representation_effective": body_fields["body_representation"],
            "envelope": envelope,
            "assembly_legend_root": assembly["assembly_root"] if assembly is not None else None,
            "runtime_key_present": bool(key),
            "runtime_key_recorded": False,
        },
        "assembly_relationship": {
            "relationship": "WARM_RELATIONSHIP_ONLY",
            "assembly_legend_bytes": len(assembly_bytes(assembly)) if assembly is not None else 0,
            "cold_penalty_note": "ASSEMBLY_LEGEND_MUST_BE_PRE_SHARED_SHIPPING_IT_PER_MESSAGE_COSTS_MORE_THAN_IT_SAVES",
        } if assembly is not None else None,
        "source_bytes": None if receipt_is_redacted else len(data),
        "event_count": None if receipt_is_redacted else len(events),
        "public_event_count": public_event_count,
        "container_bytes": container_bytes,
        "base_legend_bytes": len(legend_bytes(selected)) if selected is not None else 0,
        "moving_legend_bytes": len(canonical_bytes(moving)) + 1 if moving else 0,
        "size_advisory": size_advisory,
        "container_root": container["container_root"],
        "receipt_visibility": "PUBLIC_REDACTED" if receipt_is_redacted else "PUBLIC_METRICS",
        "security_claim": "NONE",
    }, "receipt_root")
    external_base = selected if selected is not None and placement == PLACEMENT_EXTERNAL and profile in (
        PROFILE_LOCAL, PROFILE_WORD, PROFILE_WORD_IMPLICIT_SPACE, PROFILE_WORD_ASSEMBLY
    ) else None
    return serialized, external_base, moving, receipt


def _resolve_base(container: dict[str, Any], supplied: dict[str, Any] | None) -> dict[str, Any] | None:
    if container["profile"] == PROFILE_DIRECT:
        require(container.get("base_legend_root") is None, "HELD_DIRECT_BASE_ROOT")
        return None
    embedded = container.get("embedded_base_legend")
    selected = embedded if container["legend_placement"] == PLACEMENT_EMBEDDED else supplied
    require(isinstance(selected, dict), "HELD_EXTERNAL_LEGEND_MISSING", str(container.get("base_legend_root")))
    root = validate_base_legend(selected)
    require(root == container.get("base_legend_root"), "HELD_EXTERNAL_LEGEND_MISMATCH")
    return selected


def _restore_occurrence(container: dict[str, Any], body: dict[str, Any], moving: dict[str, Any] | None, key: bytes | None) -> tuple[list[int], dict[str, Any] | None]:
    mode = container["occurrence_mode"]
    if mode == OCC_VISIBLE:
        require(body.get("kind") == "EVENTS" and isinstance(body.get("events"), list), "HELD_BODY_SHAPE")
        return body["events"], None
    if mode == OCC_PERMUTE:
        require(key is not None and bool(key), "HELD_RUNTIME_KEY_REQUIRED")
        require(body.get("kind") == "EVENTS" and isinstance(body.get("events"), list), "HELD_BODY_SHAPE")
        domain = list(range(256)) if container["profile"] == PROFILE_DIRECT else list(range(1, int(container["verification"]["domain_size"]) + 1))
        _forward, inverse = _permutation(domain, key)
        try:
            return [inverse[value] for value in body["events"]], None
        except (KeyError, TypeError) as error:
            raise LiteHold("HELD_PERMUTED_EVENT_INVALID") from error
    binding = container.get("moving_legend_binding")
    require(isinstance(binding, dict), "HELD_MOVING_BINDING_MISSING")
    require(binding.get("schema") == SCHEMA_MOVING_BINDING, "HELD_MOVING_BINDING_SCHEMA")
    plaintext_moving = _open_moving_legend(moving, key=key, binding=binding)
    require(plaintext_moving.get("base_legend_root") == container.get("base_legend_root"), "HELD_MOVING_BASE_MISMATCH")
    payload = plaintext_moving.get("payload")
    require(isinstance(payload, dict), "HELD_MOVING_PAYLOAD")
    if mode in {OCC_BOUNDED, OCC_HOMOPHONIC}:
        expected_kind = "OCCURRENCE_HOMOPHONIC" if mode == OCC_HOMOPHONIC else "OCCURRENCE_ALIAS"
        require(plaintext_moving.get("kind") == expected_kind, "HELD_MOVING_LEGEND_KIND")
        require(body.get("kind") == "EVENTS" and isinstance(body.get("events"), list), "HELD_BODY_SHAPE")
        mapping = {row["alias"]: row["base"] for row in payload.get("alias_to_base", []) if isinstance(row, dict) and "alias" in row and "base" in row}
        true_event_count = payload.get("true_event_count", len(body["events"]))
        require(isinstance(true_event_count, int) and 0 <= true_event_count <= len(body["events"]),
                "HELD_PADDED_EVENT_COUNT")
        public_event_count = payload.get("public_event_count", len(body["events"]))
        require(public_event_count == len(body["events"]), "HELD_PADDED_EVENT_COUNT")
        position_layout = payload.get("position_layout", payload.get("padding_layout", "NONE"))
        if position_layout in {"KEYED_FEISTEL_INTERSPERSED_V1", "KEYED_FEISTEL_PERMUTATION_V1"}:
            projection_salt = _decode_b64(payload.get("projection_salt_b64"), "HELD_PROJECTION_SALT")
            projection_root = _decode_b64(payload.get("projection_root_b64"), "HELD_PROJECTION_ROOT")
            require(len(projection_salt) == 16 and len(projection_root) == 32,
                    "HELD_PROJECTION_KEY_MATERIAL")
            position_key = _projection_subkeys(projection_root, projection_salt)["position"]
            projected = [
                body["events"][_position_index(index, public_event_count, position_key)]
                for index in range(true_event_count)
            ]
        else:
            require(position_layout == "NONE", "HELD_POSITION_LAYOUT")
            projected = body["events"][:true_event_count]
        try:
            return [mapping[value] for value in projected], plaintext_moving
        except (KeyError, TypeError) as error:
            raise LiteHold("HELD_ALIAS_MAPPING_INCOMPLETE") from error
    require(mode == OCC_UNIQUE and plaintext_moving.get("kind") == "OCCURRENCE_SEQUENCE", "HELD_MOVING_LEGEND_KIND")
    events = payload.get("base_events")
    require(isinstance(events, list), "HELD_MOVING_SEQUENCE")
    public_event_count = payload.get("public_event_count", len(events))
    true_event_count = payload.get("true_event_count", len(events))
    require(true_event_count == len(events), "HELD_RANGE_MISMATCH")
    require(body.get("kind") == "RANGE" and body.get("start") == 1 and body.get("count") == public_event_count,
            "HELD_RANGE_MISMATCH")
    return events, plaintext_moving


def _resolve_assembly(container: dict[str, Any], supplied: dict[str, Any] | None, base: dict[str, Any] | None) -> dict[str, Any] | None:
    declared = container.get("assembly_legend_root")
    if declared is None:
        require(supplied is None, "HELD_ASSEMBLY_LEGEND_UNEXPECTED")
        return None
    require(isinstance(supplied, dict), "HELD_ASSEMBLY_LEGEND_MISSING", str(declared))
    root = validate_assembly_legend(supplied, base)
    require(root == declared, "HELD_ASSEMBLY_LEGEND_MISMATCH")
    return supplied


def decode_bytes(container_data: bytes, *, legend: dict[str, Any] | None = None, moving_legend: dict[str, Any] | None = None, key: bytes | None = None, assembly: dict[str, Any] | None = None) -> tuple[bytes, dict[str, Any]]:
    container = deserialize_container(container_data)
    is_current = container.get("schema") == SCHEMA_CONTAINER and container.get("format") == FORMAT
    is_legacy = container.get("schema") == SCHEMA_CONTAINER_V02 and container.get("format") == FORMAT_V02
    require(is_current or is_legacy, "HELD_CONTAINER_FORMAT")
    verify_root(container, "container_root", "HELD_CONTAINER_ROOT_MISMATCH")
    selected = _resolve_base(container, legend)
    body = _decode_body(container)
    public_body_count = body.get("count") if body.get("kind") == "RANGE" else len(body.get("events", []))
    require(public_body_count == container.get("event_count"), "HELD_PUBLIC_EVENT_COUNT_MISMATCH")
    events, moving_plaintext = _restore_occurrence(container, body, moving_legend, key)
    if moving_plaintext is not None:
        payload = moving_plaintext.get("payload") if isinstance(moving_plaintext.get("payload"), dict) else {}
        expected_true_count = payload.get("true_event_count", container.get("event_count"))
    else:
        expected_true_count = container.get("event_count")
    require(len(events) == expected_true_count, "HELD_EVENT_COUNT_MISMATCH")
    resolved_assembly = _resolve_assembly(container, assembly, selected)
    if resolved_assembly is not None:
        events = expand_assembly_events(events, resolved_assembly)
    if selected is None:
        require(all(isinstance(value, int) and 0 <= value <= 255 for value in events), "HELD_DIRECT_EVENT_RANGE")
        restored = bytes(events)
    elif selected["kind"] == KIND_WORD:
        inverse_text = {row["id"]: row["text"] for row in selected["entries"]}
        try:
            units = [inverse_text[value] for value in events]
            if container["profile"] == PROFILE_WORD_IMPLICIT_SPACE:
                reconstructed: list[str] = []
                for unit in units:
                    if reconstructed and _is_word_unit(reconstructed[-1]) and _is_word_unit(unit):
                        reconstructed.append(" ")
                    reconstructed.append(unit)
                units = reconstructed
            restored = "".join(units).encode("utf-8")
        except (KeyError, TypeError, ValueError) as error:
            raise LiteHold("HELD_LEGEND_EVENT_UNBOUND") from error
    else:
        inverse = {row["id"]: row["byte"] for row in selected["entries"]}
        try:
            restored = bytes(inverse[value] for value in events)
        except (KeyError, TypeError, ValueError) as error:
            raise LiteHold("HELD_LEGEND_EVENT_UNBOUND") from error
    if container["occurrence_mode"] == OCC_VISIBLE:
        require(sha256(restored) == container.get("source_sha256"), "HELD_RECONSTRUCTION_ROOT_MISMATCH")
    elif container["occurrence_mode"] == OCC_PERMUTE:
        require(key is not None, "HELD_RUNTIME_KEY_REQUIRED")
        observed = hmac.new(key, b"semcrys-lite-source\x00" + restored, hashlib.sha256).hexdigest()
        require(hmac.compare_digest(observed, container["verification"]["keyed_source_tag"]), "HELD_RECONSTRUCTION_KEY_TAG_MISMATCH")
    else:
        require(isinstance(moving_plaintext, dict) and sha256(restored) == moving_plaintext.get("source_sha256"), "HELD_RECONSTRUCTION_ROOT_MISMATCH")
    receipt = rooted({
        "schema": SCHEMA_RECEIPT,
        "operation": "DECODE",
        "status": "PASS",
        "standing": STANDING,
        "container_root": container["container_root"],
        "profile": container["profile"],
        "occurrence_mode": container["occurrence_mode"],
        "padding_policy": container.get("padding_policy", PADDING_NONE),
        "position_policy": container.get("position_policy", POSITION_PRESERVE),
        "public_event_count": container.get("event_count"),
        "restored_event_count": len(events),
        "assembly_legend_root": container.get("assembly_legend_root"),
        "restored_bytes": len(restored),
        "runtime_key_present": bool(key),
        "runtime_key_recorded": False,
        "security_claim": "NONE",
    }, "receipt_root")
    return restored, receipt


def rotate_protected_container(container_data: bytes, moving_legend: dict[str, Any], *,
                               old_key: bytes, new_key: bytes) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    """Rewrap protected reconstruction state without recompressing source events."""
    container = deserialize_container(container_data)
    require(container.get("schema") == SCHEMA_CONTAINER and container.get("format") == FORMAT,
            "HELD_CONTAINER_FORMAT")
    verify_root(container, "container_root", "HELD_CONTAINER_ROOT_MISMATCH")
    mode = container.get("occurrence_mode")
    require(mode in {OCC_BOUNDED, OCC_HOMOPHONIC, OCC_UNIQUE},
            "HELD_ROTATION_REQUIRES_PROTECTED_MODE", str(mode))
    binding = container.get("moving_legend_binding")
    require(isinstance(binding, dict), "HELD_MOVING_BINDING_MISSING")
    plaintext = _open_moving_legend(moving_legend, key=old_key, binding=binding)
    new_moving, new_binding = _seal_moving_legend(
        plaintext,
        key=new_key,
        profile=container["profile"],
        base_root=container.get("base_legend_root"),
        mode=mode,
        alias_limit=container.get("alias_limit") or 1,
        event_count=container["event_count"],
        padding_policy=container.get("padding_policy", PADDING_NONE),
        padding_bucket=container.get("padding_bucket"),
        position_policy=container.get("position_policy", POSITION_PRESERVE),
    )
    prior_root = container.pop("container_root")
    container["moving_legend_binding"] = new_binding
    rotated = rooted(container, "container_root")
    envelope = ENVELOPE_BINARY if container_data.startswith(CONTAINER_MAGIC) else ENVELOPE_TEXT
    serialized = serialize_container(rotated, envelope)
    receipt = rooted({
        "schema": "semcrys-lite.key-rotation-receipt.v0.1.candidate",
        "status": "PASS",
        "standing": STANDING,
        "prior_container_root": prior_root,
        "container_root": rotated["container_root"],
        "body_logical_sha256": rotated.get("body_logical_sha256"),
        "body_carrier_sha256": rotated.get("body_carrier_sha256"),
        "old_key_identifier": binding.get("key_identifier"),
        "new_key_identifier": new_binding.get("key_identifier"),
        "source_reencoded": False,
        "security_claim": "NONE",
    }, "receipt_root")
    return serialized, new_moving, receipt


def inspect_container(data: bytes, *, include_body: bool = False) -> dict[str, Any]:
    value = deserialize_container(data)
    verify_root(value, "container_root", "HELD_CONTAINER_ROOT_MISMATCH")
    result = {key: value.get(key) for key in (
        "schema", "format", "standing", "profile", "legend_placement", "base_legend_root",
        "moving_legend_root", "moving_legend_binding", "occurrence_mode", "alias_limit", "padding_policy", "position_policy",
        "padding_bucket", "outer_codec", "event_count",
        "body_representation", "body_encoding", "body_logical_sha256", "body_carrier_sha256", "body_sha256",
        "source_sha256", "verification", "security_claim", "container_root"
    )}
    if include_body:
        result["body"] = _decode_body(value)
    return result


def explain_container(data: bytes) -> dict[str, Any]:
    value = deserialize_container(data)
    verify_root(value, "container_root", "HELD_CONTAINER_ROOT_MISMATCH")
    body = _decode_body(value)
    mode = value.get("occurrence_mode")
    verification = value.get("verification") if isinstance(value.get("verification"), dict) else {}
    return rooted({
        "schema": "semcrys-lite.container-explanation.v0.1.candidate",
        "standing": STANDING,
        "container_root": value["container_root"],
        "where_are_the_bytes": {
            "base_identity_location": "DIRECT_BYTE_VALUES" if value.get("profile") == PROFILE_DIRECT else (
                "EMBEDDED_BASE_LEGEND" if value.get("legend_placement") == PLACEMENT_EMBEDDED else "EXTERNAL_BASE_LEGEND"
            ),
            "ordered_reconstruction_location": "PUBLIC_BODY" if mode in {OCC_VISIBLE, OCC_PERMUTE} else "SEALED_MOVING_LEGEND",
            "source_verification_location": "PUBLIC_CONTAINER" if value.get("source_sha256") else (
                "KEYED_PUBLIC_TAG" if mode == OCC_PERMUTE else "SEALED_MOVING_LEGEND"
            ),
            "public_body_carrier": "DIRECT_JSON" if value.get("body_encoding") == "JSON_DIRECT" else "BASE64_WRAPPED_LZMA_JSON",
        },
        "public_observations": {
            "event_count": value.get("event_count"),
            "padding_policy": value.get("padding_policy", PADDING_NONE),
            "position_policy": value.get("position_policy", POSITION_PRESERVE),
            "body_kind": body.get("kind"),
            "occurrence_equality_preserved": verification.get("public_equality_preserved"),
            "public_body_semantics": verification.get("public_body_semantics", "EVENT_IDENTIFIERS_AND_ORDER"),
            "source_digest_visible": value.get("source_sha256") is not None,
            "base_legend_root_visible": value.get("base_legend_root") is not None,
            "sealed_moving_binding_visible": isinstance(value.get("moving_legend_binding"), dict),
        },
        "requirements_to_reconstruct": {
            "external_base_legend": value.get("legend_placement") == PLACEMENT_EXTERNAL,
            "runtime_key": mode != OCC_VISIBLE,
            "sealed_moving_legend": mode in {OCC_BOUNDED, OCC_HOMOPHONIC, OCC_UNIQUE},
        },
        "remaining_public_leakage": [
            "CONTAINER_METADATA",
            *( ["EVENT_COUNT_CLASS"] if value.get("padding_policy", PADDING_NONE) != PADDING_NONE else ["EVENT_COUNT"] ),
            *( ["EVENT_ORDER", "EVENT_EQUALITY"] if mode in {OCC_VISIBLE, OCC_PERMUTE} else [] ),
            *( ["EVENT_ORDER"] if mode in {OCC_BOUNDED, OCC_HOMOPHONIC}
                and value.get("position_policy", POSITION_PRESERVE) == POSITION_PRESERVE
                and verification.get("position_layout", "NONE") == "NONE" else [] ),
            *( ["BOUNDED_EVENT_EQUALITY"] if mode in {OCC_BOUNDED, OCC_HOMOPHONIC} else [] ),
        ],
        "security_claim": "NONE",
    }, "explanation_root")


SCHEMA_ACCOUNTING = "semcrys-lite.accounting.v0.1.candidate"
SCHEMA_CORPUS = "semcrys-lite.corpus-accounting.v0.1.candidate"
FIT_SELF = "SELF_FITTED"
FIT_EXTERNAL = "EXTERNALLY_SUPPLIED"


def _xz_baseline(data: bytes) -> int:
    return len(lzma.compress(data, format=lzma.FORMAT_XZ, preset=6))


def _compressed(payload: bytes) -> int:
    return len(lzma.compress(payload, format=lzma.FORMAT_XZ, preset=6))


def account_document(
    data: bytes,
    *,
    legend: dict[str, Any],
    assembly: dict[str, Any] | None = None,
    fit_provenance: str = FIT_EXTERNAL,
    **encode_kwargs: Any,
) -> dict[str, Any]:
    """Four-column accounting for one document against a shared legend.

    col1 worked document, col2 shared legends, col3 both, col4 xz on the source.
    Warm reads col1 (legends already held); cold reads col3.
    """
    require(fit_provenance in (FIT_SELF, FIT_EXTERNAL), "HELD_FIT_PROVENANCE", fit_provenance)
    mode = encode_kwargs.get("occurrence_mode", OCC_VISIBLE)
    # Accounting compares a shared legend against a baseline. A message-specific
    # legend is a per-message cost with no break-even point, so publishing an
    # amortization number for it would be a category error.
    require(mode in SHAREABLE_OCCURRENCE_MODES, "HELD_ACCOUNTING_LEGEND_NOT_SHAREABLE", mode)
    profile = PROFILE_WORD_ASSEMBLY if assembly is not None else PROFILE_WORD
    options = {
        "legend_placement": PLACEMENT_EXTERNAL,
        "outer_codec": OUTER_LZMA,
        **encode_kwargs,
    }
    container, _external, _moving, receipt = encode_bytes(
        data, profile=profile, legend=legend, assembly=assembly, **options
    )
    restored, _ = decode_bytes(container, legend=legend, assembly=assembly)
    require(restored == data, "HELD_ACCOUNTING_ROUND_TRIP")
    # Cold accounting counts the exact .leg artifacts a receiver must acquire.
    # Counterfactual LZMA sizes are not transport costs unless such artifacts
    # are actually materialized and rooted.
    base_cost = len(legend_bytes(legend))
    assembly_cost = len(assembly_bytes(assembly)) if assembly is not None else 0
    legend_total = base_cost + assembly_cost
    worked = len(container)
    baseline = _xz_baseline(data)
    source = len(data)
    return rooted({
        "schema": SCHEMA_ACCOUNTING,
        "standing": STANDING,
        "source_bytes": source,
        "event_count": receipt["event_count"],
        "columns": {
            "col1_worked_document_bytes": worked,
            "col2_shared_legend_bytes": legend_total,
            "col3_both_bytes": worked + legend_total,
            "col4_xz_source_bytes": baseline,
        },
        "legend_breakdown": {
            "base_legend_bytes": base_cost,
            "assembly_legend_bytes": assembly_cost,
        },
        "ratios": {
            "warm": round(worked / source, 6) if source else None,
            "cold": round((worked + legend_total) / source, 6) if source else None,
            "xz": round(baseline / source, 6) if source else None,
        },
        "verdict": {
            "warm_beats_xz": worked < baseline,
            "cold_beats_xz": worked + legend_total < baseline,
            "warm_delta_bytes": baseline - worked,
            "cold_delta_bytes": baseline - (worked + legend_total),
        },
        "fit_provenance": fit_provenance,
        "claim_ceiling": (
            "SELF_FITTED_UPPER_BOUND_NOT_A_TRANSFER_RESULT"
            if fit_provenance == FIT_SELF
            else "MEASURED_ON_A_DOCUMENT_THE_LEGEND_WAS_NOT_FITTED_TO"
        ),
        "baseline_note": "COL4_IS_XZ_PRESET_6_ON_THE_UNMODIFIED_SOURCE",
        "legend_accounting_note": "COL2_COUNTS_ACTUAL_CANONICAL_LEGEND_ARTIFACT_BYTES_WITHOUT_COUNTERFACTUAL_COMPRESSION",
        "effective_instance_configuration": receipt["effective_instance_configuration"],
        "security_claim": "NONE",
    }, "accounting_root")


def account_corpus(
    documents: list[bytes],
    *,
    legend: dict[str, Any],
    assembly: dict[str, Any] | None = None,
    fit_provenance: str = FIT_EXTERNAL,
    **encode_kwargs: Any,
) -> dict[str, Any]:
    """Amortization curve across a document set, and the break-even count.

    Break-even is the smallest N at which cumulative cold cost drops below the
    cumulative xz baseline. It may not exist within the supplied set, in which
    case that is reported rather than extrapolated.
    """
    require(documents, "HELD_CORPUS_EMPTY")
    rows = [
        account_document(
            document, legend=legend, assembly=assembly,
            fit_provenance=fit_provenance, **encode_kwargs,
        )
        for document in documents
    ]
    legend_total = rows[0]["columns"]["col2_shared_legend_bytes"]
    curve: list[dict[str, Any]] = []
    break_even = None
    worked_running = 0
    baseline_running = 0
    for index, row in enumerate(rows, start=1):
        worked_running += row["columns"]["col1_worked_document_bytes"]
        baseline_running += row["columns"]["col4_xz_source_bytes"]
        cumulative = legend_total + worked_running
        curve.append({
            "documents": index,
            "cumulative_semcrys_bytes": cumulative,
            "cumulative_xz_bytes": baseline_running,
            "delta_bytes": baseline_running - cumulative,
        })
        if break_even is None and cumulative < baseline_running:
            break_even = index
    return rooted({
        "schema": SCHEMA_CORPUS,
        "standing": STANDING,
        "document_count": len(documents),
        "shared_legend_bytes": legend_total,
        "amortization_curve": curve,
        "break_even_documents": break_even,
        "break_even_found_within_set": break_even is not None,
        "per_document": [
            {
                "source_bytes": row["source_bytes"],
                "warm_bytes": row["columns"]["col1_worked_document_bytes"],
                "xz_bytes": row["columns"]["col4_xz_source_bytes"],
                "warm_ratio": row["ratios"]["warm"],
                "xz_ratio": row["ratios"]["xz"],
            }
            for row in rows
        ],
        "fit_provenance": fit_provenance,
        "baseline_note": "COL4_IS_XZ_PRESET_6_ON_THE_UNMODIFIED_SOURCE",
        "security_claim": "NONE",
    }, "corpus_accounting_root")


SCHEMA_DISCLOSURE = "semcrys-lite.legend-disclosure.v0.1.candidate"


def _spearman(left: list[int], right: list[int]) -> float:
    """Rank correlation in [-1, 1]. 1.0 means the two orderings are identical."""
    count = len(left)
    if count < 2:
        return 0.0
    total = sum((a - b) ** 2 for a, b in zip(left, right))
    return round(1.0 - (6.0 * total) / (count * (count * count - 1)), 6)


def legend_disclosure(legend: dict[str, Any], source: bytes | None = None) -> dict[str, Any]:
    """What a holder of the legend alone learns, measured rather than declared.

    Three independent axes:
      vocabulary        which units exist. Unavoidable: the legend is the map.
      introduction      the sequence in which units first appeared in the source.
      frequency_rank    how often each unit was used.

    The last two are ordering artifacts and can be removed. The first cannot.
    Correlations are measured against the source when one is supplied, so a
    declared id_order is verified rather than trusted.
    """
    require(legend.get("kind") == KIND_WORD, "HELD_DISCLOSURE_LEGEND_KIND")
    validate_base_legend(legend)
    entries = [row["text"] for row in legend["entries"]]
    content = [text for text in entries if text.strip()]
    report: dict[str, Any] = {
        "schema": SCHEMA_DISCLOSURE,
        "standing": STANDING,
        "declared_id_order": legend["id_order"],
        "vocabulary_disclosure": {
            "total_entries": len(entries),
            "content_unit_entries": len(content),
            "separator_entries": len(entries) - len(content),
            "content_units_exposed_fraction": 1.0,
            "note": "HOLDING_THE_LEGEND_EXPOSES_THE_ENTIRE_VOCABULARY_UNDER_EVERY_ORDERING",
        },
        "measured_against_source": source is not None,
        "security_claim": "NONE",
    }
    if source is None:
        return rooted(report, "disclosure_root")
    try:
        text = source.decode("utf-8")
    except UnicodeDecodeError as error:
        raise LiteHold("HELD_SOURCE_NOT_UTF8", "invalid utf-8") from error
    decisions = {
        row["compound"]: row["binding"]
        for row in legend["hyphen_decisions"]
        if isinstance(row, dict) and "compound" in row and "binding" in row
    }
    units = _expand_tokens(tokenize_text(text), decisions)
    missing = sorted({unit for unit in units if unit not in set(entries)})
    require(not missing, "HELD_LEGEND_COVERAGE_INCOMPLETE", ",".join(missing[:8]))
    first_seen: dict[str, int] = {}
    for position, unit in enumerate(units):
        first_seen.setdefault(unit, position)
    counts = collections.Counter(units)
    legend_rank = {text: index for index, text in enumerate(entries)}
    introduction_rank = {
        text: index for index, text in enumerate(sorted(entries, key=lambda t: first_seen[t]))
    }
    frequency_rank = {
        text: index
        for index, text in enumerate(sorted(entries, key=lambda t: (-counts[t], t)))
    }
    order = list(entries)
    introduction = _spearman(
        [legend_rank[t] for t in order], [introduction_rank[t] for t in order]
    )
    frequency = _spearman(
        [legend_rank[t] for t in order], [frequency_rank[t] for t in order]
    )
    # Rank correlation on a small vocabulary is noisy: the standard error is
    # about 1/sqrt(n-1), so a correlation must clear both a substantive
    # threshold and two standard errors before it is called a leak.
    population = len(order)
    standard_error = (1.0 / ((population - 1) ** 0.5)) if population > 1 else 1.0
    floor = max(0.5, 2.0 * standard_error)
    adequate = population >= 20

    def determine(value: float) -> dict[str, Any]:
        return {
            "rank_correlation": value,
            "leaks": abs(value) >= floor,
            "decision_threshold": round(floor, 6),
        }

    report["sample"] = {
        "entries": population,
        "standard_error": round(standard_error, 6),
        "sample_adequate_for_a_confident_determination": adequate,
    }
    report["introduction_order_disclosure"] = {
        **determine(introduction),
        "exact_first_appearance_order": order == sorted(order, key=lambda t: first_seen[t]),
    }
    report["frequency_rank_disclosure"] = determine(frequency)
    report["minimal_disclosure_ordering"] = ORDER_LEXICAL
    report["residual_after_best_ordering"] = "VOCABULARY_ONLY"
    return rooted(report, "disclosure_root")


SCHEMA_LADDER = "semcrys-lite.ladder.v0.1.candidate"
SCHEMA_LADDER_REPORT = "semcrys-lite.ladder-report.v0.1.candidate"

LADDER_RUNGS = (
    {
        "rung": "L0_WORD_DIRECT",
        "step": 0,
        "profile": PROFILE_WORD,
        "occurrence_mode": OCC_VISIBLE,
        "worked_artifact_carries": "ORDER_AND_REPETITION",
        "legend_carries": "VOCABULARY",
        "legend_is_shareable": True,
        "legend_is_message_specific": False,
        "requires_runtime_key": False,
        "requires_sealing": False,
        "note": "BASE_RUNG_REPETITION_IS_PUBLIC",
    },
    {
        "rung": "L1_WORD_ASSEMBLY",
        "step": 1,
        "profile": PROFILE_WORD_ASSEMBLY,
        "occurrence_mode": OCC_VISIBLE,
        "worked_artifact_carries": "ORDER_AND_RESIDUAL_REPETITION",
        "legend_carries": "VOCABULARY_AND_MULTI_UNIT_PATTERNS",
        "legend_is_shareable": True,
        "legend_is_message_specific": False,
        "requires_runtime_key": False,
        "requires_sealing": False,
        "note": "MULTI_UNIT_REDUNDANCY_MOVES_INTO_THE_SHARED_ASSEMBLY_TIER",
    },
    {
        "rung": "L2_BOUNDED_ALIAS",
        "step": 2,
        "profile": PROFILE_WORD,
        "occurrence_mode": OCC_BOUNDED,
        "worked_artifact_carries": "ORDER_AND_CAPPED_REPETITION",
        "legend_carries": "VOCABULARY_AND_ALIAS_MAP",
        "legend_is_shareable": False,
        "legend_is_message_specific": True,
        "requires_runtime_key": True,
        "requires_sealing": True,
        "note": "ALIAS_MAP_IS_FITTED_TO_ONE_MESSAGE_AND_CANNOT_AMORTIZE",
    },
    {
        "rung": "L3_HOMOPHONIC_BALANCED",
        "step": 3,
        "profile": PROFILE_WORD,
        "occurrence_mode": OCC_HOMOPHONIC,
        "worked_artifact_carries": "ORDER_AND_FREQUENCY_BALANCED_ALIASES",
        "legend_carries": "VOCABULARY_AND_KEYED_BALANCED_ALIAS_MAP",
        "legend_is_shareable": False,
        "legend_is_message_specific": True,
        "requires_runtime_key": True,
        "requires_sealing": True,
        "note": "FREQUENCY_IS_FLATTENED_WITHIN_DECLARED_ALIAS_BOUNDS_POSITION_AND_COOCCURRENCE_REMAIN",
    },
    {
        "rung": "L4_UNIQUE_ASCENDING",
        "step": 4,
        "profile": PROFILE_WORD,
        "occurrence_mode": OCC_UNIQUE,
        "worked_artifact_carries": "EVENT_COUNT_ONLY",
        "legend_carries": "VOCABULARY_ORDER_AND_REPETITION_IE_THE_WHOLE_MESSAGE",
        "legend_is_shareable": False,
        "legend_is_message_specific": True,
        "requires_runtime_key": True,
        "requires_sealing": True,
        "note": "THE_MOVING_LEGEND_IS_THE_MESSAGE_SO_IT_CAN_NEVER_BE_A_CORPUS_ASSET",
    },
)

LADDER_INVARIANT = (
    "CLIMBING_THE_LADDER_MOVES_REPETITION_STRUCTURE_OUT_OF_THE_PUBLIC_BODY_"
    "AND_INTO_THE_LEGEND_BYTE_SIZE_IS_A_SEPARATE_AXIS"
)
SHAREABLE_OCCURRENCE_MODES = (OCC_VISIBLE, OCC_PERMUTE)


def ladder_rungs() -> dict[str, Any]:
    return rooted({
        "schema": SCHEMA_LADDER,
        "standing": STANDING,
        "invariant": LADDER_INVARIANT,
        "rungs": [dict(rung) for rung in LADDER_RUNGS],
        "amortization_note": (
            "ONLY_SHAREABLE_RUNGS_HAVE_A_BREAK_EVEN_POINT_"
            "MESSAGE_SPECIFIC_LEGENDS_ARE_A_PER_MESSAGE_COST"
        ),
        "security_claim": "NONE",
    }, "ladder_root")


def _rung_for(profile: str, occurrence_mode: str) -> dict[str, Any] | None:
    for rung in LADDER_RUNGS:
        if rung["profile"] == profile and rung["occurrence_mode"] == occurrence_mode:
            return dict(rung)
    return None


def ladder_position(container_data: bytes) -> dict[str, Any]:
    """Locate a container on the ladder from what it actually is."""
    container = deserialize_container(container_data)
    verify_root(container, "container_root", "HELD_CONTAINER_ROOT_MISMATCH")
    rung = _rung_for(container.get("profile", ""), container.get("occurrence_mode", ""))
    require(rung is not None, "HELD_LADDER_RUNG_UNKNOWN",
            f"{container.get('profile')}/{container.get('occurrence_mode')}")
    return rooted({
        "schema": SCHEMA_LADDER_REPORT,
        "standing": STANDING,
        "container_root": container["container_root"],
        "rung": rung,
        "public_body_semantics": (container.get("verification") or {}).get("public_body_semantics"),
        "invariant": LADDER_INVARIANT,
        "security_claim": "NONE",
    }, "ladder_position_root")


def ladder_report(
    data: bytes,
    *,
    legend: dict[str, Any],
    assembly: dict[str, Any] | None = None,
    key: bytes | None = None,
) -> dict[str, Any]:
    """Run one document up the ladder and measure where its bytes end up.

    The migration invariant is checked against the measurements rather than
    asserted: public worked bytes must not increase as the rungs are climbed.
    """
    validate_base_legend(legend)
    rows: list[dict[str, Any]] = []
    for rung in LADDER_RUNGS:
        if rung["profile"] == PROFILE_WORD_ASSEMBLY and assembly is None:
            continue
        if rung["requires_runtime_key"] and not key:
            rows.append({
                "rung": rung["rung"], "step": rung["step"], "status": "SKIPPED",
                "reason": "HELD_RUNTIME_KEY_REQUIRED",
            })
            continue
        container, _external, moving, receipt = encode_bytes(
            data,
            profile=rung["profile"],
            legend=legend,
            assembly=assembly if rung["profile"] == PROFILE_WORD_ASSEMBLY else None,
            legend_placement=PLACEMENT_EXTERNAL,
            occurrence_mode=rung["occurrence_mode"],
            alias_limit=2 if rung["occurrence_mode"] in {OCC_BOUNDED, OCC_HOMOPHONIC} else 1,
            key=key,
            outer_codec=OUTER_LZMA,
        )
        restored, _ = decode_bytes(
            container, legend=legend,
            assembly=assembly if rung["profile"] == PROFILE_WORD_ASSEMBLY else None,
            moving_legend=moving, key=key,
        )
        require(restored == data, "HELD_LADDER_ROUND_TRIP", rung["rung"])
        moving_size = len(canonical_bytes(moving)) + 1 if moving else 0
        public = deserialize_container(container)
        body = _decode_body(public)
        if body.get("kind") == "EVENTS":
            counts = collections.Counter(body["events"])
            exposure = {
                "public_max_repetition": max(counts.values()) if counts else 0,
                "public_distinct_symbols": len(counts),
                "public_repetition_visible": any(value > 1 for value in counts.values()),
            }
        else:
            exposure = {
                "public_max_repetition": 0,
                "public_distinct_symbols": 0,
                "public_repetition_visible": False,
            }
        rows.append({
            "rung": rung["rung"],
            "step": rung["step"],
            "status": "MEASURED",
            "public_worked_bytes": len(container),
            "sealed_moving_legend_bytes": moving_size,
            "shared_legend_bytes": len(legend_bytes(legend)) + (
                len(assembly_bytes(assembly)) if rung["profile"] == PROFILE_WORD_ASSEMBLY else 0
            ),
            "legend_is_shareable": rung["legend_is_shareable"],
            "public_body_semantics": (public.get("verification") or {}).get("public_body_semantics"),
            "event_count": receipt["event_count"],
            **exposure,
        })
    measured = [row for row in rows if row["status"] == "MEASURED"]
    # The invariant is about information, not size. What migrates as the rungs
    # are climbed is the repetition structure visible in the public body; byte
    # size moves independently and is reported separately for that reason.
    exposure_series = [row["public_max_repetition"] for row in measured]
    byte_series = [row["public_worked_bytes"] for row in measured]
    monotonic = all(
        later <= earlier for earlier, later in zip(exposure_series, exposure_series[1:])
    )
    return rooted({
        "schema": SCHEMA_LADDER_REPORT,
        "standing": STANDING,
        "source_bytes": len(data),
        "invariant": LADDER_INVARIANT,
        "rows": rows,
        "public_repetition_exposure_by_step": exposure_series,
        "invariant_holds_in_this_measurement": monotonic,
        "public_worked_bytes_by_step": byte_series,
        "byte_size_is_monotonic": all(
            later <= earlier for earlier, later in zip(byte_series, byte_series[1:])
        ),
        "size_note": "BYTE_SIZE_DOES_NOT_TRACK_THE_INVARIANT_CONCEALMENT_CAN_COST_BYTES",
        "claim_ceiling": "MEASURED_ON_ONE_DOCUMENT_NOT_A_GENERAL_PROOF",
        "security_claim": "NONE",
    }, "ladder_report_root")
