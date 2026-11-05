"""Second-pass publication phase: exact logical-byte reservations, not OS/RSS limits.

Only enrolled after the bounded transform returns and closes its private scope.
All new receipt/backup files enforce the reserved length before every write.
SPDX-License-Identifier: Apache-2.0
"""
import hashlib,json,os,stat
from pathlib import Path
from streaming_legend.scratch_budget import ScratchBudget,ScratchError
from streaming_legend.scratch_io import validate_limit
from .publication_lock import contract as concurrency_contract

POLICY={
 'schema':'semcrys.publication-resource-policy.v0.1',
 'scope':'SECOND_PASS_TRANSFORM_THEN_STAGED_OUTPUT_RECEIPT_AND_BACKUPS',
 'phases':'SEQUENTIAL_MAX_NOT_SUM',
 'publication_basis':'STAGED_OUTPUT_PLUS_UTF8_LF_RECEIPT_PLUS_ALL_REPLACEMENT_COPIES',
 'existing_targets_counted':False,'replacement_copies_counted':True,
 'reserve_auxiliary_bytes':'BEFORE_ANY_RECEIPT_OR_BACKUP_WRITE',
 'recovery_journal_capacity_bytes':65536,
 'recovery_journal_accounting':'RESERVE_FULL_CAP_BEFORE_WRITE',
 'copy_buffer_bytes':1024*1024,'filesystem_allocation_overhead_counted':False,
 'process_rss_limit':False,'power_failure_atomicity':False,
 'concurrent_external_writers_supported':False,'whole_application_limit':False,
 'transported_bytes_changed':False,'standing':'CANDIDATE_ONLY','security_claim':'NONE'}

def root(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')).hexdigest()

def realization_shape(operation):
    if operation=='SECOND_PASS':return ('semcrys.second-pass-result.v0.1','SECOND_PASS_TRANSFORM_AND_ENROLLED_NESTED_IO')
    from .application import OPERATIONS,scope_for
    if operation not in OPERATIONS:raise ScratchError('HELD_PUBLICATION_RESOURCE_OPERATION')
    return OPERATIONS[operation][0],scope_for(operation)

def compile_instance(limit,receipt,replace,progress=None,operation='SECOND_PASS'):
    validate_limit(limit)
    realization_shape(operation)
    policy=dict(POLICY)
    if operation!='SECOND_PASS':
        policy['scope']=('PRIMARY_APPLICATION' if operation in ('ENCODE','DECODE') else 'LEGEND_WORKFLOW')+'_REALIZATION_THEN_STAGED_OUTPUT_RECEIPT_AND_BACKUPS'
        from .composite_operations import OPERATIONS as composite_operations
        if operation in composite_operations:policy['scope']='COMPOSITE_FILE_REALIZATION_THEN_STAGED_OUTPUT_RECEIPT_AND_BACKUPS'
    value={'schema':'semcrys.publication-resource-instance.v0.1','standing':'CANDIDATE_ONLY',
      'operation':operation+'_PUBLICATION','limit_bytes':limit,'receipt_requested':receipt,
      'replace_requested':replace,'policy':policy,'publication_concurrency':concurrency_contract(),
      'operation_sequence':['COMPILE_PUBLICATION_INSTANCE','ACQUIRE_PARENT_PROCESS_LOCKS','RUN_BOUNDED_TRANSFORM_AND_CLOSE_SCOPE',
        'VERIFY_TRANSFORM_RECEIPT','COUNT_PUBLICATION_BYTES','RESERVE_ALL_AUXILIARIES',
        'WRITE_EXACT_RECEIPT_AND_BACKUPS','FSYNC_STAGED_FILES_AND_BACKUPS','WRITE_AND_FSYNC_BOUNDED_RECOVERY_JOURNAL','ATOMIC_NO_REPLACE_OR_EXPLICIT_REPLACE','OWNERSHIP_GUARDED_ROLLBACK','CLEANUP','RELEASE_PROCESS_LOCKS'],
      'authority_effect':'NONE'}
    value['instance_constitution_sha256']=root(value)
    if progress:progress(json.loads(json.dumps({'stage':'PUBLICATION_INSTANCE_COMPILED','effective_configuration':value})))
    return value

def regular_size(path):
    info=Path(path).lstat()
    if not stat.S_ISREG(info.st_mode):raise ScratchError('HELD_PUBLICATION_NOT_REGULAR_FILE')
    return info.st_size

def transform_peak(result,limit,stage,operation='SECOND_PASS'):
    """Validate the trusted transform's local resource receipt, not arbitrary code."""
    try:
        ic=result['scratch_instance'];budget=result['scratch_budget']
        expected_schema,expected_scope=realization_shape(operation)
        valid=(result['status']=='PASS' and result['schema']==expected_schema
          and ic['operation']==operation and ic['policy']['limit_bytes']==limit
          and root({k:v for k,v in ic.items() if k!='instance_constitution_sha256'})==ic['instance_constitution_sha256']
          and root({k:v for k,v in result.items() if k!='receipt_sha256'})==result['receipt_sha256']
          and budget['scope']==expected_scope
          and budget['limit_bytes']==limit and budget['active_writers']==0
          and not budget['poisoned'] and type(budget['peak_reserved_bytes']) is int
          and regular_size(stage)<=budget['peak_reserved_bytes']<=limit)
    except (KeyError,TypeError,ValueError):valid=False
    if not valid:raise ScratchError('HELD_PUBLICATION_TRANSFORM_RECEIPT')
    # The transform returns only after its with-block closes handles and removes
    # its private directory. The old peak is retained, not charged concurrently.
    return budget['peak_reserved_bytes']

def receipt_chunks(value):
    for text in json.JSONEncoder(indent=2,sort_keys=True).iterencode(value):
        yield text.encode('utf-8')
    yield b'\n'

def prepare(result,stage,targets,backups,instance,prior_peak,journal_capacity=0):
    """Fixed-point receipt length counts its own byte/peak fields exactly."""
    size=regular_size(stage)
    copied=[regular_size(t) if b is not None else 0 for t,b in zip(targets,backups)]
    resources={'instance':instance,'staged_output_bytes':size,'backup_bytes':copied,
      'receipt_bytes':0,'journal_reserved_bytes':journal_capacity,'publication_reserved_bytes':0,'transform_peak_reserved_bytes':prior_peak,
      'combined_peak_reserved_bytes':prior_peak,'basis':'SEQUENTIAL_PHASE_MAX'}
    result['publication']['scratch']=resources
    # Only decimal lengths/peaks vary. Bounded monotone iteration; never publish
    # a guessed size or rely on newline translation for the counted bytes.
    for _ in range(16):
        total=size+sum(copied)+resources['receipt_bytes']+journal_capacity
        resources['publication_reserved_bytes']=total
        resources['combined_peak_reserved_bytes']=max(prior_peak,total)
        length=sum(map(len,receipt_chunks(result))) if len(targets)==2 else 0
        if length==resources['receipt_bytes']:break
        resources['receipt_bytes']=length
    else:raise ScratchError('HELD_PUBLICATION_RECEIPT_SIZE')
    quota=ScratchBudget(Path(stage).parent,instance['limit_bytes'])
    quota.reserve_native('staged_output',size)
    quota.reserve_native('receipt',resources['receipt_bytes'])
    quota.reserve_native('recovery_journal',journal_capacity)
    for n,length in enumerate(copied):quota.reserve_native('backup:'+str(n),length)
    assert quota.used==resources['publication_reserved_bytes']
    return resources

def write_exact(path,chunks,expected):
    """Exclusive new file; a pre-reserved cap is enforced before every write."""
    done=0
    with Path(path).open('xb') as out:
        for chunk in chunks:
            if len(chunk)>expected-done:raise ScratchError('HELD_PUBLICATION_FILE_CHANGED')
            if out.write(chunk)!=len(chunk):raise ScratchError('HELD_SCRATCH_SHORT_WRITE')
            done+=len(chunk)
        if done!=expected:raise ScratchError('HELD_PUBLICATION_FILE_CHANGED')

def copy_exact(source,target,expected):
    if regular_size(source)!=expected:raise ScratchError('HELD_PUBLICATION_FILE_CHANGED')
    with Path(source).open('rb') as src:
        if os.fstat(src.fileno()).st_size!=expected:raise ScratchError('HELD_PUBLICATION_FILE_CHANGED')
        def chunks():
            remaining=expected
            while remaining:
                block=src.read(min(remaining,1024*1024))
                if not block:raise ScratchError('HELD_PUBLICATION_FILE_CHANGED')
                remaining-=len(block);yield block
            if src.read(1):raise ScratchError('HELD_PUBLICATION_FILE_CHANGED')
        write_exact(target,chunks(),expected)
    if regular_size(source)!=expected:raise ScratchError('HELD_PUBLICATION_FILE_CHANGED')
