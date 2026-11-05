"""Bounded copies of private, preverified archive input spans.
SPDX-License-Identifier: Apache-2.0
"""
import hashlib,os
from pathlib import Path
from streaming_app.core import Refusal
from streaming_legend.crys_v2 import PROLOGUE,SECTION

BLOCK_BYTES=1024*1024
def stamp(st):return (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)
def exact(source,n):
    value=source.read(n)
    if len(value)!=n:raise Refusal('HELD_META_TEMPLATE_TRUNCATED')
    return value

class FileSpan:
    def __init__(self,path,offset=0,length=None,*,identity=None,handle_identity=None):
        self.path=Path(path);self.identity=stamp(self.path.stat()) if identity is None else identity
        if handle_identity is None:
            with self.path.open('rb') as source:
                handle_identity=stamp(os.fstat(source.fileno()))
            if handle_identity[:4]!=self.identity[:4] or stamp(self.path.stat())!=self.identity:
                raise Refusal('HELD_META_SPAN_CHANGED')
        self.handle_identity=handle_identity
        total=self.identity[2]
        if length is None:length=total-offset
        if type(offset) is not int or type(length) is not int or offset<0 or length<0 or offset+length>total:
            raise Refusal('HELD_META_SPAN_BOUNDS')
        self.offset,self.length=offset,length
        # Metadata is an early refusal signal, not content custody. Windows
        # can expose unchanged creation/change times for a same-size rewrite.
        digest=hashlib.sha256()
        with self.path.open('rb') as source:
            if stamp(os.fstat(source.fileno()))!=self.handle_identity:raise Refusal('HELD_META_SPAN_CHANGED')
            source.seek(offset);remaining=length
            while remaining:
                block=exact(source,min(remaining,BLOCK_BYTES));digest.update(block);remaining-=len(block)
            if stamp(os.fstat(source.fileno()))!=self.handle_identity:raise Refusal('HELD_META_SPAN_CHANGED')
        if stamp(self.path.stat())!=self.identity:raise Refusal('HELD_META_SPAN_CHANGED')
        self.content_sha256=digest.digest()
    def __len__(self):return self.length
    def copy_to(self,output):
        if stamp(self.path.stat())!=self.identity:raise Refusal('HELD_META_SPAN_CHANGED')
        with self.path.open('rb') as source:
            if stamp(os.fstat(source.fileno()))!=self.handle_identity:raise Refusal('HELD_META_SPAN_CHANGED')
            source.seek(self.offset);remaining=self.length;digest=hashlib.sha256()
            while remaining:
                block=source.read(min(remaining,BLOCK_BYTES))
                if not block:raise Refusal('HELD_META_SPAN_TRUNCATED')
                digest.update(block);output.write(block);remaining-=len(block)
            if digest.digest()!=self.content_sha256:raise Refusal('HELD_META_SPAN_CHANGED')
            if stamp(os.fstat(source.fileno()))!=self.handle_identity:raise Refusal('HELD_META_SPAN_CHANGED')
        if stamp(self.path.stat())!=self.identity:raise Refusal('HELD_META_SPAN_CHANGED')

def template_spans(path,indices):
    path=Path(path);identity=stamp(path.stat());total=identity[2]
    with path.open('rb') as source:
        handle_identity=stamp(os.fstat(source.fileno()))
        if handle_identity[:4]!=identity[:4]:raise Refusal('HELD_META_SPAN_CHANGED')
        _,_,_,header_bytes=PROLOGUE.unpack(exact(source,PROLOGUE.size))
        pos=PROLOGUE.size+header_bytes;start=0;parts=[];done=False
        while pos<total:
            source.seek(pos)
            code,_,_,size,_=SECTION.unpack(exact(source,SECTION.size))
            lo=pos+SECTION.size;hi=lo+size
            if hi>total:raise Refusal('HELD_META_TEMPLATE_TRUNCATED')
            if code==b'LEGD':
                digest=hashlib.sha256();remaining=size
                while remaining:
                    block=exact(source,min(remaining,BLOCK_BYTES));digest.update(block);remaining-=len(block)
                key=digest.hexdigest()
                if key not in indices:raise Refusal('HELD_META_TEMPLATE_LEGEND')
                parts.append((0,FileSpan(path,start,lo-start,identity=identity,handle_identity=handle_identity)))
                parts.append((1,indices[key]));start=hi
            pos=hi
            if len(parts)>8192:raise Refusal('HELD_META_TEMPLATE_SEGMENTS')
            if code==b'DONE':done=True;break
        if not done:raise Refusal('HELD_META_TEMPLATE_END')
        if stamp(os.fstat(source.fileno()))!=handle_identity:raise Refusal('HELD_META_SPAN_CHANGED')
    if stamp(path.stat())!=identity:raise Refusal('HELD_META_SPAN_CHANGED')
    parts.append((0,FileSpan(path,start,total-start,identity=identity,handle_identity=handle_identity)))
    return parts
