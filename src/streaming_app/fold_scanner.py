"""Bounded historical wordmode + fold scanner. SPDX-License-Identifier: Apache-2.0

Matches the frozen regex at normal unit sizes, including its asymmetric CJK
behavior (a leading ideograph is isolated; one inside an existing word is not).
Oversize runs are deliberately literalized, not claimed as identical token units.
"""
import codecs
from pathlib import Path

TOKENIZER = "HISTORICAL_WORDMODE_FOLD_BOUNDED_V1"
COMMON_SEPS = (" ", ", ", ". ", ": ", "; ", " (", ") ", "\n", "\r\n", "\n\n", ".\r\n\r\n", " - ", "'s ", ", and ", ". The ")
MARKS = ((0x300,0x36f),(0x483,0x489),(0x64b,0x65f),(0x670,0x670),(0x6d6,0x6ed),(0x900,0x903),(0x93a,0x94f),(0x951,0x957))
NOSPACE = ((0x3040,0x30ff),(0x3400,0x4dbf),(0x4e00,0x9fff),(0xf900,0xfaff))
CONNECTORS = "-_'./"

def _in(c,ranges): return any(a<=ord(c)<=b for a,b in ranges)
def _word(c): return c.isalnum() or _in(c,MARKS)

def iter_raw(path,*,chunk_bytes=1048576,max_unit_bytes=4096):
    from .core import Refusal
    if type(chunk_bytes) is not int or chunk_bytes<1 or type(max_unit_bytes) is not int or not 4<=max_unit_bytes<=4096:
        raise Refusal("HELD_INVALID_SCANNER_LIMIT")
    decoder=codecs.getincrementaldecoder("utf-8")("strict")
    mode=None; pending=bytearray(); connector=""; oversized=False
    def flush():
        nonlocal pending
        if pending:
            result=("lit" if oversized else mode,bytes(pending)); pending=bytearray()
            yield result
    def append(c):
        nonlocal oversized
        raw=c.encode("utf-8")
        if len(pending)+len(raw)>max_unit_bytes:
            oversized=True
            yield from flush()
        pending.extend(raw)
    def consume(c):
        nonlocal mode,connector,oversized
        if mode=="tok":
            if connector:
                if _word(c):
                    yield from append(connector); connector=""
                    yield from append(c); return
                yield from flush(); mode="sep"; oversized=False
                yield from append(connector); connector=""
            elif _word(c):
                yield from append(c); return
            elif c in CONNECTORS:
                connector=c; return
            else:
                yield from flush(); mode="sep"; oversized=False
        if _word(c) or _in(c,NOSPACE):
            yield from flush(); oversized=False
            if _in(c,NOSPACE):
                mode=None; yield "tok",c.encode("utf-8")
            else:
                mode="tok"; yield from append(c)
        else:
            mode="sep"; yield from append(c)
    try:
        with Path(path).open("rb") as handle:
            while raw:=handle.read(chunk_bytes):
                for c in decoder.decode(raw,final=False): yield from consume(c)
            decoder.decode(b"",final=True)
    except UnicodeDecodeError as exc: raise Refusal("HELD_SOURCE_NOT_UTF8",str(exc.start)) from exc
    yield from flush()
    if connector: yield "sep",connector.encode("utf-8")

def iter_folded(path,*,chunk_bytes=1048576,max_unit_bytes=4096):
    allow={s.encode("utf-8") for s in COMMON_SEPS}
    held=None
    for kind,value in iter_raw(path,chunk_bytes=chunk_bytes,max_unit_bytes=max_unit_bytes):
        if held is not None:
            if kind=="sep" and value in allow and len(held)+len(value)<=max_unit_bytes:
                yield "tok",held+value; held=None; continue
            yield "tok",held; held=None
        if kind=="tok": held=value
        else: yield kind,value
    if held is not None: yield "tok",held
