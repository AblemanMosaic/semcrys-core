"""Bounded second-pass event composition; no encryption or group-legend claim.
SPDX-License-Identifier: Apache-2.0
"""
from streaming_legend import scratch_io as sio
from streaming_legend import block_output
import hashlib,io,os,tempfile
from array import array
from contextlib import ExitStack
from collections import Counter
from functools import lru_cache
from itertools import chain
from pathlib import Path
from streaming_legend.core import LegendReader as RawReader,canonical,file_sha256,write_legend
from streaming_legend.assembly import (ExecutionLegendReader,MODES,COMPACT_MODE,PAIR_MODE,PAIR_ABI,
    MAX_PAIR_DEPTH,MAX_PAIR_VALUE,apply,parse_program,parse_compact,parse_composed,compact_program,program,pair_program)
from streaming_legend.crys_v2 import write_crys
from streaming_app.core import (Refusal,protect_outputs,_venc,_vdec,_capture_controls,
    _compress_outer,_decompress_outer,_validate_lineage,decode_file,PREDECESSOR_HEAD,
    REQUESTABLE_OUTER_CODECS)
from .library import _bounded_snapshot
from .event_stream import EventSpool, fractionate_disk, dispersion_disk, RESOURCE_POLICY
from .terminal_store import TerminalStore

SCHEMA='semcrys.instance-constitution.v0.8'
SCHEMA_TOPK='semcrys.instance-constitution.v0.11'
BODY_SCHEMA='semcrys.composed-event-body.v0.1'
MAGIC=b'SPP1'
MAX_SOURCE=64*1024*1024
MAX_EVENTS=1_000_000
MAX_ENTRIES=1_000_000
MAX_LEGEND=64*1024*1024
MAX_ROUNDS=400
IN_MEMORY_FRACTIONATION_MAX_EVENTS=250_000
OPERATIONS=['SNAPSHOT_AND_BIND_INPUTS','VERIFY_FIRST_PASS_INVERSE','COMPOSE_TERMINAL_PROGRAMS',
 'FRACTIONATE_EXACT_EVENT_STREAM','WRITE_ROOTED_COMPOSED_LEGENDS','VERIFY_TEXT_AND_EVENT_INVERSES',
 'MEASURE_DELIVERY_AND_DISPERSION','SELECT_DECLARED_OBJECTIVE','PUBLISH_WITHOUT_INPUT_MUTATION']

def root(value): return hashlib.sha256(canonical(value)).hexdigest()
def fail(code): raise Refusal(code)
def integer(value,maximum,minimum=0):
    if type(value) is not int or not minimum<=value<=maximum: fail('HELD_SECOND_PASS_LIMIT')
def isroot(value):
    return type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value)

def validate_configuration(config,header):
    keys={'schema','standing','predecessor_head','profile','source_sha256','external_legend_roots',
      'outer_codec','legend_stack','physical_body_schema','implicit_fallback','security_claim',
      'second_pass','instance_constitution_sha256'}
    if type(config) is not dict or set(config)!=keys: fail('HELD_COMPOSED_CONFIGURATION_FIELDS')
    if config['schema'] not in (SCHEMA,SCHEMA_TOPK) or config['standing']!='CANDIDATE_ONLY' or config['predecessor_head']!=PREDECESSOR_HEAD:
        fail('HELD_COMPOSED_CONFIGURATION_SCHEMA')
    if config['profile']!='C:COMPOSED_SECOND_PASS' or config['physical_body_schema']!=BODY_SCHEMA: fail('HELD_COMPOSED_PROFILE')
    if config['outer_codec'] not in REQUESTABLE_OUTER_CODECS or config['security_claim']!='NONE' or config['implicit_fallback'] is not False:
        fail('HELD_COMPOSED_CONFIGURATION_CLAIM')
    if config['external_legend_roots']!=[] or header['glyph_binding'] is not None: fail('HELD_COMPOSED_DEPENDENCIES')
    if not isroot(config['source_sha256']) or config['source_sha256']!=header['decoded_sha256']: fail('HELD_COMPOSED_SOURCE_ROOT')
    bindings=header['legend_bindings']
    if len(bindings)!=1 or bindings[0]['role']!='BASE' or bindings[0]['mode']!='EMBEDDED': fail('HELD_COMPOSED_STACK')
    if config['legend_stack']!=[{k:bindings[0][k] for k in ('role','mode','sha256')}]: fail('HELD_COMPOSED_STACK')
    spec=config['second_pass']
    spec_fields={'abi','arm','base_entries','literal_entries','pair_entries','input_events','output_events',
      'input_physical_sha256','input_container_sha256','rounds','min_count','max_pair_bytes','max_depth'}
    if config['schema']==SCHEMA_TOPK:spec_fields.add('hot_k')
    if type(spec) is not dict or set(spec)!=spec_fields: fail('HELD_COMPOSED_SPEC')
    allowed=('TOPK',) if config['schema']==SCHEMA_TOPK else ('IDENTITY','ALL','TOP3')
    if spec['abi']!=PAIR_ABI or spec['arm'] not in allowed: fail('HELD_COMPOSED_ABI')
    if config['schema']==SCHEMA_TOPK:integer(spec['hot_k'],MAX_ENTRIES,1)
    for k in ('input_physical_sha256','input_container_sha256'):
        if not isroot(spec[k]): fail('HELD_COMPOSED_INPUT_ROOT')
    for k in ('base_entries','literal_entries'): integer(spec[k],MAX_ENTRIES)
    integer(spec['rounds'],MAX_ROUNDS); integer(spec['pair_entries'],spec['rounds'])
    integer(spec['base_entries']+spec['literal_entries']+spec['pair_entries'],MAX_ENTRIES)
    integer(spec['min_count'],MAX_EVENTS,2)
    integer(spec['input_events'],MAX_EVENTS); integer(spec['output_events'],spec['input_events'])
    if spec['max_pair_bytes']!=MAX_PAIR_VALUE or spec['max_depth']!=MAX_PAIR_DEPTH: fail('HELD_COMPOSED_LIMIT_BINDING')
    if spec['arm']=='IDENTITY' and (spec['pair_entries'] or spec['input_events']!=spec['output_events']): fail('HELD_COMPOSED_IDENTITY')
    if root({k:v for k,v in config.items() if k!='instance_constitution_sha256'})!=config['instance_constitution_sha256']:
        fail('HELD_INSTANCE_CONSTITUTION_ROOT')

def decode_physical(body,output,config,legend,*,max_decoded_bytes):
    spec=config['second_pass']; raw=RawReader(legend)
    terminals=spec['base_entries']+spec['literal_entries']
    if raw.header['unit_mode']!=PAIR_MODE or raw.header['parent_sha256'] is not None or raw.count!=terminals+spec['pair_entries']:
        fail('HELD_COMPOSED_LEGEND_BINDING')
    raw.verify(check_duplicates=False)
    stored=[data for _,data in raw.iter_values()]
    @lru_cache(maxsize=4096)
    def node(n): return parse_composed(stored[n-1],raw.count)
    depths=bytearray([255])*raw.count; visiting=bytearray(raw.count)
    def depth(n):
        known=depths[n-1]
        if known!=255:return known
        if visiting[n-1]:fail('HELD_ASSEMBLY_CYCLE')
        visiting[n-1]=1;item=node(n)
        if item[0]=='PAIR':result=max(depth(item[1]),depth(item[2]))+1
        elif item[0]=='REFERENCE':result=depth(item[1])+1
        else:result=0
        visiting[n-1]=0
        if result>=MAX_PAIR_DEPTH:fail('HELD_ASSEMBLY_DEPTH_LIMIT')
        depths[n-1]=result;return result
    @lru_cache(maxsize=128)
    def value(n):
        item=node(n)
        if item[0] in ('LITERAL','EVENT_LITERAL'):result=item[1]
        elif item[0]=='PAIR':
            if max(item[1:])>=n:fail('HELD_PAIR_NON_BACKWARD_REFERENCE')
            result=value(item[1])+value(item[2])
            if len(result)>MAX_PAIR_VALUE:fail('HELD_PAIR_EXPANSION_LIMIT')
        else:
            base=value(item[1]) if item[0]=='REFERENCE' else item[1]
            result=apply(base,item[2],item[3])
        return result
    # Validate every program, including unused nodes, not just the emitted path.
    for n,data in enumerate(stored,1):
        item=parse_composed(data,raw.count)
        if n<=terminals:
            if item[0]=='PAIR': fail('HELD_COMPOSED_TERMINAL_KIND')
            if n>spec['base_entries'] and item[0]!='EVENT_LITERAL': fail('HELD_COMPOSED_LITERAL_KIND')
            if n<=spec['base_entries'] and item[0]=='EVENT_LITERAL': fail('HELD_COMPOSED_TERMINAL_KIND')
            if item[0]=='REFERENCE' and (item[1]>spec['base_entries'] or node(item[1])[0]=='PAIR'):
                fail('HELD_COMPOSED_FORM_REFERENCE')
        elif item[0]!='PAIR' or max(item[1:])>=n: fail('HELD_PAIR_NON_BACKWARD_REFERENCE')
    for n in range(1,raw.count+1):
        depth(n);value(n)  # cycle, depth and byte expansion limits
    def leaves(n,depth=0):
        if depth>=MAX_PAIR_DEPTH: fail('HELD_ASSEMBLY_DEPTH_LIMIT')
        if not 1<=n<=raw.count: fail('HELD_BODY_ID_RANGE')
        if n<=terminals:
            yield n; return
        item=node(n)
        yield from leaves(item[1],depth+1); yield from leaves(item[2],depth+1)
    total=events=0; digest=hashlib.sha256(b'SPV2')
    with Path(body).open('rb') as source,block_output.open_output(Path(output),'wb') as target:
        if source.read(4)!=MAGIC or _vdec(source)!=spec['input_events'] or _vdec(source)!=spec['output_events']:
            fail('HELD_COMPOSED_BODY_HEADER')
        for _ in range(spec['output_events']):
            identifier=_vdec(source)
            if identifier is None: fail('HELD_COMPOSED_BODY_TRUNCATED')
            for n in leaves(identifier):
                v=value(n)
                if not v: fail('HELD_EMPTY_LEGEND_VALUE')
                events+=1; total+=len(v)
                if events>spec['input_events'] or total>max_decoded_bytes: fail('HELD_DECODED_SIZE_LIMIT')
                digest.update(_venc(n) if n<=spec['base_entries'] else b'\0'+_venc(len(v))+v)
                target.write(v)
        if source.read(1): fail('HELD_COMPOSED_BODY_TRAILING')
    if events!=spec['input_events'] or digest.hexdigest()!=spec['input_physical_sha256']: fail('HELD_COMPOSED_EVENT_ROOT')

def _terminals(stack,physical,*,max_events,event_path,records):
    sizes=array('I'); offset=0; used_bytes=0
    if sizes.itemsize!=4:fail('HELD_TERMINAL_METADATA_WIDTH')
    for path in stack:
        raw=RawReader(path); execution=ExecutionLegendReader(path); mode=raw.header['unit_mode']
        if mode not in ('TOKEN',*MODES): fail('HELD_SECOND_PASS_INPUT_LEGEND_MODE')
        for _,data in raw.iter_values():
            item=('LITERAL',data) if mode=='TOKEN' else (parse_compact(data,raw.count) if mode==COMPACT_MODE else parse_program(data,raw.count))
            if item[0]=='LITERAL': encoded=compact_program(b'\0'+item[1])
            elif item[0]=='REFERENCE': encoded=compact_program(program(item[1]+offset,None,item[2],item[3]))
            else: encoded=compact_program(program(None,item[1],item[2],item[3]))
            records.append(encoded); used_bytes+=len(encoded)
            if len(records)>MAX_ENTRIES or used_bytes>MAX_LEGEND: fail('HELD_SECOND_PASS_LEGEND_LIMIT')
        sizes.extend(len(v) for _,v in execution.iter_values())
        offset+=raw.count
    base_entries=len(records)
    def events():
        nonlocal used_bytes
        with physical.open('rb') as f:
            if f.read(4)!=b'SPV2': fail('HELD_SECOND_PASS_INPUT_BODY')
            while True:
                n=_vdec(f)
                if n is None: break
                if n:
                    if n>base_entries: fail('HELD_BODY_ID_RANGE')
                else:
                    length=_vdec(f)
                    if length is None or not 1<=length<=4096: fail('HELD_LITERAL_LENGTH')
                    value=f.read(length)
                    if len(value)!=length: fail('HELD_TRUNCATED_LITERAL')
                    n,created=records.intern_literal(value)
                    if created:
                        sizes.append(len(value));used_bytes+=len(value)+2
                if len(records)>MAX_ENTRIES or used_bytes>MAX_LEGEND: fail('HELD_SECOND_PASS_LIMIT')
                yield n
    ids=EventSpool.write(event_path,events(),limit=max_events)
    return records,sizes,ids,base_entries,records.literal_count

def terminal_depths(records,*,compact=False):
    """Depth includes form-reference edges before adding pair edges."""
    memo=bytearray([255])*len(records)
    def visit(identifier,trail=()):
        if memo[identifier-1]!=255: return memo[identifier-1]
        if identifier in trail or len(trail)>=MAX_PAIR_DEPTH: fail('HELD_ASSEMBLY_DEPTH_LIMIT')
        item=parse_composed(records[identifier-1],len(records))
        if item[0]=='PAIR': fail('HELD_SECOND_PASS_INPUT_LEGEND_MODE')
        depth=1+visit(item[1],trail+(identifier,)) if item[0]=='REFERENCE' else 0
        if depth>=MAX_PAIR_DEPTH:fail('HELD_ASSEMBLY_DEPTH_LIMIT')
        memo[identifier-1]=depth; return depth
    for n in range(1,len(records)+1):visit(n)
    return memo if compact else list(memo)

def fractionate(ids,sizes,*,rounds,min_count,hot_only,progress=None,initial_depths=None):
    seq=list(ids); counts=Counter(seq)
    hot=set(n for n,_ in counts.most_common(hot_only)) if hot_only else None
    lengths=list(sizes); depths=list(initial_depths) if initial_depths is not None else [0]*len(sizes); mapping=[]
    if len(depths)!=len(sizes) or any(type(d) is not int or not 0<=d<MAX_PAIR_DEPTH for d in depths):
        fail('HELD_PAIR_INITIAL_DEPTHS')
    for step in range(rounds):
        pairs=Counter((a,b) for a,b in zip(seq,seq[1:]) if
            (hot is None or a in hot or b in hot) and lengths[a-1]+lengths[b-1]<=MAX_PAIR_VALUE
            and max(depths[a-1],depths[b-1])+1<MAX_PAIR_DEPTH)
        if not pairs: break
        (a,b),count=pairs.most_common(1)[0]
        if count<min_count or len(lengths)>=MAX_ENTRIES: break
        new=len(lengths)+1; result=[]; i=0
        while i<len(seq):
            if i+1<len(seq) and seq[i]==a and seq[i+1]==b: result.append(new); i+=2
            else: result.append(seq[i]); i+=1
        seq=result; mapping.append((a,b)); lengths.append(lengths[a-1]+lengths[b-1])
        depths.append(max(depths[a-1],depths[b-1])+1)
        if progress and (step%20==0 or step==rounds-1):
            progress({'stage':'SECOND_PASS_FRACTIONATION','round':step+1,'events':len(seq),'hot_only':hot_only})
    return seq,mapping

def dispersion(ids):
    c=Counter(ids)
    return max(c.values(),default=0)/max(len(ids),1)

def scratch_instance(limit,progress):
    value={'schema':'semcrys.second-pass-scratch-instance.v0.1','standing':'CANDIDATE_ONLY',
      'operation':'SECOND_PASS','policy':{**sio.POLICY,'limit_bytes':limit},
      'operation_sequence':['COMPILE_SCRATCH_INSTANCE','CREATE_PRIVATE_SCOPE','RESERVE_BEFORE_GROWTH',
                            'VERIFY_BEFORE_PUBLICATION','CLEANUP_PRIVATE_STATE'],
      'scope':'SECOND_PASS_TRANSFORM_AND_ENROLLED_NESTED_IO',
      'publication_receipt_and_backup_budgeted':False,
      'transported_configuration_effect':'NONE','authority_effect':'NONE'}
    value['instance_constitution_sha256']=root(value)
    if progress:progress({'stage':'SCRATCH_INSTANCE_COMPILED','effective_configuration':value})
    return value

def transform(source,output,*,external_legends=(),selection='MIN_DELIVERY',accounting='COLD',
              rounds=400,min_count=10,hot_k=3,max_source_bytes=MAX_SOURCE,max_events=MAX_EVENTS,progress=None,
              max_scratch_bytes=sio.DEFAULT_LIMIT):
    sio.validate_limit(max_scratch_bytes)
    source,target=Path(source),Path(output); external_legends=[Path(p) for p in external_legends]
    protect_outputs([target],[source,*external_legends])
    if target.suffix.lower()!='.crys': fail('HELD_CRYS_SUFFIX_REQUIRED')
    hot_arm='TOP3' if hot_k==3 else 'TOPK'
    if selection not in ('MIN_DELIVERY','MIN_DISPERSION','IDENTITY','ALL',hot_arm) or accounting not in ('COLD','WARM'):
        fail('HELD_SECOND_PASS_CONFIGURATION')
    integer(rounds,MAX_ROUNDS); integer(min_count,MAX_EVENTS,2);integer(hot_k,MAX_ENTRIES,1)
    integer(max_source_bytes,MAX_SOURCE); integer(max_events,MAX_EVENTS)
    if len(external_legends)>1023: fail('HELD_SECOND_PASS_LEGEND_LIMIT')
    resource_instance=scratch_instance(max_scratch_bytes,progress)
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sp-',dir=target.parent) as name, \
         sio.Scope(name,max_scratch_bytes,publication=target,
                   operation_scope='SECOND_PASS_TRANSFORM_AND_ENROLLED_NESTED_IO') as scratch_budget, \
         ExitStack() as resources:
        work=scratch_budget.root; original=work/'original.crys'
        input_root=_bounded_snapshot(source,original,MAX_SOURCE)
        legends=[]; legend_bytes=0
        for n,p in enumerate(external_legends):
            q=work/('e'+str(n)+'.leg'); _bounded_snapshot(p,q,MAX_LEGEND-legend_bytes)
            legend_bytes+=q.stat().st_size; legends.append(q)
        capture=work/'c'; capture.mkdir()
        inspected,body,embedded=_capture_controls(original,capture)
        config=inspected['configuration']
        if config.get('physical_body_schema')!='semcrys.packed-token.v0.2': fail('HELD_SECOND_PASS_INPUT_CONFIGURATION')
        from streaming_app.core import _validate_configuration
        _validate_configuration(config,inspected['header'])
        byroot={file_sha256(p):p for p in legends}; required=config['external_legend_roots']
        if len(byroot)!=len(legends) or set(byroot)!=set(required): fail('HELD_SECOND_PASS_EXACT_DEPENDENCIES')
        stack=[]; embed=iter(embedded)
        for row in inspected['header']['legend_bindings']:
            stack.append(byroot[row['sha256']] if row['mode']=='EXTERNAL' else next(embed))
        if sum(p.stat().st_size for p in stack)>MAX_LEGEND: fail('HELD_SECOND_PASS_LEGEND_LIMIT')
        _validate_lineage(stack)
        ic={'schema':'semcrys.second-pass-selection-instance.v0.1','standing':'CANDIDATE_ONLY',
          'input_container_sha256':input_root,'input_legend_roots':[file_sha256(p) for p in stack],
          'selection':selection,'accounting':accounting,'rounds':rounds,'min_count':min_count,
          'terminal_depth_policy':'EXACT_COMBINED_FORM_AND_PAIR_DEPTH',
          'runtime_resource_policy':dict(RESOURCE_POLICY),
          'max_source_bytes':max_source_bytes,'max_events':max_events,'max_legend_bytes':MAX_LEGEND,
          'operation_sequence':OPERATIONS,'output_placement':'ONE_EMBEDDED_COMPOSED_LEGEND_OR_UNCHANGED_ORIGINAL',
          'comparison_scope':'EXACT_SOURCE_FOUR_CANDIDATES_NOT_PREDICTION','security_claim':'NONE',
          'audit_scope':'LOCAL_RECEIPTS_SEPARATE_NOT_FREE','group_legend':'DISTINCT_OPERATION_USE_GROUP_LEGEND_PACK'}
        if hot_k!=3:
            ic['schema']='semcrys.second-pass-selection-instance.v0.2';ic['hot_k']=hot_k
        ic['instance_constitution_sha256']=root(ic)
        if progress: progress({'stage':'SECOND_PASS_INSTANCE_COMPILED','effective_configuration':ic})
        decoded=work/'decoded'; decode_file(original,decoded,external_legends=legends,max_decoded_bytes=max_source_bytes)
        physical=body
        if config['outer_codec']!='NONE':
            physical=work/'physical'; _decompress_outer(
                body,physical,config['outer_codec'],max_decoded_bytes=10*max_source_bytes+4)
        terminal_store=resources.enter_context(TerminalStore(work/'terminals.sqlite'))
        records,sizes,ids,base,literals=_terminals(stack,physical,max_events=max_events,event_path=work/'input.events',records=terminal_store)
        depths=terminal_depths(records,compact=True)
        original_physical_root=file_sha256(physical)
        memory_ids=list(ids) if len(ids)<=IN_MEMORY_FRACTIONATION_MAX_EVENTS else None
        realization='IN_MEMORY' if memory_ids is not None else 'DISK_BACKED'
        baseline_dispersion=(dispersion(memory_ids) if memory_ids is not None else
            dispersion_disk(ids,work/'original-counts.sqlite'))
        external_bytes=sum(p.stat().st_size for p in legends)
        rows=[{'id':'ORIGINAL','container_bytes':original.stat().st_size,'body_bytes':body.stat().st_size,
          'legend_bytes':sum(p.stat().st_size for p in stack),'external_bytes':external_bytes,
          'delivery_bytes':original.stat().st_size+(external_bytes if accounting=='COLD' else 0),
          'dispersion':baseline_dispersion,'events':len(ids),'pairs':0,'sha256':input_root,
          'text_inverse':True,'event_inverse':True,'first_pass_artifacts_disposable':False}]
        paths=[original]; configs=[config]
        for arm in ('IDENTITY','ALL',hot_arm):
            if arm=='IDENTITY':
                seq,pairs=(memory_ids if memory_ids is not None else ids),[]
            elif memory_ids is not None:
                seq,pairs=fractionate(memory_ids,sizes,rounds=rounds,min_count=min_count,
                    hot_only=hot_k if arm==hot_arm else None,progress=progress,initial_depths=depths)
            else:
                seq,pairs=fractionate_disk(ids,sizes,rounds=rounds,min_count=min_count,
                    hot_only=hot_k if arm==hot_arm else None,progress=progress,initial_depths=depths,
                    workspace=work/(arm+'-events'))
            programs=chain(records,(pair_program(a,b) for a,b in pairs))
            legend=work/(arm+'.leg')
            write_legend(legend,programs,entry_count=len(records)+len(pairs),legend_id='COMPOSED-SECOND-PASS',
                unit_mode=PAIR_MODE)
            physical_out=work/(arm+'.body')
            with block_output.open_output(physical_out,'wb') as f:
                f.write(MAGIC+_venc(len(ids))+_venc(len(seq)))
                for n in seq: f.write(_venc(n))
            encoded=physical_out
            if config['outer_codec']!='NONE':
                suffix='.xz' if config['outer_codec']=='LZMA' or config['outer_codec'].startswith('LZMA2_XZ_') else '.bz2'
                encoded=work/(arm+suffix); _compress_outer(physical_out,encoded,config['outer_codec'])
            cfg={'schema':SCHEMA_TOPK if arm=='TOPK' else SCHEMA,'standing':'CANDIDATE_ONLY','predecessor_head':PREDECESSOR_HEAD,
              'profile':'C:COMPOSED_SECOND_PASS','source_sha256':config['source_sha256'],'external_legend_roots':[],
              'outer_codec':config['outer_codec'],'legend_stack':[{'role':'BASE','mode':'EMBEDDED','sha256':file_sha256(legend)}],
              'physical_body_schema':BODY_SCHEMA,'implicit_fallback':False,'security_claim':'NONE',
              'second_pass':{'abi':PAIR_ABI,'arm':arm,'base_entries':base,'literal_entries':literals,
                'pair_entries':len(pairs),'input_events':len(ids),'output_events':len(seq),
                'input_physical_sha256':original_physical_root,'input_container_sha256':input_root,
                 'rounds':rounds,'min_count':min_count,'max_pair_bytes':MAX_PAIR_VALUE,'max_depth':MAX_PAIR_DEPTH}}
            if arm=='TOPK':cfg['second_pass']['hot_k']=hot_k
            cfg['instance_constitution_sha256']=root(cfg)
            path=work/(arm+'.crys'); write_crys(path,configuration=cfg,body=encoded,
                legend_stack=[('BASE','EMBEDDED',legend)],decoded_sha256=cfg['source_sha256'])
            decode_file(path,decoded,max_decoded_bytes=max_source_bytes)
            if file_sha256(decoded)!=cfg['source_sha256']: fail('HELD_SECOND_PASS_TEXT_INVERSE')
            rows.append({'id':arm,'container_bytes':path.stat().st_size,'body_bytes':encoded.stat().st_size,
              'raw_body_bytes':physical_out.stat().st_size,'legend_bytes':legend.stat().st_size,'external_bytes':0,
              'delivery_bytes':path.stat().st_size,
              'dispersion':dispersion(seq) if memory_ids is not None else dispersion_disk(seq,work/(arm+'-dispersion.sqlite')),
              'fractionation_realization':realization,'events':len(seq),'pairs':len(pairs),
              'sha256':file_sha256(path),'text_inverse':True,'event_inverse':True,'first_pass_artifacts_disposable':True})
            paths.append(path); configs.append(cfg)
            if progress: progress({'stage':'SECOND_PASS_ARM_VERIFIED','measurement':rows[-1]})
        if selection.startswith('MIN_'):
            key='delivery_bytes' if selection=='MIN_DELIVERY' else 'dispersion'
            # Original wins exact ties. Dispersion has no security standing.
            selected=min(range(len(rows)),key=lambda i:(rows[i][key],i))
        else: selected=next(i for i,r in enumerate(rows) if r['id']==selection)
        result={'schema':'semcrys.second-pass-result.v0.1','status':'PASS','standing':'CANDIDATE_ONLY',
          'effective_configuration':ic,'selected_configuration':configs[selected],'selected_id':rows[selected]['id'],
          'candidates':rows,'output_sha256':rows[selected]['sha256'],
          'saved_delivery_bytes':rows[0]['delivery_bytes']-rows[selected]['delivery_bytes'],
          'external_decoder_dependencies':required if selected==0 else [],
          'first_pass_artifacts_disposable':selected!=0,'prior_artifacts_deleted':False,
          'original_legend_files_byte_recreated':False,'original_packed_event_stream_verified':True,
          'terminal_form_programs_preserved':True,'shared_state_mutated':False,'authority_effect':'NONE','security_claim':'NONE'}
        # Close terminal handles before final publication and receipt accounting.
        resources.close()
        result['scratch_instance']=resource_instance
        result['scratch_budget']=scratch_budget.outcome()
        result['scratch_budget']['captured_at']='BEFORE_PUBLICATION_NOT_TRANSACTION_RECEIPT_OR_BACKUPS'
        result['receipt_sha256']=root(result)
        sio.replace(paths[selected],target)
    return result
