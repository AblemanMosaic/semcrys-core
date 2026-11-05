"""Compact virtual legend projection ABI. SPDX-License-Identifier: Apache-2.0"""
import hashlib
import io
import json
import struct
from pathlib import Path
from .core import LegendError,canonical,_venc,_vdec

MAGIC=b"SCFOLD\x1a\n"
SCHEMA="semcrys.legend.fold-projection.v0.1"
COMPACT_SCHEMA="semcrys.legend.fold-projection.v0.2"
AUDIT_FIELDS={'ordering','calibration_roots','candidate_policy'}
MAX_BYTES=4*1024*1024
MAX_FRONT=65536
MAX_VALUE_BYTES=4096
MAX_FRONT_VALUE_BYTES=16*1024*1024
SIGNAL_CODEC="MOVE_BASE_OR_CONCAT_TWO_BASE_ULEB128_V1"
ORDERING="CALIBRATION_COUNT_DESC_FIRST_SEEN_ASC"
CANDIDATE_POLICY="OBSERVED_UNITS_PLUS_LONGEST_SEPARATOR_COMPONENTS_V1"
TOKENIZER="HISTORICAL_WORDMODE_FOLD_BOUNDED_V1"

def root(value): return isinstance(value,str) and len(value)==64 and all(c in "0123456789abcdef" for c in value)
def refuse(code): raise LegendError(code)
def serialize(header,signal):
    data=canonical(header)
    output=MAGIC+struct.pack(">I",len(data))+data+signal
    parse(output)
    return output

def parse(data):
    if type(data) is not bytes or len(data)>MAX_BYTES: refuse("HELD_FOLD_ARTIFACT_LIMIT")
    if len(data)<12 or data[:8]!=MAGIC: refuse("HELD_FOLD_MAGIC")
    size=struct.unpack(">I",data[8:12])[0]
    if size>65536 or 12+size>len(data): refuse("HELD_FOLD_HEADER_LIMIT")
    raw=data[12:12+size]
    try:
        h=json.loads(raw.decode("utf-8"))
        if type(h) is not dict or canonical(h)!=raw: refuse("HELD_FOLD_NONCANONICAL_HEADER")
    except (ValueError,UnicodeError,RecursionError) as exc:
        if isinstance(exc,LegendError): raise
        raise LegendError("HELD_FOLD_HEADER") from exc
    required={"schema","standing","base_legend_sha256","base_entries","front_entries","macro_entries",
        "projected_entries","signal_sha256","signal_codec","tokenizer","max_unit_bytes","front_cap",
        "ordering","calibration_roots","candidate_policy"}
    compact=h.get('schema')==COMPACT_SCHEMA
    if compact: required=(required-AUDIT_FIELDS)|{'provenance_sha256'}
    if set(h)!=required or h["schema"] not in (SCHEMA,COMPACT_SCHEMA) or h["standing"]!="CANDIDATE_ONLY": refuse("HELD_FOLD_SCHEMA")
    if compact and not root(h['provenance_sha256']): refuse('HELD_FOLD_PROVENANCE_ROOT')
    if not root(h["base_legend_sha256"]) or not root(h["signal_sha256"]): refuse("HELD_FOLD_ROOT")
    for key,maximum in (("base_entries",1000000000),("front_entries",MAX_FRONT),("macro_entries",MAX_FRONT),
                        ("projected_entries",1000000000+MAX_FRONT),("front_cap",MAX_FRONT)):
        if type(h[key]) is not int or not 0<=h[key]<=maximum: refuse("HELD_FOLD_COUNT")
    if type(h["max_unit_bytes"]) is not int or h["max_unit_bytes"]!=MAX_VALUE_BYTES: refuse("HELD_FOLD_UNIT_LIMIT")
    if h["signal_codec"]!=SIGNAL_CODEC or h["tokenizer"]!=TOKENIZER:
        refuse("HELD_FOLD_MECHANISM")
    if not compact:
        if h['ordering']!=ORDERING or h['candidate_policy']!=CANDIDATE_POLICY: refuse('HELD_FOLD_MECHANISM')
        if type(h["calibration_roots"]) is not list or not 1<=len(h["calibration_roots"])<=512 or any(not root(r) for r in h["calibration_roots"]):
            refuse("HELD_FOLD_CALIBRATION_ROOTS")
    if h["macro_entries"]>h["front_entries"] or h["front_entries"]>h["front_cap"] or h["projected_entries"]!=h["base_entries"]+h["macro_entries"]:
        refuse("HELD_FOLD_CARDINALITY")
    signal=data[12+size:]
    if hashlib.sha256(signal).hexdigest()!=h["signal_sha256"]: refuse("HELD_FOLD_SIGNAL_ROOT")
    stream=io.BytesIO(signal)
    def integer():
        try: return _vdec(stream,boundary=len(signal))
        except LegendError as exc: raise LegendError("HELD_FOLD_VARINT",str(exc)) from exc
    if integer()!=h["front_entries"]: refuse("HELD_FOLD_FRONT_COUNT")
    entries=[]; moved=set(); pairs=set(); macros=0
    for _ in range(h["front_entries"]):
        tag=stream.read(1)
        if tag not in (b"\0",b"\1"): refuse("HELD_FOLD_TAG")
        ranks=(integer(),) if tag==b"\0" else (integer(),integer())
        if any(not 1<=n<=h["base_entries"] for n in ranks): refuse("HELD_FOLD_BASE_RANK")
        if tag==b"\0":
            if ranks[0] in moved: refuse("HELD_FOLD_DUPLICATE_BASE")
            moved.add(ranks[0])
        else:
            if ranks in pairs: refuse("HELD_FOLD_DUPLICATE_MACRO")
            pairs.add(ranks); macros+=1
        entries.append(ranks)
    if stream.read(1): refuse("HELD_FOLD_TRAILING_BYTES")
    if macros!=h["macro_entries"]: refuse("HELD_FOLD_MACRO_COUNT")
    return h,entries,signal

def load(path):
    path=Path(path)
    if path.suffix.lower()!=".leg": refuse("HELD_LEG_SUFFIX_REQUIRED")
    if path.stat().st_size>MAX_BYTES: refuse("HELD_FOLD_ARTIFACT_LIMIT")
    with path.open("rb") as f: data=f.read(MAX_BYTES+1)
    h,entries,signal=parse(data)
    return h,entries,signal,data,hashlib.sha256(data).hexdigest()

def encode_signal(entries):
    data=bytearray(_venc(len(entries)))
    for ranks in entries:
        data.append(0 if len(ranks)==1 else 1)
        for n in ranks: data.extend(_venc(n))
    return bytes(data)

def binding(header,digest,mode='EMBEDDED'):
    value={"schema":header['schema'],"sha256":digest,"mode":mode,"base_legend_sha256":header["base_legend_sha256"],
        "front_entries":header["front_entries"],"projected_entries":header["projected_entries"]}
    validate_binding(value)
    return value

def validate_binding(value):
    keys={'schema','sha256','mode','base_legend_sha256','front_entries','projected_entries'}
    if type(value) is not dict or set(value)!=keys or value['schema'] not in (SCHEMA,COMPACT_SCHEMA) or value['mode'] not in ('EMBEDDED','EXTERNAL'):
        refuse('HELD_FOLD_BINDING_SCHEMA')
    if not root(value['sha256']) or not root(value['base_legend_sha256']): refuse('HELD_FOLD_ROOT')
    for key,maximum in (('front_entries',MAX_FRONT),('projected_entries',1000000000+MAX_FRONT)):
        if type(value[key]) is not int or not 0<=value[key]<=maximum: refuse('HELD_FOLD_COUNT')
    if value['front_entries']>value['projected_entries']: refuse('HELD_FOLD_CARDINALITY')

def reference(value):
    validate_binding(value)
    if value['mode']!='EXTERNAL': refuse('HELD_FOLD_REFERENCE_MODE')
    return canonical({'schema':'semcrys.fold-reference.v0.1','binding':value})

def parse_reference(data):
    try: value=json.loads(data.decode('utf-8'))
    except (ValueError,UnicodeError,RecursionError) as exc: raise LegendError('HELD_FOLD_REFERENCE_SCHEMA') from exc
    if type(value) is not dict or set(value)!={'schema','binding'} or value['schema']!='semcrys.fold-reference.v0.1':
        refuse('HELD_FOLD_REFERENCE_SCHEMA')
    if reference(value['binding'])!=data: refuse('HELD_FOLD_NONCANONICAL_REFERENCE')
    return value['binding']

def inspect(path):
    h,entries,signal,data,digest=load(path)
    result={"status":"PASS","schema":"semcrys.fold-inspection.v0.1","standing":"CANDIDATE_ONLY",
        "sha256":digest,"header":h,"signal_bytes":len(signal),"artifact_bytes":len(data),
        "base_dependent_semantic_validation":"REQUIRES_EXACT_BASE","canonical_csil_identity":False}
    if h['schema']==COMPACT_SCHEMA:
        result.update(provenance_status='ROOT_REFERENCED_NOT_LOADED_OR_VERIFIED',
            provenance_sha256=h['provenance_sha256'],provenance_required_for_inverse=False,
            provenance_required_for_source_audit=True)
    return result
