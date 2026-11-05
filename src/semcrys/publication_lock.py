"""Cooperative local-process publication locks; zero-byte persistent lock inode.
SPDX-License-Identifier: Apache-2.0
"""
import ctypes,errno,json,os,stat,sys
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path
from streaming_app.core import Refusal

NAME='.semcrys-publication.lock'
def contract():
    value=json.loads(files('semcrys').joinpath('PUBLICATION_CONCURRENCY_CONTRACT.json').read_text(encoding='utf-8'))
    if (value.get('lock_file')!=NAME or value.get('lock_scope')!='RESOLVED_OUTPUT_PARENT'
        or value.get('lock_payload_bytes')!=0 or value.get('contention')!='REFUSE_WITHOUT_WAIT'
        or value.get('no_replace')!='NATIVE_ATOMIC_RENAME_NOREPLACE'):
        raise Refusal('HELD_PUBLICATION_CONCURRENCY_CONTRACT')
    return value

def _regular(info):
    return stat.S_ISREG(info.st_mode) and not (getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0))

@contextmanager
def destinations(targets,inputs=()):
    """All locks are acquired nonblocking, released on exceptions/process exit.

    Never unlink the lock file: waiters may already hold its inode. This is
    local coordination metadata, not transported data or an ownership receipt.
    External removal of lock files or parent renames is outside this contract.
    """
    contract();targets=tuple(Path(p).absolute() for p in targets)
    inputs=tuple(Path(p).absolute() for p in inputs if p is not None)
    if any(p.name.casefold()==NAME for p in (*targets,*inputs)):
        raise Refusal('HELD_PUBLICATION_RESERVED_LOCK_PATH')
    parents=sorted({p.parent.resolve() for p in targets},key=lambda p:os.path.normcase(str(p)))
    handles=[]
    try:
        for parent in parents:
            parent.mkdir(parents=True,exist_ok=True);path=parent/NAME
            try:
                before=path.lstat()
                if not _regular(before) or before.st_size!=0 or before.st_nlink!=1:
                    raise Refusal('HELD_PUBLICATION_LOCK_FILE')
            except FileNotFoundError:pass
            fd=os.open(path,os.O_RDWR|os.O_CREAT|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_BINARY',0),0o600)
            try:
                handles.append(fd)
            except BaseException:
                os.close(fd);raise
            # Register ownership before acquiring: an interrupt immediately
            # after a successful syscall must still close/release this handle.
            try:
                info=os.fstat(fd);now=path.lstat()
                if (not _regular(info) or not _regular(now) or info.st_size!=0 or info.st_nlink!=1
                    or (info.st_dev,info.st_ino)!=(now.st_dev,now.st_ino)):
                    raise Refusal('HELD_PUBLICATION_LOCK_FILE')
                try:
                    if os.name=='nt':
                        import msvcrt
                        msvcrt.locking(fd,msvcrt.LK_NBLCK,1)
                    else:
                        import fcntl
                        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except OSError as exc:
                    if exc.errno in (errno.EACCES,errno.EAGAIN,errno.EDEADLK):
                        raise Refusal('HELD_PUBLICATION_BUSY',str(parent)) from exc
                    raise
            except BaseException:
                raise
        yield
    finally:
        # close releases the kernel lock even after process termination.
        for fd in reversed(handles):os.close(fd)

def move_new(source,target):
    """Consume stage only on successful native atomic no-replace rename.

    No copy/link/check-then-replace fallback; unavailable platforms fail closed.
    Windows rename refuses existing targets. Linux renameat2 uses RENAME_NOREPLACE.
    """
    try:
        if os.name=='nt':os.rename(source,target)
        elif sys.platform.startswith('linux'):
            libc=ctypes.CDLL(None,use_errno=True)
            try:rename=libc.renameat2
            except AttributeError:raise Refusal('HELD_PUBLICATION_NOREPLACE_UNAVAILABLE')
            rename.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
            rename.restype=ctypes.c_int
            if rename(-100,os.fsencode(source),-100,os.fsencode(target),1):
                error=ctypes.get_errno()
                if error in (errno.ENOSYS,errno.EINVAL,errno.EOPNOTSUPP):
                    raise Refusal('HELD_PUBLICATION_NOREPLACE_UNAVAILABLE')
                raise OSError(error,os.strerror(error),os.fspath(target))
        else:raise Refusal('HELD_PUBLICATION_NOREPLACE_UNAVAILABLE')
    except FileExistsError as exc:
        raise Refusal('HELD_PUBLICATION_TARGET_EXISTS',str(target)) from exc

def commit_file(source,target,replace):
    if replace:os.replace(source,target)
    else:move_new(source,target)
