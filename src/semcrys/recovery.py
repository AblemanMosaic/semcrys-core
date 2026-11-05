"""Explicit, rooted process-interruption recovery; not power-loss atomicity."""
import hashlib,json,os,re,stat
from pathlib import Path
from streaming_app.core import Refusal
from .publication_resources import root,write_exact

JOURNAL_CAP=64*1024
JOURNAL_NAME='RECOVERY.json'
SCHEMA='semcrys.publication-recovery-journal.v0.1'

def fail(code):raise Refusal(code)
def absolute(path):
    p=Path(path).absolute()
    if p!=p.resolve(strict=False):fail('HELD_RECOVERY_PATH_ALIAS')
    return p
def fingerprint(path):
    p=absolute(path)
    try:info=p.lstat()
    except FileNotFoundError:return None
    if not stat.S_ISREG(info.st_mode):fail('HELD_RECOVERY_NOT_REGULAR')
    with p.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    if p.stat().st_size!=info.st_size:fail('HELD_RECOVERY_FILE_CHANGED')
    return {'bytes':info.st_size,'sha256':digest}
def sync_file(path):
    with Path(path).open('r+b') as f:os.fsync(f.fileno())
def prepare(journal,targets,staged,backups):
    rows=[]
    for index,(target,stage,backup) in enumerate(zip(targets,staged,backups)):
        new=fingerprint(Path(stage).resolve());old=fingerprint(Path(backup).resolve()) if backup is not None else None
        if new is None:fail('HELD_RECOVERY_STAGE_MISSING')
        if fingerprint(Path(target).resolve())!=old:fail('HELD_RECOVERY_TARGET_CHANGED')
        rows.append({'role':'OUTPUT' if index==0 else 'RECEIPT',
          'target':str(Path(target).resolve()),'stage':str(Path(stage).resolve()),
          'backup':str(Path(backup).resolve()) if backup is not None else None,
          'old':old,'new':new})
    value={'schema':SCHEMA,'standing':'CANDIDATE_ONLY','intent':'EXPLICIT_ROLLBACK_TO_PRIOR_TARGETS',
      'rows':rows,'power_failure_atomicity':False,'concurrent_writers_supported':False}
    value['journal_root']=root(value)
    data=json.dumps(value,sort_keys=True,ensure_ascii=True,separators=(',',':')).encode('utf-8')+b'\n'
    if len(data)>JOURNAL_CAP:fail('HELD_RECOVERY_JOURNAL_LIMIT')
    # Backups must be flushed before the intent record permits target mutation.
    for backup in backups:
        if backup is not None:sync_file(backup)
    write_exact(journal,[data],len(data));sync_file(journal)
    return {'journal':str(Path(journal).resolve()),'journal_root':value['journal_root'],
      'journal_bytes':len(data),'journal_capacity_bytes':JOURNAL_CAP}

def _pairs(items):
    result={}
    for k,v in items:
        if k in result:fail('HELD_RECOVERY_DUPLICATE_KEY')
        result[k]=v
    return result
def _shape_fingerprint(value,optional=False):
    if value is None and optional:return
    if not isinstance(value,dict) or set(value)!= {'bytes','sha256'}:fail('HELD_RECOVERY_SCHEMA')
    if type(value['bytes']) is not int or not 0<=value['bytes']<=2**63-1:fail('HELD_RECOVERY_SCHEMA')
    if not isinstance(value['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',value['sha256']):fail('HELD_RECOVERY_SCHEMA')
def load(journal,expected_root=None):
    path=absolute(journal)
    if path.name!=JOURNAL_NAME:fail('HELD_RECOVERY_JOURNAL_NAME')
    if not stat.S_ISREG(path.lstat().st_mode):fail('HELD_RECOVERY_NOT_REGULAR')
    with path.open('rb') as f:data=f.read(JOURNAL_CAP+1)
    if len(data)>JOURNAL_CAP:fail('HELD_RECOVERY_JOURNAL_LIMIT')
    try:v=json.loads(data,object_pairs_hook=_pairs)
    except (json.JSONDecodeError,UnicodeError,RecursionError):fail('HELD_RECOVERY_JSON')
    keys={'schema','standing','intent','rows','power_failure_atomicity','concurrent_writers_supported','journal_root'}
    if not isinstance(v,dict) or set(v)!=keys:fail('HELD_RECOVERY_SCHEMA')
    if (v['schema']!=SCHEMA or v['standing']!='CANDIDATE_ONLY'
        or v['intent']!='EXPLICIT_ROLLBACK_TO_PRIOR_TARGETS'
        or v['power_failure_atomicity'] is not False or v['concurrent_writers_supported'] is not False):fail('HELD_RECOVERY_SCHEMA')
    if v['journal_root']!=root({k:val for k,val in v.items() if k!='journal_root'}):fail('HELD_RECOVERY_ROOT')
    if expected_root is not None and v['journal_root']!=expected_root:fail('HELD_RECOVERY_EXPECTED_ROOT')
    if not isinstance(v['rows'],list) or len(v['rows']) not in (1,2):fail('HELD_RECOVERY_SCHEMA')
    seen={path};directories={}
    for index,row in enumerate(v['rows']):
        if not isinstance(row,dict) or set(row)!= {'role','target','stage','backup','old','new'}:fail('HELD_RECOVERY_SCHEMA')
        if row['role']!=('OUTPUT' if index==0 else 'RECEIPT'):fail('HELD_RECOVERY_SCHEMA')
        _shape_fingerprint(row['old'],optional=True);_shape_fingerprint(row['new'])
        for key in ('target','stage'):
            if not isinstance(row[key],str) or not Path(row[key]).is_absolute():fail('HELD_RECOVERY_PATH')
        target,stage=absolute(row['target']),absolute(row['stage'])
        if stage.parent.parent!=target.parent or not stage.parent.name.startswith('semcrys-publish-'):fail('HELD_RECOVERY_PATH')
        if stage.name!='new'+target.suffix or (index==0 and stage.parent!=path.parent):fail('HELD_RECOVERY_PATH')
        if row['old'] is None:
            if row['backup'] is not None:fail('HELD_RECOVERY_SCHEMA')
            backup=None
        else:
            if not isinstance(row['backup'],str) or not Path(row['backup']).is_absolute():fail('HELD_RECOVERY_SCHEMA')
            backup=absolute(row['backup'])
            if backup!=stage.parent/'previous':fail('HELD_RECOVERY_PATH')
        paths=[target,stage]+([backup] if backup is not None else [])
        if any(p in seen for p in paths) or len(set(paths))!=len(paths):fail('HELD_RECOVERY_PATH_ALIAS')
        seen.update(paths);directories[stage.parent]={stage,*( [backup] if backup else [])}
    directories[path.parent].add(path)
    for folder,allowed in directories.items():
        if not folder.is_dir():fail('HELD_RECOVERY_DIRECTORY_MISSING')
        if any(p not in allowed for p in folder.iterdir()):fail('HELD_RECOVERY_UNEXPECTED_FILE')
    return v

def _states(value):
    states=[]
    for row in value['rows']:
        current=fingerprint(row['target']);stage=fingerprint(row['stage'])
        backup=fingerprint(row['backup']) if row['backup'] is not None else None
        if stage is not None and stage!=row['new']:fail('HELD_RECOVERY_STAGE_CHANGED')
        if backup is not None and backup!=row['old']:fail('HELD_RECOVERY_BACKUP_CHANGED')
        if current==row['old']:state='OLD'
        elif current==row['new']:
            state='NEW'
            if row['old'] is not None and backup is None:fail('HELD_RECOVERY_BACKUP_MISSING')
        else:fail('HELD_RECOVERY_TARGET_CHANGED')
        states.append(state)
    return states
def inspect(journal,expected_root=None):
    value=load(journal,expected_root);states=_states(value)
    return {'schema':'semcrys.publication-recovery-inspection.v0.1','status':'PASS','standing':'CANDIDATE_ONLY',
      'journal':str(Path(journal).resolve()),'journal_root':value['journal_root'],
      'state':'ALL_OLD' if all(s=='OLD' for s in states) else 'ALL_NEW' if all(s=='NEW' for s in states) else 'MIXED',
      'targets':[{'role':r['role'],'target':r['target'],'state':s} for r,s in zip(value['rows'],states)],
      'effect':'READ_ONLY','rollback_requires_explicit_targets_and_expected_root':True,
      'power_failure_atomicity':False,'concurrent_writers_supported':False}
def rollback(journal,*,output,receipt=None,expected_root,progress=None):
    # Validate before creating local coordination metadata; then validate again
    # while holding the same parent locks used by ordinary publication.
    if not isinstance(expected_root,str) or not re.fullmatch('[0-9a-f]{64}',expected_root):fail('HELD_RECOVERY_EXPECTED_ROOT')
    value=load(journal,expected_root)
    targets=[str(Path(output).resolve())]+([str(Path(receipt).resolve())] if receipt is not None else [])
    if targets!=[r['target'] for r in value['rows']]:fail('HELD_RECOVERY_TARGET_AUTHORIZATION')
    from .publication_lock import destinations
    with destinations(targets):
        return _rollback_locked(journal,output=output,receipt=receipt,expected_root=expected_root,progress=progress)

def _rollback_locked(journal,*,output,receipt=None,expected_root,progress=None):
    if not isinstance(expected_root,str) or not re.fullmatch('[0-9a-f]{64}',expected_root):fail('HELD_RECOVERY_EXPECTED_ROOT')
    value=load(journal,expected_root)
    targets=[str(Path(output).resolve())]+([str(Path(receipt).resolve())] if receipt is not None else [])
    if targets!=[r['target'] for r in value['rows']]:fail('HELD_RECOVERY_TARGET_AUTHORIZATION')
    # Read-only validation of every row occurs before the first mutation.
    initial=_states(value)
    ic={'schema':'semcrys.recovery-instance.v0.1','standing':'CANDIDATE_ONLY',
      'journal_root':expected_root,'targets':targets,'operation':'ROLLBACK_TO_PRIOR',
      'operation_sequence':['VERIFY_JOURNAL_ROOT_AND_EXPLICIT_TARGETS','VERIFY_ALL_FILE_STATES',
        'RESTORE_OLD_TARGETS_IN_REVERSE_ORDER','REVERIFY_ALL_OLD','RETAIN_JOURNAL'],
      'new_temporary_payload_bytes':0,'power_failure_atomicity':False,'concurrent_writers_supported':False}
    ic['instance_constitution_sha256']=root(ic)
    if progress:progress({'stage':'RECOVERY_INSTANCE_COMPILED','effective_configuration':json.loads(json.dumps(ic))})
    changed=[]
    for index in reversed(range(len(value['rows']))):
        # Recheck the whole still-valid journal and all states between mutations.
        load(journal,expected_root);states=_states(value);row=value['rows'][index]
        if states[index]=='NEW':
            if row['old'] is None:Path(row['target']).unlink()
            else:os.replace(row['backup'],row['target'])
            changed.append(row['role'])
            if progress:progress({'stage':'RECOVERY_TARGET_ROLLED_BACK','role':row['role']})
    final=inspect(journal,expected_root)
    if final['state']!='ALL_OLD':fail('HELD_RECOVERY_INCOMPLETE')
    return {'schema':'semcrys.publication-recovery-result.v0.1','status':'PASS','standing':'CANDIDATE_ONLY',
      'effective_configuration':ic,'initial_states':initial,'changed_roles':changed,'final_state':'ALL_OLD',
      'journal_retained':True,'automatic_cleanup':False,'new_temporary_payload_bytes':0,
      'power_failure_atomicity':False,'release_ready':False}
