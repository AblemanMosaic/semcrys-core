"""Explicit new-directory quarantine after process interruption. No deletion."""
import hashlib,json,os,re,stat
from pathlib import Path,PurePosixPath
from streaming_app.core import Refusal
from .publication_resources import root,write_exact
from .recovery import absolute,_pairs

SCHEMA='semcrys.directory-recovery-journal.v0.1'
NAME='DIRECTORY_RECOVERY.json'
CAP=256*1024
LABEL='directory-recovery-journal'
MAX_FILES=2048
def fail(code):raise Refusal(code)
def regular(p,kind):
    p=absolute(p);info=p.lstat()
    if getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0):fail('HELD_DIRECTORY_RECOVERY_REPARSE')
    if (kind=='FILE' and not stat.S_ISREG(info.st_mode)) or (kind=='DIR' and not stat.S_ISDIR(info.st_mode)):
        fail('HELD_DIRECTORY_RECOVERY_NOT_REGULAR')
    return info
def fingerprint(p):
    info=regular(p,'FILE')
    with p.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    if p.stat().st_size!=info.st_size:fail('HELD_DIRECTORY_RECOVERY_CHANGED')
    return {'bytes':info.st_size,'sha256':digest}
def tree(path):
    path=absolute(path)
    if not os.path.lexists(path):return None
    regular(path,'DIR');files=[];dirs=[];total=0;pending=[path]
    while pending:
        folder=pending.pop()
        # Refuse entries before descent/hash; never materialize an unbounded
        # rglob list or follow a junction before checking it.
        with os.scandir(folder) as entries:
            for entry in entries:
                p=Path(entry.path);info=p.lstat();rel=p.relative_to(path).as_posix()
                if stat.S_ISDIR(info.st_mode):
                    regular(p,'DIR')
                    if len(dirs)>=MAX_FILES:fail('HELD_DIRECTORY_RECOVERY_INVENTORY_LIMIT')
                    dirs.append(rel);pending.append(p)
                else:
                    regular(p,'FILE')
                    if len(files)>=MAX_FILES or total+info.st_size>1<<40:fail('HELD_DIRECTORY_RECOVERY_INVENTORY_LIMIT')
                    row={'path':rel,**fingerprint(p)};files.append(row);total+=row['bytes']
    return {'files':sorted(files,key=lambda r:r['path']),'directories':sorted(dirs)}
def _relative(value):
    if not isinstance(value,str) or not value or PurePosixPath(value).as_posix()!=value:fail('HELD_DIRECTORY_RECOVERY_PATH')
    p=PurePosixPath(value)
    if p.is_absolute() or any(not re.fullmatch(r'[A-Za-z0-9_.-]+',part) or part in ('.','..') for part in p.parts):fail('HELD_DIRECTORY_RECOVERY_PATH')
    return value
def prepare(journal,target,stage,budget):
    if budget._native.get(LABEL)!=CAP:fail('HELD_DIRECTORY_RECOVERY_UNRESERVED')
    target,stage,journal=map(absolute,(target,stage,journal))
    if os.path.lexists(target):fail('HELD_DIRECTORY_DESTINATION_EXISTS')
    manifest=tree(stage)
    if manifest is None:fail('HELD_DIRECTORY_RECOVERY_STAGE_MISSING')
    value={'schema':SCHEMA,'standing':'CANDIDATE_ONLY','intent':'EXPLICIT_QUARANTINE_NEW_DIRECTORY',
      'target':str(target),'stage':str(stage),'manifest':manifest,'manifest_root':root(manifest),
      'power_failure_atomicity':False,'concurrent_writers_supported':False,'new_temporary_payload_bytes':0}
    value['journal_root']=root(value)
    data=json.dumps(value,sort_keys=True,ensure_ascii=True,separators=(',',':')).encode('utf-8')+b'\n'
    if len(data)>CAP:fail('HELD_DIRECTORY_RECOVERY_JOURNAL_LIMIT')
    # This one writer is covered by the full pre-reserved cap, not double-charged.
    write_exact(journal,[data],len(data))
    with journal.open('r+b') as f:os.fsync(f.fileno())
    load(journal,value['journal_root'])
    return {'journal':str(journal),'journal_root':value['journal_root'],'journal_bytes':len(data),'journal_capacity_bytes':CAP}
def load(journal,expected_root=None):
    p=absolute(journal)
    if p.name!=NAME:fail('HELD_DIRECTORY_RECOVERY_JOURNAL_NAME')
    regular(p,'FILE')
    with p.open('rb') as f:data=f.read(CAP+1)
    if len(data)>CAP:fail('HELD_DIRECTORY_RECOVERY_JOURNAL_LIMIT')
    try:v=json.loads(data,object_pairs_hook=_pairs)
    except (ValueError,UnicodeError,RecursionError) as exc:raise Refusal('HELD_DIRECTORY_RECOVERY_JSON') from exc
    keys={'schema','standing','intent','target','stage','manifest','manifest_root','power_failure_atomicity','concurrent_writers_supported','new_temporary_payload_bytes','journal_root'}
    if type(v) is not dict or set(v)!=keys:fail('HELD_DIRECTORY_RECOVERY_SCHEMA')
    if v['schema']!=SCHEMA or v['standing']!='CANDIDATE_ONLY' or v['intent']!='EXPLICIT_QUARANTINE_NEW_DIRECTORY':fail('HELD_DIRECTORY_RECOVERY_SCHEMA')
    if v['power_failure_atomicity'] is not False or v['concurrent_writers_supported'] is not False or type(v['new_temporary_payload_bytes']) is not int or v['new_temporary_payload_bytes']!=0:fail('HELD_DIRECTORY_RECOVERY_SCHEMA')
    if v['journal_root']!=root({k:x for k,x in v.items() if k!='journal_root'}):fail('HELD_DIRECTORY_RECOVERY_ROOT')
    if expected_root is not None and v['journal_root']!=expected_root:fail('HELD_DIRECTORY_RECOVERY_EXPECTED_ROOT')
    for key in ('target','stage'):
        if not isinstance(v[key],str) or not Path(v[key]).is_absolute():fail('HELD_DIRECTORY_RECOVERY_PATH')
    target,stage=absolute(v['target']),absolute(v['stage'])
    if stage!=p.parent/'result' or p.parent.parent!=target.parent or not p.parent.name.startswith('dr-') or target==p.parent:fail('HELD_DIRECTORY_RECOVERY_PATH')
    regular(p.parent,'DIR')
    if any(item not in (p,stage) for item in p.parent.iterdir()):fail('HELD_DIRECTORY_RECOVERY_UNEXPECTED_PRIVATE_ENTRY')
    m=v['manifest']
    if type(m) is not dict or set(m)!= {'files','directories'} or any(type(m[k]) is not list or len(m[k])>MAX_FILES for k in m):fail('HELD_DIRECTORY_RECOVERY_MANIFEST')
    paths=[];total=0
    for row in m['files']:
        if type(row) is not dict or set(row)!= {'path','bytes','sha256'}:fail('HELD_DIRECTORY_RECOVERY_MANIFEST')
        paths.append(_relative(row['path']))
        if type(row['bytes']) is not int or not 0<=row['bytes']<=1<<40:fail('HELD_DIRECTORY_RECOVERY_MANIFEST')
        if type(row['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}',row['sha256']):fail('HELD_DIRECTORY_RECOVERY_MANIFEST')
        total+=row['bytes']
    dirs=[_relative(d) for d in m['directories']]
    if paths!=sorted(set(paths)) or dirs!=sorted(set(dirs)) or len({s.casefold() for s in paths+dirs})!=len(paths+dirs) or total>1<<40:fail('HELD_DIRECTORY_RECOVERY_MANIFEST')
    for rel in paths+dirs:
        parent=PurePosixPath(rel).parent
        if str(parent)!='.' and str(parent) not in dirs:fail('HELD_DIRECTORY_RECOVERY_MANIFEST')
    if v['manifest_root']!=root(m):fail('HELD_DIRECTORY_RECOVERY_MANIFEST_ROOT')
    return v
def state(value):
    stage,target=tree(Path(value['stage'])),tree(Path(value['target']))
    if stage is not None and stage!=value['manifest']:fail('HELD_DIRECTORY_RECOVERY_STAGE_CHANGED')
    if target is not None and target!=value['manifest']:fail('HELD_DIRECTORY_RECOVERY_TARGET_CHANGED')
    if stage is not None and target is not None:fail('HELD_DIRECTORY_RECOVERY_BOTH_PRESENT')
    if stage is None and target is None:return 'NEITHER_PRESENT'
    return 'PREPARED' if stage is not None else 'PUBLISHED'
def inspect(journal,expected_root=None):
    value=load(journal,expected_root);current=state(value)
    return {'schema':'semcrys.directory-recovery-inspection.v0.1','status':'PASS','standing':'CANDIDATE_ONLY',
      'journal':str(absolute(journal)),'journal_root':value['journal_root'],'target':value['target'],'stage':value['stage'],
      'state':current,'effect':'READ_ONLY','files':len(value['manifest']['files']),
      'quarantine_requires_explicit_output_and_expected_root':True,'power_failure_atomicity':False,'concurrent_writers_supported':False}
def quarantine(journal,*,output,expected_root,progress=None):
    if not isinstance(expected_root,str) or not re.fullmatch('[0-9a-f]{64}',expected_root):fail('HELD_DIRECTORY_RECOVERY_EXPECTED_ROOT')
    value=load(journal,expected_root)
    if str(Path(output).resolve(strict=False))!=value['target']:fail('HELD_DIRECTORY_RECOVERY_TARGET_AUTHORIZATION')
    from .publication_lock import destinations
    with destinations([output]):
        return _quarantine_locked(journal,output=output,expected_root=expected_root,progress=progress)

def _quarantine_locked(journal,*,output,expected_root,progress=None):
    if not isinstance(expected_root,str) or not re.fullmatch('[0-9a-f]{64}',expected_root):fail('HELD_DIRECTORY_RECOVERY_EXPECTED_ROOT')
    value=load(journal,expected_root)
    if str(Path(output).resolve(strict=False))!=value['target']:fail('HELD_DIRECTORY_RECOVERY_TARGET_AUTHORIZATION')
    initial=state(value)
    if initial=='NEITHER_PRESENT':fail('HELD_DIRECTORY_RECOVERY_PAYLOAD_MISSING')
    ic={'schema':'semcrys.directory-recovery-instance.v0.1','standing':'CANDIDATE_ONLY','journal_root':expected_root,
      'target':value['target'],'stage':value['stage'],'operation':'QUARANTINE_NEW_DIRECTORY',
      'operation_sequence':['VERIFY_JOURNAL_AND_EXPLICIT_TARGET','VERIFY_COMPLETE_TREE','RENAME_TARGET_TO_EMPTY_PRIVATE_STAGE_IF_PUBLISHED','VERIFY_PREPARED','RETAIN_ALL_PAYLOAD_AND_JOURNAL'],
      'new_temporary_payload_bytes':0,'recursive_deletion':False,'power_failure_atomicity':False,'concurrent_writers_supported':False}
    ic['instance_constitution_sha256']=root(ic)
    if progress:progress(json.loads(json.dumps({'stage':'DIRECTORY_RECOVERY_INSTANCE_COMPILED','effective_configuration':ic})))
    load(journal,expected_root);current=state(value)
    if current not in ('PREPARED','PUBLISHED'):fail('HELD_DIRECTORY_RECOVERY_PAYLOAD_MISSING')
    changed=current=='PUBLISHED'
    if changed:
        # Exact caller-authorized target, complete tree verified; no copy/deletion.
        from .publication_lock import move_new
        move_new(value['target'],value['stage'])
        if progress:progress({'stage':'DIRECTORY_RECOVERY_TARGET_QUARANTINED'})
    final=inspect(journal,expected_root)
    if final['state']!='PREPARED':fail('HELD_DIRECTORY_RECOVERY_INCOMPLETE')
    return {'schema':'semcrys.directory-recovery-result.v0.1','status':'PASS','standing':'CANDIDATE_ONLY',
      'effective_configuration':ic,'initial_state':initial,'changed':changed,'final_state':'PREPARED',
      'journal_retained':True,'all_payload_retained':True,'output_absent':True,'new_temporary_payload_bytes':0,
      'automatic_cleanup':False,'release_ready':False,'power_failure_atomicity':False}
