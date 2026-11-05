"""Explicit aggregate logical-byte accounting for private scratch adapters.

Not a filesystem sandbox or an application-wide quota: every writer and native
allocation must be enrolled by its caller. No public CLI claim until integration.
SPDX-License-Identifier: Apache-2.0
"""
from pathlib import Path
from threading import RLock


class ScratchError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def integer(value):
    return type(value) is int and value >= 0


class ScratchBudget:
    """Own new files beneath one private root; reserve before growing a file."""
    def __init__(self, root, limit_bytes):
        if not integer(limit_bytes):
            raise ScratchError("HELD_SCRATCH_INVALID_LIMIT")
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise ScratchError("HELD_SCRATCH_ROOT")
        self.limit = limit_bytes
        self.used = 0
        self.peak = 0
        self.poisoned = False
        self._files = {}
        self._native = {}
        self._lock = RLock()

    def _ready(self):
        if self.poisoned:
            raise ScratchError("HELD_SCRATCH_POISONED")

    def _path(self, path):
        path = Path(path).absolute()
        resolved = path.resolve(strict=False)
        try:
            resolved.relative_to(self.root)
        except ValueError:
            raise ScratchError("HELD_SCRATCH_PATH_ESCAPE") from None
        if resolved == self.root or path != resolved:
            raise ScratchError("HELD_SCRATCH_PATH_ALIAS")
        return resolved

    def _adjust(self, old, new):
        self._ready()
        if not integer(new):
            raise ScratchError("HELD_SCRATCH_INVALID_SIZE")
        requested = self.used - old + new
        if requested > self.limit:
            self.poisoned = True
            raise ScratchError("HELD_SCRATCH_BUDGET")
        self.used = requested
        self.peak = max(self.peak, requested)

    def open(self, path, mode="xb"):
        if mode not in ("xb", "wb", "r+b", "ab"):
            raise ScratchError("HELD_SCRATCH_WRITE_MODE")
        path = self._path(path)
        with self._lock:
            self._ready()
            row = self._files.get(path)
            if row is not None and row["active"]:
                raise ScratchError("HELD_SCRATCH_FILE_BUSY")
            if path.exists() and row is None:
                raise ScratchError("HELD_SCRATCH_UNOWNED_FILE")
            if row is not None:
                if not path.exists() or path.stat().st_size != row["bytes"]:
                    self.poisoned = True
                    raise ScratchError("HELD_SCRATCH_FILE_CHANGED")
            elif mode == "r+b":
                raise ScratchError("HELD_SCRATCH_MISSING_FILE")
            old = 0 if row is None else row["bytes"]
            # New files always use exclusive creation, even for wb/ab.
            actual_mode = "xb" if row is None else mode
            handle = path.open(actual_mode)
            current = 0 if mode in ("xb", "wb") else old
            self._adjust(old, current)
            self._files[path] = {"bytes": current, "active": True}
            if mode == "ab":
                handle.seek(0, 2)
            return ScratchWriter(self, path, handle, append=(mode == "ab"))

    def unlink(self, path):
        """Release only a closed, enrolled file after its successful deletion."""
        path = self._path(path)
        with self._lock:
            row = self._files.get(path)
            if row is None:
                raise ScratchError("HELD_SCRATCH_UNOWNED_FILE")
            if row["active"]:
                raise ScratchError("HELD_SCRATCH_FILE_BUSY")
            if path.stat().st_size != row["bytes"]:
                raise ScratchError("HELD_SCRATCH_FILE_CHANGED")
            path.unlink()
            self.used -= row["bytes"]
            del self._files[path]

    def replace(self, source, target):
        source, target = self._path(source), self._path(target)
        with self._lock:
            self._ready()
            row = self._files.get(source)
            prior = self._files.get(target)
            if row is None or (target.exists() and prior is None):
                raise ScratchError("HELD_SCRATCH_UNOWNED_FILE")
            if row["active"] or (prior is not None and prior["active"]):
                raise ScratchError("HELD_SCRATCH_FILE_BUSY")
            if source == target:
                return
            if source.stat().st_size != row["bytes"] or (prior is not None and target.stat().st_size != prior["bytes"]):
                self.poisoned = True
                raise ScratchError("HELD_SCRATCH_FILE_CHANGED")
            source.replace(target)
            self.used -= 0 if prior is None else prior["bytes"]
            del self._files[source]
            self._files[target] = row

    def reserve_native(self, label, capacity_bytes):
        """Reserve a native adapter's full cap before opening it.

        The adapter must independently enforce that cap (e.g. SQLite pages)
        and call release_native only after closing/removing its allocation.
        """
        if not isinstance(label, str) or not label:
            raise ScratchError("HELD_SCRATCH_NATIVE_LABEL")
        if not integer(capacity_bytes):
            raise ScratchError("HELD_SCRATCH_INVALID_SIZE")
        with self._lock:
            if label in self._native:
                raise ScratchError("HELD_SCRATCH_NATIVE_DUPLICATE")
            self._adjust(0, capacity_bytes)
            self._native[label] = capacity_bytes

    def release_native(self, label):
        with self._lock:
            if label not in self._native:
                raise ScratchError("HELD_SCRATCH_NATIVE_UNKNOWN")
            self.used -= self._native.pop(label)

    def receipt(self):
        with self._lock:
            return {"schema": "semcrys.scratch-budget-receipt.v0.1",
                    "standing": "CANDIDATE_ONLY", "limit_bytes": self.limit,
                    "reserved_bytes": self.used, "peak_reserved_bytes": self.peak,
                    "tracked_file_bytes": sum(r["bytes"] for r in self._files.values()),
                    "native_capacity_bytes": sum(self._native.values()),
                    "active_writers": sum(r["active"] for r in self._files.values()),
                    "poisoned": self.poisoned,
                    "basis": "LOGICAL_FILE_LENGTH_PLUS_FULL_NATIVE_CAPACITY",
                    "filesystem_allocation_overhead_counted": False,
                    "ram_limit": False, "unregistered_io_enforced": False,
                    "public_application_integrated": False}


class ScratchWriter:
    """Sequential/seekable binary writer: charge extension before OS writes."""
    def __init__(self, budget, path, handle, append=False):
        self.budget, self.path, self._handle = budget, path, handle
        self._append = append

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    @property
    def closed(self):
        return self._handle.closed

    def _ready(self):
        if self.closed:
            raise ValueError("I/O operation on closed scratch file")
        self.budget._ready()

    def write(self, value):
        view = memoryview(value)
        with self.budget._lock:
            self._ready()
            if self._append:
                self._handle.seek(0, 2)
            row = self.budget._files[self.path]
            new = max(row["bytes"], self._handle.tell() + view.nbytes)
            self.budget._adjust(row["bytes"], new)
            row["bytes"] = new
            try:
                amount = self._handle.write(view)
                if amount != view.nbytes:
                    raise ScratchError("HELD_SCRATCH_SHORT_WRITE")
                return amount
            except BaseException:
                # Keep the conservative reservation if physical state is uncertain.
                self.budget.poisoned = True
                raise

    def truncate(self, size=None):
        with self.budget._lock:
            self._ready()
            if size is None:
                size = self._handle.tell()
            if not integer(size):
                raise ScratchError("HELD_SCRATCH_INVALID_SIZE")
            row = self.budget._files[self.path]
            old = row["bytes"]
            self.budget._adjust(old, max(old, size))
            row["bytes"] = max(old, size)
            try:
                result = self._handle.truncate(size)
            except BaseException:
                self.budget.poisoned = True
                raise
            self.budget.used -= row["bytes"] - size
            row["bytes"] = size
            return result

    def seek(self, offset, whence=0):
        self._ready()
        return self._handle.seek(offset, whence)

    def tell(self):
        return self._handle.tell()

    def read(self, size=-1):
        self._ready()
        return self._handle.read(size)

    def flush(self):
        try:
            return self._handle.flush()
        except BaseException:
            self.budget.poisoned = True
            raise

    def close(self):
        if not self.closed:
            try:
                self._handle.close()
            except BaseException:
                self.budget.poisoned = True
                raise
            finally:
                self.budget._files[self.path]["active"] = not self.closed
