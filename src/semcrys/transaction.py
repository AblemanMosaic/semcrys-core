"""Exception-safe artifact/receipt publication, not crash-atomic filesystem transactions."""
import json
import os
import shutil
import tempfile
from pathlib import Path
from streaming_app.core import Refusal, protect_outputs
from . import publication_resources as resources
from . import recovery
from . import publication_lock as locks

def publish(operation,output,*,inputs=(),receipt=None,replace=False,metadata=None,max_scratch_bytes=None,progress=None,resource_operation='SECOND_PASS'):
    # Only enrolled second-pass and primary encode/decode callers supply this option. Other callers
    # retain their existing behavior; do not imply a whole-application quota.
    instance=(resources.compile_instance(max_scratch_bytes,receipt is not None,replace,progress,operation=resource_operation)
              if max_scratch_bytes is not None else None)
    targets=[Path(output)] + ([Path(receipt)] if receipt is not None else [])
    inputs=tuple(inputs)
    protect_outputs(targets,inputs)
    with locks.destinations(targets,inputs):
        return _publish_locked(operation,targets,receipt,replace,metadata,max_scratch_bytes,progress,resource_operation,instance)

def _publish_locked(operation,targets,receipt,replace,metadata,max_scratch_bytes,progress,resource_operation,instance):
    for target in targets:
        if target.is_symlink() or (target.exists() and not target.is_file()): raise Refusal('HELD_OUTPUT_NOT_REGULAR_FILE')
        if target.exists() and not replace: raise Refusal('HELD_OUTPUT_EXISTS_USE_REPLACE',str(target))
    directories=[]; staged=[]; backups=[]; committed=[]; preserve=False
    try:
        for target in targets:
            target.parent.mkdir(parents=True,exist_ok=True)
            directory=Path(tempfile.mkdtemp(prefix='semcrys-publish-',dir=target.parent)); directories.append(directory)
            staged.append(directory/('new'+target.suffix))
            backups.append(directory/'previous' if target.exists() else None)
        result=operation(staged[0])
        prior_peak=resources.transform_peak(result,max_scratch_bytes,staged[0],operation=resource_operation) if instance else None
        journal=directories[0]/recovery.JOURNAL_NAME
        result={**result,**(metadata or {}),'publication':{'output':str(targets[0]),'receipt':str(targets[1]) if receipt is not None else None,
            'recovery_journal':str(journal.resolve()),
            'contract':'ROLLBACK_ON_OBSERVED_EXCEPTION_NOT_POWER_FAILURE_ATOMICITY'}}
        accounting=resources.prepare(result,staged[0],targets,backups,instance,prior_peak,recovery.JOURNAL_CAP) if instance else None
        if accounting and progress:
            # Observers receive detached data, not mutable reservation controls.
            progress(json.loads(json.dumps({'stage':'PUBLICATION_BYTES_RESERVED','scratch':accounting})))
        if receipt is not None:
            if accounting:resources.write_exact(staged[1],resources.receipt_chunks(result),accounting['receipt_bytes'])
            else:staged[1].write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
        for index,(stage,target,backup) in enumerate(zip(staged,targets,backups)):
            if accounting:
                expected=accounting['staged_output_bytes'] if index==0 else accounting['receipt_bytes']
                if resources.regular_size(stage)!=expected:raise Refusal('HELD_PUBLICATION_FILE_CHANGED')
            with stage.open('r+b') as handle: os.fsync(handle.fileno())
            if backup is not None:
                if accounting:
                    resources.copy_exact(target,backup,accounting['backup_bytes'][index])
                    shutil.copystat(target,backup)
                else:shutil.copy2(target,backup)
        prepared=recovery.prepare(journal,targets,staged,backups)
        prepared_rows=recovery.load(Path(prepared['journal']),prepared['journal_root'])['rows']
        stage_ids=[(s.stat().st_dev,s.stat().st_ino) for s in staged]
        if progress:progress({'stage':'PUBLICATION_PREPARED',**prepared})
        try:
            for index,(stage,target) in enumerate(zip(staged,targets)):
                # Record the attempt before the syscall. An asynchronous
                # exception may arrive after the rename but before it returns.
                committed.append(index)
                if replace and recovery.fingerprint(target.resolve())!=prepared_rows[index]['old']:
                    raise Refusal('HELD_PUBLICATION_TARGET_CHANGED')
                locks.commit_file(stage,target,replace)
                if progress:progress({'stage':'PUBLICATION_TARGET_COMMITTED','index':index})
        except BaseException:
            preserve=True
            failures=[]
            for index in reversed(committed):
                try:
                    # A completed replace consumes its unique staging file.
                    # If it still exists, this target was never committed.
                    if staged[index].exists(): continue
                    info=targets[index].lstat()
                    if ((info.st_dev,info.st_ino)!=stage_ids[index]
                        or recovery.fingerprint(targets[index].resolve())!=prepared_rows[index]['new']):
                        raise Refusal('HELD_ROLLBACK_TARGET_CHANGED')
                    if backups[index] is None: targets[index].unlink()
                    else: os.replace(backups[index],targets[index])
                except BaseException as exc: failures.append(type(exc).__name__+': '+str(exc))
            if failures:
                raise Refusal('HELD_ROLLBACK_INCOMPLETE',json.dumps({'errors':failures,'recovery_directories':[str(p) for p in directories]}))
            preserve=False
            raise
        return result
    finally:
        if not preserve:
            for directory in directories:
                # These exact directories were created above; never user roots.
                shutil.rmtree(directory)
