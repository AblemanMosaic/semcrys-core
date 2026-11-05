"""Canonical human-inspectable integer projection over packed token events.

This is a representation choice, not a stable CSIL namespace or a security
mechanism. SPDX-License-Identifier: Apache-2.0
"""
from pathlib import Path

from streaming_legend import scratch_io as sio

MAGIC=b'SIT1\n'
SCHEMA='semcrys.integer-token.v0.1'
CODEC='DECIMAL_ID_AND_LOWER_HEX_LITERAL_LINES_V1'
MAX_LINE=2*4096+3


def _refuse(code):
    from .core import Refusal
    raise Refusal(code)


def _venc(number):
    if type(number) is not int or not 0<=number<=(1<<64)-1:_refuse('HELD_VARINT_U64_RANGE')
    out=bytearray()
    while True:
        byte=number&127;number>>=7;out.append(byte|(128 if number else 0))
        if not number:return bytes(out)


def _vdec(handle):
    raw=handle.read(1)
    if not raw:return None
    number=shift=0
    while True:
        byte=raw[0]
        if shift==63 and byte>1:_refuse('HELD_VARINT_U64_RANGE')
        number|=(byte&127)<<shift
        if not byte&128:
            if shift and byte==0:_refuse('HELD_NONCANONICAL_VARINT')
            return number
        shift+=7
        if shift>63:_refuse('HELD_MALFORMED_BODY_VARINT')
        raw=handle.read(1)
        if not raw:_refuse('HELD_TRUNCATED_BODY_VARINT')


def encode(packed,output,*,entries,max_unit_bytes):
    events=identifiers=literals=characters=0
    with Path(packed).open('rb') as source,sio.open_output(output,'wb') as target:
        if source.read(4)!=b'SPV2':_refuse('HELD_INTEGER_INPUT_BODY')
        target.write(MAGIC)
        while True:
            identifier=_vdec(source)
            if identifier is None:break
            if identifier:
                if identifier>entries:_refuse('HELD_BODY_ID_RANGE')
                line=b'I:'+str(identifier).encode('ascii')+b'\n';identifiers+=1
            else:
                length=_vdec(source)
                if length is None or not 1<=length<=max_unit_bytes:_refuse('HELD_LITERAL_LENGTH')
                value=source.read(length)
                if len(value)!=length:_refuse('HELD_TRUNCATED_LITERAL')
                line=b'L:'+value.hex().encode('ascii')+b'\n';literals+=1
            target.write(line);events+=1;characters+=len(line)-1
    return {'schema':'semcrys.integer-projection-stats.v0.1','events':events,
      'identifiers':identifiers,'literals':literals,'symbol_characters':characters,
      'packed_bytes':Path(packed).stat().st_size,'projected_bytes':Path(output).stat().st_size}


def decode(projected,output,*,entries,max_unit_bytes,max_packed_bytes):
    events=identifiers=literals=0;written=4
    with Path(projected).open('rb') as source,sio.open_output(output,'wb') as target:
        if source.read(len(MAGIC))!=MAGIC:_refuse('HELD_INTEGER_BODY_MAGIC')
        target.write(b'SPV2')
        while True:
            line=source.readline(MAX_LINE+1)
            if not line:break
            if len(line)>MAX_LINE or not line.endswith(b'\n') or b'\r' in line:_refuse('HELD_INTEGER_LINE')
            value=line[:-1]
            if value.startswith(b'I:'):
                digits=value[2:]
                # Bound before int(): Python itself refuses extremely long
                # decimal strings, which would otherwise escape our typed ABI.
                if not digits or len(digits)>20 or (len(digits)>1 and digits.startswith(b'0')) or not digits.isdigit():_refuse('HELD_INTEGER_IDENTIFIER')
                identifier=int(digits)
                if not 1<=identifier<=entries:_refuse('HELD_BODY_ID_RANGE')
                frame=_venc(identifier);identifiers+=1
            elif value.startswith(b'L:'):
                text=value[2:]
                if not text or len(text)%2 or any(c not in b'0123456789abcdef' for c in text):_refuse('HELD_INTEGER_LITERAL')
                literal=bytes.fromhex(text.decode('ascii'))
                if not 1<=len(literal)<=max_unit_bytes:_refuse('HELD_LITERAL_LENGTH')
                frame=b'\0'+_venc(len(literal))+literal;literals+=1
            else:_refuse('HELD_INTEGER_LINE')
            written+=len(frame)
            if written>max_packed_bytes:_refuse('HELD_DECODED_SIZE_LIMIT')
            target.write(frame);events+=1
    return {'schema':'semcrys.integer-projection-stats.v0.1','events':events,
      'identifiers':identifiers,'literals':literals,'packed_bytes':written,
      'projected_bytes':Path(projected).stat().st_size}
