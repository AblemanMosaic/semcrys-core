"""Group-legend pooling across related artifacts with byte-exact restoration.

This module owns the horizontal operation historically implemented under the
``metalegend`` name. Its existing on-disk ``semcrys.metalegend-*`` schema
identifiers remain immutable compatibility ABI; they do not define the
canonical conceptual name. New Python code and CLI automation should import
``semcrys.group_legend`` and use ``group-legend pack|unpack``.

SPDX-License-Identifier: Apache-2.0
"""
from streaming_legend import scratch_io as sio
import hashlib,io,json,os,shutil,tempfile
from contextlib import ExitStack
from pathlib import Path
from streaming_legend.core import LegendReader,write_legend,canonical,file_sha256
from streaming_legend.core import PROLOGUE as LEG_PROLOGUE,FOOTER as LEG_FOOTER,U64
from streaming_legend.crys_v2 import write_crys,inspect_crys,PROLOGUE,SECTION,Limits
from streaming_app.core import Refusal,protect_outputs,decode_file,_capture_controls,_venc,_vdec,_lzma_compress,_lzma_decompress
from .library import _bounded_snapshot
from streaming_legend.abi import META_MODE
from .file_spans import FileSpan,template_spans
from .record_pool import RecordPool,RESOURCE_POLICY
from . import group_auxiliary as aux

UNIT_MODE=META_MODE
SCHEMA='semcrys.metalegend-instance.v0.1'
BODY_MAGIC=b'SMA1'
MAX_DOCUMENTS=32
MAX_LEGENDS=1024
MAX_ENTRIES=1_000_000
MAX_INPUT=64*1024*1024
MAX_BODY=160*1024*1024
MAX_OUTPUT=128*1024*1024
LIMITS={'documents':MAX_DOCUMENTS,'legends':MAX_LEGENDS,'entries':MAX_ENTRIES,
 'input_bytes':MAX_INPUT,'body_bytes':MAX_BODY,'output_bytes':MAX_OUTPUT}
OPERATIONS=['VERIFY_EXACT_SOURCE_CONTAINERS','VERIFY_COMPLETE_DEPENDENCIES','POOL_EXACT_LEGEND_RECORDS',
 'BUILD_PER_LEGEND_INTEGER_MAPS','PRESERVE_CONTAINER_TEMPLATES','MEASURE_POOLED_AND_VERBATIM_ARCHIVES',
 'VERIFY_EXACT_ARTIFACT_AND_TEXT_RESTORATION','SELECT_DECLARED_COST','PUBLISH_NEW_DIRECTORY']
def root(value): return hashlib.sha256(canonical(value)).hexdigest()
def fail(code): raise Refusal(code)
def number(n,cap,minimum=0):
    if type(n) is not int or not minimum<=n<=cap: fail('HELD_META_LIMIT')
def isroot(s): return type(s) is str and len(s)==64 and all(c in '0123456789abcdef' for c in s)
def write_json(p,v): sio.write_bytes(p,canonical(v)+b'\n')
def scratch_instance(operation,limit,progress):
    value={'schema':'semcrys.archive-scratch-instance.v0.1','standing':'CANDIDATE_ONLY',
      'operation':operation,'policy':{**sio.POLICY,'limit_bytes':limit},
      'operation_sequence':['COMPILE_SCRATCH_INSTANCE','CREATE_PRIVATE_SCOPE','RESERVE_BEFORE_GROWTH',
                            'VERIFY_BEFORE_PUBLICATION','CLEANUP_PRIVATE_STATE'],
      'transported_configuration_effect':'NONE','authority_effect':'NONE'}
    value['instance_constitution_sha256']=root(value)
    if progress:progress(json.loads(json.dumps({'stage':'SCRATCH_INSTANCE_COMPILED','effective_configuration':value})))
    return value
def blob(f,b): f.write(_venc(len(b))); f.write(b)
def templates(data,indices):
    # The full input container was structurally verified before this scan.
    _,_,_,size=PROLOGUE.unpack(data[:PROLOGUE.size])
    pos=PROLOGUE.size+size; start=0; result=[]
    while pos<len(data):
        code,_,_,size,_=SECTION.unpack(data[pos:pos+SECTION.size])
        lo=pos+SECTION.size; hi=lo+size
        if code==b'LEGD':
            result.append((0,data[start:lo]))
            result.append((1,indices[hashlib.sha256(data[lo:hi]).hexdigest()]))
            start=hi
        pos=hi
        if code==b'DONE': break
    result.append((0,data[start:]))
    return result

def configuration(manifest,pool,placement,mode,codec):
    v={'schema':SCHEMA,'standing':'CANDIDATE_ONLY','profile':'B:METALEGEND_ARCHIVE',
       'source_manifest':manifest,'manifest_sha256':root(manifest),'pool_sha256':file_sha256(pool),
       'pool_entries':LegendReader(pool).count,'placement':placement,'mode':mode,'outer_codec':codec,
       'body_schema':'semcrys.metalegend-body.v0.1','limits':LIMITS,'operation_sequence':OPERATIONS,
       'security_claim':'NONE','implicit_fallback':False}
    if manifest['schema']==aux.MANIFEST_SCHEMA:
        v.update(schema=aux.SCHEMA,limits={**LIMITS,'auxiliaries':aux.MAX_AUX},auxiliary_contract_root=aux.contract_root())
    v['instance_constitution_sha256']=root(v); return v

def validate(config,header):
    keys={'schema','standing','profile','source_manifest','manifest_sha256','pool_sha256','pool_entries','placement',
      'mode','outer_codec','body_schema','limits','operation_sequence','security_claim','implicit_fallback','instance_constitution_sha256'}
    extended=type(config) is dict and config.get('schema')==aux.SCHEMA
    if extended:keys.add('auxiliary_contract_root')
    if type(config) is not dict or set(config)!=keys: fail('HELD_META_CONFIGURATION_FIELDS')
    if config['schema'] not in (SCHEMA,aux.SCHEMA) or config['standing']!='CANDIDATE_ONLY' or config['profile']!='B:METALEGEND_ARCHIVE':
        fail('HELD_META_CONFIGURATION_SCHEMA')
    if extended and config['auxiliary_contract_root']!=aux.contract_root():fail('HELD_META_AUXILIARY_CONTRACT')
    expected_limits={**LIMITS,'auxiliaries':aux.MAX_AUX} if extended else LIMITS
    if config['body_schema']!='semcrys.metalegend-body.v0.1' or config['limits']!=expected_limits or config['operation_sequence']!=OPERATIONS:
        fail('HELD_META_CONFIGURATION_OPERATIONS')
    if config['security_claim']!='NONE' or config['implicit_fallback'] is not False: fail('HELD_META_SECURITY_CLAIM')
    if config['mode'] not in ('META','VERBATIM') or config['placement'] not in ('EMBEDDED','EXTERNAL') or config['outer_codec'] not in ('NONE','LZMA'):
        fail('HELD_META_CONFIGURATION_MODE')
    number(config['pool_entries'],MAX_ENTRIES)
    if config['mode']=='VERBATIM' and config['pool_entries']!=0: fail('HELD_META_CONTROL_POOL')
    for field in ('manifest_sha256','pool_sha256','instance_constitution_sha256'):
        if not isroot(config[field]): fail('HELD_META_ROOT')
    manifest=config['source_manifest']
    manifest_schema=aux.MANIFEST_SCHEMA if extended else 'semcrys.restored-artifacts.v0.1'
    if type(manifest) is not dict or set(manifest)!={'schema','artifacts'} or manifest['schema']!=manifest_schema:
        fail('HELD_META_MANIFEST')
    rows=manifest['artifacts']
    cap=MAX_DOCUMENTS+MAX_LEGENDS+(aux.MAX_AUX if extended else 0)
    if type(rows) is not list or not 2<=len(rows)<=cap: fail('HELD_META_MANIFEST')
    documents=0; seen_dependency=False; total=0; dependency_roots=[];aux_roots=[];aux_bytes=0
    for r in rows:
        kinds=('CONTAINER','LEGEND',*aux.KINDS) if extended else ('CONTAINER','LEGEND')
        if type(r) is not dict or set(r)!={'kind','bytes','sha256'} or r['kind'] not in kinds or not isroot(r['sha256']):
            fail('HELD_META_MANIFEST_ROW')
        number(r['bytes'],MAX_OUTPUT); total+=r['bytes']
        if r['kind']=='CONTAINER':
            if seen_dependency: fail('HELD_META_MANIFEST_ORDER')
            documents+=1
        elif r['kind']=='LEGEND':
            if aux_roots:fail('HELD_META_MANIFEST_ORDER')
            seen_dependency=True; dependency_roots.append(r['sha256'])
        else:
            seen_dependency=True;aux_roots.append((r['kind'],r['sha256']));aux_bytes+=r['bytes']
    number(documents,MAX_DOCUMENTS,2); number(total,MAX_OUTPUT)
    number(len(dependency_roots),MAX_LEGENDS)
    number(len(aux_roots),aux.MAX_AUX);number(aux_bytes,aux.MAX_BYTES)
    if extended and not aux_roots:fail('HELD_META_EMPTY_AUXILIARY_VARIANT')
    if aux_roots!=sorted(set(aux_roots)):fail('HELD_META_AUXILIARY_ORDER')
    if dependency_roots!=sorted(set(dependency_roots)): fail('HELD_META_DEPENDENCY_ORDER')
    if root(manifest)!=config['manifest_sha256'] or header['decoded_sha256']!=config['manifest_sha256']:
        fail('HELD_META_MANIFEST_ROOT')
    expected=[{'role':'META','mode':config['placement'],'sha256':config['pool_sha256'],'schema':'semcrys.legend.binary.v0.2'}]
    if header['legend_bindings']!=expected or header['glyph_binding'] is not None: fail('HELD_META_POOL_BINDING')
    if root({k:v for k,v in config.items() if k!='instance_constitution_sha256'})!=config['instance_constitution_sha256']:
        fail('HELD_INSTANCE_CONSTITUTION_ROOT')

class Reader:
    def __init__(self,f): self.f=f
    def n(self,cap,minimum=0):
        value=_vdec(self.f); number(value,cap,minimum); return value
    def data(self,cap):
        n=self.n(cap); value=self.f.read(n)
        if len(value)!=n: fail('HELD_META_TRUNCATED')
        return value

def _restore(archive,directory,*,meta=None,max_output_bytes=MAX_OUTPUT):
    number(max_output_bytes,MAX_OUTPUT)
    directory.mkdir(); scratch=directory/'scratch'; scratch.mkdir()
    inspection,body,embedded=_capture_controls(archive,scratch,
      limits=Limits(max_section_bytes=MAX_BODY,max_total_payload_bytes=2*MAX_BODY,max_legend_entries=MAX_ENTRIES))
    cfg=inspection['configuration']
    from .group_bundle import SCHEMA as BUNDLE_SCHEMA,unwrap_captured
    if cfg.get('schema') in (BUNDLE_SCHEMA,aux.BUNDLE_SCHEMA):
        if meta is not None or embedded: fail('HELD_BUNDLE_UNUSED_POOL')
        inner=scratch/'inner.crys'; unwrap_captured(inspection,body,inner)
        result=_restore(inner,scratch/'restored',max_output_bytes=max_output_bytes)
        for row in result['restored_artifacts']:
            sio.replace(scratch/'restored'/row['file'],directory/row['file'])
        result['inner_configuration']=result['effective_configuration']
        result['effective_configuration']=cfg
        result['inner_archive_sha256']=result['archive_sha256']
        result['archive_sha256']=file_sha256(archive)
        result['complete_bundle_inverse']=True
        sio.rmtree(scratch)
        return result
    validate(cfg,inspection['header'])
    if cfg['placement']=='EMBEDDED':
        if meta is not None or len(embedded)!=1: fail('HELD_META_UNUSED_OR_MISSING_POOL')
        pool=embedded[0]
    else:
        if meta is None: fail('HELD_META_EXTERNAL_POOL_REQUIRED')
        pool=Path(meta)
    if file_sha256(pool)!=cfg['pool_sha256']: fail('HELD_META_POOL_ROOT')
    table=LegendReader(pool,max_entries=MAX_ENTRIES); table.verify()
    if table.count!=cfg['pool_entries'] or table.header['unit_mode']!=UNIT_MODE or table.header['parent_sha256'] is not None:
        fail('HELD_META_POOL_TYPE')
    if sum(r['bytes'] for r in cfg['source_manifest']['artifacts'])>max_output_bytes: fail('HELD_META_OUTPUT_BUDGET')
    physical=body
    if cfg['outer_codec']=='LZMA':
        physical=scratch/'raw'; _lzma_decompress(body,physical,max_decoded_bytes=MAX_BODY)
    recipes=[]; total_entries=0; aggregate=0
    with physical.open('rb') as f:
        if f.read(4)!=BODY_MAGIC: fail('HELD_META_BODY_MAGIC')
        reader=Reader(f); count=reader.n(MAX_LEGENDS)
        if cfg['mode']=='VERBATIM' and count: fail('HELD_META_CONTROL_RECIPE')
        prior=''
        for i in range(count):
            raw=reader.data(1024*1024)
            try: header=json.loads(raw)
            except (ValueError,UnicodeError,RecursionError) as exc: raise Refusal('HELD_META_LEGEND_HEADER') from exc
            fields={'schema','standing','legend_id','unit_mode','parent_sha256','entry_count','index_stride'}
            if type(header) is not dict or set(header)!=fields or canonical(header)!=raw or header['schema']!='semcrys.legend.binary.v0.2' or header['standing']!='CANDIDATE_ONLY':
                fail('HELD_META_LEGEND_HEADER')
            digest=f.read(32).hex()
            if not isroot(digest) or digest<=prior: fail('HELD_META_RECIPE_ORDER')
            prior=digest; expected_bytes=reader.n(MAX_INPUT); count_entries=reader.n(MAX_ENTRIES)
            if header['entry_count']!=count_entries or type(header['entry_count']) is not int: fail('HELD_META_ENTRY_COUNT')
            number(header['index_stride'],(1<<64)-1,1)
            if type(header['legend_id']) is not str or not header['legend_id'] or type(header['unit_mode']) is not str or not header['unit_mode']:
                fail('HELD_META_LEGEND_HEADER')
            total_entries+=count_entries; number(total_entries,MAX_ENTRIES)
            aggregate+=expected_bytes; number(aggregate,MAX_OUTPUT)
            overhead=LEG_PROLOGUE.size+len(raw)+LEG_FOOTER.size+U64.size*((count_entries+header['index_stride']-1)//header['index_stride'])
            if overhead>expected_bytes: fail('HELD_META_RECIPE_BYTE_BUDGET')
            path=scratch/(str(i)+'.leg')
            # The writer preserves exact stored programs, IDs, header and sparse
            # index stride. Pool IDs never become executable local references.
            def values():
                available=expected_bytes-overhead
                for _ in range(count_entries):
                    value=table.get(reader.n(table.count,1))
                    available-=len(_venc(len(value)))+len(value)
                    if available<0: fail('HELD_META_RECIPE_BYTE_BUDGET')
                    yield value
                if available: fail('HELD_META_RECIPE_BYTE_BUDGET')
            write_legend(path,values(),entry_count=count_entries,legend_id=header['legend_id'],
                unit_mode=header['unit_mode'],parent_sha256=header['parent_sha256'],index_stride=header['index_stride'])
            if file_sha256(path)!=digest or path.stat().st_size!=expected_bytes: fail('HELD_META_LEGEND_RECONSTRUCTION')
            recipes.append(path)
        artifacts=cfg['source_manifest']['artifacts']
        cap=MAX_DOCUMENTS+MAX_LEGENDS+(aux.MAX_AUX if cfg['schema']==aux.SCHEMA else 0)
        if reader.n(cap)!=len(artifacts): fail('HELD_META_ARTIFACT_COUNT')
        rows=[]
        for index,expected in enumerate(artifacts):
            suffix={'CONTAINER':'.crys','LEGEND':'.leg','GLYPH':'.gly','FOLD':'.leg'}[expected['kind']]
            output=directory/(f'{index:06d}'+suffix)
            segments=reader.n(8193,1); size=0
            with sio.open_output(output,'wb') as target:
                for _ in range(segments):
                    tag=f.read(1)
                    if tag==b'\0':
                        amount=reader.n(expected['bytes'])
                        size+=amount
                        if size>expected['bytes']: fail('HELD_META_ARTIFACT_SIZE')
                        while amount:
                            block=f.read(min(amount,1024*1024))
                            if not block: fail('HELD_META_TRUNCATED')
                            target.write(block); amount-=len(block)
                    elif tag==b'\1':
                        if cfg['mode']!='META': fail('HELD_META_CONTROL_REFERENCE')
                        if expected['kind'] in aux.KINDS: fail('HELD_META_AUXILIARY_MUST_BE_VERBATIM')
                        item=recipes[reader.n(len(recipes),1)-1]
                        size+=item.stat().st_size
                        if size>expected['bytes']: fail('HELD_META_ARTIFACT_SIZE')
                        with item.open('rb') as source: shutil.copyfileobj(source,target,1024*1024)
                    else: fail('HELD_META_SEGMENT_TAG')
            if size!=expected['bytes'] or file_sha256(output)!=expected['sha256']: fail('HELD_META_ARTIFACT_ROOT')
            rows.append({**expected,'file':output.name})
        if f.read(1): fail('HELD_META_BODY_TRAILING')
    # Exact original containers restore first, then their real application
    # Source decoders receive only exact typed dependencies restored by this archive.
    deps={r['sha256']:directory/r['file'] for r in rows if r['kind']=='LEGEND'}
    auxiliary={(r['kind'],r['sha256']):directory/r['file'] for r in rows if r['kind'] in aux.KINDS}
    used_aux=set()
    decoded=[]
    for r in rows:
        if r['kind']!='CONTAINER': continue
        p=directory/r['file']; view=inspect_crys(p)
        roots=[b['sha256'] for b in view['header']['legend_bindings'] if b['mode']=='EXTERNAL']
        if any(s not in deps for s in roots): fail('HELD_META_RESTORED_DEPENDENCY')
        destination=scratch/'decoded'
        options,required_aux=aux.decoder_options(view,auxiliary);used_aux.update(required_aux.items())
        result=decode_file(p,destination,external_legends=[deps[s] for s in roots],max_decoded_bytes=MAX_INPUT,**options)
        decoded.append(result['output_sha256'])
    if used_aux!=set(auxiliary):fail('HELD_META_UNUSED_AUXILIARY')
    sio.rmtree(scratch)
    return {'status':'PASS','schema':'semcrys.metalegend-unpack-result.v0.1','standing':'CANDIDATE_ONLY',
      'archive_sha256':file_sha256(archive),'effective_configuration':cfg,'restored_artifacts':rows,
      'decoded_source_roots':decoded,'manifest_sha256':cfg['manifest_sha256'],
      'exact_original_artifacts':True,'security_claim':'NONE'}

def _unpack(archive,output,*,meta=None,max_output_bytes=MAX_OUTPUT,progress=None,max_scratch_bytes=sio.DEFAULT_LIMIT):
    sio.validate_limit(max_scratch_bytes)
    resource_instance=scratch_instance('UNPACK',max_scratch_bytes,progress)
    archive,output=Path(archive),Path(output)
    protect_outputs([output],[archive,*([meta] if meta is not None else [])])
    if output.exists() or output.is_symlink(): fail('HELD_META_DESTINATION_EXISTS')
    output.parent.mkdir(parents=True,exist_ok=True)
    scratch_budget=sio.ACTIVE.get()
    if scratch_budget is None or scratch_budget.limit!=max_scratch_bytes:fail('HELD_META_OWNER_SCOPE_REQUIRED')
    with sio.TempDirectory(prefix='mu-',dir=output.parent) as name:
        w=Path(name); source=w/'archive.crys'; _bounded_snapshot(archive,source,2*MAX_BODY)
        pool=None
        if meta is not None: pool=w/'pool.leg'; _bounded_snapshot(meta,pool,MAX_BODY)
        if progress: progress({'stage':'META_UNPACK_START','archive_sha256':file_sha256(source),'max_output_bytes':max_output_bytes})
        result=_restore(source,w/'result',meta=pool,max_output_bytes=max_output_bytes)
        result['scratch_budget']=scratch_budget.outcome()
        result['scratch_instance']=resource_instance
        result['scratch_budget']['captured_at']='BEFORE_AUDIT_SERIALIZATION_AND_PUBLICATION'
        result['receipt_sha256']=root(result); write_json(w/'result/UNPACK_RECEIPT.json',result)
        if output.exists(): fail('HELD_META_DESTINATION_EXISTS')
        sio.replace(w/'result',output)
    return result

def _pack(output,*,sources,legends=(),glyphs=(),fold_fronts=(),placement='EMBEDDED',selection='MIN_TOTAL',outer_codec='AUTO',
         max_input_bytes=MAX_INPUT,progress=None,layout='BODY_ONLY',accounting='COLD',receiver_roots=(),shared_pool=None,
         max_scratch_bytes=sio.DEFAULT_LIMIT):
    sio.validate_limit(max_scratch_bytes)
    resource_instance=scratch_instance('PACK',max_scratch_bytes,progress)
    output=Path(output); sources=[Path(p) for p in sources]; legends=[Path(p) for p in legends]
    glyphs=[Path(p) for p in glyphs];fold_fronts=[Path(p) for p in fold_fronts]
    number(len(glyphs)+len(fold_fronts),aux.MAX_AUX)
    number(len(sources),MAX_DOCUMENTS,2); number(len(legends),MAX_LEGENDS); number(max_input_bytes,MAX_INPUT)
    if placement not in ('EMBEDDED','EXTERNAL','AUTO') or selection not in ('MIN_TOTAL','META','VERBATIM') or outer_codec not in ('NONE','LZMA','AUTO'):
        fail('HELD_META_CONFIGURATION')
    if layout not in ('BODY_ONLY','WHOLE_BUNDLE','AUTO') or accounting not in ('COLD','WARM'):
        fail('HELD_META_CONFIGURATION')
    if layout=='WHOLE_BUNDLE' and (placement=='EXTERNAL' or outer_codec=='NONE'):
        fail('HELD_BUNDLE_REQUIRES_EMBEDDED_LZMA')
    if type(receiver_roots) not in (tuple,list) or len(receiver_roots)>MAX_LEGENDS or any(not isroot(r) for r in receiver_roots):
        fail('HELD_META_RECEIVER_ROOT')
    if len(set(receiver_roots))!=len(receiver_roots): fail('HELD_META_DUPLICATE_RECEIVER_ROOT')
    if accounting=='COLD' and receiver_roots: fail('HELD_META_COLD_RECEIVER_ROOTS')
    receiver_roots=sorted(receiver_roots)
    if output.exists() or output.is_symlink(): fail('HELD_META_DESTINATION_EXISTS')
    protect_outputs([output],[*sources,*legends,*glyphs,*fold_fronts,*([shared_pool] if shared_pool is not None else [])]); output.parent.mkdir(parents=True,exist_ok=True)
    scratch_budget=sio.ACTIVE.get()
    if scratch_budget is None or scratch_budget.limit!=max_scratch_bytes:fail('HELD_META_OWNER_SCOPE_REQUIRED')
    with sio.TempDirectory(prefix='mp-',dir=output.parent) as name, ExitStack() as resources:
        w=Path(name); copies=[]; total=0; provided={}
        for i,p in enumerate(sources):
            q=w/(str(i)+'.crys'); _bounded_snapshot(p,q,max_input_bytes-total); total+=q.stat().st_size; copies.append(q)
        depsize=0
        for i,p in enumerate(legends):
            q=w/('e'+str(i)+'.leg'); digest=_bounded_snapshot(p,q,MAX_INPUT-depsize); depsize+=q.stat().st_size
            if digest in provided: fail('HELD_META_DUPLICATE_DEPENDENCY')
            provided[digest]=q
        auxiliary={};auxbytes=0
        for kind,paths in (('GLYPH',glyphs),('FOLD',fold_fronts)):
            for i,p in enumerate(paths):
                q=w/(kind+str(i)+('.gly' if kind=='GLYPH' else '.leg'))
                digest=_bounded_snapshot(p,q,aux.MAX_BYTES-auxbytes);auxbytes+=q.stat().st_size
                if (kind,digest) in auxiliary:fail('HELD_META_DUPLICATE_AUXILIARY')
                auxiliary[kind,digest]=q
        shared=None
        if shared_pool is not None:
            shared=w/'shared.leg'; _bounded_snapshot(shared_pool,shared,MAX_INPUT)
            reader=LegendReader(shared,max_entries=MAX_ENTRIES); reader.verify()
            if reader.header['unit_mode']!=UNIT_MODE or reader.header['parent_sha256'] is not None:
                fail('HELD_META_SHARED_POOL_TYPE')
        ic={'schema':'semcrys.metalegend-request.v0.2','standing':'CANDIDATE_ONLY',
          'source_roots':[file_sha256(p) for p in copies],'dependency_roots':sorted(provided),'placement':placement,
          'selection':selection,'outer_codec':outer_codec,'max_input_bytes':max_input_bytes,'limits':LIMITS,
          'operation_sequence':OPERATIONS,'security_claim':'NONE',
          'accounting':accounting,'receiver_roots':receiver_roots,'receiver_state_proof':'CALLER_DECLARATION_NOT_AUTHENTICATION',
          'layout':layout,'shared_pool_sha256':file_sha256(shared) if shared is not None else None,
          'cost_rule':'ARCHIVE_PLUS_UNSHARED_EXTERNAL_POOL_ONCE; FULL_COLD_COST_RETAINED',
          'runtime_resource_policy':dict(RESOURCE_POLICY),
          'scratch_policy':{**sio.POLICY,'limit_bytes':max_scratch_bytes},
          'pool_identity':'EXACT_STORED_RECORD_BYTES_NOT_SHARED_SEMANTIC_IDENTITY'}
        if auxiliary:
            ic.update(schema='semcrys.metalegend-request.v0.3',auxiliary_roots=[{'kind':k,'sha256':r} for k,r in sorted(auxiliary)],
                auxiliary_contract=aux.contract(),auxiliary_contract_root=aux.contract_root(),limits={**LIMITS,'auxiliaries':aux.MAX_AUX})
        ic['instance_constitution_sha256']=root(ic)
        if progress: progress(json.loads(json.dumps({'stage':'META_INSTANCE_COMPILED','effective_configuration':ic})))
        all_legends={}; required=set(); decoded_roots=[];used_aux=set()
        for i,p in enumerate(copies):
            cap=w/('c'+str(i)); cap.mkdir(); view,_,embedded=_capture_controls(p,cap)
            cfg=view['configuration']
            from .group_bundle import SCHEMA as BUNDLE_SCHEMA
            if cfg.get('schema') in (SCHEMA,BUNDLE_SCHEMA,aux.SCHEMA,aux.BUNDLE_SCHEMA): fail('HELD_META_RECURSIVE_ARCHIVE_NOT_QUALIFIED')
            options,required_aux=aux.decoder_options(view,auxiliary);used_aux.update(required_aux.items())
            roots=[r['sha256'] for r in view['header']['legend_bindings'] if r['mode']=='EXTERNAL']; required.update(roots)
            if any(r not in provided for r in roots): fail('HELD_META_DEPENDENCY_MISSING')
            for q in [*embedded,*[provided[r] for r in roots]]: all_legends[file_sha256(q)]=q
            result=decode_file(p,w/'decoded',external_legends=[provided[r] for r in roots],max_decoded_bytes=MAX_INPUT,**options)
            decoded_roots.append(result['output_sha256'])
        if required!=set(provided): fail('HELD_META_UNUSED_DEPENDENCY')
        if used_aux!=set(auxiliary):fail('HELD_META_UNUSED_AUXILIARY')
        number(len(all_legends),MAX_LEGENDS)
        originals=[('CONTAINER',p) for p in copies]+[('LEGEND',provided[r]) for r in sorted(provided)]+[(k,auxiliary[k,r]) for k,r in sorted(auxiliary)]
        manifest={'schema':aux.MANIFEST_SCHEMA if auxiliary else 'semcrys.restored-artifacts.v0.1','artifacts':
          [{'kind':k,'bytes':p.stat().st_size,'sha256':file_sha256(p)} for k,p in originals]}
        ordered=sorted(all_legends); leg_indices={r:i+1 for i,r in enumerate(ordered)}
        pool_index=resources.enter_context(RecordPool(w/'pool-index.sqlite'))
        entry_total=record_bytes=0; legend_headers={}
        for digest in ordered:
            p=all_legends[digest]; table=LegendReader(p,max_entries=MAX_ENTRIES); table.verify(check_duplicates=False)
            legend_headers[digest]=table.header
            for _,value in table.iter_values():
                entry_total+=1; number(entry_total,MAX_ENTRIES)
                record_bytes+=len(value); number(record_bytes,MAX_INPUT)
                pool_index.add_required(value)
        pool_index.build(None if shared is None else (v for _,v in LegendReader(shared).iter_values()))
        rows=[]; candidates=[]
        placements=('EMBEDDED','EXTERNAL') if placement=='AUTO' else (placement,)
        def candidate(path,pool,cfg,mode,codec,where,physical_layout,body_bytes,identifier):
            result=_restore(path,w/(identifier+'-restore'),meta=pool if where=='EXTERNAL' else None)
            if result['decoded_source_roots']!=decoded_roots: fail('HELD_META_SOURCE_CORRESPONDENCE')
            size=path.stat().st_size; external=pool.stat().st_size if where=='EXTERNAL' else 0
            pooled_root=file_sha256(pool)
            shared_bytes=external if accounting=='WARM' and pooled_root in receiver_roots else 0
            row={'id':identifier,'mode':mode,'outer_codec':codec,'placement':where,'layout':physical_layout,
              'archive_bytes':size,'external_meta_bytes':external,'total_bytes':size+external,
              'charged_delivery_bytes':size+external-shared_bytes,'preshared_meta_bytes':shared_bytes,
              'body_bytes':body_bytes,'pool_bytes':pool.stat().st_size,'sha256':file_sha256(path),'pool_sha256':pooled_root,
              'artifact_inverses':len(originals),'text_inverses':len(copies)}
            rows.append(row); candidates.append((path,pool,cfg))
            if progress: progress(json.loads(json.dumps({'stage':'META_CANDIDATE_VERIFIED','measurement':row})))
        for mode in ('VERBATIM','META'):
            pool=w/(mode+'.leg')
            if mode=='META' and shared is not None: sio.copy2(shared,pool)
            else: write_legend(pool,pool_index.values() if mode=='META' else [],entry_count=pool_index.count if mode=='META' else 0,
                legend_id='BATCH-META-RECORDS',unit_mode=UNIT_MODE)
            raw=w/(mode+'.body')
            with sio.open_output(raw,'wb') as f:
                f.write(BODY_MAGIC); f.write(_venc(len(ordered) if mode=='META' else 0))
                if mode=='META':
                    for digest in ordered:
                        p=all_legends[digest]; table=LegendReader(p)
                        blob(f,canonical(legend_headers[digest])); f.write(bytes.fromhex(digest))
                        f.write(_venc(p.stat().st_size)); f.write(_venc(table.count))
                        for _,v in table.iter_values(): f.write(_venc(pool_index[v]))
                f.write(_venc(len(originals)))
                for kind,p in originals:
                    if mode=='VERBATIM' or kind in aux.KINDS: parts=[(0,FileSpan(p))]
                    elif kind=='LEGEND': parts=[(1,leg_indices[file_sha256(p)])]
                    else: parts=template_spans(p,leg_indices)
                    f.write(_venc(len(parts)))
                    for tag,value in parts:
                        f.write(bytes([tag]))
                        if tag: f.write(_venc(value))
                        else:
                            f.write(_venc(len(value)));value.copy_to(f)
            if raw.stat().st_size>MAX_BODY: fail('HELD_META_BODY_BUDGET')
            if layout in ('BODY_ONLY','AUTO'):
                for codec in (('NONE','LZMA') if outer_codec=='AUTO' else (outer_codec,)):
                    body=raw
                    if codec=='LZMA':
                        body=w/(mode+'.xz'); _lzma_compress(raw,body)
                    for where in placements:
                        cfg=configuration(manifest,pool,where,mode,codec)
                        identifier=mode+'-'+codec+('-'+where if placement=='AUTO' else '')
                        path=w/(identifier+'.crys')
                        binding=('META',where,pool if where=='EMBEDDED' else file_sha256(pool))
                        write_crys(path,configuration=cfg,body=body,legend_stack=[binding],decoded_sha256=cfg['manifest_sha256'])
                        candidate(path,pool,cfg,mode,codec,where,'BODY_ONLY',body.stat().st_size,identifier)
            if layout in ('WHOLE_BUNDLE','AUTO') and 'EMBEDDED' in placements and outer_codec!='NONE':
                from .group_bundle import wrap
                inner=w/(mode+'-inner.crys'); cfg=configuration(manifest,pool,'EMBEDDED',mode,'NONE')
                write_crys(inner,configuration=cfg,body=raw,legend_stack=[('META','EMBEDDED',pool)],decoded_sha256=cfg['manifest_sha256'])
                identifier=mode+'-WHOLE-LZMA'; path=w/(identifier+'.crys'); compressed=w/(identifier+'.xz')
                cfg=wrap(inner,path,compressed)
                candidate(path,pool,cfg,mode,'LZMA','EMBEDDED','WHOLE_BUNDLE',compressed.stat().st_size,identifier)
        if set(receiver_roots)-{r['pool_sha256'] for r in rows}: fail('HELD_META_UNKNOWN_RECEIVER_POOL')
        eligible=[i for i,r in enumerate(rows) if selection=='MIN_TOTAL' or r['mode']==selection]
        if not eligible: fail('HELD_META_NO_ADMISSIBLE_CANDIDATE')
        chosen=min(eligible,key=lambda i:(rows[i]['charged_delivery_bytes'],i)); row=rows[chosen]; path,pool,cfg=candidates[chosen]
        stage=w/'result'; stage.mkdir(); sio.copy2(path,stage/'archive.crys')
        if row['placement']=='EXTERNAL': sio.copy2(pool,stage/'meta.leg')
        result={'schema':'semcrys.metalegend-pack-result.v0.1','status':'PASS','standing':'CANDIDATE_ONLY',
          'effective_configuration':ic,'selected_configuration':cfg,'selected_id':row['id'],'candidates':rows,
          'archive':'archive.crys','meta':'meta.leg' if row['placement']=='EXTERNAL' else None,'output_sha256':row['sha256'],
          'original_file_bytes':sum(p.stat().st_size for _,p in originals),'selected_total_bytes':row['total_bytes'],
          'warm_archive_only_bytes_if_exact_meta_preshared':row['archive_bytes'],
          'selected_delivery_bytes':row['charged_delivery_bytes'],'selected_layout':row['layout'],
          'selected_placement':row['placement'],'selected_preshared_meta_bytes':row['preshared_meta_bytes'],
          'warm_receiver_state_verified':False,'receiver_roots_checked_against_exact_pool':True,
          'audit_receipt_cost':'SEPARATE_NOT_INCLUDED_NOT_FREE',
          'source_legend_records':entry_total,'distinct_pooled_records':pool_index.required_count,'pool_capacity_entries':pool_index.count,
          'duplicates_removed_from_pool':entry_total-pool_index.required_count,'restored_manifest':manifest,
          'exact_artifact_and_text_restoration':True,'pool_is_not_semantic_identity':True,
          'input_mutation':False,'security_claim':'NONE','authority_effect':'NONE'}
        result['scratch_budget']=scratch_budget.outcome()
        result['scratch_instance']=resource_instance
        result['scratch_budget']['captured_at']='BEFORE_AUDIT_SERIALIZATION_AND_PUBLICATION'
        result['receipt_sha256']=root(result); write_json(stage/'META_RECEIPT.json',result)
        if output.exists(): fail('HELD_META_DESTINATION_EXISTS')
        sio.replace(stage,output)
    return result

def unpack(archive,output,*,meta=None,max_output_bytes=MAX_OUTPUT,progress=None,max_scratch_bytes=sio.DEFAULT_LIMIT):
    """Public quota/publication/recovery entry; exact restored artifacts unchanged."""
    from .directory_application import run
    return run('UNPACK',archive,output,meta=meta,max_output_bytes=max_output_bytes,
               progress=progress,max_scratch_bytes=max_scratch_bytes)

def pack(output,*,sources,legends=(),glyphs=(),fold_fronts=(),placement='EMBEDDED',selection='MIN_TOTAL',outer_codec='AUTO',
         max_input_bytes=MAX_INPUT,progress=None,layout='BODY_ONLY',accounting='COLD',receiver_roots=(),shared_pool=None,
         max_scratch_bytes=sio.DEFAULT_LIMIT):
    """Public quota/publication/recovery entry; codec selection unchanged."""
    from .directory_application import run
    return run('PACK',None,output,sources=sources,legends=legends,glyphs=glyphs,fold_fronts=fold_fronts,placement=placement,selection=selection,
      outer_codec=outer_codec,max_input_bytes=max_input_bytes,progress=progress,layout=layout,accounting=accounting,
      receiver_roots=receiver_roots,shared_pool=shared_pool,max_scratch_bytes=max_scratch_bytes)
