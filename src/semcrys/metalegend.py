"""Recursive legend-of-a-legend operations and legacy compatibility aliases.

``metalegend`` is reserved for vertical recursive representations of one
legend. The historical cross-artifact ``pack``/``unpack`` exports remain for
v0.1 source compatibility only; their implementation and canonical ownership
live in :mod:`semcrys.group_legend`.
"""
from __future__ import annotations

from pathlib import Path

from .recursive_metalegend import MAGIC as WHOLE_MAGIC
from .recursive_metalegend import build as build_whole
from .recursive_metalegend import inspect as inspect_whole
from .recursive_metalegend import restore as restore_whole
from .recursive_metalegend import verify as verify_whole
from .seekable_metalegend import MAGIC as SEEKABLE_MAGIC
from .seekable_metalegend import SeekableMetalegendReader
from .seekable_metalegend import build as build_seekable
from .seekable_metalegend import inspect as inspect_seekable
from .seekable_metalegend import restore as restore_seekable
from .seekable_metalegend import verify as verify_seekable


def _magic(path) -> bytes:
    with Path(path).open("rb") as handle:
        return handle.read(8)


def build(source, output, *, layout="seekable", **options):
    """Build a recursive metalegend; seekable framing is the v0.1 default."""
    if layout == "seekable":
        return build_seekable(source, output, **options)
    if layout == "whole":
        options.pop("frame_blocks", None)
        return build_whole(source, output, **options)
    raise ValueError("HELD_METALEGEND_LAYOUT")


def inspect(source, **options):
    signature = _magic(source)
    if signature == SEEKABLE_MAGIC:
        return inspect_seekable(source, **options)
    if signature == WHOLE_MAGIC:
        options.pop("verify_frames", None)
        return inspect_whole(source)
    raise ValueError("HELD_METALEGEND_MAGIC")


def restore(source, output):
    signature = _magic(source)
    if signature == SEEKABLE_MAGIC:
        return restore_seekable(source, output)
    if signature == WHOLE_MAGIC:
        return restore_whole(source, output)
    raise ValueError("HELD_METALEGEND_MAGIC")


def verify(source):
    signature = _magic(source)
    if signature == SEEKABLE_MAGIC:
        return verify_seekable(source)
    if signature == WHOLE_MAGIC:
        return verify_whole(source)
    raise ValueError("HELD_METALEGEND_MAGIC")


def pack(*args, **kwargs):
    """Compatibility alias for :func:`semcrys.group_legend.pack`."""
    from .group_legend import pack as group_pack
    return group_pack(*args, **kwargs)


def unpack(*args, **kwargs):
    """Compatibility alias for :func:`semcrys.group_legend.unpack`."""
    from .group_legend import unpack as group_unpack
    return group_unpack(*args, **kwargs)


__all__ = [
    "build", "build_seekable", "build_whole", "inspect", "restore", "verify",
    "SeekableMetalegendReader", "pack", "unpack",
]
