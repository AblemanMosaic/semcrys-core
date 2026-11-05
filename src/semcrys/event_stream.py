"""Private disk-backed second-pass events, not a transported codec.
SPDX-License-Identifier: Apache-2.0
"""
import sqlite3
import heapq
import struct
from array import array
from contextlib import closing
from pathlib import Path

from streaming_app.core import Refusal
from streaming_legend.assembly import MAX_PAIR_DEPTH, MAX_PAIR_VALUE
from streaming_legend import scratch_io as sio
from streaming_legend import block_output

MAX_ENTRIES = 1_000_000
BLOCK_EVENTS = 16384
COUNT_BATCH = 4096
CACHE_KIB = 2048
DATABASE_BYTES = 128 * 1024 * 1024
U32 = struct.Struct('<I')
RESOURCE_POLICY = {
    'event_storage': 'PRIVATE_U32_LE_SPOOL_NOT_WIRE_FORMAT',
    'event_read_block_bytes': BLOCK_EVENTS * 4,
    'sequential_output_block_bytes': block_output.BLOCK_BYTES,
    'output_block_policy': 'COALESCE_BEFORE_QUOTA_CHECKED_WRITE; DISCARD_PENDING_ON_ERROR',
    'count_storage': 'SQLITE_WITH_FIRST_OCCURRENCE_TIEBREAK',
    'count_batch_max_distinct_pairs': COUNT_BATCH,
    'sqlite_cache_target_kib': CACHE_KIB,
    'sqlite_database_limit_bytes': DATABASE_BYTES,
    'sqlite_cache_is_hard_rss_limit': False,
    'count_ranking': 'STREAMING_TOP_K_COUNT_DESC_FIRST_OCCURRENCE_ASC_NO_SQL_TEMP_SORT',
    'standalone_aggregate_scratch_quota': True,
    'terminal_program_table': 'DISK_SQLITE_WITH_LITERAL_INDEX',
    'terminal_database_limit_bytes': 256 * 1024 * 1024,
    'terminal_sqlite_cache_target_kib': 2048,
    'metadata_arrays': 'UINT32_LENGTH_UINT8_DEPTH',
    'metadata_logical_max_bytes_per_set': 5 * MAX_ENTRIES,
    'metadata_sets_live': 2,
    'metadata_bound_excludes_allocator_overhead': True,
    'whole_application_streaming': False,
}


class EventSpool:
    """Reiterable bounded-block event source; length is verified on every read."""
    def __init__(self, path, count):
        self.path, self.count = Path(path), count
        if type(count) is not int or not 0 <= count <= MAX_ENTRIES:
            raise Refusal('HELD_EVENT_SPOOL_COUNT')

    def __len__(self):
        return self.count

    def __iter__(self):
        with self.path.open('rb') as source:
            remaining = self.count
            while remaining:
                amount = min(remaining, BLOCK_EVENTS)
                data = source.read(amount * 4)
                if len(data) != amount * 4:
                    raise Refusal('HELD_EVENT_SPOOL_TRUNCATED')
                for (identifier,) in struct.iter_unpack('<I', data):
                    if not 1 <= identifier <= MAX_ENTRIES:
                        raise Refusal('HELD_EVENT_SPOOL_ID')
                    yield identifier
                remaining -= amount
            if source.read(1):
                raise Refusal('HELD_EVENT_SPOOL_TRAILING')

    @classmethod
    def write(cls, path, events, *, limit=MAX_ENTRIES):
        path = Path(path)
        if type(limit) is not int or not 0 <= limit <= MAX_ENTRIES:
            raise Refusal('HELD_EVENT_SPOOL_COUNT')
        # Exclusive creation: never overwrite caller input or another spool.
        stream = iter(events)
        with block_output.open_output(path,'xb') as output:
            count = 0
            try:
                for identifier in stream:
                    if type(identifier) is not int or not 1 <= identifier <= MAX_ENTRIES:
                        raise Refusal('HELD_EVENT_SPOOL_ID')
                    count += 1
                    if count > limit:
                        raise Refusal('HELD_SECOND_PASS_LIMIT')
                    output.write(U32.pack(identifier))
            except BaseException:
                # Outer private workspace owns removal, including interrupted writes.
                raise
            finally:
                if hasattr(stream, 'close'):
                    stream.close()
        return cls(path, count)


class DiskCounts:
    """Bounded in-process batches; SQL preserves Counter's first-seen tie order."""
    def __init__(self, path, *, database_bytes=DATABASE_BYTES):
        self.path = Path(path)
        self.connection = None
        if type(database_bytes) is not int or database_bytes < 8192:
            raise Refusal('HELD_EVENT_COUNTER_BUDGET')
        with sio.open_output(self.path,'xb'):
            pass
        try:
            self.connection = sio.sqlite_connect(self.path,capacity_bytes=max(16384,database_bytes))
            self.connection.execute('PRAGMA page_size=4096')
            self.connection.execute('PRAGMA journal_mode=OFF')
            self.connection.execute('PRAGMA synchronous=OFF')
            self.connection.execute('PRAGMA temp_store=FILE')
            self.connection.execute('PRAGMA cache_size=-' + str(CACHE_KIB))
            self.connection.execute('PRAGMA max_page_count=' + str(database_bytes // 4096))
            self.connection.execute('CREATE TABLE counts (a INTEGER,b INTEGER,n INTEGER,first INTEGER,PRIMARY KEY(a,b)) WITHOUT ROWID')
            self.max_batch = 0
        except BaseException:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def count(self, pairs):
        pending = {}
        try:
            self.connection.execute('DELETE FROM counts')
            def flush():
                self.max_batch = max(self.max_batch, len(pending))
                self.connection.executemany(
                    'INSERT INTO counts VALUES (?,?,?,?) ON CONFLICT(a,b) DO UPDATE SET n=counts.n+excluded.n',
                    ((a,b,n,first) for (a,b),(n,first) in pending.items()))
                pending.clear()
            for ordinal, pair in enumerate(pairs):
                if pair in pending:
                    pending[pair][0] += 1
                else:
                    pending[pair] = [1, ordinal]
                if len(pending) >= COUNT_BATCH:
                    flush()
            if pending:
                flush()
            self.connection.commit()
        except sqlite3.Error as exc:
            if getattr(exc, 'sqlite_errorcode', None) == sqlite3.SQLITE_FULL:
                raise Refusal('HELD_EVENT_COUNTER_DISK_BUDGET') from exc
            raise
        finally:
            if hasattr(pairs, 'close'):
                pairs.close()
        return self

    def top(self, limit):
        # Do not let SQLite spill a temporary sort outside the reserved main DB.
        # Production requests only k=1 or k=3; retain bounded generic inspection.
        if type(limit) is not int or not 0<=limit<=MAX_ENTRIES:
            raise Refusal('HELD_EVENT_COUNTER_TOP_LIMIT')
        with closing(self.connection.execute('SELECT a,b,n,first FROM counts')) as rows:
            chosen=heapq.nsmallest(limit,rows,key=lambda row:(-row[2],row[3]))
        return [(a,b,n) for a,b,n,_ in chosen]

    def maximum(self):
        return self.connection.execute('SELECT COALESCE(MAX(n),0) FROM counts').fetchone()[0]


def dispersion_disk(events, path):
    with DiskCounts(path) as counts, closing(iter(events)) as stream:
        counts.count((n,0) for n in stream)
        return counts.maximum() / max(len(events), 1)


def fractionate_disk(events, sizes, *, workspace, rounds, min_count, hot_only,
                     progress=None, initial_depths=None):
    work = Path(workspace)
    work.mkdir()  # new private arm workspace only
    if len(sizes)>MAX_ENTRIES or any(type(n) is not int or not 0<=n<=MAX_PAIR_VALUE for n in sizes):
        raise Refusal('HELD_PAIR_INITIAL_LENGTHS')
    if initial_depths is not None and (len(initial_depths) != len(sizes) or
        any(type(d) is not int or not 0 <= d < MAX_PAIR_DEPTH for d in initial_depths)):
        raise Refusal('HELD_PAIR_INITIAL_DEPTHS')
    lengths = array('I', sizes)
    if lengths.itemsize!=4:raise Refusal('HELD_TERMINAL_METADATA_WIDTH')
    depths = bytearray(initial_depths) if initial_depths is not None else bytearray(len(sizes))
    sequence = events
    mapping = []
    with DiskCounts(work / 'counts.sqlite') as counts:
        hot = None
        if hot_only:
            with closing(iter(events)) as stream:
                counts.count((n,0) for n in stream)
            hot = {a for a,_,_ in counts.top(hot_only)}
        for step in range(rounds):
            def adjacent():
                with closing(iter(sequence)) as stream:
                    a = next(stream, None)
                    for b in stream:
                        if not 1 <= a <= len(lengths) or not 1 <= b <= len(lengths):
                            raise Refusal('HELD_BODY_ID_RANGE')
                        if ((hot is None or a in hot or b in hot)
                            and lengths[a-1] + lengths[b-1] <= MAX_PAIR_VALUE
                            and max(depths[a-1], depths[b-1]) + 1 < MAX_PAIR_DEPTH):
                            yield a,b
                        a = b
            counts.count(adjacent())
            best = counts.top(1)
            if not best:
                break
            a,b,number = best[0]
            if number < min_count or len(lengths) >= MAX_ENTRIES:
                break
            new = len(lengths) + 1
            def replacement():
                with closing(iter(sequence)) as stream:
                    current = next(stream, None)
                    while current is not None:
                        following = next(stream, None)
                        if current == a and following == b:
                            yield new
                            current = next(stream, None)
                        else:
                            yield current
                            current = following
            result = EventSpool.write(work / ('round-' + str(step) + '.events'), replacement())
            # Both readers are closed before exact owned-intermediate deletion.
            if sequence is not events:
                sio.unlink(sequence.path)
            sequence = result
            mapping.append((a,b))
            lengths.append(lengths[a-1] + lengths[b-1])
            depths.append(max(depths[a-1], depths[b-1]) + 1)
            if progress and (step % 20 == 0 or step == rounds - 1):
                progress({'stage':'SECOND_PASS_FRACTIONATION','round':step+1,
                          'events':len(sequence),'hot_only':hot_only})
    return sequence, mapping
