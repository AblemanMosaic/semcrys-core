"""Bounded directory realizations. No replacement, security or crash guarantee.
SPDX-License-Identifier: Apache-2.0
"""
import json,os,stat,tempfile,shutil
from pathlib import Path
from importlib.resources import files
from streaming_legend import scratch_io as sio
from streaming_legend.scratch_budget import ScratchError
from streaming_legend.core import canonical,file_sha256
from streaming_app.core import protect_outputs
from .publication_resources import root
from .fold_provenance import compact_front
from .batch import encode_batch
from .archive import encode_selected_archive
from . import directory_recovery as recovery
from . import publication_lock as locks

SCOPE='DIRECTORY_REALIZATION_LOCAL_RECEIPTS_AND_PUBLICATION'
RECEIPT='LOCAL_RESOURCE_RECEIPT.json'
def _compact(source,output,**options):
    return {**compact_front(source,output,**options),'schema':'semcrys.fold-compact-result.v0.1'}
def _batch(source,output,**options):
    if source is not None:raise ScratchError('HELD_BATCH_SOURCE_POSITION')
    return encode_batch(output,**options)
def _meta_pack(source,output,**options):
    if source is not None:raise ScratchError('HELD_META_PACK_SOURCE_POSITION')
    from .group_legend import _pack
    return _pack(output,max_scratch_bytes=sio.ACTIVE.get().limit,**options)
def _meta_unpack(source,output,**options):
    from .group_legend import _unpack
    return _unpack(source,output,max_scratch_bytes=sio.ACTIVE.get().limit,**options)
OPERATIONS={'FOLD_COMPACT':('semcrys.fold-compact-result.v0.1',_compact),
 'BATCH_ENCODE':('semcrys.batch-result.v0.1',_batch),
 'ARCHIVE_ENCODE_SELECTED':('semcrys.archive-realization.v0.1',encode_selected_archive),
 'PACK':('semcrys.metalegend-pack-result.v0.1',_meta_pack),
 'UNPACK':('semcrys.metalegend-unpack-result.v0.1',_meta_unpack)}

def compile_instance(operation,limit,progress=None):
    sio.validate_limit(limit)
    if operation not in OPERATIONS:raise ScratchError('HELD_DIRECTORY_OPERATION')
    model=json.loads(files('semcrys').joinpath('DIRECTORY_RESOURCE_CONTRACT.json').read_text(encoding='utf-8'))
    if operation not in model['operations'] or model['scope']!=SCOPE or model['local_resource_receipt']!=RECEIPT:
        raise ScratchError('HELD_DIRECTORY_RESOURCE_CONTRACT')
    if model.get('recovery_journal_capacity_bytes')!=recovery.CAP or model.get('recovery_journal')!=recovery.NAME:
        raise ScratchError('HELD_DIRECTORY_RESOURCE_CONTRACT')
    if model.get('recovery_max_files')!=recovery.MAX_FILES or model.get('recovery_max_directories')!=recovery.MAX_FILES:
        raise ScratchError('HELD_DIRECTORY_RESOURCE_CONTRACT')
    ic={'schema':'semcrys.directory-resource-instance.v0.1','standing':'CANDIDATE_ONLY',
      'operation':operation,'model':model,'model_root':root(model),'publication_concurrency':locks.contract(),
      'policy':{**sio.POLICY,'scope':SCOPE,'limit_bytes':limit,'native_database_default_capacity_bytes':sio.DB_CAP},
      'operation_sequence':['COMPILE_RESOURCE_INSTANCE','PROTECT_ALL_INPUTS','ACQUIRE_PARENT_PROCESS_LOCKS','REQUIRE_ABSENT_TARGET','OPEN_PRIVATE_SCOPE','RESERVE_RECOVERY_JOURNAL_CAPACITY',
        'REALIZE_WITH_NESTED_IO','CLOSE_NESTED_RESOURCES','VERIFY_OWNED_DIRECTORY','WRITE_SELF_COUNTED_RESOURCE_RECEIPT',
        'FSYNC_FILES','PREPARE_RESERVED_RECOVERY_JOURNAL','REVERIFY_DIRECTORY','REQUIRE_ABSENT_TARGET','ATOMIC_RENAME_NOREPLACE_DIRECTORY','CLOSE_SCOPE','RELEASE_PROCESS_LOCKS'],
      'authority_effect':'NONE','security_claim':'NONE'}
    ic['instance_constitution_sha256']=root(ic)
    if progress:progress(json.loads(json.dumps({'stage':'DIRECTORY_RESOURCE_INSTANCE_COMPILED','effective_configuration':ic})))
    return ic

def absent(target):
    if os.path.lexists(target):raise ScratchError('HELD_DIRECTORY_DESTINATION_EXISTS')

def inventory(stage,budget):
    """No symlinks/reparse points, untracked files, open native work or size drift."""
    budget._ready();budget.check_closed(stage)
    if budget.connections or budget.fds or budget.databases:raise ScratchError('HELD_DIRECTORY_OPEN_RESOURCE')
    if budget._native!={recovery.LABEL:recovery.CAP}:raise ScratchError('HELD_DIRECTORY_NATIVE_RESERVATION')
    def reparse(info):return bool(getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0))
    if not stage.is_dir() or stage.is_symlink() or reparse(stage.lstat()):raise ScratchError('HELD_DIRECTORY_STAGE')
    rows=[];seen=set()
    for p in sorted(stage.rglob('*')):
        info=p.lstat()
        if p.is_symlink() or reparse(info):raise ScratchError('HELD_DIRECTORY_NONREGULAR_ENTRY')
        if stat.S_ISDIR(info.st_mode):continue
        if not stat.S_ISREG(info.st_mode):raise ScratchError('HELD_DIRECTORY_NONREGULAR_ENTRY')
        entry=budget._files.get(p)
        if entry is None:raise ScratchError('HELD_DIRECTORY_UNOWNED_FILE')
        if entry['active'] or entry['bytes']!=info.st_size:raise ScratchError('HELD_DIRECTORY_FILE_CHANGED')
        rows.append({'path':p.relative_to(stage).as_posix(),'bytes':info.st_size,'sha256':file_sha256(p)})
        seen.add(p)
    if seen!=set(budget._files):raise ScratchError('HELD_DIRECTORY_EXTRA_SCRATCH_FILES')
    return rows

def _resource_receipt(stage,budget,ic,result,rows):
    path=stage/RECEIPT
    if path.exists():raise ScratchError('HELD_DIRECTORY_RECEIPT_COLLISION')
    before=budget.outcome();n=0
    for _ in range(16):
        counted={**before,'reserved_bytes':before['reserved_bytes']+n,
          'tracked_file_bytes':before['tracked_file_bytes']+n,
          'peak_reserved_bytes':max(before['peak_reserved_bytes'],before['reserved_bytes']+n)}
        value={'schema':'semcrys.directory-resource-receipt.v0.1','standing':'CANDIDATE_ONLY',
          'scratch_instance':ic,'scratch_budget':counted,'realization_result_root':root(result),
          'files_before_resource_receipt':rows,'files_root':root(rows),'resource_receipt_bytes':n,
          'publication_status':'PREPARED_NOT_COMMIT_ATTESTATION','security_claim':'NONE'}
        value['resource_receipt_root']=root(value);data=canonical(value)+b'\n'
        if len(data)==n:break
        n=len(data)
    else:raise ScratchError('HELD_DIRECTORY_RECEIPT_SIZE')
    if n>ic['model']['max_resource_receipt_bytes']:raise ScratchError('HELD_DIRECTORY_RECEIPT_LIMIT')
    sio.write_bytes(path,data)
    if budget.outcome()!=counted:raise ScratchError('HELD_DIRECTORY_RECEIPT_ACCOUNTING')
    return value

def run(operation,source,output,*,max_scratch_bytes=sio.DEFAULT_LIMIT,progress=None,**options):
    ic=compile_instance(operation,max_scratch_bytes,progress)
    if sio.ACTIVE.get() is not None:raise ScratchError('HELD_SCRATCH_NESTED_ROOT')
    if 'legend_context' in options:raise ScratchError('HELD_DIRECTORY_EXTERNAL_CONTEXT')
    inputs=[source] if source is not None else []
    for key in ('sources','external_legends','fronts','legends','glyphs','fold_fronts'):
        if key in options:options[key]=tuple(options[key]);inputs.extend(options[key])
    inputs.extend(options[k] for k in ('base','glyph_registry','fold_front','shared_pool','meta') if options.get(k) is not None)
    requested=Path(output).absolute();protect_outputs([requested],inputs);absent(requested)
    # Caller spelling may be a Windows short path. Freeze its resolved target;
    # never put a short-path alias into the recovery journal itself.
    target=requested.resolve(strict=False)
    with locks.destinations([target],inputs):
        return _run_locked(operation,source,target,max_scratch_bytes,progress,options,ic)

def _run_locked(operation,source,target,max_scratch_bytes,progress,options,ic):
    absent(target)
    target.parent.mkdir(parents=True,exist_ok=True)
    private=Path(tempfile.mkdtemp(prefix='dr-',dir=target.parent)).resolve();preserve=False
    try:
        with sio.Scope(private,max_scratch_bytes,publication=target,operation_scope=SCOPE) as budget:
            budget.reserve_native(recovery.LABEL,recovery.CAP)
            staged=budget.root/'result'
            if operation!='FOLD_COMPACT':options['progress']=progress
            result=OPERATIONS[operation][1](source,staged,**options)
            if result.get('status')!='PASS' or result.get('schema')!=OPERATIONS[operation][0]:
                raise ScratchError('HELD_DIRECTORY_REALIZATION_RESULT')
            rows=inventory(staged,budget);receipt=_resource_receipt(staged,budget,ic,result,rows)
            expected=inventory(staged,budget)
            for row in expected:
                with (staged/row['path']).open('r+b') as handle:os.fsync(handle.fileno())
            journal=recovery.prepare(private/recovery.NAME,target,staged,budget)
            preserve=True
            if progress:progress(json.loads(json.dumps({'stage':'DIRECTORY_PREPARED','resource_receipt':receipt,**journal})))
            if inventory(staged,budget)!=expected:raise ScratchError('HELD_DIRECTORY_CONTENT_CHANGED')
            absent(target)
            # Validate the journal and complete manifest again after observers.
            if recovery.inspect(journal['journal'],journal['journal_root'])['state']!='PREPARED':
                raise ScratchError('HELD_DIRECTORY_RECOVERY_STATE')
            absent(target);sio.replace(staged,target,directory_rename=locks.move_new)
            answer={**result,'scratch_instance':ic,'scratch_budget':receipt['scratch_budget'],
              'directory_resources':{'file':RECEIPT,'sha256':file_sha256(target/RECEIPT),
                'resource_receipt_root':receipt['resource_receipt_root'],'bytes':receipt['resource_receipt_bytes'],
                'scope':SCOPE,'payload_files_changed':False,'new_local_audit_file':True},
              'directory_recovery':{**journal,'journal_retained_on_success':False,
                'payloads_retained_on_prepared_exception':True,'automatic_rollback':False},
              'directory_publication':'NEW_DIRECTORY_RENAME_NOT_POWER_FAILURE_OR_CONCURRENT_WRITER_GUARANTEE'}
            if 'receipt_sha256' in result:
                # The legacy on-disk receipt covers the internal realization.
                # The public return additionally covers final resources/recovery.
                answer['realization_receipt_sha256']=result['receipt_sha256']
                answer.pop('receipt_sha256');answer['receipt_sha256']=root(answer)
            if progress:progress(json.loads(json.dumps({'stage':'DIRECTORY_PUBLISHED','directory_resources':answer['directory_resources'],**journal})))
            preserve=False
        return answer
    finally:
        if not preserve:
            # Only the resolved, uniquely allocated private directory above.
            # Prepared exceptions retain their journal and payload for inspection.
            shutil.rmtree(private)
