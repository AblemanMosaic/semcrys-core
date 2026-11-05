"""Optional hash-bound native acceleration for SemCrys buffer operations."""

from .kernel import (
    NativeRequiredError,
    fold_pairs,
    pack_varints,
    parse_packed_events,
    reset_metrics,
    runtime_status,
    unpack_varints,
)

__all__ = [
    "NativeRequiredError",
    "fold_pairs",
    "pack_varints",
    "parse_packed_events",
    "reset_metrics",
    "runtime_status",
    "unpack_varints",
]
