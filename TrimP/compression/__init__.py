"""Compression package — 9 compressors."""
from TrimP.compression.bash import BashCompressor
from TrimP.compression.search import SearchCompressor
from TrimP.compression.json_table import JsonTableCompressor
from TrimP.compression.delta import DeltaCompressor
from TrimP.compression.skeleton import SkeletonCompressor
from TrimP.compression.archive import ArchiveManager
from TrimP.compression.verbosity import VerbosityNudger
from TrimP.compression.structural import StructuralAuditor
from TrimP.compression.loop_detect import LoopDetector
from TrimP.compression.activity import ActivityMode

__all__ = [
    "BashCompressor", "SearchCompressor", "JsonTableCompressor",
    "DeltaCompressor", "SkeletonCompressor", "ArchiveManager",
    "VerbosityNudger", "StructuralAuditor", "LoopDetector", "ActivityMode",
]
