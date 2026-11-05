"""Measured outer-codec selection for one exact source/configuration.

The selector compares complete .crys artifacts, verifies every inverse, and
records dependency accounting.  It makes no global or predictive optimum
claim.  SPDX-License-Identifier: Apache-2.0
"""
import hashlib
import platform
import sys
from pathlib import Path

from streaming_app.core import (
    Refusal, REQUESTABLE_OUTER_CODECS, EXTENDED_OUTER_CODECS, encode_file, decode_file,
    outer_codec_configuration, protect_outputs, _is_root, _snapshot,
)
from streaming_app.legend_context import VerifiedLegendContext
from streaming_legend import scratch_io as sio
from streaming_legend.core import canonical, file_sha256
from streaming_legend.assembly import ExecutionLegendReader as LegendReader

from .artifacts import canonical_object, inspect_artifact

SCHEMA = 'semcrys.codec-selection.v0.1'
INSTANCE = 'semcrys.codec-selection-instance.v0.1'
MAX_RECORD = 4 * 1024 * 1024
MAX_SOURCE = 64 * 1024 * 1024
MAX_LEGENDS = 1024 * 1024 * 1024
DEFAULT_CODECS = ('NONE','LZMA','LZMA2_XZ_0','LZMA2_XZ_6','LZMA2_XZ_9','BZ2_1','BZ2_9')
OPERATIONS = [
    'ROOT_SOURCE_AND_DEPENDENCIES', 'COMPILE_EXACT_CANDIDATES',
    'REALIZE_COMPLETE_CONTAINERS', 'VERIFY_EACH_EXACT_INVERSE',
    'MEASURE_CONTAINER_BODY_AND_DEPENDENCY_BYTES', 'SELECT_MINIMUM',
    'PUBLISH_ROOTED_SELECTION',
]


def measurement_codec_configuration(name):
    """Describe every measured cell, including frozen compatibility spellings."""
    if name == 'NONE':
        return {'schema':'semcrys.codec-measurement-configuration.v0.1','name':'NONE',
            'status':'EXECUTABLE','codec':'NONE','codec_version':'NONE','framing':'NONE',
            'level':None,'dictionary':{'mode':'NONE','sha256':None},
            'operation_sequence':['ENCODE_PHYSICAL_BODY']}
    if name == 'LZMA':
        return {'schema':'semcrys.codec-measurement-configuration.v0.1','name':'LZMA',
            'status':'EXECUTABLE_FROZEN_DEV73','codec':'LZMA2','codec_version':'XZ_STREAM_FORMAT_1_0',
            'framing':'XZ','level':6,'dictionary':{'mode':'NONE','sha256':None},
            'operation_sequence':['ENCODE_PHYSICAL_BODY','APPLY_OUTER_CODEC']}
    if name in ('ZSTD','ZSTD_DICT'):
        return {'schema':'semcrys.codec-measurement-configuration.v0.1','name':name,
            'status':'TYPED_UNAVAILABLE','code':'HELD_OPTIONAL_CODEC_ADAPTER_NOT_PACKAGED',
            'codec':'ZSTANDARD','dictionary':{'mode':'TRAINED' if name=='ZSTD_DICT' else 'NONE','sha256':None}}
    config=outer_codec_configuration(name)
    return {'schema':'semcrys.codec-measurement-configuration.v0.1','name':name,
        'status':'EXECUTABLE','realization_configuration':config}


def _implementation_identity():
    from . import __version__
    from .integrity import verify_self
    verified=verify_self()
    return {'application_version':__version__,'application_payload_root':verified['payload_root'],
        'python_implementation':platform.python_implementation(),'python_version':platform.python_version(),
        'platform_system':platform.system(),'platform_machine':platform.machine(),'byteorder':sys.byteorder,
        'lzma_adapter':'PYTHON_STDLIB_LZMA','bz2_adapter':'PYTHON_STDLIB_BZ2'}


def _rooted(value, field):
    return {**value, field: hashlib.sha256(canonical(value)).hexdigest()}


def _check_root(value, field):
    if type(value) is not dict or not _is_root(value.get(field)):
        raise Refusal('HELD_CODEC_SELECTION_ROOT')
    if _rooted({k:v for k,v in value.items() if k != field}, field) != value:
        raise Refusal('HELD_CODEC_SELECTION_ROOT')


def _options(codecs, accounting, receiver_roots, max_source_bytes, max_legend_bytes):
    if type(codecs) not in (list,tuple) or not codecs or len(codecs) > len(REQUESTABLE_OUTER_CODECS):
        raise Refusal('HELD_CODEC_CANDIDATE_SET')
    candidates=list(codecs)
    if len(set(candidates)) != len(candidates) or any(c not in REQUESTABLE_OUTER_CODECS for c in candidates):
        raise Refusal('HELD_CODEC_CANDIDATE_SET')
    if accounting not in ('COLD','WARM'):
        raise Refusal('HELD_CODEC_ACCOUNTING')
    roots=list(receiver_roots)
    if len(roots) != len(set(roots)) or any(not _is_root(r) for r in roots):
        raise Refusal('HELD_RECEIVER_ROOT_SET')
    if type(max_source_bytes) is not int or not 0 <= max_source_bytes <= MAX_SOURCE:
        raise Refusal('HELD_CODEC_SOURCE_BUDGET')
    if type(max_legend_bytes) is not int or not 0 <= max_legend_bytes <= MAX_LEGENDS:
        raise Refusal('HELD_CODEC_LEGEND_BUDGET')
    return candidates, sorted(roots)


def _legend_rows(paths, context):
    rows=context.rows(paths)
    if sum(Path(r['path']).stat().st_size for r in rows) > context.maximum:
        raise Refusal('HELD_CODEC_LEGEND_BUDGET')
    parent=None
    for row in rows:
        reader=LegendReader(row['path'])
        if reader.header['parent_sha256'] != parent:
            raise Refusal('HELD_LEGEND_PARENT_SEQUENCE')
        row['bytes']=Path(row['path']).stat().st_size
        parent=row['sha256']
    return rows


def select(source, output, *, profile, external_legends=(), legend_policy=None,
           codecs=DEFAULT_CODECS, accounting='COLD', receiver_roots=(),
           max_source_bytes=MAX_SOURCE, max_legend_bytes=MAX_LEGENDS, progress=None):
    source,output=Path(source),Path(output)
    protect_outputs([output],[source,*external_legends])
    output.parent.mkdir(parents=True,exist_ok=True)
    candidates,receiver=_options(codecs,accounting,receiver_roots,max_source_bytes,max_legend_bytes)
    if legend_policy is None:
        legend_policy='TOTAL' if profile=='A:LONGITUDINAL_TOKEN_DELTA' else 'PROFITABLE'
    if legend_policy not in ('TOTAL','PROFITABLE'):
        raise Refusal('HELD_LEGEND_POLICY')
    if source.stat().st_size > max_source_bytes: raise Refusal('HELD_CODEC_SOURCE_BUDGET')
    with sio.TempDirectory(prefix='codec-selection-',dir=output.parent) as name, \
         VerifiedLegendContext(max_legend_bytes=max_legend_bytes) as context:
        work=Path(name); frozen=work/'source'; source_root=_snapshot(source,frozen)
        if frozen.stat().st_size > max_source_bytes: raise Refusal('HELD_CODEC_SOURCE_BUDGET')
        legends=_legend_rows(external_legends,context); roots=[r['sha256'] for r in legends]
        if not set(receiver).issubset(roots): raise Refusal('HELD_RECEIVER_ROOT_OUTSIDE_DEPENDENCIES')
        missing=sorted(set(roots)-set(receiver))
        if accounting=='WARM' and missing: raise Refusal('HELD_CODEC_RECEIVER_ROOT_MISSING',','.join(missing))
        dependency_bytes=sum(r['bytes'] for r in legends if r['sha256'] in missing) if accounting=='COLD' else 0
        codec_configurations=[measurement_codec_configuration(c) for c in candidates]
        instance=_rooted({'schema':INSTANCE,'standing':'CANDIDATE_ONLY',
            'source_sha256':source_root,'source_bytes':frozen.stat().st_size,
            'profile':profile,'legend_roots':roots,'legend_policy':legend_policy,
            'codecs':candidates,'codec_configurations':codec_configurations,
            'implementation_identity':_implementation_identity(),
            'accounting':accounting,'receiver_roots':receiver,
            'dependency_bytes':dependency_bytes,'max_source_bytes':max_source_bytes,
            'max_legend_bytes':max_legend_bytes,'projection':'PACKED',
            'objective':'MIN_EXACT_COMPLETE_CONTAINER_PLUS_MISSING_DEPENDENCIES',
            'tie_break':'CALLER_CANDIDATE_ORDER','operation_sequence':OPERATIONS,
            'security_claim':'NONE','global_optimality':False},'instance_constitution_sha256')
        if progress: progress({'stage':'CODEC_SELECTION_INSTANCE_COMPILED','effective_configuration':instance})
        rows=[]
        for order,(codec,codec_configuration) in enumerate(zip(candidates,codec_configurations)):
            try:
                outer_codec_configuration(codec)
            except Refusal as exc:
                if exc.code!='HELD_OPTIONAL_CODEC_ADAPTER_NOT_PACKAGED': raise
                rows.append({'codec':codec,'codec_configuration':codec_configuration,
                    'order':order,'status':'UNAVAILABLE','code':exc.code})
                continue
            if progress: progress({'stage':'CODEC_CANDIDATE_STARTED','codec':codec})
            target=work/(f'{order:02d}.crys'); inverse=work/(f'{order:02d}.decoded')
            realized=encode_file(frozen,target,profile=profile,
                external_legends=[r['path'] for r in legends],outer_codec=codec,
                legend_policy=legend_policy,legend_context=context)
            decoded=decode_file(target,inverse,external_legends=[r['path'] for r in legends],legend_context=context)
            if decoded['output_sha256']!=source_root or file_sha256(inverse)!=source_root:
                raise Refusal('HELD_CODEC_INVERSE_MISMATCH',codec)
            accounting_row=inspect_artifact(target)['byte_accounting']
            row={'codec':codec,'codec_configuration':codec_configuration,
                'order':order,'status':'PASS','container_bytes':target.stat().st_size,
                'dependency_bytes':dependency_bytes,'score_bytes':target.stat().st_size+dependency_bytes,
                'container_sha256':realized['output_sha256'],'decoded_sha256':decoded['output_sha256'],
                'body_payload_bytes':accounting_row['body_payload_bytes'],
                'effective_configuration':realized['effective_configuration'],'receipt':realized['receipt']}
            rows.append(row)
            if progress: progress({'stage':'CODEC_CANDIDATE_FINISHED','codec':codec,
                'container_bytes':row['container_bytes'],'body_payload_bytes':row['body_payload_bytes']})
        passed=[r for r in rows if r['status']=='PASS']
        if not passed: raise Refusal('HELD_NO_CODEC_CANDIDATE_AVAILABLE')
        winner=min(passed,key=lambda r:(r['score_bytes'],r['order']))
        value=_rooted({'schema':SCHEMA,'standing':'CANDIDATE_ONLY','instance_constitution':instance,
            'rows':rows,'selected_codec':winner['codec'],'selected_container_sha256':winner['container_sha256'],
            'selected_container_bytes':winner['container_bytes'],'selection_scope':'ONE_EXACT_SOURCE_AND_CONFIGURATION',
            'future_prediction':False,'security_claim':'NONE'},'selection_root')
        data=canonical(value)
        if len(data)>MAX_RECORD: raise Refusal('HELD_CODEC_SELECTION_RECORD_LIMIT')
        sio.write_bytes(output,data)
    return {'schema':'semcrys.codec-selection-result.v0.1','status':'PASS','standing':'CANDIDATE_ONLY',
        'selection_root':value['selection_root'],'output_sha256':file_sha256(output),
        'selected_codec':winner['codec'],'selected_container_bytes':winner['container_bytes'],
        'candidate_count':len(rows),'available_candidate_count':len(passed),
        'effective_configuration':instance,'global_optimality':False}


def load(path):
    value=canonical_object(path,MAX_RECORD); _check_root(value,'selection_root')
    expected={'schema','standing','instance_constitution','rows','selected_codec','selected_container_sha256',
        'selected_container_bytes','selection_scope','future_prediction','security_claim','selection_root'}
    if set(value)!=expected or value['schema']!=SCHEMA or value['standing']!='CANDIDATE_ONLY' or \
       value['selection_scope']!='ONE_EXACT_SOURCE_AND_CONFIGURATION' or value['future_prediction'] is not False or \
       value['security_claim']!='NONE': raise Refusal('HELD_CODEC_SELECTION_SCHEMA')
    ic=value['instance_constitution']; _check_root(ic,'instance_constitution_sha256')
    candidates,receiver=_options(ic.get('codecs'),ic.get('accounting'),ic.get('receiver_roots'),
        ic.get('max_source_bytes'),ic.get('max_legend_bytes'))
    if ic.get('schema')!=INSTANCE or ic.get('standing')!='CANDIDATE_ONLY' or ic.get('operation_sequence')!=OPERATIONS or \
       ic.get('projection')!='PACKED' or ic.get('objective')!='MIN_EXACT_COMPLETE_CONTAINER_PLUS_MISSING_DEPENDENCIES' or \
       ic.get('tie_break')!='CALLER_CANDIDATE_ORDER' or ic.get('security_claim')!='NONE' or ic.get('global_optimality') is not False or \
       not _is_root(ic.get('source_sha256')) or type(ic.get('source_bytes')) is not int or not 0<=ic['source_bytes']<=ic['max_source_bytes'] or \
       type(ic.get('legend_roots')) is not list or len(ic['legend_roots'])!=len(set(ic['legend_roots'])) or any(not _is_root(r) for r in ic['legend_roots']) or \
       type(ic.get('dependency_bytes')) is not int or ic['dependency_bytes']<0:
        raise Refusal('HELD_CODEC_SELECTION_CONFIGURATION')
    expected_configurations=[measurement_codec_configuration(c) for c in candidates]
    implementation=ic.get('implementation_identity')
    if type(implementation) is not dict or set(implementation)!={'application_version','application_payload_root','python_implementation','python_version','platform_system','platform_machine','byteorder','lzma_adapter','bz2_adapter'} or \
       not _is_root(implementation.get('application_payload_root')) or implementation.get('byteorder') not in ('little','big'):
        raise Refusal('HELD_CODEC_SELECTION_IMPLEMENTATION')
    if ic.get('codec_configurations')!=expected_configurations or receiver!=ic['receiver_roots'] or candidates!=ic['codecs'] or type(value['rows']) is not list or len(value['rows'])!=len(candidates):
        raise Refusal('HELD_CODEC_SELECTION_SEQUENCE')
    passed=[]
    for order,(codec,codec_configuration,row) in enumerate(zip(candidates,expected_configurations,value['rows'])):
        if type(row) is not dict or row.get('codec')!=codec or row.get('codec_configuration')!=codec_configuration or row.get('order')!=order: raise Refusal('HELD_CODEC_SELECTION_SEQUENCE')
        if row.get('status')=='UNAVAILABLE':
            if row!={'codec':codec,'codec_configuration':codec_configuration,'order':order,
                    'status':'UNAVAILABLE','code':'HELD_OPTIONAL_CODEC_ADAPTER_NOT_PACKAGED'} or codec not in ('ZSTD','ZSTD_DICT'):
                raise Refusal('HELD_CODEC_SELECTION_ROW')
            continue
        required={'codec','codec_configuration','order','status','container_bytes','dependency_bytes','score_bytes','container_sha256','decoded_sha256','body_payload_bytes','effective_configuration','receipt'}
        if set(row)!=required or row['status']!='PASS' or not _is_root(row['container_sha256']) or row['decoded_sha256']!=ic['source_sha256']:
            raise Refusal('HELD_CODEC_SELECTION_ROW')
        for field in ('container_bytes','dependency_bytes','score_bytes','body_payload_bytes'):
            if type(row[field]) is not int or row[field]<0: raise Refusal('HELD_CODEC_SELECTION_ROW')
        if row['dependency_bytes']!=ic['dependency_bytes'] or row['score_bytes']!=row['container_bytes']+row['dependency_bytes']:
            raise Refusal('HELD_CODEC_SELECTION_SCORE')
        effective=row['effective_configuration']
        if type(effective) is not dict or effective.get('outer_codec')!=codec or \
           effective.get('source_sha256')!=ic['source_sha256'] or \
           effective.get('profile')!=ic['profile'] or \
           effective.get('external_legend_roots')!=ic['legend_roots'] or \
           effective.get('legend_policy')!=ic['legend_policy']:
            raise Refusal('HELD_CODEC_SELECTION_CONFIGURATION')
        if codec in EXTENDED_OUTER_CODECS:
            if effective.get('outer_codec_configuration')!=outer_codec_configuration(codec):
                raise Refusal('HELD_CODEC_SELECTION_CONFIGURATION')
        elif effective.get('schema')!='semcrys.instance-constitution.v0.2':
            raise Refusal('HELD_CODEC_SELECTION_CONFIGURATION')
        passed.append(row)
    if not passed:
        raise Refusal('HELD_NO_CODEC_CANDIDATE_AVAILABLE')
    winner=min(passed,key=lambda r:(r['score_bytes'],r['order']))
    if (value['selected_codec'],value['selected_container_sha256'],value['selected_container_bytes']) != \
       (winner['codec'],winner['container_sha256'],winner['container_bytes']): raise Refusal('HELD_CODEC_SELECTION_NOT_MINIMUM')
    return value,winner


def encode_selected(source, selection_path, output, *, external_legends=(), progress=None):
    source,selection_path,output=Path(source),Path(selection_path),Path(output)
    protect_outputs([output],[source,selection_path,*external_legends])
    output.parent.mkdir(parents=True,exist_ok=True)
    selection,winner=load(selection_path); ic=selection['instance_constitution']
    if ic['implementation_identity']!=_implementation_identity():
        raise Refusal('HELD_CODEC_SELECTION_IMPLEMENTATION_CHANGED')
    if source.stat().st_size>ic['max_source_bytes']: raise Refusal('HELD_CODEC_SOURCE_BUDGET')
    with sio.TempDirectory(prefix='codec-replay-',dir=output.parent) as name, \
         VerifiedLegendContext(max_legend_bytes=ic['max_legend_bytes']) as context:
        work=Path(name); frozen=work/'source'; source_root=_snapshot(source,frozen)
        if source_root!=ic['source_sha256'] or frozen.stat().st_size!=ic['source_bytes']:
            raise Refusal('HELD_CODEC_SELECTION_SOURCE_CHANGED')
        legends=_legend_rows(external_legends,context)
        if [r['sha256'] for r in legends]!=ic['legend_roots']:
            raise Refusal('HELD_CODEC_SELECTION_DEPENDENCIES_CHANGED')
        target=work/'selected.crys'
        realized=encode_file(frozen,target,profile=ic['profile'],external_legends=[r['path'] for r in legends],
            outer_codec=winner['codec'],legend_policy=ic['legend_policy'],legend_context=context)
        if target.stat().st_size!=winner['container_bytes'] or realized['output_sha256']!=winner['container_sha256'] or \
           canonical(realized['effective_configuration'])!=canonical(winner['effective_configuration']) or \
           canonical(realized['receipt'])!=canonical(winner['receipt']):
            raise Refusal('HELD_CODEC_SELECTED_REALIZATION_DRIFT')
        inverse=work/'decoded'; decoded=decode_file(target,inverse,external_legends=[r['path'] for r in legends],legend_context=context)
        if decoded['output_sha256']!=source_root: raise Refusal('HELD_CODEC_INVERSE_MISMATCH')
        sio.replace(target,output)
    return {**realized,'selection_root':selection['selection_root'],'selected_codec':winner['codec'],
        'selection_replay':'EXACT_SELECTED_CANDIDATE_ONLY','global_optimality':False,
        'accounting':{'mode':ic['accounting'],'container_bytes':winner['container_bytes'],
            'dependency_bytes':winner['dependency_bytes'],'score_bytes':winner['score_bytes']}}
