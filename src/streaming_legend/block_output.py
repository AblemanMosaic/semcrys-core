"""Bounded sequential coalescing above, never instead of, quota-checked I/O.
SPDX-License-Identifier: Apache-2.0
"""
from contextlib import contextmanager
from . import scratch_io as sio
from .scratch_budget import ScratchError

BLOCK_BYTES=64*1024


class BlockWriter:
    """Write-only adapter; caller owns the sink. No seek or file-descriptor API."""
    def __init__(self,sink,block_bytes=BLOCK_BYTES):
        if type(block_bytes) is not int or not 1<=block_bytes<=BLOCK_BYTES:
            raise ScratchError('HELD_OUTPUT_BLOCK_LIMIT')
        self.sink=sink;self.block_bytes=block_bytes;self.pending=bytearray();self.closed=False
    def _ready(self):
        if self.closed:raise ValueError('I/O operation on closed block writer')
    def _send(self,data):
        try:
            if self.sink.write(data)!=len(data):raise ScratchError('HELD_SCRATCH_SHORT_WRITE')
        except BaseException:
            # A failed sink may retain a memoryview in its traceback. Detach
            # rather than resize that exported buffer and mask the real error.
            self.closed=True;self.pending=bytearray();raise
    def _drain(self):
        if self.pending:
            self._send(self.pending)
            self.pending.clear()
    def write(self,data):
        self._ready()
        if isinstance(data,memoryview):data=data.cast('B')
        elif not isinstance(data,(bytes,bytearray)):raise TypeError('binary data required')
        length=len(data)
        # Hot path: no per-fragment memoryview or underlying tell/reservation.
        if length<=self.block_bytes-len(self.pending):
            self.pending.extend(data)
            if len(self.pending)==self.block_bytes:self._drain()
            return length
        view=memoryview(data);offset=0
        if self.pending:
            amount=self.block_bytes-len(self.pending)
            self.pending.extend(view[:amount]);offset=amount;self._drain()
        while length-offset>=self.block_bytes:
            self._send(view[offset:offset+self.block_bytes]);offset+=self.block_bytes
        self.pending.extend(view[offset:])
        return length
    def flush(self):
        self._ready();self._drain()
        try:self.sink.flush()
        except BaseException:self.closed=True;raise
    def discard(self):
        self.pending.clear();self.closed=True


@contextmanager
def open_output(path,mode='wb',*,block_bytes=BLOCK_BYTES):
    # This adapter is explicitly sequential: no append, seek, or read-update.
    if mode not in ('wb','xb'):raise ScratchError('HELD_OUTPUT_BLOCK_MODE')
    if type(block_bytes) is not int or not 1<=block_bytes<=BLOCK_BYTES:
        raise ScratchError('HELD_OUTPUT_BLOCK_LIMIT')
    with sio.open_output(path,mode) as sink:
        output=BlockWriter(sink,block_bytes)
        try:
            yield output
            output.flush()
        finally:
            output.discard()
