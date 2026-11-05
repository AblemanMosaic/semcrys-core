import hashlib
import json
from importlib.resources import files
from streaming_app.core import Refusal
from streaming_legend.core import canonical

def verify_self():
    try:
        with files('semcrys').joinpath('PAYLOAD_MANIFEST.json').open('rb') as handle: raw=handle.read(4*1024*1024+1)
        if len(raw)>4*1024*1024: raise Refusal('HELD_DISTRIBUTION_MANIFEST_LIMIT')
        manifest=json.loads(raw.decode('utf-8'))
    except (OSError,ValueError,UnicodeError,RecursionError) as exc:
        if isinstance(exc,Refusal): raise
        raise Refusal('HELD_DISTRIBUTION_MANIFEST_MISSING_OR_INVALID') from exc
    if type(manifest) is not dict or set(manifest)!={'schema','files','payload_root'} or manifest['schema']!='semcrys.payload-manifest.v0.1':
        raise Refusal('HELD_DISTRIBUTION_MANIFEST_SCHEMA')
    rows=manifest.get('files')
    if not isinstance(rows,list) or not rows or hashlib.sha256(canonical(rows)).hexdigest()!=manifest.get('payload_root'):
        raise Refusal('HELD_DISTRIBUTION_MANIFEST_ROOT')
    seen=set()
    for row in rows:
        if type(row) is not dict or set(row)!={'package','path','bytes','sha256'}:
            raise Refusal('HELD_DISTRIBUTION_MANIFEST_ROW')
        package,path=row['package'],row['path']
        if not isinstance(package,str) or not isinstance(path,str) or package not in ('semcrys','streaming_app','streaming_legend') or not path or path.startswith('/') or '\\' in path or ':' in path or any(p in ('','..','.') for p in path.split('/')):
            raise Refusal('HELD_DISTRIBUTION_MANIFEST_PATH')
        if (package,path) in seen or type(row['bytes']) is not int or row['bytes']<0 or not isinstance(row['sha256'],str) or len(row['sha256'])!=64 or any(c not in '0123456789abcdef' for c in row['sha256']):
            raise Refusal('HELD_DISTRIBUTION_MANIFEST_ROW')
        seen.add((package,path))
        try: data=files(package).joinpath(path).read_bytes()
        except OSError as exc: raise Refusal('HELD_DISTRIBUTION_FILE_MISSING',path) from exc
        if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:
            raise Refusal('HELD_DISTRIBUTION_FILE_CHANGED',package+'/'+path)
    observed=set()
    for package in ('semcrys','streaming_app','streaming_legend'):
        for entry in files(package).iterdir():
            if entry.name=='__pycache__': continue
            if package=='semcrys' and entry.name=='PAYLOAD_MANIFEST.json': continue
            if not entry.is_file(): raise Refusal('HELD_DISTRIBUTION_UNDECLARED_DIRECTORY',entry.name)
            observed.add((package,entry.name))
    if seen!=observed: raise Refusal('HELD_DISTRIBUTION_INCOMPLETE_INVENTORY')
    return {'schema':'semcrys.distribution-verification.v0.1','status':'PASS','standing':'CANDIDATE_ONLY',
        'payload_root':manifest['payload_root'],'files':len(rows),'inventory_complete':True,'publisher_authentication':'NOT_CLAIMED'}

def catalogue(): return json.loads(files('semcrys').joinpath('PROFILE_CATALOGUE.json').read_text(encoding='utf-8'))
