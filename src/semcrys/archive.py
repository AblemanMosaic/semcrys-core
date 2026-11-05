"""Bounded exact-workload selection; not a predictor of unseen archives.

SPDX-License-Identifier: Apache-2.0
"""
import hashlib,os,tempfile
from pathlib import Path
from .artifacts import canonical_object
from .library import _bounded_snapshot,_utf8,rooted,_verify_root
from streaming_app.core import Refusal,encode_file,protect_outputs,_is_root
from streaming_app.legend_context import VerifiedLegendContext
from streaming_app.fold_projection import FoldView
from streaming_legend import fold
from streaming_legend import scratch_io as sio
from streaming_legend.core import canonical,file_sha256

MAX_SOURCE=64*1024*1024
MAX_LEGEND=1024*1024*1024
MAX_DOCUMENTS=32
MAX_FRONTS=8
MAX_REALIZATIONS=512
MAX_RECORD=8*1024*1024
SCHEMA='semcrys.archive-selection.v0.1'
OPERATIONS=['SNAPSHOT_SOURCES_AND_DEPENDENCIES','VALIDATE_BOUNDED_CANDIDATES','COMPILE_ARCHIVE_INSTANCE',
    'REALIZE_EACH_ADMISSIBLE_RECIPE_WITH_EXACT_INVERSE','CHARGE_MISSING_DEPENDENCIES_ONCE',
    'CALCULATE_EXPLICIT_IDENTICAL_WORKLOAD_REUSE','SELECT_MINIMUM_WITH_ID_TIEBREAK','GUARD_AND_PUBLISH']
SCOPE='EXACT_ORDERED_FILES_AND_LISTED_CONFIGURATIONS; HORIZON_REPEATS_THIS_IDENTICAL_WORKLOAD_NOT_UNSEEN_DATA'
LEGACY_EXCLUSIONS=['LOCAL_SELECTION_AND_REPLAY_RECEIPTS','OS_NETWORK_SESSION_FRAMING','UNMEASURED_FUTURE_DOCUMENTS']
EXCLUSIONS=LEGACY_EXCLUSIONS+['SEPARATE_PROJECTION_PROVENANCE_DOSSIERS']

def _options(accounting,receiver_roots,outer_codec,horizon,max_source_bytes,max_legend_bytes):
    if accounting not in ('COLD','WARM') or outer_codec not in ('NONE','LZMA'): raise Refusal('HELD_ARCHIVE_CONFIGURATION')
    if type(horizon) is not int or not 1<=horizon<=32: raise Refusal('HELD_ARCHIVE_HORIZON')
    if type(max_source_bytes) is not int or not 0<=max_source_bytes<=MAX_SOURCE: raise Refusal('HELD_ARCHIVE_SOURCE_BUDGET')
    if type(max_legend_bytes) is not int or not 1<=max_legend_bytes<=MAX_LEGEND: raise Refusal('HELD_ARCHIVE_LEGEND_BUDGET')
    if type(receiver_roots) not in (list,tuple) or len(receiver_roots)>MAX_FRONTS+1 or any(not _is_root(r) for r in receiver_roots) or len(receiver_roots)!=len(set(receiver_roots)):
        raise Refusal('HELD_ARCHIVE_RECEIVER_ROOTS')
    return sorted(receiver_roots)

def _sources(paths,work,budget):
    if not 1<=len(paths)<=MAX_DOCUMENTS: raise Refusal('HELD_ARCHIVE_DOCUMENT_COUNT')
    rows=[]; snapshots=[]; used=0
    for i,value in enumerate(paths):
        p=Path(value)
        if p.stat().st_size>budget-used: raise Refusal('HELD_ARCHIVE_SOURCE_BUDGET')
        q=work/f's{i}'; root=_bounded_snapshot(p,q,budget-used); used+=q.stat().st_size
        rows.append({'sha256':root,'bytes':q.stat().st_size,'utf8':_utf8(q)}); snapshots.append(q)
    return rows,snapshots

def _dependencies(base,fronts,work,budget,context):
    if not 1<=len(fronts)<=MAX_FRONTS: raise Refusal('HELD_ARCHIVE_FRONT_COUNT')
    row=context.prepare(base)
    if row['reader'].header['parent_sha256'] is not None: raise Refusal('HELD_ARCHIVE_BASE_REQUIRED')
    base_info={'sha256':row['sha256'],'bytes':row['path'].stat().st_size,'entry_count':row['entries']}
    if base_info['bytes']>budget: raise Refusal('HELD_ARCHIVE_LEGEND_BUDGET')
    registry=[]; paths={}; total=base_info['bytes']
    for i,path in enumerate(fronts):
        h,_,_,data,root=fold.load(path); total+=len(data)
        if total>budget: raise Refusal('HELD_ARCHIVE_LEGEND_BUDGET')
        if root in paths: raise Refusal('HELD_ARCHIVE_DUPLICATE_FRONT')
        q=work/f'f{i}.leg'; sio.write_bytes(q,data)
        FoldView(q,row['path'],context)  # Validate even candidates unavailable to receiver.
        registry.append({'sha256':root,'bytes':len(data),'front_entries':h['front_entries'],'front_cap':h['front_cap']})
        paths[root]=q
    if not any(r['front_entries']==0 for r in registry): raise Refusal('HELD_ARCHIVE_ZERO_FRONT_REQUIRED')
    return base_info,sorted(registry,key=lambda r:r['sha256']),row['path'],paths

def _recipes(base,fronts):
    recipes=[{'id':'BASE:RAW','profile':'C:RAW_BYTES','front':None,'placement':None,'dependencies':[]},
        {'id':'BASE:LOCAL','profile':'C:SELF_CONTAINED_TOKEN','front':None,'placement':None,'dependencies':[]},
        {'id':'BASE:PRESHARED','profile':'T:PRESHARED_TOKEN','front':None,'placement':None,'dependencies':[base['sha256']]}]
    for row in fronts:
        for placement in ('EMBEDDED','EXTERNAL'):
            deps=[base['sha256']]+([row['sha256']] if placement=='EXTERNAL' else [])
            recipes.append({'id':'FOLD:'+row['sha256']+':'+placement,'profile':'T:PRESHARED_TOKEN',
                'front':row['sha256'],'placement':placement,'dependencies':deps})
    return sorted(recipes,key=lambda r:r['id'])

def _unavailable(recipe,ic):
    missing=sorted(set(recipe['dependencies'])-set(ic['receiver_roots']))
    if ic['accounting']=='WARM' and missing:
        return {'recipe':recipe,'status':'UNAVAILABLE','code':'RECEIVER_DEPENDENCY_NOT_DECLARED','missing_roots':missing}
    if not all(s['utf8'] for s in ic['sources']) and recipe['profile']!='C:RAW_BYTES':
        return {'recipe':recipe,'status':'UNAVAILABLE','code':'SOURCE_NOT_UTF8'}
    return None

def _arguments(recipe,ic,base,fronts,context):
    args={'profile':recipe['profile'],'external_legends':[base] if recipe['dependencies'] else [],
        'outer_codec':ic['outer_codec'],'legend_context':context}
    if recipe['front'] is not None:
        args.update(fold_front=fronts[recipe['front']],fold_placement=recipe['placement'])
        if recipe['placement']=='EXTERNAL':
            args.update(accounting=ic['accounting'],receiver_roots=[r for r in ic['receiver_roots'] if r in recipe['dependencies']])
    return args

def _document(source,output,result):
    return {'source_sha256':file_sha256(source),'source_bytes':source.stat().st_size,
        'container_sha256':result['output_sha256'],'container_bytes':output.stat().st_size,
        'instance_constitution_sha256':result['effective_configuration']['instance_constitution_sha256']}

def _cost(recipe,documents,ic):
    sizes={r['sha256']:r['bytes'] for r in [ic['base'],*ic['fronts']]}
    missing=sorted(set(recipe['dependencies'])-set(ic['receiver_roots']))
    acquisition=sum(sizes[r] for r in missing); wire=sum(d['container_bytes'] for d in documents)
    return {'missing_roots':missing,'new_dependency_bytes':acquisition,'one_delivery_container_bytes':wire,
        'one_delivery_accounted_bytes':wire+acquisition,'horizon_score_bytes':wire*ic['horizon']+acquisition}

def select_archive(output,*,sources,base,fronts,accounting,receiver_roots=(),outer_codec='NONE',horizon=1,
                   max_source_bytes=MAX_SOURCE,max_legend_bytes=MAX_LEGEND,progress=None):
    target=Path(output); sources=list(sources); fronts=list(fronts)
    protect_outputs([target],[*sources,base,*fronts])
    receiver=_options(accounting,receiver_roots,outer_codec,horizon,max_source_bytes,max_legend_bytes)
    if not 1<=len(sources)<=MAX_DOCUMENTS or len(sources)*(3+2*len(fronts))>MAX_REALIZATIONS: raise Refusal('HELD_ARCHIVE_REALIZATION_BUDGET')
    target.parent.mkdir(parents=True,exist_ok=True)
    with sio.TempDirectory(prefix='as-',dir=target.parent) as name:
        work=Path(name)
        with VerifiedLegendContext(max_legend_bytes=max_legend_bytes,progress=progress) as context:
            source_rows,snapshots=_sources(sources,work,max_source_bytes)
            base_info,front_info,base_path,front_paths=_dependencies(base,fronts,work,max_legend_bytes,context)
            if not set(receiver)<={base_info['sha256'],*(r['sha256'] for r in front_info)}: raise Refusal('HELD_ARCHIVE_UNKNOWN_RECEIVER_ROOT')
            ic=rooted({'schema':'semcrys.archive-selection-instance.v0.1','standing':'CANDIDATE_ONLY',
                'sources':source_rows,'base':base_info,'fronts':front_info,'accounting':accounting,'receiver_roots':receiver,
                'outer_codec':outer_codec,'horizon':horizon,'max_source_bytes':max_source_bytes,'max_legend_bytes':max_legend_bytes,
                'candidate_recipes':_recipes(base_info,front_info),'operation_sequence':OPERATIONS,'selection_scope':SCOPE,
                'projection':'PACKED','security_claim':'NONE','relationship_state_mutation':False},'instance_constitution_sha256')
            if progress: progress({'stage':'ARCHIVE_INSTANCE_COMPILED','effective_configuration':ic})
            rows=[]
            for recipe in ic['candidate_recipes']:
                unavailable=_unavailable(recipe,ic)
                if unavailable: rows.append(unavailable); continue
                if progress: progress({'stage':'ARCHIVE_CANDIDATE_STARTED','candidate':recipe['id']})
                documents=[]
                for i,source in enumerate(snapshots):
                    trial=work/'trial.crys'; result=encode_file(source,trial,**_arguments(recipe,ic,base_path,front_paths,context))
                    documents.append(_document(source,trial,result)); sio.unlink(trial)
                    if progress: progress({'stage':'ARCHIVE_DOCUMENT_MEASURED','candidate':recipe['id'],'index':i})
                row={'recipe':recipe,'status':'PASS','documents':documents,**_cost(recipe,documents,ic)}; rows.append(row)
                if progress: progress({'stage':'ARCHIVE_CANDIDATE_FINISHED','candidate':recipe['id'],'score_bytes':row['horizon_score_bytes']})
            winner=min((r for r in rows if r['status']=='PASS'),key=lambda r:(r['horizon_score_bytes'],r['recipe']['id']))
            value=rooted({'schema':SCHEMA,'standing':'CANDIDATE_ONLY','instance_constitution':ic,'rows':rows,
                'selected_id':winner['recipe']['id'],'not_counted':EXCLUSIONS,'acquisition_encoding':'EXACT_UNCOMPRESSED_DEPENDENCY_ARTIFACTS',
                'receiver_evidence':'CALLER_DECLARATION_NOT_REMOTE_ATTESTATION','future_reuse_prediction':False},'selection_root')
            data=canonical(value)
            if len(data)>MAX_RECORD: raise Refusal('HELD_ARCHIVE_RECORD_LIMIT')
            pending=work/'selection.json'; sio.write_bytes(pending,data); load_selection(pending)
            context.verify_used(); execution=context.receipt()
        sio.replace(pending,target)
    return {'status':'PASS','standing':'CANDIDATE_ONLY','selection_root':value['selection_root'],'selected_id':winner['recipe']['id'],
        'effective_configuration':ic,'horizon_score_bytes':winner['horizon_score_bytes'],
        'one_delivery_accounted_bytes':winner['one_delivery_accounted_bytes'],'execution_context':execution,
        'candidate_count':len(rows),'global_optimality':False,'future_reuse_prediction':False,'output_sha256':file_sha256(target)}

def load_selection(path):
    value=canonical_object(path,MAX_RECORD); _verify_root(value,'selection_root')
    keys={'schema','standing','instance_constitution','rows','selected_id','not_counted','acquisition_encoding','receiver_evidence','future_reuse_prediction','selection_root'}
    if set(value)!=keys or value['schema']!=SCHEMA or value['standing']!='CANDIDATE_ONLY' or value['future_reuse_prediction'] is not False:
        raise Refusal('HELD_ARCHIVE_SELECTION_SCHEMA')
    if value['not_counted'] not in (EXCLUSIONS,LEGACY_EXCLUSIONS) or value['acquisition_encoding']!='EXACT_UNCOMPRESSED_DEPENDENCY_ARTIFACTS' or value['receiver_evidence']!='CALLER_DECLARATION_NOT_REMOTE_ATTESTATION':
        raise Refusal('HELD_ARCHIVE_ACCOUNTING_CONTRACT')
    ic=value['instance_constitution']
    if type(ic) is not dict: raise Refusal('HELD_ARCHIVE_INSTANCE_SCHEMA')
    _verify_root(ic,'instance_constitution_sha256')
    keys={'schema','standing','sources','base','fronts','accounting','receiver_roots','outer_codec','horizon',
        'max_source_bytes','max_legend_bytes','candidate_recipes','operation_sequence','selection_scope','projection',
        'security_claim','relationship_state_mutation','instance_constitution_sha256'}
    if set(ic)!=keys or ic['schema']!='semcrys.archive-selection-instance.v0.1' or ic['standing']!='CANDIDATE_ONLY' or ic['projection']!='PACKED' or ic['security_claim']!='NONE' or ic['relationship_state_mutation'] is not False:
        raise Refusal('HELD_ARCHIVE_INSTANCE_SCHEMA')
    if ic['operation_sequence']!=OPERATIONS or ic['selection_scope']!=SCOPE: raise Refusal('HELD_ARCHIVE_OPERATION_SEQUENCE')
    receiver=_options(ic['accounting'],ic['receiver_roots'],ic['outer_codec'],ic['horizon'],ic['max_source_bytes'],ic['max_legend_bytes'])
    if receiver!=ic['receiver_roots']: raise Refusal('HELD_ARCHIVE_RECEIVER_ORDER')
    if type(ic['sources']) is not list or not 1<=len(ic['sources'])<=MAX_DOCUMENTS: raise Refusal('HELD_ARCHIVE_DOCUMENT_COUNT')
    for s in ic['sources']:
        if type(s) is not dict or set(s)!={'sha256','bytes','utf8'} or not _is_root(s['sha256']) or type(s['bytes']) is not int or s['bytes']<0 or type(s['utf8']) is not bool: raise Refusal('HELD_ARCHIVE_SOURCE_SCHEMA')
    if sum(s['bytes'] for s in ic['sources'])>ic['max_source_bytes']: raise Refusal('HELD_ARCHIVE_SOURCE_BUDGET')
    base=ic['base']; fronts=ic['fronts']
    if type(base) is not dict or set(base)!={'sha256','bytes','entry_count'} or not _is_root(base['sha256']) or type(base['bytes']) is not int or not 1<=base['bytes']<=MAX_LEGEND or type(base['entry_count']) is not int or not 0<=base['entry_count']<=1000000000:
        raise Refusal('HELD_ARCHIVE_BASE_SCHEMA')
    if type(fronts) is not list or not 1<=len(fronts)<=MAX_FRONTS: raise Refusal('HELD_ARCHIVE_FRONT_COUNT')
    for r in fronts:
        if type(r) is not dict or set(r)!={'sha256','bytes','front_entries','front_cap'} or not _is_root(r['sha256']) or type(r['bytes']) is not int or not 1<=r['bytes']<=fold.MAX_BYTES:
            raise Refusal('HELD_ARCHIVE_FRONT_SCHEMA')
        if any(type(r[k]) is not int for k in ('front_entries','front_cap')) or not 0<=r['front_entries']<=r['front_cap']<=fold.MAX_FRONT: raise Refusal('HELD_ARCHIVE_FRONT_SCHEMA')
    roots=[r['sha256'] for r in fronts]
    if roots!=sorted(set(roots)) or base['sha256'] in roots: raise Refusal('HELD_ARCHIVE_DUPLICATE_FRONT')
    if not any(r['front_entries']==0 for r in fronts): raise Refusal('HELD_ARCHIVE_ZERO_FRONT_REQUIRED')
    if base['bytes']+sum(r['bytes'] for r in fronts)>ic['max_legend_bytes']: raise Refusal('HELD_ARCHIVE_LEGEND_BUDGET')
    if not set(receiver)<={base['sha256'],*roots}: raise Refusal('HELD_ARCHIVE_UNKNOWN_RECEIVER_ROOT')
    recipes=_recipes(base,fronts)
    if len(recipes)*len(ic['sources'])>MAX_REALIZATIONS: raise Refusal('HELD_ARCHIVE_REALIZATION_BUDGET')
    if ic['candidate_recipes']!=recipes or type(value['rows']) is not list or len(value['rows'])!=len(recipes): raise Refusal('HELD_ARCHIVE_RECIPE_SEQUENCE')
    passed=[]
    for recipe,row in zip(recipes,value['rows']):
        if type(row) is not dict or row.get('recipe')!=recipe: raise Refusal('HELD_ARCHIVE_RECIPE_SEQUENCE')
        unavailable=_unavailable(recipe,ic)
        if unavailable is not None:
            if row!=unavailable: raise Refusal('HELD_ARCHIVE_AVAILABILITY')
            continue
        if set(row)!={'recipe','status','documents','missing_roots','new_dependency_bytes','one_delivery_container_bytes','one_delivery_accounted_bytes','horizon_score_bytes'} or row['status']!='PASS':
            raise Refusal('HELD_ARCHIVE_ROW_SCHEMA')
        if type(row['documents']) is not list or len(row['documents'])!=len(ic['sources']): raise Refusal('HELD_ARCHIVE_DOCUMENT_COUNT')
        for d,s in zip(row['documents'],ic['sources']):
            if type(d) is not dict or set(d)!={'source_sha256','source_bytes','container_sha256','container_bytes','instance_constitution_sha256'} or d['source_sha256']!=s['sha256'] or type(d['source_bytes']) is not int or d['source_bytes']!=s['bytes']:
                raise Refusal('HELD_ARCHIVE_DOCUMENT_BINDING')
            if type(d['container_bytes']) is not int or not 1<=d['container_bytes']<=10*MAX_SOURCE+fold.MAX_BYTES+1048576 or not _is_root(d['container_sha256']) or not _is_root(d['instance_constitution_sha256']):
                raise Refusal('HELD_ARCHIVE_DOCUMENT_BINDING')
        cost=_cost(recipe,row['documents'],ic)
        if any(row[k]!=v or (k!='missing_roots' and type(row[k]) is not int) for k,v in cost.items()): raise Refusal('HELD_ARCHIVE_SCORE')
        passed.append(row)
    winner=min(passed,key=lambda r:(r['horizon_score_bytes'],r['recipe']['id']))
    if value['selected_id']!=winner['recipe']['id']: raise Refusal('HELD_ARCHIVE_NOT_MINIMUM')
    return value,winner

def encode_selected_archive(selection_path,output,*,sources,base,fronts,progress=None):
    target=Path(output); sources=list(sources); fronts=list(fronts)
    if target.exists(): raise Refusal('HELD_ARCHIVE_DESTINATION_EXISTS')
    protect_outputs([target],[selection_path,*sources,base,*fronts])
    selection,winner=load_selection(selection_path); ic=selection['instance_constitution']; recipe=winner['recipe']
    target.parent.mkdir(parents=True,exist_ok=True)
    with sio.TempDirectory(prefix='ar-',dir=target.parent) as name:
        work=Path(name); stage=work/'result'; stage.mkdir()
        with VerifiedLegendContext(max_legend_bytes=ic['max_legend_bytes'],progress=progress) as context:
            source_rows,snapshots=_sources(sources,work,ic['max_source_bytes'])
            if source_rows!=ic['sources']: raise Refusal('HELD_ARCHIVE_SOURCE_CHANGED')
            base_info,front_info,base_path,front_paths=_dependencies(base,fronts,work,ic['max_legend_bytes'],context)
            if base_info!=ic['base'] or front_info!=ic['fronts']: raise Refusal('HELD_ARCHIVE_DEPENDENCY_CHANGED')
            documents=[]
            for i,source in enumerate(snapshots):
                dest=stage/f'{i:06d}.crys'; realized=encode_file(source,dest,**_arguments(recipe,ic,base_path,front_paths,context))
                doc=_document(source,dest,realized)
                if doc!=winner['documents'][i]: raise Refusal('HELD_ARCHIVE_SELECTED_REALIZATION_DRIFT')
                documents.append({'file':dest.name,**doc})
                if progress: progress({'stage':'ARCHIVE_SELECTED_DOCUMENT','index':i})
            bound={base_info['sha256']:base_path,**front_paths}; dependencies=[]
            if winner['missing_roots']: (stage/'dependencies').mkdir()
            for root in winner['missing_roots']:
                path=stage/'dependencies'/(root+'.leg')
                if _bounded_snapshot(bound[root],path,ic['max_legend_bytes'])!=root: raise Refusal('HELD_ARCHIVE_DEPENDENCY_CHANGED')
                dependencies.append({'file':'dependencies/'+path.name,'sha256':root,'bytes':path.stat().st_size})
            if sum(r['bytes'] for r in dependencies)!=winner['new_dependency_bytes']: raise Refusal('HELD_ARCHIVE_SCORE')
            context.verify_used(); execution=context.receipt()
        result=rooted({'schema':'semcrys.archive-realization.v0.1','status':'PASS','standing':'CANDIDATE_ONLY',
            'selection_root':selection['selection_root'],'selected_id':recipe['id'],'effective_configuration':ic,
            'documents':documents,'dependencies':dependencies,'cost':_cost(recipe,winner['documents'],ic),
            'materialization':'ONE_DELIVERY_PLUS_MISSING_DEPENDENCIES; HORIZON_IS_EXPLICIT_IDENTICAL_WORKLOAD_COST_MODEL',
            'replay_scope':'EXACT_SELECTED_ARTIFACTS_NOT_REEXECUTION_OR_AUTHENTICATION_OF_ALTERNATIVE_LEDGER',
            'not_counted':EXCLUSIONS,'execution_context':execution,'receiver_state_changed':False,'security_claim':'NONE'},'realization_root')
        sio.write_bytes(stage/'LOCAL_REPLAY_RECEIPT.json',canonical(result))
        if target.exists(): raise Refusal('HELD_ARCHIVE_DESTINATION_EXISTS')
        sio.replace(stage,target)
    return result
