"""Explicit historical SC import. Format reimplementation, not old runtime execution.
SPDX-License-Identifier: Apache-2.0
"""
import codecs,hashlib,io,json,re
from importlib.resources import files
from pathlib import Path
from streaming_app.core import Refusal,encode_file,decode_file,protect_outputs
from streaming_legend.core import file_sha256,canonical
from streaming_legend import scratch_io as sio
from streaming_legend.block_output import open_output
from .publication_resources import root

MAX_SOURCE=64*1024**2;MAX_JSON=64*1024**2;MAX_OUTPUT=128*1024**2
MAX_ENTRIES=1000000;MAX_VALUE=16*1024**2;MAX_CODE=64
def fail(code):raise Refusal('HELD_LEGACY_'+code)
def number(n,maximum,minimum=0):
    if type(n) is not int or not minimum<=n<=maximum:fail('LIMIT')
    return n
def digest(value):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{64}',value):fail('HASH')
    return value
def pairs(rows):
    d={}
    for k,v in rows:
        if k in d:fail('DUPLICATE_JSON_KEY')
        d[k]=v
    return d
def parse(data):
    if len(data)>MAX_JSON:fail('METADATA_LIMIT')
    try:return json.loads(data.decode('utf-8'),object_pairs_hook=pairs,
        parse_constant=lambda x:fail('NONFINITE_JSON'))
    except (UnicodeError,ValueError,RecursionError) as exc:
        if isinstance(exc,Refusal):raise
        raise Refusal('HELD_LEGACY_JSON') from exc
def text(value,maximum=MAX_VALUE,empty=True):
    if type(value) is not str or (not empty and not value):fail('STRING')
    try:raw=value.encode('utf-8')
    except UnicodeError as exc:raise Refusal('HELD_LEGACY_UNICODE') from exc
    if len(raw)>maximum:fail('VALUE_LIMIT')
    return value
def snapshot(source,target,limit,expected=None):
    total=0;h=hashlib.sha256()
    with Path(source).open('rb') as src,sio.open_output(target,'wb') as dst:
        while data:=src.read(1024*1024):
            total+=len(data)
            if total>limit:fail('SOURCE_LIMIT')
            dst.write(data);h.update(data)
    value=h.hexdigest()
    if expected is not None and value!=digest(expected):fail('SOURCE_ROOT')
    return value
def legacy_legend_hash(entries):
    return hashlib.sha256(json.dumps(entries,sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest()
def validate_header(h,kind):
    if type(h) is not dict:fail('HEADER')
    if 'members' in h:fail('MEMBER_ARCHIVE_UNQUALIFIED')
    common={'v','registry','mode','sha256','symbols'}
    allowed=common|({'emit'} if kind=='SC_PACKED' else
        {'base','width','width_mode','placement','legend_sha256','order','grouping','bind','ordering_cost'})
    required={'v','sha256','registry'}|({'emit','symbols','mode'} if kind=='SC_PACKED' else {'base','width','legend_sha256'})
    if set(h)-allowed or not required<=set(h):fail('HEADER_FIELDS')
    if type(h['v']) is not int or h['v'] not in ((1,) if kind=='SC_PACKED' else (1,2)):fail('VERSION')
    text(h['registry'],4096,False);digest(h['sha256'])
    if 'symbols' in h:number(h['symbols'],MAX_ENTRIES)
    if 'mode' in h and h['mode'] not in ('word','blob'):fail('MODE')
    if kind=='SC_PACKED':
        if h['emit']!='packed':fail('PACKED_HEADER')
    else:
        digest(h['legend_sha256']);number(h['base'],200000,2)
        mode=h.get('width_mode','fixed')
        if mode not in ('fixed','variable'):fail('WIDTH_MODE')
        if mode=='fixed':number(h['width'],MAX_CODE,1)
        elif type(h['width']) is not int or h['width']!=0:fail('WIDTH')
        if 'placement' in h and h['placement'] not in ('embedded','sidecar','shared'):fail('PLACEMENT')
    return h
def registry(path,h):
    v=parse(path.read_bytes())
    if type(v) is not dict or v.get('schema')!='semcrys.gly.v1':fail('GLYPH_SCHEMA')
    if set(v)-{'schema','name','kind','glyphs','bindings','bounded','notes'}:fail('GLYPH_FIELDS')
    glyphs=v.get('glyphs')
    if type(glyphs) is not list or len(glyphs)!=h['base'] or v.get('name')!=h['registry']:fail('GLYPH_BINDING')
    if any(type(g) is not str or len(g)!=1 or 0xD800<=ord(g)<=0xDFFF for g in glyphs) or len(set(glyphs))!=len(glyphs):fail('GLYPHS')
    if 'kind' in v and v['kind'] not in ('bound','template'):fail('GLYPH_KIND')
    if 'bounded' in v and type(v['bounded']) is not bool:fail('GLYPH_FIELDS')
    bindings=v.get('bindings',{})
    if type(bindings) is not dict:fail('GLYPH_BINDINGS')
    for k,value in bindings.items():text(k,MAX_CODE*4,False);text(value)
    return glyphs
def entries(v,h):
    if type(v) is not dict:fail('LEGEND')
    if v.get('schema')=='semcrys.legend.v1':
        if set(v)-{'schema','registry','width','entries','docs','min_docs','total','homophony','sha256'}:fail('LEGEND_FIELDS')
        if type(v.get('width')) is not int:fail('LEGEND_BINDING')
        for key in ('docs','min_docs','homophony'):
            if key in v:number(v[key],1<<40)
        if 'total' in v and type(v['total']) is not bool:fail('LEGEND_FIELDS')
        if v.get('registry')!=h['registry'] or v.get('width')!=h['width']:fail('LEGEND_BINDING')
        e=v.get('entries')
        if type(e) is not dict or v.get('sha256')!=legacy_legend_hash(e):fail('LEGEND_ROOT')
    else:e=v
    if len(e)>MAX_ENTRIES:fail('ENTRY_LIMIT')
    for k,value in e.items():
        text(k,MAX_CODE*4,False);text(value)
        if len(k)>MAX_CODE:fail('CODE_LIMIT')
    if legacy_legend_hash(e)!=h['legend_sha256']:fail('LEGEND_ROOT')
    return e
def line(src):
    b=src.readline(MAX_JSON+1)
    if len(b)>MAX_JSON:fail('METADATA_LIMIT')
    if not b.endswith(b'\n'):fail('TEXT_FRAME')
    return b[:-1]
class Sink:
    def __init__(self,out,limit):self.out=out;self.limit=limit;self.size=0;self.hash=hashlib.sha256()
    def write(self,data):
        if self.size+len(data)>self.limit:fail('OUTPUT_LIMIT')
        self.out.write(data);self.size+=len(data);self.hash.update(data)
def decode_text(source,out,legend,glyph,limit):
    with source.open('rb') as f:
        first=line(f)
        if not first.startswith('§SC1 '.encode('utf-8')):fail('TEXT_MAGIC')
        h=validate_header(parse(first[len('§SC1 '.encode('utf-8')):]),'SC_TEXT')
        second=line(f);embedded=second.startswith('§LEGEND '.encode('utf-8'))
        if embedded:
            if legend is not None or h.get('placement') in ('sidecar','shared'):fail('LEGEND_PLACEMENT')
            e=entries(parse(second[len('§LEGEND '.encode('utf-8')):]),h);second=line(f)
        else:
            if legend is None or h.get('placement')=='embedded':fail('LEGEND_REQUIRED')
            e=entries(parse(legend.read_bytes()),h)
        if second!='§BODY'.encode('utf-8'):fail('TEXT_FRAME')
        glyphs=registry(glyph,h);gset=set(glyphs);variable=h.get('width_mode','fixed')=='variable'
        continuation=set(glyphs[len(glyphs)-max(1,len(glyphs)//16):]) if variable else set()
        if variable and len(gset-continuation)<2:fail('VARIABLE_RADIX')
        for code in e:
            if not set(code)<=gset:fail('CODE_ALPHABET')
            if variable:
                if not set(code[:-1])<=continuation or code[-1] in continuation:fail('CODE_GRAMMAR')
            elif len(code)!=h['width']:fail('CODE_WIDTH')
        # Incremental UTF-8 and code carry preserve splits and exact line endings.
        decoder=codecs.getincrementaldecoder('utf-8')('strict');pending=''
        with open_output(out) as writer:
            sink=Sink(writer,limit)
            while True:
                block=f.read(65536)
                try:chunk=decoder.decode(block,final=not block)
                except UnicodeError as exc:raise Refusal('HELD_LEGACY_UNICODE') from exc
                for c in chunk:
                    if pending or c in gset:
                        if c not in gset:fail('CODE_GRAMMAR')
                        pending+=c
                        if len(pending)>MAX_CODE:fail('CODE_LIMIT')
                        complete=c not in continuation if variable else len(pending)==h['width']
                        if complete:
                            if pending not in e:fail('UNKNOWN_CODE')
                            sink.write(e[pending].encode('utf-8'));pending=''
                    else:sink.write(c.encode('utf-8'))
                if not block:break
            if pending:fail('TRUNCATED_CODE')
    if sink.hash.hexdigest()!=h['sha256']:fail('DECODED_ROOT')
    return h,sink.size
def varint(src,eof=False):
    n=0
    for i in range(10):
        b=src.read(1)
        if not b:
            if eof and i==0:return None
            fail('TRUNCATED_VARINT')
        x=b[0];n|=(x&127)<<(7*i)
        if not x&128:
            if i and x==0:fail('NONCANONICAL_VARINT')
            if n>0xFFFFFFFFFFFFFFFF:fail('VARINT_LIMIT')
            return n
    fail('VARINT_LIMIT')
def blob(src):
    n=varint(src);number(n,MAX_JSON)
    b=src.read(n)
    if len(b)!=n:fail('TRUNCATED_METADATA')
    return parse(b)
def decode_packed(source,out,limit):
    with source.open('rb') as src:
        if src.read(4)!=b'SCB1':fail('PACKED_MAGIC')
        h=validate_header(blob(src),'SC_PACKED');units=blob(src)
        if type(units) is not list or len(units)!=h['symbols'] or len(units)>MAX_ENTRIES:fail('UNITS')
        values=[text(v).encode('utf-8') for v in units]
        with open_output(out) as writer:
            sink=Sink(writer,limit)
            while (n:=varint(src,eof=True)) is not None:
                if n:
                    if n>len(values):fail('UNKNOWN_ID')
                    sink.write(values[n-1])
                else:
                    remaining=varint(src)
                    if remaining>limit-sink.size:fail('OUTPUT_LIMIT')
                    decoder=codecs.getincrementaldecoder('utf-8')('strict')
                    while remaining:
                        data=src.read(min(65536,remaining))
                        if not data:fail('TRUNCATED_LITERAL')
                        remaining-=len(data)
                        try:decoder.decode(data,final=not remaining)
                        except UnicodeError as exc:raise Refusal('HELD_LEGACY_UNICODE') from exc
                        sink.write(data)
    if sink.hash.hexdigest()!=h['sha256']:fail('DECODED_ROOT')
    return h,sink.size
def migrate(source,output,*,format,expected_source_sha256,legacy_legend=None,legacy_glyph=None,
            profile='C:SELF_CONTAINED_TOKEN',external_legends=(),outer_codec='NONE',legend_policy=None,
            max_source_bytes=MAX_SOURCE,max_decoded_bytes=MAX_OUTPUT,progress=None):
    if sio.ACTIVE.get() is None:fail('OWNER_SCOPE_REQUIRED')
    number(max_source_bytes,MAX_SOURCE);number(max_decoded_bytes,MAX_OUTPUT);digest(expected_source_sha256)
    if format not in ('SC_TEXT','SC_PACKED'):fail('FORMAT')
    if format=='SC_TEXT' and legacy_glyph is None:fail('GLYPH_REQUIRED')
    if format=='SC_PACKED' and (legacy_legend is not None or legacy_glyph is not None):fail('UNUSED_DEPENDENCY')
    deps=[p for p in (legacy_legend,legacy_glyph) if p is not None]
    protect_outputs([output],[source,*deps,*external_legends])
    model=json.loads(files('semcrys').joinpath('LEGACY_MIGRATION_CONTRACT.json').read_text(encoding='utf-8'))
    if model['CM1']['max_source_bytes']!=MAX_SOURCE or model['CM1']['max_decoded_bytes']!=MAX_OUTPUT:fail('MODEL')
    with sio.TempDirectory(prefix='legacy-') as folder:
        w=Path(folder);src=w/'source'
        sr=snapshot(source,src,max_source_bytes,expected_source_sha256)
        snapshots={};roots={}
        for role,path in (('legend',legacy_legend),('glyph',legacy_glyph)):
            if path is not None:
                snapshots[role]=w/role;roots[role]=snapshot(path,snapshots[role],MAX_JSON)
        ic={'schema':'semcrys.legacy-migration-instance.v0.1','standing':'CANDIDATE_ONLY',
            'model':model,'model_root':root(model),'format':format,'source_sha256':sr,'legacy_dependencies':roots,
            'profile':profile,'outer_codec':outer_codec,'legend_policy':legend_policy,
            'current_legend_roots':[file_sha256(p) for p in external_legends],
            'max_source_bytes':max_source_bytes,'max_decoded_bytes':max_decoded_bytes,
            'operation_sequence':['ROOT_PRIVATE_SNAPSHOTS','STRICT_LEGACY_PARSE','STREAM_DECODE','VERIFY_ORIGINAL_SOURCE_HASH',
                'CURRENT_PROFILE_ENCODE','VERIFY_CURRENT_INVERSE','RECHECK_INPUT_CUSTODY'],
            'authority_effect':'NONE','security_claim':'NONE'}
        ic['instance_constitution_sha256']=root(ic)
        if progress:progress(json.loads(json.dumps({'stage':'LEGACY_INSTANCE_COMPILED','effective_configuration':ic})))
        decoded=w/'decoded'
        if format=='SC_TEXT':header,n=decode_text(src,decoded,snapshots.get('legend'),snapshots['glyph'],max_decoded_bytes)
        else:header,n=decode_packed(src,decoded,max_decoded_bytes)
        result=encode_file(decoded,output,profile=profile,external_legends=external_legends,
                           outer_codec=outer_codec,legend_policy=legend_policy)
        # The legacy API boundary returns the same JSON types as its stored receipt.
        # The core encoder's count_stats tuple has identical canonical bytes but
        # otherwise becomes a list only when the publication receipt is parsed.
        result=json.loads(canonical(result))
        inverse=decode_file(output,w/'inverse',external_legends=external_legends,max_decoded_bytes=max_decoded_bytes)
        if inverse['output_sha256']!=header['sha256']:fail('CURRENT_INVERSE')
        if file_sha256(source)!=sr or any(file_sha256(p)!=roots[role] for role,p in (('legend',legacy_legend),('glyph',legacy_glyph)) if p is not None):fail('INPUT_CHANGED')
        if [file_sha256(p) for p in external_legends]!=ic['current_legend_roots']:fail('CURRENT_LEGEND_CHANGED')
    return {**result,'schema':'semcrys.legacy-migration-result.v0.1','status':'PASS',
        'migration_instance':ic,'legacy_decoded_sha256':header['sha256'],'decoded_bytes':n,
        'legacy_header':header,'byte_exact_migration':True,'old_local_ids_preserved':False,
        'canonical_identity_effect':'NONE','source_mutation':False}
