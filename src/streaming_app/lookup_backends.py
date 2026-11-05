"""Candidate physical lookup alternatives; do not change encoded identities.

New backends are opt-in through VerifiedLegendContext, plain TOKEN legends only.
Private process memory is trusted just as the existing SQLite connection is.
Payload budgets are not promises about peak RSS or SQLite allocator overhead.
"""
from array import array
import hashlib
import mmap
import sqlite3
from streaming_legend.core import LegendError

class CompactReader:
    def __init__(self, reader, mode, expected_root):
        self.base=reader; self.mode=mode; self.handle=None; self.data=None
        try:
            self.handle=reader.path.open('rb'); reader._check_snapshot(self.handle)
            self.data=mmap.mmap(self.handle.fileno(),0,access=mmap.ACCESS_READ) if mode=='MMAP' else self.handle.read()
            if hashlib.sha256(self.data).hexdigest()!=expected_root:
                raise LegendError('HELD_BACKEND_SNAPSHOT_ROOT')
            offsets=array('Q'); pos=reader.entries_start
            for _ in range(reader.count):
                offsets.append(pos); size,pos=self._length(pos)
                pos+=size
                if size>reader.max_value_bytes or pos>reader.index_offset: raise LegendError('HELD_BACKEND_VALUE_LIMIT')
            if pos!=reader.index_offset: raise LegendError('HELD_BACKEND_ENTRY_REGION')
            # Freeze the local offset array. It is a derived cache, not identity.
            self.offsets=memoryview(offsets.tobytes()).cast('Q')
            reader._check_snapshot(self.handle); reader._check_snapshot()
        except BaseException:
            self.close(); raise
    def __getattr__(self,name): return getattr(self.base,name)
    def _length(self,pos):
        value=shift=0
        while True:
            if pos>=self.base.index_offset or shift>63: raise LegendError('HELD_BACKEND_VARINT')
            b=self.data[pos]; pos+=1; value|=(b&127)<<shift
            if not b&128: return value,pos
            shift+=7
    def get(self,identifier):
        if self.data is None: raise LegendError('HELD_BACKEND_CLOSED')
        if type(identifier) is not int or not 1<=identifier<=self.base.count: raise LegendError('HELD_LEGEND_ID_RANGE')
        self.base._check_snapshot();self.base._check_snapshot(self.handle)
        size,pos=self._length(self.offsets[identifier-1])
        return self.data[pos:pos+size]
    def get_many(self,identifiers):
        if self.data is None: raise LegendError('HELD_BACKEND_CLOSED')
        values=[];self.base._check_snapshot();self.base._check_snapshot(self.handle)
        for identifier in identifiers:
            if type(identifier) is not int or not 1<=identifier<=self.base.count: raise LegendError('HELD_LEGEND_ID_RANGE')
            size,pos=self._length(self.offsets[identifier-1])
            values.append(self.data[pos:pos+size])
        self.base._check_snapshot();self.base._check_snapshot(self.handle)
        return values
    def close(self):
        data=self.data;self.data=None
        if isinstance(data,mmap.mmap): data.close()
        if self.handle is not None: self.handle.close();self.handle=None
        if 'offsets' in self.__dict__: self.offsets.release();del self.offsets

def estimate(row, mode):
    if mode not in ('MMAP','RAM'): raise LegendError('HELD_BACKEND_MODE')
    db_size=row['database'].stat().st_size; leg_size=row['path'].stat().st_size
    return 16*row['entries']+(leg_size+db_size if mode=='RAM' else 0)

def activate(row, mode, remaining, mmap_limit):
    if row['reader'].header['unit_mode']!='TOKEN': raise LegendError('HELD_BACKEND_UNIT_MODE')
    db_size=row['database'].stat().st_size; leg_size=row['path'].stat().st_size
    # Include immutable offset storage and its construction array at peak.
    payload_estimate=estimate(row,mode)
    if payload_estimate>remaining: raise LegendError('HELD_BACKEND_PAYLOAD_BUDGET')
    compact=CompactReader(row['reader'],mode,row['sha256']); replacement=None
    try:
        if mode=='RAM':
            replacement=sqlite3.connect(':memory:')
            row['connection'].backup(replacement)
            replacement.execute('PRAGMA query_only=ON')
            replacement.execute('PRAGMA temp_store=MEMORY')
            old=row['connection'];row['connection']=replacement;replacement=None;old.close()
            effective_mmap=0
        else:
            result=row['connection'].execute(f'PRAGMA mmap_size={mmap_limit}').fetchone()
            effective_mmap=result[0] if result else 0
            if not effective_mmap: raise LegendError('HELD_BACKEND_MMAP_UNAVAILABLE')
        row['reader']=compact
        row['backend']={'mode':mode,'payload_estimate_bytes':payload_estimate,'offset_bytes':8*row['entries'],
          'legend_bytes':leg_size,'sqlite_database_bytes':db_size,'sqlite_mmap_bytes':effective_mmap,
          'hard_rss_limit':False,'full_root_guards_retained':True}
        return payload_estimate
    except BaseException:
        if replacement is not None: replacement.close()
        compact.close();raise
