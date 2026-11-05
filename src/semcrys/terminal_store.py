"""Private disk-backed terminal programs and literal interning.
No canonical identity or transported ABI lives in this store.
SPDX-License-Identifier: Apache-2.0
"""
from streaming_legend import scratch_io as sio
import sqlite3
from pathlib import Path
from streaming_app.core import Refusal

MAX_ENTRIES=1_000_000
MAX_PAYLOAD=64*1024*1024
DATABASE_BYTES=256*1024*1024
CACHE_KIB=2048


class TerminalStore:
    def __init__(self,path,*,max_entries=MAX_ENTRIES,max_payload=MAX_PAYLOAD,database_bytes=DATABASE_BYTES):
        if (type(max_entries) is not int or not 0<=max_entries<=MAX_ENTRIES
            or type(max_payload) is not int or not 0<=max_payload<=MAX_PAYLOAD
            or type(database_bytes) is not int or not 12288<=database_bytes<=DATABASE_BYTES):
            raise Refusal('HELD_TERMINAL_STORE_BUDGET')
        self.path=Path(path);self.connection=None;self.count=0;self.payload_bytes=0;self.literal_count=0
        self.max_entries=max_entries;self.max_payload=max_payload;self.poisoned=False
        with sio.open_output(self.path,'xb'):pass
        try:
            self.connection=sio.sqlite_connect(self.path,capacity_bytes=max(16384,database_bytes))
            self.connection.execute('PRAGMA page_size=4096')
            self.connection.execute('PRAGMA journal_mode=OFF')
            self.connection.execute('PRAGMA synchronous=OFF')
            self.connection.execute('PRAGMA temp_store=FILE')
            self.connection.execute('PRAGMA cache_size=-'+str(CACHE_KIB))
            self.connection.execute('PRAGMA max_page_count='+str(database_bytes//4096))
            self.connection.execute('CREATE TABLE records (id INTEGER PRIMARY KEY,data BLOB NOT NULL)')
            self.connection.execute('CREATE TABLE literals (value BLOB PRIMARY KEY,id INTEGER NOT NULL) WITHOUT ROWID')
        except BaseException:
            self.close();raise

    def __enter__(self):return self
    def __exit__(self,*exc):self.close()
    def close(self):
        if self.connection is not None:self.connection.close();self.connection=None
    def __len__(self):return self.count
    def _ready(self):
        if self.connection is None or self.poisoned:raise Refusal('HELD_TERMINAL_STORE_CLOSED')
    def _sql(self,sql,args=()):
        self._ready()
        try:return self.connection.execute(sql,args)
        except sqlite3.Error as exc:
            self.poisoned=True
            if getattr(exc,'sqlite_errorcode',None)==sqlite3.SQLITE_FULL:
                raise Refusal('HELD_TERMINAL_STORE_DISK_BUDGET') from exc
            raise

    def append(self,data):
        self._ready()
        if type(data) is not bytes or len(data)>8224:raise Refusal('HELD_TERMINAL_PROGRAM_SIZE')
        if self.count>=self.max_entries or self.payload_bytes+len(data)>self.max_payload:
            raise Refusal('HELD_SECOND_PASS_LEGEND_LIMIT')
        identifier=self.count+1
        self._sql('INSERT INTO records VALUES (?,?)',(identifier,data))
        self.count=identifier;self.payload_bytes+=len(data)
        return identifier

    def intern_literal(self,value):
        self._ready()
        if type(value) is not bytes or not 1<=len(value)<=4096:raise Refusal('HELD_LITERAL_LENGTH')
        row=self._sql('SELECT id FROM literals WHERE value=?',(value,)).fetchone()
        if row is not None:return row[0],False
        identifier=self.append(b'\xff\4'+value)
        self._sql('INSERT INTO literals VALUES (?,?)',(value,identifier))
        self.literal_count+=1
        return identifier,True

    def __getitem__(self,index):
        self._ready()
        if type(index) is not int:raise TypeError('integer terminal index required')
        if index<0:index+=self.count
        if not 0<=index<self.count:raise IndexError(index)
        row=self._sql('SELECT data FROM records WHERE id=?',(index+1,)).fetchone()
        if row is None:raise Refusal('HELD_TERMINAL_STORE_MISSING')
        return row[0]

    def __iter__(self):
        cursor=self._sql('SELECT id,data FROM records ORDER BY id')
        expected=1
        try:
            for identifier,data in cursor:
                if identifier!=expected:raise Refusal('HELD_TERMINAL_STORE_ORDER')
                expected+=1;yield data
            if expected!=self.count+1:raise Refusal('HELD_TERMINAL_STORE_COUNT')
        finally:cursor.close()
