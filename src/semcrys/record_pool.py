"""Disk-backed exact byte pool; local IDs are not semantic identities.
SPDX-License-Identifier: Apache-2.0
"""
from streaming_legend import scratch_io as sio
import sqlite3
from pathlib import Path
from streaming_app.core import Refusal

MAX_ENTRIES=1000000
DATABASE_BYTES=256*1024*1024
CACHE_KIB=2048
RESOURCE_POLICY={
 'container_literals':'BOUNDED_FILE_SPANS','span_copy_block_bytes':1024*1024,
 'pool_and_index':'DISK_SQLITE_BLOB_ORDER','pool_database_limit_bytes':DATABASE_BYTES,
 'pool_cache_target_kib':CACHE_KIB,'cache_is_hard_rss_limit':False,
 'whole_application_resource_bound':False,'aggregate_temporary_storage_bound':False}

class RecordPool:
    def __init__(self,path,*,database_bytes=DATABASE_BYTES):
        if type(database_bytes) is not int or not 16384<=database_bytes<=DATABASE_BYTES:
            raise Refusal('HELD_META_POOL_BUDGET')
        self.path=Path(path);self.connection=None;self.required_count=0;self.count=0;self.built=False;self.poisoned=False
        with sio.open_output(self.path,'xb'):pass
        try:
            self.connection=sio.sqlite_connect(self.path,capacity_bytes=database_bytes)
            self.connection.execute('PRAGMA page_size=4096')
            self.connection.execute('PRAGMA journal_mode=OFF')
            self.connection.execute('PRAGMA synchronous=OFF')
            self.connection.execute('PRAGMA temp_store=FILE')
            self.connection.execute('PRAGMA cache_size=-'+str(CACHE_KIB))
            self.connection.execute('PRAGMA max_page_count='+str(database_bytes//4096))
            self.connection.execute('CREATE TABLE required (value BLOB PRIMARY KEY) WITHOUT ROWID')
            self.connection.execute('CREATE TABLE pool (value BLOB PRIMARY KEY,id INTEGER NOT NULL UNIQUE) WITHOUT ROWID')
        except BaseException:self.close();raise
    def __enter__(self):return self
    def __exit__(self,*exc):self.close()
    def close(self):
        if self.connection is not None:self.connection.close();self.connection=None
    def _ready(self):
        if self.connection is None or self.poisoned:raise Refusal('HELD_META_POOL_CLOSED')
    def _sql(self,sql,args=()):
        self._ready()
        try:return self.connection.execute(sql,args)
        except sqlite3.Error as exc:
            self.poisoned=True
            if getattr(exc,'sqlite_errorcode',None)==sqlite3.SQLITE_FULL:
                raise Refusal('HELD_META_POOL_DISK_BUDGET') from exc
            raise
    def add_required(self,value):
        if self.built:raise Refusal('HELD_META_POOL_FROZEN')
        if type(value) is not bytes:raise Refusal('HELD_META_POOL_VALUE')
        inserted=self._sql('INSERT OR IGNORE INTO required VALUES (?)',(value,)).rowcount
        self.required_count+=inserted
        if self.required_count>MAX_ENTRIES:raise Refusal('HELD_META_LIMIT')
    def required_values(self):
        cursor=self._sql('SELECT value FROM required ORDER BY value')
        try:
            for (value,) in cursor:yield value
        finally:cursor.close()
    def build(self,shared_values=None):
        if self.built:raise Refusal('HELD_META_POOL_FROZEN')
        stream=iter(self.required_values() if shared_values is None else shared_values)
        try:
            for value in stream:
                if type(value) is not bytes:raise Refusal('HELD_META_POOL_VALUE')
                if self.count>=MAX_ENTRIES:raise Refusal('HELD_META_LIMIT')
                self._sql('INSERT INTO pool VALUES (?,?)',(value,self.count+1));self.count+=1
            missing=self._sql('SELECT 1 FROM required LEFT JOIN pool USING(value) WHERE pool.id IS NULL LIMIT 1').fetchone()
            if missing is not None:raise Refusal('HELD_META_SHARED_POOL_COVERAGE')
            self.built=True
        except BaseException:
            self.poisoned=True;raise
        finally:
            if hasattr(stream,'close'):stream.close()
    def values(self):
        if not self.built:raise Refusal('HELD_META_POOL_NOT_BUILT')
        cursor=self._sql('SELECT value FROM pool ORDER BY id')
        try:
            for (value,) in cursor:yield value
        finally:cursor.close()
    def __getitem__(self,value):
        if not self.built:raise Refusal('HELD_META_POOL_NOT_BUILT')
        row=self._sql('SELECT id FROM pool WHERE value=?',(value,)).fetchone()
        if row is None:raise Refusal('HELD_META_SHARED_POOL_COVERAGE')
        return row[0]
