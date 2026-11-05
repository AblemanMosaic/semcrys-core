"""Explicit bounded importer for historical ordered packed legends.

SPDX-License-Identifier: Apache-2.0
The legacy ordered vocabulary is transport data, not canonical GTK identity.
"""
import hashlib,json,os,struct,tempfile,time
from pathlib import Path
from .library import _bounded_snapshot
from streaming_app.core import Refusal,protect_outputs,_is_root
from streaming_legend import LegendReader,write_legend
from streaming_legend.core import canonical,file_sha256
from streaming_legend import scratch_io as sio

SCHEMA='semcrys.packed.legend.v0.1'
MAX_SOURCE=1024*1024*1024
MAX_ENTRIES=10_000_000
MAX_VALUE=16*1024*1024
U64=struct.Struct('>Q')

def _pairs(rows):
    result={}
    for k,v in rows:
        if k in result: raise Refusal('HELD_ORDERED_DUPLICATE_KEY')
        result[k]=v
    return result

class Stream:
    def __init__(self,path,*,max_value_bytes=MAX_VALUE,chunk=65536):
        self.file=Path(path).open('r',encoding='utf-8',newline='')
        self.buffer=''; self.pos=0; self.eof=False; self.chunk=chunk
        self.limit=6*max_value_bytes+65536
        self.decoder=json.JSONDecoder(object_pairs_hook=_pairs,parse_constant=lambda x: (_ for _ in ()).throw(Refusal('HELD_ORDERED_JSON_CONSTANT')))
    def close(self): self.file.close()
    def more(self):
        self.buffer=self.buffer[self.pos:]; self.pos=0
        try: part=self.file.read(self.chunk)
        except UnicodeError as exc: raise Refusal('HELD_ORDERED_UTF8') from exc
        self.buffer+=part; self.eof=not part
        if len(self.buffer)>self.limit: raise Refusal('HELD_ORDERED_JSON_TOKEN_LIMIT')
    def peek(self):
        while True:
            while self.pos<len(self.buffer) and self.buffer[self.pos] in ' \r\n\t': self.pos+=1
            if self.pos<len(self.buffer): return self.buffer[self.pos]
            if self.eof: return ''
            self.more()
    def take(self,char):
        if self.peek()!=char: raise Refusal('HELD_ORDERED_JSON_SYNTAX',char)
        self.pos+=1
    def value(self,kind):
        first=self.peek()
        if (kind is str and first!='"') or (kind is dict and first!='{') or (kind is int and first not in '-0123456789') or not first:
            raise Refusal('HELD_ORDERED_VALUE_TYPE')
        while True:
            try: value,end=self.decoder.raw_decode(self.buffer,self.pos)
            except (ValueError,RecursionError) as exc:
                if isinstance(exc,Refusal): raise
                if self.eof: raise Refusal('HELD_ORDERED_JSON_VALUE') from exc
                self.more(); continue
            if end==len(self.buffer) and not self.eof:
                self.more(); continue
            if end<len(self.buffer) and self.buffer[end] not in ',]}: \r\n\t': raise Refusal('HELD_ORDERED_JSON_DELIMITER')
            if type(value) is not kind: raise Refusal('HELD_ORDERED_VALUE_TYPE')
            self.pos=end; return value
    def key(self,name,first=False):
        if not first: self.take(',')
        if self.value(str)!=name: raise Refusal('HELD_ORDERED_FIELD_SEQUENCE',name)
        self.take(':')

class OrderedValues:
    def __init__(self,path,*,max_entries=MAX_ENTRIES,max_value_bytes=MAX_VALUE,progress=None,chunk=65536):
        self.stream=Stream(path,max_value_bytes=max_value_bytes,chunk=chunk); self.progress=progress
        self.max_value=max_value_bytes; self.count=0; self.digest=hashlib.sha256(); self.metadata=None
        try:
            s=self.stream; s.take('{'); s.key('schema',True)
            if s.value(str)!=SCHEMA: raise Refusal('HELD_ORDERED_SCHEMA')
            s.key('ordering'); self.ordering=s.value(str)
            if self.ordering!='frequency_desc_first_seen_ties': raise Refusal('HELD_ORDERED_ORDERING')
            s.key('cap'); self.cap=s.value(int); s.key('entries'); self.entries=s.value(int)
            if not 0<=self.entries<=self.cap<=max_entries: raise Refusal('HELD_ORDERED_ENTRY_LIMIT')
            s.key('id2unit'); s.take('[')
        except Exception: self.close(); raise
    def close(self): self.stream.close()
    def __iter__(self):
        s=self.stream
        for index in range(self.entries):
            if index: s.take(',')
            value=s.value(str)
            try: raw=value.encode('utf-8')
            except UnicodeError as exc: raise Refusal('HELD_ORDERED_SURROGATE') from exc
            if not raw or len(raw)>self.max_value: raise Refusal('HELD_ORDERED_UNIT_SIZE')
            self.digest.update(U64.pack(len(raw))); self.digest.update(raw); self.count+=1
            if self.progress and self.count%250000==0: self.progress({'stage':'IMPORT_UNITS','entries':self.count,'total':self.entries})
            yield raw
        s.take(']'); s.key('occurrences'); s.take('['); total=0
        for index in range(self.entries):
            if index: s.take(',')
            n=s.value(int)
            if not 0<=n<=(1<<64)-1: raise Refusal('HELD_ORDERED_OCCURRENCE_RANGE')
            total+=n
        s.take(']'); s.key('train'); train=s.value(dict)
        if set(train)!={'bytes','sha256','token_units','distinct_units'} or not _is_root(train['sha256']): raise Refusal('HELD_ORDERED_TRAIN_METADATA')
        if any(type(train[k]) is not int or not 0<=train[k]<=(1<<64)-1 for k in ('bytes','token_units','distinct_units')) or total>train['token_units']:
            raise Refusal('HELD_ORDERED_TRAIN_METADATA')
        s.key('lineage'); lineage=s.value(str)
        if not lineage or len(lineage)>4096: raise Refusal('HELD_ORDERED_LINEAGE')
        s.take('}')
        if s.peek(): raise Refusal('HELD_ORDERED_TRAILING_DATA')
        self.metadata={'source_schema':SCHEMA,'source_ordering':self.ordering,'source_cap':self.cap,'source_train':train,
            'source_lineage':lineage,'occurrences_sum':total,'ordered_units_sha256':self.digest.hexdigest()}

def import_ordered(source,output,*,expected_source_sha256,max_source_bytes=MAX_SOURCE,max_entries=MAX_ENTRIES,max_value_bytes=MAX_VALUE,progress=None):
    source,output=Path(source),Path(output); protect_outputs([output],[source])
    if not _is_root(expected_source_sha256): raise Refusal('HELD_ORDERED_EXPECTED_ROOT_REQUIRED')
    for value,maximum in [(max_source_bytes,MAX_SOURCE),(max_entries,MAX_ENTRIES),(max_value_bytes,MAX_VALUE)]:
        if type(value) is not int or not 1<=value<=maximum: raise Refusal('HELD_ORDERED_LIMIT')
    if output.suffix.lower()!='.leg': raise Refusal('HELD_LEG_SUFFIX_REQUIRED')
    if source.stat().st_size>max_source_bytes: raise Refusal('HELD_ORDERED_SOURCE_LIMIT')
    instance={'schema':'semcrys.ordered-import-instance.v0.1','standing':'CANDIDATE_ONLY','source_sha256':expected_source_sha256,
        'source_format':SCHEMA,'output_format':'semcrys.legend.binary.v0.2','max_source_bytes':max_source_bytes,
        'max_entries':max_entries,'max_value_bytes':max_value_bytes,'operation_sequence':['SNAPSHOT_VERIFY_ROOT','STREAM_VALIDATE_AND_WRITE','VERIFY_FULL_ORDERED_CORRESPONDENCE','PUBLISH'],
        'id_rule':'LEGACY_ARRAY_POSITION_PLUS_ONE_UNCHANGED','canonical_csil_mutation':False,'security_claim':'NONE'}
    instance['instance_constitution_sha256']=hashlib.sha256(canonical(instance)).hexdigest()
    if progress: progress({'stage':'INSTANCE_COMPILED','effective_configuration':instance})
    output.parent.mkdir(parents=True,exist_ok=True); started=time.perf_counter()
    with sio.TempDirectory(prefix='semcrys-ordered-import-',dir=output.parent) as name:
        work=Path(name); snapshot=work/'source.json'; root=_bounded_snapshot(source,snapshot,max_source_bytes)
        if root!=expected_source_sha256: raise Refusal('HELD_ORDERED_SOURCE_ROOT')
        values=OrderedValues(snapshot,max_entries=max_entries,max_value_bytes=max_value_bytes,progress=progress)
        try:
            pending=work/'converted.leg'
            result=write_legend(pending,values,entry_count=values.entries,legend_id='ORDERED-V01:'+root,unit_mode='TOKEN',max_value_bytes=max_value_bytes)
            metadata=values.metadata
        finally: values.close()
        if progress: progress({'stage':'VERIFY_ORDERED_CORRESPONDENCE','entries':result['entry_count']})
        digest=hashlib.sha256(); count=0
        for identifier,raw in LegendReader(pending,max_entries=max_entries,max_value_bytes=max_value_bytes).iter_values():
            count+=1
            if identifier!=count: raise Refusal('HELD_ORDERED_ID_SEQUENCE')
            digest.update(U64.pack(len(raw))); digest.update(raw)
        if count!=result['entry_count'] or digest.hexdigest()!=metadata['ordered_units_sha256']:
            raise Refusal('HELD_ORDERED_CORRESPONDENCE')
        sio.replace(pending,output)
    return {'schema':'semcrys.ordered-import-result.v0.1','status':'PASS','standing':'CANDIDATE_ONLY',
        'effective_configuration':instance,'source_sha256':root,'output_sha256':file_sha256(output),'entry_count':count,
        'output_bytes':output.stat().st_size,'id_sequence_preserved':True,'metadata':metadata,
        'seconds':time.perf_counter()-started,'original_legend_mutated':False,'meaning_identity_claim':False}
