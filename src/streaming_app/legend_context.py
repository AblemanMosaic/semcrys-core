"""Ephemeral, explicit verified legend sessions; never a persistent trust cache.

SPDX-License-Identifier: Apache-2.0
Structural validation and value uniqueness run once per exact snapshot. Every
operation checks full snapshot AND derived lookup hashes, not mtime-as-custody.
The owner process and its private memory are trusted; malicious same-process
code and OS compromise are not addressed by these checks.
"""
from streaming_legend import scratch_io as sio
import hashlib
import json
import sqlite3
import tempfile
import time
import inspect
import os
from functools import wraps
from contextlib import contextmanager
from pathlib import Path
from streaming_legend.assembly import ExecutionLegendReader as LegendReader
from streaming_legend.core import canonical, file_sha256
from streaming_legend.cache import SharedLookupCache

def refuse(code):
    from .core import Refusal
    raise Refusal(code)

def governed_context(function):
    @wraps(function)
    def run(*args,**kwargs):
        context=kwargs.get('legend_context')
        if context is None:
            with VerifiedLegendContext() as context:
                return run(*args,**{**kwargs,'legend_context':context})
        if type(context) is not VerifiedLegendContext: refuse('HELD_CONTEXT_TYPE')
        # Keep the user destination untouched until *all* context exit guards
        # have passed. Inner encode/decode publication targets only this stage.
        from .core import protect_outputs
        bound=inspect.signature(function).bind(*args,**kwargs); bound.apply_defaults()
        target=Path(bound.arguments['output'])
        inputs=[bound.arguments['source'],*bound.arguments.get('external_legends',()),*context.protected_paths()]
        glyph=bound.arguments.get('glyph_registry')
        if glyph is not None: inputs.append(glyph)
        front=bound.arguments.get('fold_front')
        if front is not None: inputs.append(front)
        inputs.extend(bound.arguments.get('additional_sources',()))
        try:
            protect_outputs([target],inputs)
            target.parent.mkdir(parents=True,exist_ok=True)
            # Nested internal decode runs must not exhaust Windows MAX_PATH
            # merely because the user's workspace has a descriptive name.
            with sio.TempDirectory(prefix='sc-',dir=target.parent) as name:
                stage=Path(name)/('result'+target.suffix); bound.arguments['output']=stage
                with context.operation(): result=function(*bound.args,**bound.kwargs)
                result={**result,'execution_context':context.receipt()}
                sio.replace(stage,target)
            return result
        except BaseException:
            context._poisoned=True
            raise
    return run

class _Cursor:
    def __init__(self,row): self.row=row
    def fetchone(self): return self.row

def invalidates_on_failure(function):
    @wraps(function)
    def run(self,*args,**kwargs):
        try: return function(self,*args,**kwargs)
        except BaseException:
            self._poisoned=True
            raise
    return run

class StackLookup:
    def __init__(self,rows): self.rows=rows
    def execute(self,query,params):
        if query not in ('SELECT id FROM lookup WHERE value=?','SELECT 1 FROM lookup WHERE value=?') or len(params)!=1:
            refuse('HELD_CONTEXT_QUERY_UNAVAILABLE')
        offset=0
        for row in self.rows:
            found=row['connection'].execute('SELECT id FROM lookup WHERE value=?',params).fetchone()
            if found: return _Cursor((offset+found[0],) if query.startswith('SELECT id') else (1,))
            offset+=row['entries']
        return _Cursor(None)
    def close(self): pass  # connection ownership belongs to the context

class VerifiedLegendContext:
    def __init__(self,*,max_legend_bytes=1024*1024*1024,max_legends=1024,progress=None,
                 max_lookup_cache_bytes=8*1024*1024,max_lookup_cache_entries=32768,
                 sqlite_cache_budget_kib=16384, lookup_backend='DISK',
                 backend_payload_budget_bytes=512*1024*1024, mmap_limit_bytes=256*1024*1024,
                 persistent_lookup_cache=None):
        if lookup_backend not in ('AUTO','DISK','MMAP','RAM'): refuse('HELD_LOOKUP_BACKEND')
        if type(backend_payload_budget_bytes) is not int or backend_payload_budget_bytes<0: refuse('HELD_BACKEND_PAYLOAD_BUDGET')
        if type(mmap_limit_bytes) is not int or not 0<mmap_limit_bytes<=1<<30: refuse('HELD_BACKEND_MMAP_LIMIT')
        self.lookup_backend=lookup_backend; self.backend_budget=backend_payload_budget_bytes
        self.backend_used=0; self.mmap_limit=mmap_limit_bytes
        self.persistent_lookup_cache=None if persistent_lookup_cache is None else Path(persistent_lookup_cache)
        if type(max_legend_bytes) is not int or not 0<=max_legend_bytes<=1<<40 or type(max_legends) is not int or not 1<=max_legends<=4096:
            refuse('HELD_CONTEXT_LIMIT')
        self.maximum=max_legend_bytes; self.max_legends=max_legends; self.progress=progress
        self.lookup_cache=SharedLookupCache(max_lookup_cache_bytes,max_lookup_cache_entries)
        if type(sqlite_cache_budget_kib) is not int or not 4*max_legends<=sqlite_cache_budget_kib<=1<<30:
            refuse('HELD_CONTEXT_SQLITE_CACHE_BUDGET')
        self.sqlite_cache_budget_kib=sqlite_cache_budget_kib; self._sqlite_share_kib=0
        cache_policy=('PROCESS_OWNED_SNAPSHOTS_ROOTED_PERSISTENT_LOOKUP_HINT_FULL_HASH_GUARDS'
            if self.persistent_lookup_cache is not None else 'EPHEMERAL_PROCESS_OWNED_SNAPSHOTS_FULL_HASH_GUARDS')
        cache_operation=('LOAD_OR_BUILD_ROOTED_UNIQUE_LOOKUP'
            if self.persistent_lookup_cache is not None else 'BUILD_UNIQUE_LOOKUP')
        self.configuration={'schema':'semcrys.verified-context-instance.v0.1','standing':'CANDIDATE_ONLY',
            'policy':cache_policy,'max_legend_bytes':max_legend_bytes,'max_legends':max_legends,
            'lookup_cache_max_bytes':max_lookup_cache_bytes,'lookup_cache_max_entries':max_lookup_cache_entries,
            'sqlite_cache_budget_kib':sqlite_cache_budget_kib,'sqlite_cache_budget_kind':'AGGREGATE_SUGGESTED_PAGE_CACHE_NOT_RSS_LIMIT',
            'operation_sequence':['ROOT_SNAPSHOT','VALIDATE_STRUCTURE',cache_operation,'HASH_GUARD_REUSE','VERIFY_RECONSTRUCTION','HASH_GUARD_BEFORE_PUBLISH'],
            'persistent_cache':self.persistent_lookup_cache is not None,'security_claim':'NONE'}
        if lookup_backend!='DISK':
            self.configuration['physical_lookup']={'backend':lookup_backend,'standing':'CANDIDATE_ONLY',
              'unit_mode':'TOKEN_ONLY','payload_budget_bytes':backend_payload_budget_bytes,'mmap_limit_bytes':mmap_limit_bytes,
              'scope':'EXPLICIT_LOW_LEVEL_CONTEXT_ONLY','hard_rss_limit':False,'transported_configuration_changed':False}
        self.configuration['instance_constitution_sha256']=hashlib.sha256(canonical(self.configuration)).hexdigest()
        if progress: progress({'stage':'CONTEXT_INSTANCE_COMPILED','effective_configuration':self.configuration})
        self._temporary=sio.TempDirectory(prefix='semcrys-verified-context-')
        self._directory=Path(self._temporary.name); self._rows={}; self._stacks=set(); self._closed=False
        self._active=0; self._used=set(); self._source_paths=set(); self._poisoned=False
        self.stats={'full_validations':0,'lookup_builds':0,'persistent_lookup_hits':0,'persistent_lookup_misses':0,
            'snapshot_bytes':0,'guard_checks':0,'operations':0,'prepare_seconds':0.0}
    def __enter__(self): self._check(); return self
    def _check(self):
        if self._closed or self._poisoned: refuse('HELD_CONTEXT_CLOSED_OR_INVALID')
    def __exit__(self,*exc): self.close()
    def close(self):
        # Closed means unusable, not necessarily cleaned. A later explicit close
        # may retry owned cleanup after a lock/quota problem is removed.
        self._closed=True
        failures=[]
        for row in self._rows.values():
            if 'backend' in row:
                try: row['reader'].close()
                except BaseException as exc: failures.append(type(exc).__name__)
            try: row['connection'].close()
            except BaseException as exc: failures.append(type(exc).__name__)
        self.lookup_cache.clear()
        if not failures:
            try: self._temporary.cleanup()
            except BaseException as exc: failures.append(type(exc).__name__)
        if failures:
            from .core import Refusal
            raise Refusal('HELD_CONTEXT_CLEANUP_INCOMPLETE',str(self._directory)+': '+','.join(failures))
    def protected_paths(self): return list(self._source_paths)+[r['path'] for r in self._rows.values()]+[r['database'] for r in self._rows.values()]
    def _guard(self,row):
        self._check()
        if file_sha256(row['path'])!=row['sha256'] or file_sha256(row['database'])!=row['database_sha256']:
            self._poisoned=True; refuse('HELD_CONTEXT_CUSTODY_CHANGED')
        row['reader']._check_snapshot(); self.stats['guard_checks']+=1
    def _persistent_paths(self,root):
        base=self.persistent_lookup_cache/'lookup-v1'/root[:2]
        return base/(root+'.sqlite3'),base/(root+'.json')
    def _load_persistent(self,root,size,entries):
        if self.persistent_lookup_cache is None:return None
        database,record_path=self._persistent_paths(root)
        try:
            if not database.is_file() or not record_path.is_file() or record_path.stat().st_size>16384:return None
            record=json.loads(record_path.read_text(encoding='utf-8'))
            claimed=record.get('record_root');body={k:v for k,v in record.items() if k!='record_root'}
            expected={'schema','legend_sha256','legend_bytes','entry_count','database_bytes','database_sha256','standing','authority_effect'}
            if set(body)!=expected or body['schema']!='semcrys.persistent-lookup-cache.v0.1' or body['legend_sha256']!=root or body['legend_bytes']!=size or body['entry_count']!=entries or body['standing']!='LOCAL_REUSABLE_DERIVED_CACHE' or body['authority_effect']!='NONE' or claimed!=hashlib.sha256(canonical(body)).hexdigest():return None
            if database.stat().st_size!=body['database_bytes'] or file_sha256(database)!=body['database_sha256']:return None
            connection=sio.sqlite_connect(database.as_uri()+'?mode=ro',uri=True)
            try:
                connection.execute('PRAGMA query_only=ON')
                table=connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='lookup'").fetchone()
                if table is None or 'WITHOUT ROWID' not in table[0].upper() or connection.execute('SELECT COUNT(*) FROM lookup').fetchone()[0]!=entries or connection.execute('PRAGMA quick_check').fetchone()[0]!='ok':
                    connection.close();return None
            except BaseException:
                connection.close();raise
            return database,body['database_sha256'],connection
        except (OSError,ValueError,KeyError,json.JSONDecodeError,sqlite3.DatabaseError):
            return None
    def _publish_persistent(self,root,size,entries,database,database_sha256):
        if self.persistent_lookup_cache is None:return
        target,record_path=self._persistent_paths(root);target.parent.mkdir(parents=True,exist_ok=True)
        pending=target.with_name(target.name+'.pending-'+str(os.getpid()))
        record_pending=record_path.with_name(record_path.name+'.pending-'+str(os.getpid()))
        try:
            with Path(database).open('rb') as incoming,sio.open_output(pending,'wb') as outgoing:
                for block in iter(lambda:incoming.read(1048576),b''):outgoing.write(block)
            if file_sha256(pending)!=database_sha256:refuse('HELD_PERSISTENT_LOOKUP_COPY')
            sio.replace(pending,target)
            body={'schema':'semcrys.persistent-lookup-cache.v0.1','legend_sha256':root,'legend_bytes':size,
                'entry_count':entries,'database_bytes':target.stat().st_size,'database_sha256':database_sha256,
                'standing':'LOCAL_REUSABLE_DERIVED_CACHE','authority_effect':'NONE'}
            record={**body,'record_root':hashlib.sha256(canonical(body)).hexdigest()}
            sio.write_bytes(record_pending,json.dumps(record,ensure_ascii=True,sort_keys=True,separators=(',',':')).encode())
            sio.replace(record_pending,record_path)
        finally:
            sio.unlink(pending,missing_ok=True)
            sio.unlink(record_pending,missing_ok=True)
    @contextmanager
    def operation(self):
        self._check(); outer=self._active==0
        if outer: self._used=set(); self.stats['operations']+=1
        self._active+=1
        try:
            yield self
            if outer:
                for root in sorted(self._used): self._guard(self._rows[root])
        except BaseException:
            self._poisoned=True
            raise
        finally: self._active-=1
    @invalidates_on_failure
    def prepare(self,path):
        self._check(); path=Path(path); self._source_paths.add(path.resolve())
        root=file_sha256(path)
        if root not in self._rows:
            if len(self._rows)>=self.max_legends or path.stat().st_size>self.maximum-self.stats['snapshot_bytes']:
                refuse('HELD_CONTEXT_LEGEND_BUDGET')
            started=time.perf_counter()
            if self.progress: self.progress({'stage':'LEGEND_CONTEXT_PREPARE','legend_sha256':root})
            # Identity is the full root in _rows and the verified content,
            # not the temporary filename. Compact private names avoid adding
            # 64 characters to an already long Windows temporary directory.
            local_name=f'{len(self._rows):04x}'
            target=self._directory/(local_name+'.leg'); digest=hashlib.sha256(); size=0
            with path.open('rb') as incoming,sio.open_output(target,'wb') as outgoing:
                for chunk in iter(lambda:incoming.read(1048576),b''):
                    size+=len(chunk)
                    if size>self.maximum-self.stats['snapshot_bytes']: refuse('HELD_CONTEXT_LEGEND_BUDGET')
                    digest.update(chunk); outgoing.write(chunk)
            if digest.hexdigest()!=root: refuse('HELD_CONTEXT_SOURCE_CHANGED')
            reader=LegendReader(target,lookup_cache=self.lookup_cache); verified=reader.verify(check_duplicates=False)
            if verified['sha256']!=root: refuse('HELD_CONTEXT_SOURCE_CHANGED')
            # Rebalance before opening the new builder, including it in the
            # aggregate target. SQLite targets do not bound its total allocations.
            share=min(2048,self.sqlite_cache_budget_kib//(len(self._rows)+1))
            for existing in self._rows.values(): existing['connection'].execute(f'PRAGMA cache_size=-{share}')
            self._sqlite_share_kib=share
            cached=self._load_persistent(root,size,reader.count)
            if cached is not None:
                db,database_sha256,connection=cached;self.stats['persistent_lookup_hits']+=1
            else:
                self.stats['persistent_lookup_misses']+=1
                db=self._directory/(local_name+'.sqlite3'); connection=sio.sqlite_connect(db,capacity_bytes=max(65536,min(sio.DB_CAP,8*size+65536)))
                try:
                    connection.execute('PRAGMA journal_mode=OFF'); connection.execute('PRAGMA synchronous=OFF')
                    connection.execute('PRAGMA temp_store=FILE'); connection.execute(f'PRAGMA cache_size=-{share}')
                    connection.execute('CREATE TABLE lookup(value BLOB PRIMARY KEY,id INTEGER NOT NULL) WITHOUT ROWID')
                    try: connection.executemany('INSERT INTO lookup(value,id) VALUES (?,?)',((value,i) for i,value in reader.iter_values()))
                    except sqlite3.IntegrityError: refuse('HELD_DUPLICATE_LEGEND_VALUE')
                    connection.commit()
                finally: connection.close()
                database_sha256=file_sha256(db);self.stats['lookup_builds']+=1
                self._publish_persistent(root,size,reader.count,db,database_sha256)
                connection=sio.sqlite_connect(db.as_uri()+'?mode=ro',uri=True)
            if file_sha256(target)!=root: refuse('HELD_CONTEXT_SOURCE_CHANGED')
            try:
                connection.execute('PRAGMA query_only=ON'); connection.execute(f'PRAGMA cache_size=-{share}')
                self._rows[root]={'path':target,'sha256':root,'entries':reader.count,'reader':reader,'database':db,
                    'database_sha256':database_sha256,'connection':connection}
            except BaseException:
                connection.close()
                raise
            if self.lookup_backend!='DISK':
                from .lookup_backends import activate,estimate
                mode=self.lookup_backend
                if mode=='AUTO':
                    remaining=self.backend_budget-self.backend_used
                    mode=('RAM' if estimate(self._rows[root],'RAM')<=remaining else
                          'MMAP' if estimate(self._rows[root],'MMAP')<=remaining else 'DISK')
                if mode!='DISK':
                    self.backend_used+=activate(self._rows[root],mode,self.backend_budget-self.backend_used,self.mmap_limit)
            self.stats['snapshot_bytes']+=size; self.stats['full_validations']+=1
            self.stats['prepare_seconds']+=time.perf_counter()-started
        row=self._rows[root]
        if root not in self._used or not self._active:
            self._guard(row); self._used.add(root)
        return row
    def rows(self,paths):
        return [{k:r[k] for k in ('path','sha256','entries')} for r in (self.prepare(p) for p in paths)]
    def reader(self,path): return self.prepare(path)['reader']
    def stack(self,paths):
        rows=[self.prepare(path) for path in paths]; roots=tuple(r['sha256'] for r in rows)
        if roots not in self._stacks:
            if len(set(roots))!=len(roots): refuse('HELD_DUPLICATE_VALUE_ACROSS_LEGEND_STACK')
            # Scan the smaller member of each pair; large base + tiny delta
            # requires only delta lookups, never copying the large base table.
            for i,left in enumerate(rows):
                for right in rows[i+1:]:
                    small,large=sorted((left,right),key=lambda r:r['entries'])
                    for (value,) in small['connection'].execute('SELECT value FROM lookup'):
                        if large['connection'].execute('SELECT 1 FROM lookup WHERE value=?',(value,)).fetchone():
                            refuse('HELD_DUPLICATE_VALUE_ACROSS_LEGEND_STACK')
            self._stacks.add(roots)
        return StackLookup(rows),sum(r['entries'] for r in rows)
    def verify_used(self):
        for root in sorted(self._used): self._guard(self._rows[root])
    def receipt(self):
        value={'schema':'semcrys.verified-context-receipt.v0.1','standing':'CANDIDATE_ONLY',
            'effective_configuration':self.configuration,
            'policy':self.configuration['policy'],
            'operation_sequence':self.configuration['operation_sequence'],
            'legend_roots':sorted(self._rows),'stats':dict(self.stats),'persistent_cache':self.persistent_lookup_cache is not None,
            'lookup_cache':self.lookup_cache.receipt(),
            'sqlite_cache_targets':{'connections':len(self._rows),'per_connection_kib':self._sqlite_share_kib,
                'aggregate_kib':len(self._rows)*self._sqlite_share_kib,'budget_kib':self.sqlite_cache_budget_kib,
                'hard_process_memory_limit':False},
            'artifact_bytes_changed':False,'security_claim':'NONE'}
        if self.lookup_backend!='DISK':
            value['physical_lookup']={'backend':self.lookup_backend,'rows':[r.get('backend',{'mode':'DISK','payload_estimate_bytes':0,
                'hard_rss_limit':False,'full_root_guards_retained':True}) for r in self._rows.values()],
                'payload_estimate_bytes':self.backend_used,'hard_rss_limit':False}
        return {**value,'receipt_sha256':hashlib.sha256(canonical(value)).hexdigest()}
