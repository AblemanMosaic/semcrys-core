"""Exact .gly v0.1 registry; token-projection qualification is explicit."""
import hashlib
import json
from pathlib import Path
from .core import canonical,LegendError

MAX_BYTES=4*1024*1024
MAX_GLYPHS=65536

def registry(glyphs,*,name,kind='TEMPLATE',bindings=None):
    if not isinstance(name,str) or not name or type(glyphs) is not list or not 1<=len(glyphs)<=MAX_GLYPHS:
        raise LegendError('HELD_INVALID_GLYPH_REGISTRY')
    if any(not isinstance(g,str) or len(g)!=1 or 0xD800<=ord(g)<=0xDFFF for g in glyphs) or len(set(glyphs))!=len(glyphs):
        raise LegendError('HELD_INVALID_GLYPH_SET')
    bound={} if bindings is None else bindings
    if type(bound) is not dict or kind not in ('TEMPLATE','BOUND'): raise LegendError('HELD_INVALID_GLYPH_KIND')
    if kind=='TEMPLATE' and bound: raise LegendError('HELD_TEMPLATE_HAS_BINDINGS')
    if kind=='BOUND' and (set(bound)!=set(glyphs) or any(not isinstance(v,str) or not v for v in bound.values())):
        raise LegendError('HELD_INCOMPLETE_GLYPH_BINDINGS')
    value={'schema':'semcrys.glyph-registry.v0.1','standing':'CANDIDATE_ONLY','name':name,'kind':kind,'glyphs':glyphs,'bindings':bound}
    try: data=canonical(value)
    except (UnicodeError,ValueError,RecursionError) as exc: raise LegendError('HELD_INVALID_GLYPH_REGISTRY') from exc
    if len(data)>MAX_BYTES: raise LegendError('HELD_GLYPH_REGISTRY_LIMIT')
    return value

def parse(data):
    if len(data)>MAX_BYTES: raise LegendError('HELD_GLYPH_REGISTRY_LIMIT')
    try:
        value=json.loads(data.decode('utf-8'))
        if type(value) is not dict or set(value)!={'schema','standing','name','kind','glyphs','bindings'}:
            raise LegendError('HELD_INVALID_GLYPH_SCHEMA')
        rebuilt=registry(value['glyphs'],name=value['name'],kind=value['kind'],bindings=value['bindings'])
        if value!=rebuilt or data!=canonical(rebuilt): raise LegendError('HELD_NONCANONICAL_GLYPH_REGISTRY')
        return rebuilt
    except (UnicodeError,ValueError,RecursionError) as exc:
        if isinstance(exc,LegendError): raise
        raise LegendError('HELD_INVALID_GLYPH_JSON') from exc

def load(path):
    with Path(path).open('rb') as handle: data=handle.read(MAX_BYTES+1)
    return parse(data),data,hashlib.sha256(data).hexdigest()

def alphabet_parameters(value):
    if value['kind']!='TEMPLATE': raise LegendError('HELD_BOUND_GLYPH_SEMANTICS_NOT_INFERRED')
    glyphs=value['glyphs']
    if len(glyphs)<2: raise LegendError('HELD_GLYPH_RADIX_REQUIRES_TWO')
    used=set(glyphs)
    # The first absent scalar is a literal introducer, never a token digit.
    escape=next((g for g in '~^|' if g not in used),None)
    if escape is None:
        escape=next(chr(code) for code in range(0xE000,0x10FFFF+1) if not 0xD800<=code<=0xDFFF and chr(code) not in used)
    return len(glyphs),escape

def code_width(count,radix):
    if type(count) is not int or not 0<=count<=(1<<64)-1: raise LegendError('HELD_GLYPH_ID_DIMENSION')
    width=1; capacity=radix
    while capacity<max(1,count): width+=1; capacity*=radix
    return width
