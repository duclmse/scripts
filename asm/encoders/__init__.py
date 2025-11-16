"""Instruction encoder modules for ARM64"""

from asm.encoders.data_proc import DATA_PROC_DISPATCH
from asm.encoders.memory import MEMORY_DISPATCH

__all__ = ["DATA_PROC_DISPATCH", "MEMORY_DISPATCH"]
