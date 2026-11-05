"""Scoped scratch I/O adapters. Not an OS sandbox or an RSS guarantee."""
import contextvars,os,shutil,sqlite3,tempfile
from pathlib import Path
from contextlib import contextmanager
from .scratch_budget import ScratchBudget,ScratchError
ACTIVE=contextvars.ContextVar('semcrys_scratch',default=None)
DEFAULT_LIMIT=4*1024**3
DB_CAP=256*1024**2
POLICY={'schema':'semcrys.scratch-policy.v0.1','logical_file_growth':'RESERVE_BEFORE_WRITE',
 'native_database':'RESERVE_MAX_PAGE_COUNT','native_temporary_btrees':'REFUSE_UNACCOUNTED_TEMP_PLANS',
 'physical_filesystem_overhead_counted':False,'process_rss_limit':False,'canonical_effect':'NONE'}

def validate_limit(limit):
    if type(limit) is not int or not 0<=limit<=1<<40:raise ScratchError('HELD_SCRATCH_INVALID_LIMIT')

class Scope(ScratchBudget):
    def __init__(self,root,limit,publication=None,operation_scope='EXPLICIT_ARCHIVE_ADAPTERS'):
        validate_limit(limit)
        super().__init__(root,limit)
        self.publication=Path(publication).absolute() if publication is not None else None
        self.operation_scope=operation_scope
        self.fds={};self.databases={};self.connections=set();self.token=None
    def __enter__(self):
        if ACTIVE.get() is not None:raise ScratchError('HELD_SCRATCH_NESTED_ROOT')
        self.token=ACTIVE.set(self);return self
    def __exit__(self,*exc):
        ACTIVE.reset(self.token)
    def directory(self,p):
        p=Path(p).absolute()
        return self.root if p==self.root else self._path(p)
    def check_closed(self,p):
        p=self._path(p)
        if any((f==p or p in f.parents) and r['active'] for f,r in self._files.items()):
            raise ScratchError('HELD_SCRATCH_FILE_BUSY')
        if any(c._budget_path==p or p in c._budget_path.parents for c in self.connections):
            raise ScratchError('HELD_SCRATCH_DATABASE_BUSY')
    def enroll_empty(self,p):
        p=self._path(p)
        if p.stat().st_size:raise ScratchError('HELD_SCRATCH_UNOWNED_FILE')
        if p not in self._files:self._files[p]={'bytes':0,'active':False}
        return p
    def release_deleted(self,p):
        p=self._path(p)
        for path,row in list(self._files.items()):
            if path==p or p in path.parents:
                if path.exists():raise ScratchError('HELD_SCRATCH_CLEANUP_INCOMPLETE')
                self.used-=row['bytes'];del self._files[path]
        for path,label in list(self.databases.items()):
            if path==p or p in path.parents:
                if path.exists():raise ScratchError('HELD_SCRATCH_CLEANUP_INCOMPLETE')
                self.release_native(label);del self.databases[path]
    def outcome(self):
        return {**self.receipt(),'adapter_policy':POLICY,
          'native_databases':len(self.databases),'scope':self.operation_scope,
          'public_application_integrated':True}

def open_output(path,mode='wb'):
    scope=ACTIVE.get()
    return Path(path).open(mode) if scope is None else scope.open(path,mode)

def write_bytes(path,data):
    with open_output(path,'wb') as f:return f.write(data)

def copy2(source,target):
    scope=ACTIVE.get()
    if scope is None:return shutil.copy2(source,target)
    with Path(source).open('rb') as incoming,open_output(target,'wb') as out:
        shutil.copyfileobj(incoming,out,1024*1024)
    shutil.copystat(source,target)
    return str(target)

def unlink(path,missing_ok=False):
    scope=ACTIVE.get()
    p=Path(path)
    if scope is None:return p.unlink(missing_ok=missing_ok)
    p=scope._path(p)
    scope.check_closed(p)
    if p.exists():p.unlink()
    elif not missing_ok:raise FileNotFoundError(p)
    scope.release_deleted(p)

def rmtree(path,*args,**kwargs):
    scope=ACTIVE.get()
    if scope is not None:
        path=scope._path(path);scope.check_closed(path)
    shutil.rmtree(path,*args,**kwargs)
    if scope is not None:scope.release_deleted(path)

def replace(source,target,*,directory_rename=None):
    scope=ACTIVE.get()
    if scope is None:return os.replace(source,target)
    source=scope._path(source);target=Path(target).absolute()
    if source.is_dir():
        scope.check_closed(source)
        outside=target==scope.publication
        if not outside:target=scope._path(target)
        for p,r in scope._files.items():
            if (p==source or source in p.parents) and r['active']:
                raise ScratchError('HELD_SCRATCH_FILE_BUSY')
        (directory_rename or os.rename)(source,target)
        for p,r in list(scope._files.items()):
            if p==source or source in p.parents:
                del scope._files[p]
                if outside:scope.used-=r['bytes']
                else:scope._files[target/p.relative_to(source)]=r
        for p,label in list(scope.databases.items()):
            if p==source or source in p.parents:
                del scope.databases[p]
                if outside:scope.release_native(label)
                else:scope.databases[target/p.relative_to(source)]=label
        return
    if target==scope.publication and not target.is_relative_to(scope.root):
        # Sole explicitly nominated file destination. The public transaction
        # controls caller overwrite consent; never grant arbitrary path escape.
        with scope._lock:
            scope._ready();scope.check_closed(source)
            row=scope._files.get(source)
            if row is None:raise ScratchError('HELD_SCRATCH_UNOWNED_FILE')
            if source.stat().st_size!=row['bytes']:
                scope.poisoned=True;raise ScratchError('HELD_SCRATCH_FILE_CHANGED')
            if target.is_symlink() or (target.exists() and not target.is_file()):
                raise ScratchError('HELD_SCRATCH_PUBLICATION_TARGET')
            os.replace(source,target)
            scope.used-=row['bytes'];del scope._files[source]
        return
    return scope.replace(source,target)

def mkstemp(*args,**kwargs):
    scope=ACTIVE.get()
    if scope is not None:
        kwargs['dir']=scope.root if kwargs.get('dir') is None else scope.directory(kwargs['dir'])
        kwargs['prefix']='s-'
    fd,name=tempfile.mkstemp(*args,**kwargs)
    if scope is not None:
        scope.enroll_empty(name);scope.fds[fd]=Path(name)
    return fd,name

def close_fd(fd):
    os.close(fd)
    scope=ACTIVE.get()
    if scope is not None:scope.fds.pop(fd,None)

def fdopen_output(fd,mode='wb'):
    scope=ACTIVE.get()
    if scope is None:return os.fdopen(fd,mode)
    path=scope.fds.pop(fd,None)
    if path is None:raise ScratchError('HELD_SCRATCH_UNENROLLED_FD')
    os.close(fd)
    return scope.open(path,mode)

class TempDirectory:
    def __init__(self,*args,**kwargs):
        self.scope=ACTIVE.get()
        if self.scope is not None:
            # Independent private directories stay under the same quota root;
            # flattening also avoids Windows MAX_PATH growth through decoders.
            kwargs['dir']=self.scope.root;kwargs['prefix']='t-'
        self.inner=tempfile.TemporaryDirectory(*args,**kwargs);self.name=self.inner.name
    def __enter__(self):return self.name
    def __exit__(self,*exc):self.cleanup()
    def cleanup(self):
        if self.scope is not None:self.scope.check_closed(self.name)
        self.inner.cleanup()
        if self.scope is not None:self.scope.release_deleted(self.name)

@contextmanager
def temporary_file(mode='w+b',dir=None):
    scope=ACTIVE.get()
    if scope is None:
        with tempfile.TemporaryFile(mode=mode,dir=dir) as f:yield f
    else:
        fd,name=mkstemp(dir=dir);os.close(fd);scope.fds.pop(fd,None)
        try:
            with scope.open(name,'r+b') as f:yield f
        finally:unlink(name,missing_ok=True)

class BudgetConnection(sqlite3.Connection):
    def configure_budget(self,scope,path,capacity,readonly=False):
        self._scope=scope;self._budget_path=path;self._plans=set();self._closed=False
        self._readonly=readonly
        self._capacity=capacity;self._initializing=True
        try:
            super().execute('PRAGMA temp_store=FILE')
            if readonly:super().execute('PRAGMA query_only=ON')
            else:
                super().execute('PRAGMA page_size=4096')
                super().execute('PRAGMA journal_mode=OFF')
                super().execute('PRAGMA synchronous=OFF')
                n=super().execute('PRAGMA max_page_count='+str(capacity//4096)).fetchone()[0]
                if n*4096>capacity:raise ScratchError('HELD_SCRATCH_DATABASE_CAP')
        finally:self._initializing=False
        scope.connections.add(self)
    def _check_sql(self,sql,params):
        self._scope._ready()
        key=sql.strip().upper()
        if key.startswith('PRAGMA '):
            compact=''.join(key.split()).rstrip(';')
            if self._readonly and not (compact.startswith('PRAGMACACHE_SIZE=') or compact in
                ('PRAGMAQUERY_ONLY=ON','PRAGMAPAGE_COUNT','PRAGMAPAGE_SIZE','PRAGMAMAX_PAGE_COUNT')):
                raise ScratchError('HELD_SCRATCH_DATABASE_READ_ONLY')
            if compact.startswith('PRAGMAJOURNAL_MODE=') and compact!='PRAGMAJOURNAL_MODE=OFF':
                raise ScratchError('HELD_SCRATCH_DATABASE_JOURNAL')
            if compact.startswith('PRAGMATEMP_STORE=') and compact!='PRAGMATEMP_STORE=FILE':
                raise ScratchError('HELD_SCRATCH_DATABASE_TEMP')
            if compact.startswith('PRAGMAMAX_PAGE_COUNT='):
                try:requested=int(compact.split('=',1)[1])
                except ValueError:raise ScratchError('HELD_SCRATCH_DATABASE_CAP') from None
                if requested*4096>self._capacity:raise ScratchError('HELD_SCRATCH_DATABASE_CAP')
                if requested<1:raise ScratchError('HELD_SCRATCH_DATABASE_CAP')
            allowed=('PRAGMAPAGE_SIZE=4096','PRAGMAJOURNAL_MODE=OFF','PRAGMASYNCHRONOUS=OFF',
                     'PRAGMATEMP_STORE=FILE','PRAGMAQUERY_ONLY=ON')
            if not (compact in allowed or compact.startswith(('PRAGMACACHE_SIZE=','PRAGMAMAX_PAGE_COUNT='))
                    or compact in ('PRAGMAPAGE_COUNT','PRAGMAPAGE_SIZE','PRAGMAMAX_PAGE_COUNT')):
                raise ScratchError('HELD_SCRATCH_DATABASE_PRAGMA')
            return
        if self._readonly and not key.startswith('SELECT '):
            raise ScratchError('HELD_SCRATCH_DATABASE_READ_ONLY')
        if key.startswith(('CREATE TABLE ','CREATE TABLE IF NOT EXISTS ')):
            if any(word in key for word in (' TEMP ','VIRTUAL','SELECT',';','--','/*')):
                raise ScratchError('HELD_SCRATCH_DATABASE_TEMP')
            self._plans.clear();return
        if key in ('BEGIN','COMMIT','ROLLBACK'):return
        if not key.startswith(('SELECT ','INSERT ','DELETE ','UPDATE ')):
            raise ScratchError('HELD_SCRATCH_DATABASE_OPERATION')
        if sql not in self._plans:
            plan=super().execute('EXPLAIN '+sql,params).fetchall()
            if any(r[1] in ('SorterOpen','OpenEphemeral','OpenAutoindex') for r in plan):
                raise ScratchError('HELD_SCRATCH_DATABASE_TEMP_PLAN')
            self._plans.add(sql)
    def execute(self,sql,parameters=()):
        self._check_sql(sql,parameters)
        try:return ResultCursor(self,super().execute(sql,parameters))
        except sqlite3.Error as e:
            if getattr(e,'sqlite_errorcode',None)==sqlite3.SQLITE_FULL:
                self._scope.poisoned=True;raise ScratchError('HELD_SCRATCH_DATABASE_CAP') from e
            raise
    def executemany(self,sql,parameters):
        values=iter(parameters)
        try:first=next(values)
        except StopIteration:
            self._scope._ready()
            return ResultCursor(self,super().executemany(sql,()))
        self._check_sql(sql,first)
        import itertools
        try:return ResultCursor(self,super().executemany(sql,itertools.chain([first],values)))
        except sqlite3.Error as e:
            if getattr(e,'sqlite_errorcode',None)==sqlite3.SQLITE_FULL:
                self._scope.poisoned=True;raise ScratchError('HELD_SCRATCH_DATABASE_CAP') from e
            raise
    def cursor(self,*args,**kwargs):
        raise ScratchError('HELD_SCRATCH_DATABASE_CURSOR_ADAPTER_REQUIRED')
    def executescript(self,*args,**kwargs):
        raise ScratchError('HELD_SCRATCH_DATABASE_SCRIPT')
    def close(self):
        if not self._closed:
            super().close();self._closed=True;self._scope.connections.discard(self)
            # Main DB remains charged until deletion; closed capacity may be
            # reduced to its actual immutable file size.
            label=self._scope.databases.get(self._budget_path)
            if label is not None and self._budget_path.exists():
                old=self._scope._native[label];new=self._budget_path.stat().st_size
                if new>old:raise ScratchError('HELD_SCRATCH_DATABASE_CAP')
                self._scope.used-=old-new;self._scope._native[label]=new

class ResultCursor:
    """Only fetch/iterate/close; no secondary unguarded SQL entry point."""
    def __init__(self,connection,cursor):self.connection=connection;self._cursor=cursor
    @property
    def rowcount(self):return self._cursor.rowcount
    def fetchone(self):return self._cursor.fetchone()
    def fetchall(self):return self._cursor.fetchall()
    def fetchmany(self,*args):return self._cursor.fetchmany(*args)
    def close(self):return self._cursor.close()
    def __iter__(self):return self
    def __next__(self):return next(self._cursor)
    def execute(self,*args,**kwargs):raise ScratchError('HELD_SCRATCH_DATABASE_CURSOR_ADAPTER_REQUIRED')
    def executemany(self,*args,**kwargs):raise ScratchError('HELD_SCRATCH_DATABASE_CURSOR_ADAPTER_REQUIRED')
    def executescript(self,*args,**kwargs):raise ScratchError('HELD_SCRATCH_DATABASE_SCRIPT')

def sqlite_connect(path,*args,capacity_bytes=DB_CAP,**kwargs):
    scope=ACTIVE.get()
    if scope is None:return sqlite3.connect(path,*args,**kwargs)
    if 'factory' in kwargs or args:raise ScratchError('HELD_SCRATCH_DATABASE_CONNECT_OPTIONS')
    if kwargs.get('uri'):
        matches=[p for p in scope.databases if p.as_uri()+'?mode=ro'==str(path)]
        if len(matches)!=1:raise ScratchError('HELD_SCRATCH_DATABASE_URI')
        p=matches[0];scope.check_closed(p);scope._ready()
        connection=sqlite3.connect(path,factory=BudgetConnection,**kwargs)
        try:connection.configure_budget(scope,p,scope._native[scope.databases[p]],readonly=True)
        except BaseException:sqlite3.Connection.close(connection);raise
        return connection
    if type(capacity_bytes) is not int or capacity_bytes<16384:raise ScratchError('HELD_SCRATCH_DATABASE_CAP')
    p=scope._path(path);capacity=(capacity_bytes//4096)*4096
    if p in scope.databases:raise ScratchError('HELD_SCRATCH_DATABASE_REOPEN_WRITE')
    if p.exists() and p.stat().st_size:raise ScratchError('HELD_SCRATCH_UNOWNED_DATABASE')
    # mkstemp/RecordPool can have enrolled an empty file; its native allowance
    # replaces that zero-length file record.
    row=scope._files.get(p)
    if row is not None:
        if row['bytes'] or row['active']:raise ScratchError('HELD_SCRATCH_FILE_BUSY')
        del scope._files[p]
    label='sqlite:'+str(p);scope.reserve_native(label,capacity);scope.databases[p]=label
    connection=None
    try:
        connection=sqlite3.connect(p,*args,factory=BudgetConnection,**kwargs)
        connection.configure_budget(scope,p,capacity)
        return connection
    except BaseException:
        if connection is not None:
            sqlite3.Connection.close(connection)
        if p.exists():p.unlink()
        scope.release_deleted(p)
        raise
