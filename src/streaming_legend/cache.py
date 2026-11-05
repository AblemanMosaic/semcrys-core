"""Context-owned LRU for exact retained block payload and span-count budgets.

Not a total Python, SQLite, process-RSS or transient parsing memory limit.
Single owning thread; internal mechanism only. No serialized artifact effect.
"""
from collections import OrderedDict
class SharedLookupCache:
    def __init__(self,max_bytes=8*1024*1024,max_entries=32768):
        for value in (max_bytes,max_entries):
            if type(value) is not int or not 0<=value<=1<<40: raise ValueError('HELD_LOOKUP_CACHE_LIMIT')
        self.max_bytes=max_bytes; self.max_entries=max_entries; self._owners=OrderedDict()
        self.bytes=0; self.entries=0; self.peak_bytes=0; self.peak_entries=0; self.evictions=0
    def release(self,owner):
        old=self._owners.pop(owner,None)
        if old is not None: self.bytes-=old[0]; self.entries-=old[1]
        owner._lookup_block=None
    def reserve(self,owner,size,count):
        self.release(owner)
        if size>self.max_bytes or count>self.max_entries: return False
        while self.bytes+size>self.max_bytes or self.entries+count>self.max_entries:
            oldest=next(iter(self._owners)); self.release(oldest); self.evictions+=1
        self._owners[owner]=(size,count); self.bytes+=size; self.entries+=count
        self.peak_bytes=max(self.peak_bytes,self.bytes); self.peak_entries=max(self.peak_entries,self.entries)
        return True
    def touch(self,owner):
        if owner in self._owners: self._owners.move_to_end(owner)
    def clear(self):
        for owner in list(self._owners): self.release(owner)
    def receipt(self):
        return {'max_bytes':self.max_bytes,'max_entries':self.max_entries,'retained_bytes':self.bytes,
            'retained_entries':self.entries,'peak_reserved_bytes':self.peak_bytes,'peak_reserved_entries':self.peak_entries,
            'owners':len(self._owners),'evictions':self.evictions,'scope':'RETAINED_SERIALIZED_BLOCKS_AND_SPAN_COUNTS_NOT_TOTAL_RSS'}
