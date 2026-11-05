"""Reversible token-ID glyph projection, not byte-to-glyph recoding."""
from streaming_legend import scratch_io as sio
import hashlib
from collections import OrderedDict
from pathlib import Path
from streaming_legend.glyph import alphabet_parameters,code_width

MAGIC=b'SGY1\n'

def _scalar(handle):
    from .core import Refusal
    first=handle.read(1)
    if not first: return None
    byte=first[0]
    size=1 if byte<128 else 2 if 0xC2<=byte<=0xDF else 3 if 0xE0<=byte<=0xEF else 4 if 0xF0<=byte<=0xF4 else 0
    if not size: raise Refusal('HELD_INVALID_GLYPH_UTF8')
    raw=first+handle.read(size-1)
    try: return raw.decode('utf-8')
    except UnicodeError as exc: raise Refusal('HELD_INVALID_GLYPH_UTF8') from exc

def encode(source,target,registry,*,entries,max_unit_bytes):
    from .core import Refusal,_vdec,PACKED_MAGIC
    radix,escape=alphabet_parameters(registry); width=code_width(entries,radix)
    alphabet=[g.encode('utf-8') for g in registry['glyphs']]; escape_bytes=escape.encode('utf-8')
    cache=OrderedDict(); cache_bytes=0; symbols=literals=0
    with Path(source).open('rb') as incoming,sio.open_output(Path(target),'wb') as output:
        if incoming.read(4)!=PACKED_MAGIC: raise Refusal('HELD_GLYPH_REQUIRES_TOKEN_STREAM')
        output.write(MAGIC)
        while True:
            identifier=_vdec(incoming)
            if identifier is None: break
            if identifier:
                if identifier>entries: raise Refusal('HELD_GLYPH_ID_RANGE')
                if identifier in cache:
                    frame=cache.pop(identifier); cache[identifier]=frame
                else:
                    number=identifier-1; digits=[b'']*width
                    for index in range(width-1,-1,-1): number,digit=divmod(number,radix); digits[index]=alphabet[digit]
                    frame=b''.join(digits); cache[identifier]=frame; cache_bytes+=len(frame)
                    while len(cache)>4096 or cache_bytes>1024*1024:
                        _,old=cache.popitem(last=False); cache_bytes-=len(old)
                output.write(frame); symbols+=1
            else:
                length=_vdec(incoming)
                if length is None or not 1<=length<=max_unit_bytes: raise Refusal('HELD_LITERAL_LENGTH')
                value=incoming.read(length)
                if len(value)!=length: raise Refusal('HELD_TRUNCATED_LITERAL')
                output.write(escape_bytes+str(length).encode('ascii')+b':'+value.hex().encode('ascii')+b';'); literals+=1
    return {'radix':radix,'width':width,'entries':entries,'literal_escape':escape,'symbols':symbols,'literals':literals,'bytes':Path(target).stat().st_size}

def decode(source,target,registry,*,entries,width,escape,max_unit_bytes,max_packed_bytes):
    from .core import Refusal,_venc,PACKED_MAGIC
    radix,expected_escape=alphabet_parameters(registry)
    if width!=code_width(entries,radix) or escape!=expected_escape: raise Refusal('HELD_GLYPH_PARAMETERS')
    inverse={glyph:index for index,glyph in enumerate(registry['glyphs'])}
    total=0
    with Path(source).open('rb') as incoming,sio.open_output(Path(target),'wb') as output:
        def emit(value):
            nonlocal total
            total+=len(value)
            if total>max_packed_bytes: raise Refusal('HELD_GLYPH_EXPANSION_LIMIT')
            output.write(value)
        if incoming.read(len(MAGIC))!=MAGIC: raise Refusal('HELD_GLYPH_BODY_MAGIC')
        emit(PACKED_MAGIC)
        while True:
            first=_scalar(incoming)
            if first is None: break
            if first==escape:
                digits=bytearray()
                while True:
                    char=incoming.read(1)
                    if char==b':': break
                    if not char or char not in b'0123456789' or len(digits)>=4: raise Refusal('HELD_GLYPH_LITERAL_LENGTH')
                    digits.extend(char)
                if not digits or digits[:1]==b'0': raise Refusal('HELD_GLYPH_LITERAL_LENGTH')
                length=int(digits)
                if not 1<=length<=max_unit_bytes: raise Refusal('HELD_GLYPH_LITERAL_LENGTH')
                encoded=incoming.read(length*2)
                if len(encoded)!=length*2 or incoming.read(1)!=b';': raise Refusal('HELD_TRUNCATED_GLYPH_LITERAL')
                try:
                    value=bytes.fromhex(encoded.decode('ascii'))
                    if value.hex().encode('ascii')!=encoded: raise ValueError()
                except (ValueError,UnicodeError) as exc: raise Refusal('HELD_NONCANONICAL_GLYPH_LITERAL') from exc
                emit(_venc(0)+_venc(length)+value)
            else:
                number=0
                for index in range(width):
                    glyph=first if index==0 else _scalar(incoming)
                    if glyph not in inverse: raise Refusal('HELD_UNKNOWN_OR_TRUNCATED_GLYPH_CODE')
                    number=number*radix+inverse[glyph]
                identifier=number+1
                if identifier>entries: raise Refusal('HELD_GLYPH_ID_RANGE')
                emit(_venc(identifier))
