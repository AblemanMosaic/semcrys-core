"""Deduplicated legend-stack and codec configuration selection.

Exact-source candidate evidence only. No future prediction, semantic family
inference, receiver attestation, or security claim. SPDX-License-Identifier: Apache-2.0
"""
import codecs,hashlib,time,tracemalloc
from pathlib import Path

from streaming_app.core import (Refusal,REQUESTABLE_OUTER_CODECS,encode_file,
    decode_file,protect_outputs,_is_root)
from streaming_app.legend_context import VerifiedLegendContext
from streaming_legend import scratch_io as sio
from streaming_legend.assembly import ExecutionLegendReader as LegendReader
from streaming_legend.core import canonical,file_sha256

from .artifacts import canonical_object,inspect_artifact
from .codec_selection import measurement_codec_configuration,_implementation_identity

LIBRARY_SCHEMA='semcrys.legend-stack-library.v0.2'
SELECTION_SCHEMA='semcrys.configuration-selection.v0.2'
INSTANCE_SCHEMA='semcrys.configuration-selection-instance.v0.2'
FAMILIES=('UNION','ULTRA','DOMAIN','SPARSE_EXTENSION','LONGITUDINAL','HYBRID')
MAX_LIBRARY=4*1024*1024;MAX_STACKS=16;MAX_ARTIFACTS=64;MAX_CANDIDATES=256
MAX_SOURCE=64*1024*1024;MAX_LEGENDS=1024*1024*1024
OPERATIONS=['ROOT_SOURCE_LIBRARY_AND_LEGENDS','COMPILE_EXACT_CROSS_PRODUCT',
 'REALIZE_COMPLETE_CONTAINERS','VERIFY_ENCODER_POSTWRITE_INVERSE','MEASURE_DELIVERY_WALL_AND_CPU',
 'SELECT_MINIMUM_DECLARED_DELIVERY_BYTES','PUBLISH_ROOTED_SELECTION']

def _rooted(value,key):return {**value,key:hashlib.sha256(canonical(value)).hexdigest()}
def _check_root(value,key):
    if type(value) is not dict or not _is_root(value.get(key)) or _rooted({k:v for k,v in value.items() if k!=key},key)!=value:
        raise Refusal('HELD_CONFIGURATION_SELECTION_ROOT')
def _name(value):
    return isinstance(value,str) and 1<=len(value)<=64 and all(c.isalnum() or c in '_.-' for c in value)

def build_library(output,stack_members):
    """stack_members are (stack_id, family, zero_based_ordinal, legend_path)."""
    output=Path(output);stack_members=tuple(stack_members)
    if not 1<=len(stack_members)<=MAX_STACKS*MAX_ARTIFACTS:raise Refusal('HELD_STACK_MEMBER_LIMIT')
    if any(type(row) not in (tuple,list) or len(row)!=4 for row in stack_members):
        raise Refusal('HELD_STACK_MEMBER_FIELDS')
    paths=[Path(row[3]) for row in stack_members];protect_outputs([output],paths)
    grouped={}
    for row in stack_members:
        identity,family,ordinal,path=row
        try:ordinal=int(ordinal)
        except (TypeError,ValueError):raise Refusal('HELD_STACK_MEMBER_ORDINAL') from None
        if not _name(identity) or family not in FAMILIES or ordinal<0:raise Refusal('HELD_STACK_MEMBER_VALUE')
        grouped.setdefault(identity,[]).append((family,ordinal,Path(path)))
    if len(grouped)>MAX_STACKS:raise Refusal('HELD_STACK_LIMIT')
    artifacts={};stacks=[]
    for identity,rows in sorted(grouped.items()):
        families={r[0] for r in rows}
        if len(families)!=1:raise Refusal('HELD_STACK_FAMILY_MISMATCH')
        rows.sort(key=lambda r:r[1])
        if [r[1] for r in rows]!=list(range(len(rows))):raise Refusal('HELD_STACK_MEMBER_ORDINAL')
        parent=None;roots=[]
        for _,_,path in rows:
            reader=LegendReader(path);verified=reader.verify();root=verified['sha256']
            if file_sha256(path)!=root:raise Refusal('HELD_STACK_DEPENDENCY_CHANGED_DURING_READ')
            if reader.header['parent_sha256']!=parent:raise Refusal('HELD_STACK_LINEAGE')
            item={'sha256':root,'bytes':path.stat().st_size,'entry_count':verified['entry_count'],
                'parent_sha256':reader.header['parent_sha256'],'unit_mode':reader.header['unit_mode']}
            if root in artifacts and artifacts[root]!=item:raise Refusal('HELD_STACK_ARTIFACT_IDENTITY')
            artifacts[root]=item;roots.append(root);parent=root
        stacks.append({'id':identity,'family':next(iter(families)),'legend_roots':roots})
    if len(artifacts)>MAX_ARTIFACTS or sum(r['bytes'] for r in artifacts.values())>MAX_LEGENDS:
        raise Refusal('HELD_STACK_ARTIFACT_BUDGET')
    value=_rooted({'schema':LIBRARY_SCHEMA,'standing':'CANDIDATE_ONLY',
      'unit_identity':'LOCAL_TRANSPORT_UNITS_NOT_GTK_SENSES','artifact_accounting':'UNIQUE_ROOT_ONCE',
      'artifacts':sorted(artifacts.values(),key=lambda r:r['sha256']),'stacks':stacks,
      'family_labels_are_semantic_proof':False,'security_claim':'NONE'},'library_root')
    data=canonical(value)
    if len(data)>MAX_LIBRARY:raise Refusal('HELD_STACK_LIBRARY_RECORD_LIMIT')
    output.parent.mkdir(parents=True,exist_ok=True)
    sio.write_bytes(output,data);load_library(output)
    return {'schema':'semcrys.legend-stack-library-build-result.v0.1','status':'PASS','standing':'CANDIDATE_ONLY',
      'library_root':value['library_root'],'output_sha256':file_sha256(output),'stacks':len(stacks),
      'unique_artifacts':len(artifacts),'deduplicated_references':sum(len(s['legend_roots']) for s in stacks)-len(artifacts)}

def load_library(path):
    value=canonical_object(path,MAX_LIBRARY);_check_root(value,'library_root')
    expected={'schema','standing','unit_identity','artifact_accounting','artifacts','stacks','family_labels_are_semantic_proof','security_claim','library_root'}
    if set(value)!=expected or value['schema']!=LIBRARY_SCHEMA or value['standing']!='CANDIDATE_ONLY' or \
       value['unit_identity']!='LOCAL_TRANSPORT_UNITS_NOT_GTK_SENSES' or value['artifact_accounting']!='UNIQUE_ROOT_ONCE' or \
       value['family_labels_are_semantic_proof'] is not False or value['security_claim']!='NONE':raise Refusal('HELD_STACK_LIBRARY_SCHEMA')
    rows=value['artifacts'];stacks=value['stacks']
    if type(rows) is not list or not 1<=len(rows)<=MAX_ARTIFACTS or type(stacks) is not list or not 1<=len(stacks)<=MAX_STACKS:
        raise Refusal('HELD_STACK_LIBRARY_LIMIT')
    roots=[];artifacts={}
    for row in rows:
        if type(row) is not dict or set(row)!={'sha256','bytes','entry_count','parent_sha256','unit_mode'} or not _is_root(row.get('sha256')) or \
           (row['parent_sha256'] is not None and not _is_root(row['parent_sha256'])) or type(row['bytes']) is not int or row['bytes']<1 or \
           type(row['entry_count']) is not int or row['entry_count']<0 or type(row['unit_mode']) is not str:
            raise Refusal('HELD_STACK_ARTIFACT_SCHEMA')
        roots.append(row['sha256']);artifacts[row['sha256']]=row
    if roots!=sorted(set(roots)) or sum(r['bytes'] for r in rows)>MAX_LEGENDS:raise Refusal('HELD_STACK_ARTIFACT_ORDER')
    names=[]
    for stack in stacks:
        if type(stack) is not dict or set(stack)!={'id','family','legend_roots'} or not _name(stack.get('id')) or stack.get('family') not in FAMILIES or \
           type(stack.get('legend_roots')) is not list or not stack['legend_roots'] or any(r not in artifacts for r in stack['legend_roots']):
            raise Refusal('HELD_STACK_SCHEMA')
        parent=None
        for root in stack['legend_roots']:
            if artifacts[root]['parent_sha256']!=parent:raise Refusal('HELD_STACK_LINEAGE')
            parent=root
        names.append(stack['id'])
    if names!=sorted(set(names)):raise Refusal('HELD_STACK_ORDER')
    return value

def _utf8(path):
    decoder=codecs.getincrementaldecoder('utf-8')('strict')
    try:
        with Path(path).open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):decoder.decode(block)
        decoder.decode(b'',final=True);return True
    except UnicodeDecodeError:return False

def _bind(paths,library,context):
    expected={r['sha256']:r for r in library['artifacts']};provided={}
    for row in context.rows(paths):
        root=row['sha256']
        if root not in expected or root in provided:raise Refusal('HELD_STACK_UNUSED_OR_DUPLICATE_DEPENDENCY')
        path=Path(row['path']);reader=LegendReader(path);item=expected[root]
        if path.stat().st_size!=item['bytes'] or reader.count!=item['entry_count'] or reader.header['parent_sha256']!=item['parent_sha256'] or reader.header['unit_mode']!=item['unit_mode']:
            raise Refusal('HELD_STACK_ARTIFACT_BINDING')
        provided[root]=path
    if set(provided)!=set(expected):raise Refusal('HELD_STACK_DEPENDENCY_MISSING')
    return provided,expected

def _options(codecs,accounting,receiver_roots,horizon,max_source_bytes,max_legend_bytes):
    codecs=list(codecs)
    if not codecs or len(codecs)>len(REQUESTABLE_OUTER_CODECS) or len(codecs)!=len(set(codecs)) or any(c not in REQUESTABLE_OUTER_CODECS for c in codecs):
        raise Refusal('HELD_CONFIGURATION_CODEC_SET')
    if accounting not in ('COLD','WARM'):raise Refusal('HELD_CONFIGURATION_ACCOUNTING')
    roots=sorted(receiver_roots)
    if len(roots)!=len(set(roots)) or any(not _is_root(r) for r in roots):raise Refusal('HELD_RECEIVER_ROOT_SET')
    if type(horizon) is not int or not 1<=horizon<=1024:raise Refusal('HELD_REUSE_HORIZON')
    if type(max_source_bytes) is not int or not 0<=max_source_bytes<=MAX_SOURCE:raise Refusal('HELD_CONFIGURATION_SOURCE_BUDGET')
    if type(max_legend_bytes) is not int or not 1<=max_legend_bytes<=MAX_LEGENDS:raise Refusal('HELD_CONFIGURATION_LEGEND_BUDGET')
    return codecs,roots

def _recipes(library,codecs):
    base=[{'id':'BASE:RAW','profile':'C:RAW_BYTES','stack_id':None,'legend_roots':[],'legend_policy':'PROFITABLE'},
      {'id':'BASE:LOCAL','profile':'C:SELF_CONTAINED_TOKEN','stack_id':None,'legend_roots':[],'legend_policy':'PROFITABLE'}]
    for stack in library['stacks']:
        base.extend([
          {'id':stack['id']+':PRESHARED','profile':'T:PRESHARED_TOKEN','stack_id':stack['id'],'legend_roots':stack['legend_roots'],'legend_policy':'PROFITABLE'},
          {'id':stack['id']+':DELTA','profile':'A:LONGITUDINAL_TOKEN_DELTA','stack_id':stack['id'],'legend_roots':stack['legend_roots'],'legend_policy':'TOTAL'}])
    result=[{**recipe,'codec':codec,'candidate_id':recipe['id']+':'+codec} for recipe in base for codec in codecs]
    if len(result)>MAX_CANDIDATES:raise Refusal('HELD_CONFIGURATION_CANDIDATE_LIMIT')
    return result

def select(source,output,*,library_path,legends,codecs=('NONE','LZMA'),accounting='COLD',receiver_roots=(),horizon=1,
           max_source_bytes=MAX_SOURCE,max_legend_bytes=MAX_LEGENDS,progress=None,
           instrumentation='SENTINEL',inverse_verification='ENCODER_POSTWRITE',lookup_backend='AUTO',
           backend_payload_budget_bytes=512*1024*1024,persistent_lookup_cache=None):
    source,output=Path(source),Path(output);protect_outputs([output],[source,library_path,*legends]);output.parent.mkdir(parents=True,exist_ok=True)
    codecs,receiver=_options(codecs,accounting,receiver_roots,horizon,max_source_bytes,max_legend_bytes)
    library=load_library(library_path)
    if instrumentation not in ('SENTINEL','DIAGNOSTIC'):raise Refusal('HELD_CONFIGURATION_INSTRUMENTATION')
    if inverse_verification not in ('ENCODER_POSTWRITE','INDEPENDENT_REDECODE'):raise Refusal('HELD_CONFIGURATION_INVERSE_MODE')
    if lookup_backend not in ('AUTO','DISK','MMAP','RAM'):raise Refusal('HELD_LOOKUP_BACKEND')
    if type(backend_payload_budget_bytes) is not int or not 0<=backend_payload_budget_bytes<=1<<40:raise Refusal('HELD_BACKEND_PAYLOAD_BUDGET')
    if source.stat().st_size>max_source_bytes:raise Refusal('HELD_CONFIGURATION_SOURCE_BUDGET')
    with sio.TempDirectory(prefix='configuration-select-',dir=output.parent) as name,VerifiedLegendContext(
            max_legend_bytes=max_legend_bytes,lookup_backend=lookup_backend,
            backend_payload_budget_bytes=backend_payload_budget_bytes,
            persistent_lookup_cache=persistent_lookup_cache) as context:
        work=Path(name);frozen=work/'source';source_root=_snapshot(source,frozen,max_source_bytes)
        bound,artifacts=_bind(legends,library,context)
        if not set(receiver).issubset(artifacts):raise Refusal('HELD_RECEIVER_ROOT_OUTSIDE_LIBRARY')
        recipes=_recipes(library,codecs);source_utf8=_utf8(frozen)
        instance=_rooted({'schema':INSTANCE_SCHEMA,'standing':'CANDIDATE_ONLY','library_root':library['library_root'],
          'source_sha256':source_root,'source_bytes':frozen.stat().st_size,'source_utf8':source_utf8,
          'codecs':codecs,'codec_configurations':[measurement_codec_configuration(c) for c in codecs],
          'candidate_recipes':recipes,'accounting':accounting,'receiver_roots':receiver,'reuse_horizon':horizon,
          'objective':'MIN_TOTAL_DELIVERY_BYTES_AT_EXACT_REUSE_HORIZON','tie_break':'CANDIDATE_ID',
          'reported_nonobjective_metrics':['VERIFICATION_WALL_NS','VERIFICATION_CPU_NS']+
            (['TRACED_PYTHON_PEAK_BYTES'] if instrumentation=='DIAGNOSTIC' else []),
          'memory_metric_scope':'PYTHON_TRACEMALLOC_NOT_PROCESS_RSS_OR_NATIVE_ALLOCATIONS' if instrumentation=='DIAGNOSTIC' else 'NOT_CAPTURED_IN_SENTINEL_MODE',
          'instrumentation':instrumentation,'inverse_verification':inverse_verification,
          'lookup_backend':lookup_backend,'backend_payload_budget_bytes':backend_payload_budget_bytes,
          'persistent_lookup_cache':persistent_lookup_cache is not None,
          'implementation_identity':_implementation_identity(),'max_source_bytes':max_source_bytes,'max_legend_bytes':max_legend_bytes,
          'operation_sequence':OPERATIONS,'future_prediction':False,'security_claim':'NONE'},'instance_constitution_sha256')
        if progress:progress({'stage':'CONFIGURATION_SELECTION_INSTANCE_COMPILED','effective_configuration':instance})
        rows=[]
        for order,recipe in enumerate(recipes):
            missing=sorted(set(recipe['legend_roots'])-set(receiver))
            unavailable=None
            if recipe['codec'] in ('ZSTD','ZSTD_DICT'):unavailable='HELD_OPTIONAL_CODEC_ADAPTER_NOT_PACKAGED'
            elif accounting=='WARM' and missing:unavailable='RECEIVER_ROOT_NOT_ACKNOWLEDGED'
            elif not source_utf8 and recipe['profile']!='C:RAW_BYTES':unavailable='SOURCE_NOT_UTF8'
            if unavailable:
                rows.append({'order':order,'recipe':recipe,'status':'UNAVAILABLE','code':unavailable,'missing_roots':missing});continue
            if progress:progress({'stage':'CONFIGURATION_CANDIDATE_STARTED','candidate':recipe['candidate_id']})
            target=work/(str(order)+'.crys');inverse=work/(str(order)+'.decoded')
            if instrumentation=='DIAGNOSTIC':tracemalloc.start()
            wall=time.perf_counter_ns();cpu=time.process_time_ns();peak=None
            try:
                realized=encode_file(frozen,target,profile=recipe['profile'],external_legends=[bound[r] for r in recipe['legend_roots']],
                    outer_codec=recipe['codec'],legend_policy=recipe['legend_policy'],legend_context=context)
                proof=realized.get('postwrite_reconstruction')
                if proof!={'status':'PASS','output_sha256':source_root,'proof':'DECODED_CANDIDATE_BYTES_HASH_MATCH_SOURCE'}:
                    raise Refusal('HELD_CONFIGURATION_INVERSE_MISMATCH')
                if inverse_verification=='INDEPENDENT_REDECODE':
                    decoded=decode_file(target,inverse,external_legends=[bound[r] for r in recipe['legend_roots']],legend_context=context)
                    if decoded['output_sha256']!=source_root or file_sha256(inverse)!=source_root:raise Refusal('HELD_CONFIGURATION_INVERSE_MISMATCH')
                cpu=time.process_time_ns()-cpu;wall=time.perf_counter_ns()-wall
                if instrumentation=='DIAGNOSTIC':_,peak=tracemalloc.get_traced_memory()
            finally:
                if instrumentation=='DIAGNOSTIC':tracemalloc.stop()
            acquisition=sum(artifacts[r]['bytes'] for r in missing);container=target.stat().st_size
            accounting_row=inspect_artifact(target)['byte_accounting']
            rows.append({'order':order,'recipe':recipe,'status':'PASS','container_bytes':container,
              'acquisition_bytes':acquisition,'reuse_horizon':horizon,'score_bytes':container*horizon+acquisition,
              'verification_wall_ns':wall,'verification_cpu_ns':cpu,'traced_python_peak_bytes':peak,
              'instrumentation':instrumentation,'inverse_verification':inverse_verification,
              'execution_metrics':realized['execution_metrics'],
              'body_payload_bytes':accounting_row['body_payload_bytes'],'container_sha256':realized['output_sha256'],
              'decoded_sha256':source_root,'effective_configuration':realized['effective_configuration'],'receipt':realized['receipt']})
            if progress:progress({'stage':'CONFIGURATION_CANDIDATE_FINISHED','candidate':recipe['candidate_id'],'score_bytes':container*horizon+acquisition})
        passed=[r for r in rows if r['status']=='PASS']
        if not passed:raise Refusal('HELD_NO_CONFIGURATION_CANDIDATE')
        winner=min(passed,key=lambda r:(r['score_bytes'],r['recipe']['candidate_id']))
        value=_rooted({'schema':SELECTION_SCHEMA,'standing':'CANDIDATE_ONLY','instance_constitution':instance,'rows':rows,
          'selected_candidate_id':winner['recipe']['candidate_id'],'selected_container_sha256':winner['container_sha256'],
          'selected_score_bytes':winner['score_bytes'],'selection_scope':'ONE_EXACT_SOURCE_LIBRARY_AND_REUSE_HORIZON',
          'future_prediction':False,'global_optimality':False,'security_claim':'NONE'},'selection_root')
        data=canonical(value)
        if len(data)>MAX_LIBRARY:raise Refusal('HELD_CONFIGURATION_SELECTION_RECORD_LIMIT')
        sio.write_bytes(output,data)
    return {'schema':'semcrys.configuration-selection-result.v0.2','status':'PASS','standing':'CANDIDATE_ONLY',
      'selection_root':value['selection_root'],'output_sha256':file_sha256(output),'selected_candidate_id':winner['recipe']['candidate_id'],
      'selected_score_bytes':winner['score_bytes'],'candidate_count':len(rows),'available_candidate_count':len(passed),
      'effective_configuration':instance,'global_optimality':False}

def _snapshot(source,target,limit):
    total=0;digest=hashlib.sha256()
    with Path(source).open('rb') as incoming,sio.open_output(target,'wb') as outgoing:
        for block in iter(lambda:incoming.read(1024*1024),b''):
            total+=len(block)
            if total>limit:raise Refusal('HELD_CONFIGURATION_SOURCE_BUDGET')
            digest.update(block);outgoing.write(block)
    return digest.hexdigest()

def load_selection(path,library):
    value=canonical_object(path,MAX_LIBRARY);_check_root(value,'selection_root')
    expected={'schema','standing','instance_constitution','rows','selected_candidate_id','selected_container_sha256','selected_score_bytes','selection_scope','future_prediction','global_optimality','security_claim','selection_root'}
    if set(value)!=expected or value['schema']!=SELECTION_SCHEMA or value['standing']!='CANDIDATE_ONLY' or value['selection_scope']!='ONE_EXACT_SOURCE_LIBRARY_AND_REUSE_HORIZON' or value['future_prediction'] is not False or value['global_optimality'] is not False or value['security_claim']!='NONE':
        raise Refusal('HELD_CONFIGURATION_SELECTION_SCHEMA')
    ic=value['instance_constitution'];_check_root(ic,'instance_constitution_sha256')
    required={'schema','standing','library_root','source_sha256','source_bytes','source_utf8','codecs','codec_configurations','candidate_recipes','accounting','receiver_roots','reuse_horizon','objective','tie_break','reported_nonobjective_metrics','memory_metric_scope','instrumentation','inverse_verification','lookup_backend','backend_payload_budget_bytes','persistent_lookup_cache','implementation_identity','max_source_bytes','max_legend_bytes','operation_sequence','future_prediction','security_claim','instance_constitution_sha256'}
    implementation=ic.get('implementation_identity')
    metrics=['VERIFICATION_WALL_NS','VERIFICATION_CPU_NS']+(['TRACED_PYTHON_PEAK_BYTES'] if ic.get('instrumentation')=='DIAGNOSTIC' else [])
    memory_scope='PYTHON_TRACEMALLOC_NOT_PROCESS_RSS_OR_NATIVE_ALLOCATIONS' if ic.get('instrumentation')=='DIAGNOSTIC' else 'NOT_CAPTURED_IN_SENTINEL_MODE'
    if set(ic)!=required or ic['schema']!=INSTANCE_SCHEMA or ic['standing']!='CANDIDATE_ONLY' or ic['library_root']!=library['library_root'] or not _is_root(ic.get('source_sha256')) or type(ic.get('source_bytes')) is not int or not 0<=ic['source_bytes']<=ic.get('max_source_bytes',-1) or type(ic.get('source_utf8')) is not bool or ic['objective']!='MIN_TOTAL_DELIVERY_BYTES_AT_EXACT_REUSE_HORIZON' or ic['tie_break']!='CANDIDATE_ID' or ic.get('instrumentation') not in ('SENTINEL','DIAGNOSTIC') or ic.get('inverse_verification') not in ('ENCODER_POSTWRITE','INDEPENDENT_REDECODE') or ic.get('lookup_backend') not in ('AUTO','DISK','MMAP','RAM') or type(ic.get('backend_payload_budget_bytes')) is not int or not 0<=ic['backend_payload_budget_bytes']<=1<<40 or type(ic.get('persistent_lookup_cache')) is not bool or ic.get('reported_nonobjective_metrics')!=metrics or ic.get('memory_metric_scope')!=memory_scope or type(implementation) is not dict or set(implementation)!={'application_version','application_payload_root','python_implementation','python_version','platform_system','platform_machine','byteorder','lzma_adapter','bz2_adapter'} or not _is_root(implementation.get('application_payload_root')) or implementation.get('byteorder') not in ('little','big') or ic['operation_sequence']!=OPERATIONS or ic['future_prediction'] is not False or ic['security_claim']!='NONE':
        raise Refusal('HELD_CONFIGURATION_SELECTION_INSTANCE')
    codecs,receiver=_options(ic['codecs'],ic['accounting'],ic['receiver_roots'],ic['reuse_horizon'],ic['max_source_bytes'],ic['max_legend_bytes'])
    if ic['codec_configurations']!=[measurement_codec_configuration(c) for c in codecs] or ic['candidate_recipes']!=_recipes(library,codecs) or receiver!=ic['receiver_roots']:
        raise Refusal('HELD_CONFIGURATION_SELECTION_SEQUENCE')
    artifacts={r['sha256']:r for r in library['artifacts']};passed=[]
    if type(value['rows']) is not list or len(value['rows'])!=len(ic['candidate_recipes']):raise Refusal('HELD_CONFIGURATION_SELECTION_SEQUENCE')
    for order,(recipe,row) in enumerate(zip(ic['candidate_recipes'],value['rows'])):
        if type(row) is not dict or row.get('order')!=order or row.get('recipe')!=recipe:raise Refusal('HELD_CONFIGURATION_SELECTION_SEQUENCE')
        missing=sorted(set(recipe['legend_roots'])-set(ic['receiver_roots']))
        code=('HELD_OPTIONAL_CODEC_ADAPTER_NOT_PACKAGED' if recipe['codec'] in ('ZSTD','ZSTD_DICT') else
              'RECEIVER_ROOT_NOT_ACKNOWLEDGED' if ic['accounting']=='WARM' and missing else
              'SOURCE_NOT_UTF8' if not ic['source_utf8'] and recipe['profile']!='C:RAW_BYTES' else None)
        if code:
            if row!={'order':order,'recipe':recipe,'status':'UNAVAILABLE','code':code,'missing_roots':missing}:raise Refusal('HELD_CONFIGURATION_SELECTION_ROW')
            continue
        fields={'order','recipe','status','container_bytes','acquisition_bytes','reuse_horizon','score_bytes','verification_wall_ns','verification_cpu_ns','traced_python_peak_bytes','instrumentation','inverse_verification','execution_metrics','body_payload_bytes','container_sha256','decoded_sha256','effective_configuration','receipt'}
        if set(row)!=fields or row['status']!='PASS' or not _is_root(row['container_sha256']) or row['decoded_sha256']!=ic['source_sha256']:raise Refusal('HELD_CONFIGURATION_SELECTION_ROW')
        for field in ('container_bytes','acquisition_bytes','score_bytes','verification_wall_ns','verification_cpu_ns','body_payload_bytes'):
            if type(row[field]) is not int or row[field]<0:raise Refusal('HELD_CONFIGURATION_SELECTION_ROW')
        if row['instrumentation']!=ic['instrumentation'] or row['inverse_verification']!=ic['inverse_verification'] or (row['traced_python_peak_bytes'] is None)!=(ic['instrumentation']=='SENTINEL') or (row['traced_python_peak_bytes'] is not None and (type(row['traced_python_peak_bytes']) is not int or row['traced_python_peak_bytes']<0)):
            raise Refusal('HELD_CONFIGURATION_SELECTION_ROW')
        execution=row['execution_metrics']
        if type(execution) is not dict or execution.get('schema')!='semcrys.execution-metrics.v0.1' or execution.get('scope')!='NONCANONICAL_RUNTIME_OBSERVATION_NOT_CONTAINER_IDENTITY' or type(execution.get('phase_wall_ns')) is not dict or any(type(v) is not int or v<0 for v in execution['phase_wall_ns'].values()):
            raise Refusal('HELD_CONFIGURATION_SELECTION_ROW')
        acquisition=sum(artifacts[r]['bytes'] for r in missing)
        effective=row['effective_configuration']
        if type(effective) is not dict or row['acquisition_bytes']!=acquisition or row['reuse_horizon']!=ic['reuse_horizon'] or row['score_bytes']!=row['container_bytes']*ic['reuse_horizon']+acquisition or effective.get('outer_codec')!=recipe['codec'] or effective.get('external_legend_roots')!=recipe['legend_roots'] or effective.get('source_sha256')!=ic['source_sha256'] or effective.get('profile')!=recipe['profile'] or effective.get('legend_policy')!=recipe['legend_policy']:
            raise Refusal('HELD_CONFIGURATION_SELECTION_SCORE')
        passed.append(row)
    if not passed:raise Refusal('HELD_NO_CONFIGURATION_CANDIDATE')
    winner=min(passed,key=lambda r:(r['score_bytes'],r['recipe']['candidate_id']))
    if (value['selected_candidate_id'],value['selected_container_sha256'],value['selected_score_bytes'])!=(winner['recipe']['candidate_id'],winner['container_sha256'],winner['score_bytes']):raise Refusal('HELD_CONFIGURATION_SELECTION_NOT_MINIMUM')
    return value,winner

def encode_selected(source,selection_path,output,*,library_path,legends,progress=None,persistent_lookup_cache=None):
    source,selection_path,output=Path(source),Path(selection_path),Path(output);protect_outputs([output],[source,selection_path,library_path,*legends]);output.parent.mkdir(parents=True,exist_ok=True)
    library=load_library(library_path);selection,winner=load_selection(selection_path,library);ic=selection['instance_constitution'];recipe=winner['recipe']
    if ic['implementation_identity']!=_implementation_identity():raise Refusal('HELD_CONFIGURATION_SELECTION_IMPLEMENTATION_CHANGED')
    if progress:progress({'stage':'CONFIGURATION_SELECTED_REPLAY_STARTED','selection_root':selection['selection_root'],'candidate':recipe['candidate_id']})
    with sio.TempDirectory(prefix='configuration-replay-',dir=output.parent) as name,VerifiedLegendContext(max_legend_bytes=ic['max_legend_bytes'],
            lookup_backend=ic['lookup_backend'],backend_payload_budget_bytes=ic['backend_payload_budget_bytes'],
            persistent_lookup_cache=persistent_lookup_cache) as context:
        work=Path(name);frozen=work/'source';root=_snapshot(source,frozen,ic['max_source_bytes'])
        if root!=ic['source_sha256'] or frozen.stat().st_size!=ic['source_bytes'] or _utf8(frozen)!=ic['source_utf8']:raise Refusal('HELD_CONFIGURATION_SELECTION_SOURCE_CHANGED')
        bound,_=_bind(legends,library,context);target=work/'chosen.crys'
        realized=encode_file(frozen,target,profile=recipe['profile'],external_legends=[bound[r] for r in recipe['legend_roots']],outer_codec=recipe['codec'],legend_policy=recipe['legend_policy'],legend_context=context)
        if realized['output_sha256']!=winner['container_sha256'] or target.stat().st_size!=winner['container_bytes'] or canonical(realized['effective_configuration'])!=canonical(winner['effective_configuration']) or canonical(realized['receipt'])!=canonical(winner['receipt']):
            raise Refusal('HELD_CONFIGURATION_SELECTED_REALIZATION_DRIFT')
        inverse=work/'decoded';decoded=decode_file(target,inverse,external_legends=[bound[r] for r in recipe['legend_roots']],legend_context=context)
        if decoded['output_sha256']!=root:raise Refusal('HELD_CONFIGURATION_INVERSE_MISMATCH')
        sio.replace(target,output)
    result={**realized,'selection_root':selection['selection_root'],'selected_candidate_id':recipe['candidate_id'],
      'selection_replay':'EXACT_SELECTED_CANDIDATE_ONLY','accounting':{'mode':ic['accounting'],'reuse_horizon':ic['reuse_horizon'],
      'container_bytes':winner['container_bytes'],'acquisition_bytes':winner['acquisition_bytes'],'score_bytes':winner['score_bytes']},'global_optimality':False}
    if progress:progress({'stage':'CONFIGURATION_SELECTED_REPLAY_FINISHED','selection_root':selection['selection_root'],'candidate':recipe['candidate_id']})
    return result
