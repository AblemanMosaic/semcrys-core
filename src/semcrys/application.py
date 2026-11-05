"""Public bounded encode/decode realization, composed with publication by CLI.

Scratch means temporary logical file bytes plus reserved native DB capacity.
This is not a process-memory limit or a sandbox for arbitrary Python code.
SPDX-License-Identifier: Apache-2.0
"""
import json, tempfile
from importlib.resources import files
from pathlib import Path
from streaming_app.core import encode_file, decode_file, protect_outputs
from streaming_legend import scratch_io as sio
from streaming_legend.scratch_budget import ScratchError
from .publication_resources import root
from .artifacts import build_legend,migrate_json_legend,extract_legend,export_glyphs,build_glyph_artifact
from .ordered_import import import_ordered
from . import composite_operations as composites

def _build_library(source,output,*,members):
    if source is not None:raise ScratchError('HELD_LIBRARY_BUILD_SOURCE')
    from .library import build_library
    return {**build_library(output,members),'schema':'semcrys.legend-library-build-result.v0.1'}

def _build_stack_library(source,output,*,stack_members):
    if source is not None:raise ScratchError('HELD_STACK_LIBRARY_BUILD_SOURCE')
    from .configuration_selection import build_library
    return build_library(output,stack_members)

OPERATIONS={
 'ENCODE':('semcrys.streaming-encode-result.v0.1',encode_file),
 'DECODE':('semcrys.streaming-decode-result.v0.1',decode_file),
 'LEGEND_BUILD':('semcrys.legend-build.v0.1',build_legend),
 'LEGEND_MIGRATE_V01':('semcrys.legend-migration.v0.1',migrate_json_legend),
 'LEGEND_IMPORT_ORDERED_V01':('semcrys.ordered-import-result.v0.1',import_ordered),
 'LEGEND_EXTRACT':('semcrys.legend-extraction.v0.1',extract_legend),
 'GLYPH_BUILD':('semcrys.glyph-build.v0.1',build_glyph_artifact),
 'GLYPH_EXPORT':('semcrys.glyph-export.v0.1',export_glyphs),
 'LIBRARY_BUILD':('semcrys.legend-library-build-result.v0.1',_build_library),
 'STACK_LIBRARY_BUILD':('semcrys.legend-stack-library-build-result.v0.1',_build_stack_library)}
OPERATIONS.update(composites.OPERATIONS)
SCOPE='PRIMARY_APPLICATION_REALIZATION_AND_ENROLLED_NESTED_IO'
ARTIFACT_SCOPE='LEGEND_WORKFLOW_REALIZATION_AND_ENROLLED_NESTED_IO'
def scope_for(operation):
    if operation in composites.OPERATIONS:return composites.SCOPE
    return SCOPE if operation in ('ENCODE','DECODE') else ARTIFACT_SCOPE

def compile_instance(operation,limit,progress=None):
    sio.validate_limit(limit)
    if operation not in OPERATIONS:raise ScratchError('HELD_APPLICATION_RESOURCE_OPERATION')
    scope=scope_for(operation)
    model_file='APPLICATION_RESOURCE_CONTRACT.json' if scope==SCOPE else 'LEGEND_RESOURCE_CONTRACT.json'
    if scope==composites.SCOPE:model_file='COMPOSITE_RESOURCE_CONTRACT.json'
    model=json.loads(files('semcrys').joinpath(model_file).read_text(encoding='utf-8'))
    if operation not in model['operations'] or model['scope']!=scope:
        raise ScratchError('HELD_APPLICATION_RESOURCE_CONTRACT')
    value={'schema':'semcrys.application-resource-instance.v0.1','standing':'CANDIDATE_ONLY',
      'model':model,'model_root':root(model),
      'operation':operation,'policy':{**sio.POLICY,'limit_bytes':limit,
        'scope':scope,'native_database_default_capacity_bytes':sio.DB_CAP,
        'scope_begins_before_legend_context':True,'external_context_reuse':False,
        'source_and_legend_inputs_counted':False,'temporary_copies_counted':True,
        'other_commands_enrolled':False,'whole_application_limit':False},
      'operation_sequence':['COMPILE_RESOURCE_INSTANCE','OPEN_PRIVATE_SCOPE',
        'RUN_GUARDED_REALIZATION_WITH_NESTED_IO','CLOSE_LEGEND_CONTEXT',
        'VERIFY_NO_OPEN_WRITERS_OR_DATABASES','RECORD_PEAK','MOVE_EXACT_STAGED_OUTPUT','CLOSE_SCOPE'],
      'transported_configuration_changed':False,'security_claim':'NONE','authority_effect':'NONE'}
    value['instance_constitution_sha256']=root(value)
    if progress:progress(json.loads(json.dumps({'stage':'APPLICATION_RESOURCE_INSTANCE_COMPILED','effective_configuration':value})))
    return value

def run(operation,source,output,*,max_scratch_bytes=sio.DEFAULT_LIMIT,progress=None,**options):
    instance=compile_instance(operation,max_scratch_bytes,progress)
    # A cached context or nested root would move owned bytes outside this scope.
    # Composite internal operations use streaming_app's explicit low-level API.
    if sio.ACTIVE.get() is not None:raise ScratchError('HELD_SCRATCH_NESTED_ROOT')
    if 'legend_context' in options:raise ScratchError('HELD_APPLICATION_EXTERNAL_CONTEXT')
    repeated=('external_legends','legends','source_parents','target_parents','additional_sources','sources','fronts')
    for key in repeated:
        if key in options:options[key]=tuple(options[key])
    if 'members' in options:options['members']=tuple(options['members'])
    if 'stack_members' in options:options['stack_members']=tuple(options['stack_members'])
    target=Path(output)
    inputs=([source] if source is not None else [])
    for key in repeated:inputs.extend(options.get(key,()))
    inputs.extend(row[2] for row in options.get('members',()))
    inputs.extend(row[3] for row in options.get('stack_members',()))
    inputs.extend(options[k] for k in ('glyph_registry','fold_front','rules','provenance','base','library_path','selection_path','legacy_legend','legacy_glyph') if options.get(k) is not None)
    protect_outputs([target],inputs)
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ap-',dir=target.parent) as name, \
         sio.Scope(name,max_scratch_bytes,publication=target,operation_scope=scope_for(operation)) as budget:
        staged=budget.root/('result'+target.suffix)
        if operation=='LEGEND_IMPORT_ORDERED_V01' or operation in composites.PROGRESS_OPERATIONS:options['progress']=progress
        result=OPERATIONS[operation][1](source,staged,**options)
        if result.get('status')!='PASS' or result.get('schema')!=OPERATIONS[operation][0]:
            raise ScratchError('HELD_APPLICATION_REALIZATION_RESULT')
        if budget.connections or budget.fds or any(r['active'] for r in budget._files.values()):
            raise ScratchError('HELD_APPLICATION_OPEN_RESOURCE')
        result={**result,'scratch_instance':instance,'scratch_budget':budget.outcome()}
        result['scratch_budget']['captured_at']='BEFORE_PUBLICATION_NOT_TRANSACTION_RECEIPT_OR_BACKUPS'
        result['receipt_sha256']=root(result)
        sio.replace(staged,target)
    if progress:progress(json.loads(json.dumps({'stage':'APPLICATION_REALIZATION_COMPLETE',
        'operation':operation,'scratch_budget':result['scratch_budget']})))
    return result

def encode(source,output,**options):return run('ENCODE',source,output,**options)
def decode(source,output,**options):return run('DECODE',source,output,**options)
