"""Typed, bounded form programs inside the binary .leg envelope.

The binary reader exposes stored programs; ExecutionLegendReader exposes their
values. Never confuse artifact hashes, local event indices and canonical CSIL.
SPDX-License-Identifier: Apache-2.0
"""
from streaming_legend import scratch_io as sio
import io
from .core import LegendReader,LegendError,_venc,_vdec,_unique_db
from .abi import FORM_MODES,COMPOSED_MODE,RECOGNIZED_UNIT_MODES

UNIT_MODE,COMPACT_MODE=FORM_MODES
MODES=(UNIT_MODE,COMPACT_MODE)
ABI='semcrys.assembly-events.v0.1'
FAMILY_ABI='semcrys.assembly-events.v0.2'
PAIR_MODE=COMPOSED_MODE
PAIR_ABI='semcrys.composed-events.v0.1'
MAX_PAIR_VALUE=1024*1024
MAX_PAIR_DEPTH=64
MAX_VALUE=4096
MAX_DEPTH=32
MAX_RULES=65536
OPERATORS=('EN_PLURAL_OR_3SG_S','EN_PLURAL_OR_3SG_ES','EN_PLURAL_OR_3SG_Y_IES',
 'EN_PAST_ED','EN_PAST_D','EN_PAST_Y_IED','EN_PAST_DOUBLE_ED','EN_PROGRESSIVE_ING',
 'EN_PROGRESSIVE_DROP_E_ING','EN_PROGRESSIVE_DOUBLE_ING','EXPLICIT_REPLACE')

def refuse(code): raise LegendError(code)
def apply(base,operator,replacement=None):
    if operator not in OPERATORS: refuse('HELD_ASSEMBLY_OPERATOR')
    if operator=='EXPLICIT_REPLACE':
        if type(replacement) is not bytes or not replacement or len(replacement)>MAX_VALUE: refuse('HELD_ASSEMBLY_REPLACEMENT')
        return replacement
    if type(base) is not bytes or not base or len(base)>MAX_VALUE: refuse('HELD_ASSEMBLY_BASE')
    # These are explicitly selected spelling transforms, not grammatical inference.
    if not base.isascii() or not base.isalpha() or base!=base.lower(): refuse('HELD_ASSEMBLY_ENGLISH_BASE')
    if operator in ('EN_PLURAL_OR_3SG_Y_IES','EN_PAST_Y_IED'):
        if not base.endswith(b'y'): refuse('HELD_ASSEMBLY_SUFFIX_PRECONDITION')
        value=base[:-1]+(b'ies' if operator=='EN_PLURAL_OR_3SG_Y_IES' else b'ied')
    elif operator=='EN_PROGRESSIVE_DROP_E_ING':
        if not base.endswith(b'e'): refuse('HELD_ASSEMBLY_SUFFIX_PRECONDITION')
        value=base[:-1]+b'ing'
    elif operator in ('EN_PAST_DOUBLE_ED','EN_PROGRESSIVE_DOUBLE_ING'):
        value=base+base[-1:]+(b'ed' if operator=='EN_PAST_DOUBLE_ED' else b'ing')
    else:
        suffix={'EN_PLURAL_OR_3SG_S':b's','EN_PLURAL_OR_3SG_ES':b'es','EN_PAST_ED':b'ed',
            'EN_PAST_D':b'd','EN_PROGRESSIVE_ING':b'ing'}[operator]
        if operator=='EN_PAST_D' and not base.endswith(b'e'): refuse('HELD_ASSEMBLY_SUFFIX_PRECONDITION')
        value=base+suffix
    if len(value)>MAX_VALUE: refuse('HELD_ASSEMBLY_EXPANSION_LIMIT')
    return value

def program(base_id,base,operator,replacement=None):
    if operator not in OPERATORS: refuse('HELD_ASSEMBLY_OPERATOR')
    data=(b'\1'+_venc(base_id)) if base_id is not None else (b'\2'+_venc(len(base))+base)
    data+=bytes([OPERATORS.index(operator)])
    if operator=='EXPLICIT_REPLACE': data+=_venc(len(replacement))+replacement
    return data

def parse_program(data,count):
    if not data or len(data)>2*MAX_VALUE+32: refuse('HELD_ASSEMBLY_PROGRAM_LIMIT')
    if data[:1]==b'\0':
        if len(data)-1>MAX_VALUE: refuse('HELD_ASSEMBLY_EXPANSION_LIMIT')
        return ('LITERAL',data[1:])
    stream=io.BytesIO(data); tag=stream.read(1)
    def integer(): return _vdec(stream,boundary=len(data))
    def literal():
        size=integer()
        if not 1<=size<=MAX_VALUE: refuse('HELD_ASSEMBLY_LITERAL_LIMIT')
        value=stream.read(size)
        if len(value)!=size: refuse('HELD_ASSEMBLY_TRUNCATED')
        return value
    if tag==b'\1':
        operand=integer()
        if not 1<=operand<=count: refuse('HELD_ASSEMBLY_REFERENCE')
    elif tag==b'\2': operand=literal()
    else: refuse('HELD_ASSEMBLY_TAG')
    code=stream.read(1)
    if len(code)!=1 or code[0]>=len(OPERATORS): refuse('HELD_ASSEMBLY_OPERATOR')
    operator=OPERATORS[code[0]]; replacement=literal() if operator=='EXPLICIT_REPLACE' else None
    if stream.read(1): refuse('HELD_ASSEMBLY_TRAILING_PROGRAM')
    return ('REFERENCE' if tag==b'\1' else 'INLINE',operand,operator,replacement)

def compact_program(data):
    if data[:1]==b'\0':
        literal=data[1:]
        return b'\xff\0'+literal[1:] if literal.startswith(b'\xff') else literal
    return b'\xff'+data

def parse_compact(data,count):
    if len(data)>2*MAX_VALUE+32: refuse('HELD_ASSEMBLY_PROGRAM_LIMIT')
    if not data.startswith(b'\xff'):
        return parse_program(b'\0'+data,count)
    if data[:2]==b'\xff\0': return parse_program(b'\0\xff'+data[2:],count)
    if data[:2] not in (b'\xff\1',b'\xff\2'): refuse('HELD_ASSEMBLY_COMPACT_TAG')
    return parse_program(data[1:],count)

def parse_composed(data,count):
    if data.startswith(b'\xff\4'):
        if not 1<=len(data)-2<=MAX_VALUE: refuse('HELD_COMPOSED_LITERAL_LIMIT')
        return ('EVENT_LITERAL',data[2:])
    if not data.startswith(b'\xff\3'): return parse_compact(data,count)
    stream=io.BytesIO(data); stream.read(2)
    left=_vdec(stream,boundary=len(data)); right=_vdec(stream,boundary=len(data))
    if not 1<=left<=count or not 1<=right<=count: refuse('HELD_PAIR_REFERENCE')
    if stream.read(1): refuse('HELD_PAIR_TRAILING_PROGRAM')
    return ('PAIR',left,right)

def pair_program(left,right): return b'\xff\3'+_venc(left)+_venc(right)

class ExecutionLegendReader(LegendReader):
    """Dispatch only this explicit unit mode; preserve ordinary legend bytes."""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.is_composed=self.header['unit_mode']==PAIR_MODE
        self.is_assembly=self.header['unit_mode'] in MODES
        self.assembly_abi=FAMILY_ABI if self.header['unit_mode']==COMPACT_MODE else ABI
        self._parse=parse_compact if self.header['unit_mode']==COMPACT_MODE else parse_program
        if self.is_composed:
            self.is_assembly=True; self.assembly_abi=PAIR_ABI; self._parse=parse_composed
        if self.header['unit_mode'].startswith('COMPOSED_') and not self.is_composed:
            refuse('HELD_COMPOSED_ABI_UNAVAILABLE')
        if self.header['unit_mode'].startswith('ASSEMBLY_') and not self.is_assembly:
            refuse('HELD_ASSEMBLY_ABI_UNAVAILABLE')
        if self.header['unit_mode'] not in RECOGNIZED_UNIT_MODES:
            refuse('HELD_LEGEND_UNIT_MODE_UNAVAILABLE')

    def _expand(self,identifier,trail):
        if identifier in trail: refuse('HELD_ASSEMBLY_CYCLE')
        if len(trail)>=(MAX_PAIR_DEPTH if self.is_composed else MAX_DEPTH): refuse('HELD_ASSEMBLY_DEPTH_LIMIT')
        value=super().get(identifier)
        node=self._parse(value,self.count)
        if node[0] in ('LITERAL','EVENT_LITERAL'): return node[1]
        if node[0]=='PAIR':
            if max(node[1:])>=identifier: refuse('HELD_PAIR_NON_BACKWARD_REFERENCE')
            left=self._expand(node[1],trail+(identifier,)); right=self._expand(node[2],trail+(identifier,))
            if len(left)+len(right)>MAX_PAIR_VALUE: refuse('HELD_PAIR_EXPANSION_LIMIT')
            return left+right
        base=self._expand(node[1],trail+(identifier,)) if node[0]=='REFERENCE' else node[1]
        return apply(base,node[2],node[3])

    def get(self,identifier):
        return self._expand(identifier,()) if self.is_assembly else super().get(identifier)

    def iter_values(self):
        if not self.is_assembly:
            yield from super().iter_values(); return
        # A flat literal scan stays sequential; references are resolved through
        # the existing sparse index. No unbounded graph/cache is materialized.
        for identifier,data in super().iter_values():
            node=self._parse(data,self.count)
            if node[0] in ('LITERAL','EVENT_LITERAL'): value=node[1]
            elif node[0]=='PAIR': value=self._expand(identifier,())
            else:
                base=self._expand(node[1],(identifier,)) if node[0]=='REFERENCE' else node[1]
                value=apply(base,node[2],node[3])
            yield identifier,value

    def verify(self,*,check_duplicates=True):
        result=super().verify(check_duplicates=False if self.is_assembly else check_duplicates)
        if not self.is_assembly: return result
        db=path=None; owned=False
        try:
            # Different event decompositions may spell the same bytes. They
            # retain distinct scoped event IDs; this is not a sense merge.
            if check_duplicates and not self.is_composed: db,path,owned=_unique_db()
            expanded=0
            for _,value in self.iter_values():
                expanded+=len(value)
                if db is not None:
                    import sqlite3
                    try: db.execute('INSERT INTO seen(value) VALUES (?)',(value,))
                    except sqlite3.IntegrityError as exc: raise LegendError('HELD_DUPLICATE_ASSEMBLY_EXPANSION') from exc
        finally:
            if db is not None: db.close()
            if owned: sio.unlink(path,missing_ok=True)
        return {**result,'assembly_abi':self.assembly_abi,'expanded_value_bytes':expanded,
            'canonical_csil_identity':False,'grammar_or_sense_inference':False}
