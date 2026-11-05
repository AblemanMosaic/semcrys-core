"""Rooted local legend libraries and measured, source-specific selection.

SPDX-License-Identifier: Apache-2.0
No family-name inference, receiver-state mutation, or security authorization.
"""
from streaming_legend import scratch_io as sio
import hashlib
import codecs
import os
import re
import tempfile
from pathlib import Path

from .artifacts import canonical_object
from streaming_app.core import Refusal, encode_file, _snapshot, _is_root, protect_outputs
from streaming_legend.assembly import ExecutionLegendReader as LegendReader
from streaming_legend.core import canonical, file_sha256
from streaming_app.legend_context import VerifiedLegendContext

MAX_MANIFEST = 1024 * 1024
MAX_MEMBERS = 16
MAX_SOURCE = 64 * 1024 * 1024
MAX_LEGENDS = 1024 * 1024 * 1024
FAMILIES = ('UNION', 'ULTRA', 'DOMAIN')
NAME = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}\Z')
SCHEMA = 'semcrys.legend-library.v0.1'
SELECTION = 'semcrys.measured-selection.v0.1'
OPERATIONS=['SNAPSHOT_AND_BIND','VALIDATE_SOURCE_UTF8','REALIZE_EACH_ADMISSIBLE_CANDIDATE','MEASURE_EXACT_BYTES','CHOOSE_MINIMUM_WITH_ID_TIEBREAK']

def _utf8(path):
    decoder=codecs.getincrementaldecoder('utf-8')('strict')
    try:
        with path.open('rb') as handle:
            for block in iter(lambda:handle.read(1024*1024),b''): decoder.decode(block)
        decoder.decode(b'',final=True); return True
    except UnicodeDecodeError: return False

def _bounded_snapshot(source,target,limit):
    total=0; digest=hashlib.sha256()
    with Path(source).open('rb') as incoming,sio.open_output(Path(target),'wb') as outgoing:
        for block in iter(lambda:incoming.read(1024*1024),b''):
            total+=len(block)
            if total>limit: raise Refusal('HELD_SELECTION_SNAPSHOT_BUDGET')
            outgoing.write(block); digest.update(block)
    return digest.hexdigest()

def rooted(value, key):
    return {**value, key: hashlib.sha256(canonical(value)).hexdigest()}

def _verify_root(value, key):
    if not _is_root(value.get(key)) or rooted({k:v for k,v in value.items() if k!=key}, key) != value:
        raise Refusal('HELD_LIBRARY_OR_SELECTION_ROOT')

def load_library(path):
    value = canonical_object(path, MAX_MANIFEST)
    if set(value) != {'schema','standing','unit_identity','members','library_root'} or value['schema'] != SCHEMA or value['standing'] != 'CANDIDATE_ONLY' or value['unit_identity'] != 'LOCAL_TRANSPORT_UNITS_NOT_GTK_SENSES':
        raise Refusal('HELD_LIBRARY_SCHEMA')
    _verify_root(value, 'library_root')
    rows = value['members']
    if type(rows) is not list or not 1 <= len(rows) <= MAX_MEMBERS:
        raise Refusal('HELD_LIBRARY_MEMBER_LIMIT')
    names = []
    for row in rows:
        if type(row) is not dict or set(row) != {'id','family','legend_sha256','legend_bytes','entry_count'}:
            raise Refusal('HELD_LIBRARY_MEMBER_FIELDS')
        if not isinstance(row['id'],str) or not NAME.fullmatch(row['id']) or row['family'] not in FAMILIES or not _is_root(row['legend_sha256']):
            raise Refusal('HELD_LIBRARY_MEMBER_VALUE')
        if type(row['legend_bytes']) is not int or not 1 <= row['legend_bytes'] <= MAX_LEGENDS or type(row['entry_count']) is not int or not 0 <= row['entry_count'] <= (1<<63)-1:
            raise Refusal('HELD_LIBRARY_MEMBER_VALUE')
        names.append(row['id'])
    if names != sorted(set(names)):
        raise Refusal('HELD_LIBRARY_MEMBER_ORDER_OR_DUPLICATE')
    return value

def build_library(output, members):
    """members: (stable local name, declared family, exact binary BASE .leg)."""
    if not 1 <= len(members) <= MAX_MEMBERS:
        raise Refusal('HELD_LIBRARY_MEMBER_LIMIT')
    protect_outputs([output],[path for _,_,path in members])
    rows=[]
    for name,family,path in members:
        reader=LegendReader(path); result=reader.verify()
        if reader.header['parent_sha256'] is not None:
            raise Refusal('HELD_LIBRARY_REQUIRES_BASE_LEGEND')
        rows.append({'id':name,'family':family,'legend_sha256':result['sha256'],
            'legend_bytes':Path(path).stat().st_size,'entry_count':result['entry_count']})
    value=rooted({'schema':SCHEMA,'standing':'CANDIDATE_ONLY','unit_identity':'LOCAL_TRANSPORT_UNITS_NOT_GTK_SENSES',
        'members':sorted(rows,key=lambda r:r['id'])},'library_root')
    # Validate using a disposable file before publishing any destination.
    with sio.TempDirectory(prefix='semcrys-library-validate-') as name:
        trial=Path(name)/'manifest'; sio.write_bytes(trial,canonical(value)); load_library(trial)
    sio.write_bytes(Path(output),canonical(value))
    return {'status':'PASS','standing':'CANDIDATE_ONLY','library_root':value['library_root'],
        'output_sha256':file_sha256(Path(output)),'members':len(rows),'families_are_user_labels_not_coverage_proof':True}

def _bind(library, paths, work, max_legend_bytes, context=None):
    if type(max_legend_bytes) is not int or not 1<=max_legend_bytes<=MAX_LEGENDS:
        raise Refusal('HELD_LIBRARY_LEGEND_BUDGET')
    if len(paths)>MAX_MEMBERS:
        raise Refusal('HELD_LIBRARY_MEMBER_LIMIT')
    required={r['legend_sha256']:r for r in library['members']}
    if sum(row['legend_bytes'] for row in required.values())>max_legend_bytes:
        raise Refusal('HELD_LIBRARY_LEGEND_BUDGET')
    provided={}; total=0
    for i,path in enumerate(paths):
        if Path(path).stat().st_size>max_legend_bytes-total: raise Refusal('HELD_LIBRARY_LEGEND_BUDGET')
        target=work/f'library-{i}.leg'; root=_bounded_snapshot(path,target,max_legend_bytes-total)
        total+=target.stat().st_size
        if root not in required or root in provided: raise Refusal('HELD_LIBRARY_UNUSED_OR_DUPLICATE_DEPENDENCY')
        reader=context.reader(target) if context is not None else LegendReader(target)
        checked={'entry_count':reader.count} if context is not None else reader.verify(); row=required[root]
        if target.stat().st_size!=row['legend_bytes'] or checked['entry_count']!=row['entry_count'] or reader.header['parent_sha256'] is not None:
            raise Refusal('HELD_LIBRARY_LEGEND_BINDING')
        provided[root]=target
    if set(provided)!=set(required): raise Refusal('HELD_LIBRARY_DEPENDENCY_MISSING')
    return provided

def _recipes(library):
    recipes=[{'id':'BASE:RAW','profile':'C:RAW_BYTES','member':None,'legend_roots':[]},
        {'id':'BASE:LOCAL','profile':'C:SELF_CONTAINED_TOKEN','member':None,'legend_roots':[]}]
    for row in library['members']:
        for suffix,profile in [('PRESHARED','T:PRESHARED_TOKEN'),('DELTA','A:LONGITUDINAL_TOKEN_DELTA')]:
            recipes.append({'id':row['id']+':'+suffix,'profile':profile,'member':row['id'],'legend_roots':[row['legend_sha256']]})
    return sorted(recipes,key=lambda r:r['id'])

def _options(accounting,receiver_roots,outer_codec,max_source_bytes,max_legend_bytes):
    if accounting not in ('WARM','COLD') or outer_codec not in ('NONE','LZMA'):
        raise Refusal('HELD_SELECTION_CONFIGURATION')
    if type(max_source_bytes) is not int or not 0<=max_source_bytes<=MAX_SOURCE:
        raise Refusal('HELD_SELECTION_SOURCE_BUDGET')
    if type(max_legend_bytes) is not int or not 1<=max_legend_bytes<=MAX_LEGENDS:
        raise Refusal('HELD_LIBRARY_LEGEND_BUDGET')
    if type(receiver_roots) not in (list,tuple): raise Refusal('HELD_RECEIVER_ROOT_SET')
    roots=list(receiver_roots)
    if any(not _is_root(r) for r in roots) or len(roots)!=len(set(roots)) or len(roots)>MAX_MEMBERS:
        raise Refusal('HELD_RECEIVER_ROOT_SET')
    return sorted(roots)

def select(source, output, *, library_path, legends, accounting='WARM', receiver_roots=(), outer_codec='NONE',
           max_source_bytes=MAX_SOURCE,max_legend_bytes=MAX_LEGENDS,progress=None):
    source,output=Path(source),Path(output)
    protect_outputs([output],[source,library_path,*legends])
    receiver=_options(accounting,receiver_roots,outer_codec,max_source_bytes,max_legend_bytes)
    library=load_library(library_path)
    if source.stat().st_size>max_source_bytes: raise Refusal('HELD_SELECTION_SOURCE_BUDGET')
    with sio.TempDirectory(prefix='semcrys-select-') as name, VerifiedLegendContext(max_legend_bytes=max_legend_bytes) as context:
        work=Path(name); frozen=work/'source'; source_root=_bounded_snapshot(source,frozen,max_source_bytes)
        if frozen.stat().st_size>max_source_bytes: raise Refusal('HELD_SELECTION_SOURCE_BUDGET')
        bound=_bind(library,legends,work,max_legend_bytes,context)
        if not set(receiver).issubset(bound): raise Refusal('HELD_RECEIVER_ROOT_OUTSIDE_LIBRARY')
        source_utf8=_utf8(frozen)
        instance=rooted({'schema':'semcrys.selection-instance.v0.1','standing':'CANDIDATE_ONLY',
            'library_root':library['library_root'],'source_sha256':source_root,'source_bytes':frozen.stat().st_size,'source_utf8':source_utf8,
            'accounting':accounting,'receiver_roots':receiver,'outer_codec':outer_codec,
            'projection':'PACKED','max_source_bytes':max_source_bytes,'max_legend_bytes':max_legend_bytes,
            'candidate_recipes':_recipes(library),'operation_sequence':OPERATIONS,
            'selection_scope':'THIS_EXACT_SOURCE_AND_LISTED_CANDIDATES_ONLY','security_claim':'NONE'},'instance_constitution_sha256')
        if progress: progress({'stage':'INSTANCE_COMPILED','effective_configuration':instance})
        rows=[]; sizes={r['legend_sha256']:r['legend_bytes'] for r in library['members']}
        for recipe in instance['candidate_recipes']:
            missing=sorted(set(recipe['legend_roots'])-set(receiver))
            if accounting=='WARM' and missing:
                rows.append({'recipe':recipe,'status':'UNAVAILABLE','code':'RECEIVER_ROOT_NOT_ACKNOWLEDGED','missing_roots':missing})
                continue
            if not source_utf8 and recipe['profile']!='C:RAW_BYTES':
                rows.append({'recipe':recipe,'status':'UNAVAILABLE','code':'SOURCE_NOT_UTF8'})
                continue
            if progress: progress({'stage':'CANDIDATE_STARTED','candidate':recipe['id']})
            target=work/'trial.crys'
            realized=encode_file(frozen,target,profile=recipe['profile'],external_legends=[bound[r] for r in recipe['legend_roots']],outer_codec=outer_codec,legend_context=context)
            acquisition=sum(sizes[r] for r in missing)
            wire=target.stat().st_size
            row={'recipe':recipe,'status':'PASS','container_bytes':wire,'new_dependency_bytes':acquisition,
                'score_bytes':wire+acquisition,'container_sha256':realized['output_sha256'],
                'effective_configuration':realized['effective_configuration'],'receipt':realized['receipt']}
            rows.append(row)
            sio.unlink(target) # disposable trial only; do not retain N whole containers
            if progress: progress({'stage':'CANDIDATE_FINISHED','candidate':recipe['id'],'container_bytes':wire,'new_dependency_bytes':acquisition})
        winner=min((r for r in rows if r['status']=='PASS'),key=lambda r:(r['score_bytes'],r['recipe']['id']))
        value=rooted({'schema':SELECTION,'standing':'CANDIDATE_ONLY','instance_constitution':instance,
            'rows':rows,'selected_id':winner['recipe']['id'],
            'not_counted_on_wire':['LOCAL_LIBRARY_MANIFEST','LOCAL_SELECTION_RECEIPT'],
            'acquisition_encoding':'EXACT_UNCOMPRESSED_BINARY_LEGEND_BYTES','future_reuse_prediction':False,
            'receiver_acknowledgement':'CALLER_DECLARATION_NOT_REMOTE_ATTESTATION'},'selection_root')
        data=canonical(value)
        if len(data)>MAX_MANIFEST: raise Refusal('HELD_SELECTION_RECORD_LIMIT')
        sio.write_bytes(output,data)
    return {'status':'PASS','standing':'CANDIDATE_ONLY','selection_root':value['selection_root'],
        'output_sha256':file_sha256(output),'selected_id':winner['recipe']['id'],'score_bytes':winner['score_bytes'],
        'effective_configuration':instance,'candidate_count':len(rows),'global_optimality':False}

def load_selection(path,library):
    value=canonical_object(path,MAX_MANIFEST); _verify_root(value,'selection_root')
    expected={'schema','standing','instance_constitution','rows','selected_id','not_counted_on_wire','acquisition_encoding','future_reuse_prediction','receiver_acknowledgement','selection_root'}
    if set(value)!=expected or value['schema']!=SELECTION or value['standing']!='CANDIDATE_ONLY' or value['future_reuse_prediction'] is not False:
        raise Refusal('HELD_SELECTION_SCHEMA')
    ic=value['instance_constitution']
    if type(ic) is not dict: raise Refusal('HELD_SELECTION_SCHEMA')
    _verify_root(ic,'instance_constitution_sha256')
    keys={'schema','standing','library_root','source_sha256','source_bytes','source_utf8','accounting','receiver_roots','outer_codec','projection','max_source_bytes','max_legend_bytes','candidate_recipes','operation_sequence','selection_scope','security_claim','instance_constitution_sha256'}
    if set(ic)!=keys or ic['schema']!='semcrys.selection-instance.v0.1' or ic['standing']!='CANDIDATE_ONLY' or ic['library_root']!=library['library_root'] or ic['projection']!='PACKED' or ic['security_claim']!='NONE' or not _is_root(ic['source_sha256']):
        raise Refusal('HELD_SELECTION_CONFIGURATION')
    _options(ic['accounting'],ic['receiver_roots'],ic['outer_codec'],ic['max_source_bytes'],ic['max_legend_bytes'])
    if type(ic['source_utf8']) is not bool: raise Refusal('HELD_SELECTION_CONFIGURATION')
    if ic['operation_sequence']!=OPERATIONS or ic['selection_scope']!='THIS_EXACT_SOURCE_AND_LISTED_CANDIDATES_ONLY':
        raise Refusal('HELD_SELECTION_OPERATION_SEQUENCE')
    if value['not_counted_on_wire']!=['LOCAL_LIBRARY_MANIFEST','LOCAL_SELECTION_RECEIPT'] or value['acquisition_encoding']!='EXACT_UNCOMPRESSED_BINARY_LEGEND_BYTES' or value['receiver_acknowledgement']!='CALLER_DECLARATION_NOT_REMOTE_ATTESTATION':
        raise Refusal('HELD_SELECTION_ACCOUNTING_CONTRACT')
    if type(ic['source_bytes']) is not int or not 0<=ic['source_bytes']<=ic['max_source_bytes']:
        raise Refusal('HELD_SELECTION_SOURCE_BUDGET')
    recipes=_recipes(library)
    if ic['candidate_recipes']!=recipes or type(value['rows']) is not list or len(value['rows'])!=len(recipes):
        raise Refusal('HELD_SELECTION_RECIPE_SEQUENCE')
    sizes={r['legend_sha256']:r['legend_bytes'] for r in library['members']}
    if not set(ic['receiver_roots']).issubset(sizes): raise Refusal('HELD_RECEIVER_ROOT_OUTSIDE_LIBRARY')
    passed=[]
    for recipe,row in zip(recipes,value['rows']):
        if type(row) is not dict or row.get('recipe')!=recipe: raise Refusal('HELD_SELECTION_RECIPE_SEQUENCE')
        missing=sorted(set(recipe['legend_roots'])-set(ic['receiver_roots']))
        if ic['accounting']=='WARM' and missing:
            if row!={'recipe':recipe,'status':'UNAVAILABLE','code':'RECEIVER_ROOT_NOT_ACKNOWLEDGED','missing_roots':missing}:
                raise Refusal('HELD_SELECTION_RECEIVER_STATE')
        elif not ic['source_utf8'] and recipe['profile']!='C:RAW_BYTES':
            if row!={'recipe':recipe,'status':'UNAVAILABLE','code':'SOURCE_NOT_UTF8'}: raise Refusal('HELD_SELECTION_INPUT_PRECONDITION')
        else:
            if set(row)!={'recipe','status','container_bytes','new_dependency_bytes','score_bytes','container_sha256','effective_configuration','receipt'} or row['status']!='PASS':
                raise Refusal('HELD_SELECTION_ROW')
            for field in ('container_bytes','new_dependency_bytes','score_bytes'):
                if type(row[field]) is not int or row[field]<0: raise Refusal('HELD_SELECTION_SCORE')
            if row['new_dependency_bytes']!=sum(sizes[r] for r in missing) or row['score_bytes']!=row['container_bytes']+row['new_dependency_bytes'] or not _is_root(row['container_sha256']):
                raise Refusal('HELD_SELECTION_SCORE')
            passed.append(row)
    winner=min(passed,key=lambda r:(r['score_bytes'],r['recipe']['id']))
    if value['selected_id']!=winner['recipe']['id']: raise Refusal('HELD_SELECTION_NOT_MINIMUM')
    return value,winner

def encode_selected(source,selection_path,output,*,library_path,legends):
    source,output=Path(source),Path(output)
    protect_outputs([output],[source,selection_path,library_path,*legends])
    library=load_library(library_path); selection,winner=load_selection(selection_path,library)
    ic=selection['instance_constitution']; recipe=winner['recipe']
    if output.suffix.lower()!='.crys': raise Refusal('HELD_CRYS_SUFFIX_REQUIRED')
    if source.stat().st_size>ic['max_source_bytes']: raise Refusal('HELD_SELECTION_SOURCE_BUDGET')
    output.parent.mkdir(parents=True,exist_ok=True)
    with sio.TempDirectory(prefix='semcrys-selected-',dir=output.parent) as name, VerifiedLegendContext(max_legend_bytes=ic['max_legend_bytes']) as context:
        work=Path(name); frozen=work/'source'; root=_bounded_snapshot(source,frozen,ic['max_source_bytes'])
        if root!=ic['source_sha256'] or frozen.stat().st_size!=ic['source_bytes']: raise Refusal('HELD_SELECTION_SOURCE_CHANGED')
        if _utf8(frozen)!=ic['source_utf8']: raise Refusal('HELD_SELECTION_INPUT_PRECONDITION')
        bound=_bind(library,legends,work,ic['max_legend_bytes'],context)
        target=work/'chosen.crys'
        realized=encode_file(frozen,target,profile=recipe['profile'],external_legends=[bound[r] for r in recipe['legend_roots']],outer_codec=ic['outer_codec'],legend_context=context)
        if realized['output_sha256']!=winner['container_sha256'] or target.stat().st_size!=winner['container_bytes'] or \
           canonical(realized['effective_configuration'])!=canonical(winner['effective_configuration']) or \
           canonical(realized['receipt'])!=canonical(winner['receipt']):
            raise Refusal('HELD_SELECTED_REALIZATION_DRIFT')
        sio.replace(target,output)
    return {**realized,'selection_root':selection['selection_root'],'selected_id':recipe['id'],
        'selection_replay':'CHOSEN_CANDIDATE_EXACT_NOT_REEXECUTION_OF_ALL_ALTERNATIVES',
        'accounting':{'mode':ic['accounting'],'container_bytes':winner['container_bytes'],'new_dependency_bytes':winner['new_dependency_bytes'],'score_bytes':winner['score_bytes']},
        'receiver_state_changed':False}
