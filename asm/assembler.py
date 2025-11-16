"""Two-pass ARM64 assembler"""

import sys

from asm.directives import DirectiveHandler
from asm.encoders.data_proc import DATA_PROC_DISPATCH
from asm.encoders.memory import MEMORY_DISPATCH, encode_adr_adrp
from asm.encoders.branch import (
    encode_b_bl, encode_b_cond, encode_br_blr_ret,
    encode_cbz_cbnz, encode_tbz_tbnz,
)


class ARM64Assembler:
    def __init__(self):
        self.labels: dict[str, int] = {}
        self.relocations: list[tuple[int, str, str]] = []
        self.address: int = 0
        self.machine_code: list[int] = []
        self.data_section: list[bytes] = []
        self.current_section: str = 'text'
        self.global_symbols: list[str] = []
        self._directives = DirectiveHandler(self)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assemble(self, source: str, base_address: int = 0x100000000) -> list[int]:
        """Two-pass assembly. Returns list of 32-bit instruction words."""
        lines = source.strip().split('\n')
        self._first_pass(lines, base_address)
        self._second_pass(lines, base_address)
        self._resolve_relocations(base_address)
        return self.machine_code

    def disassemble(self, base_address: int = 0x100000000) -> str:
        """Naive hex dump of machine_code with address + binary."""
        out = []
        for i, instr in enumerate(self.machine_code):
            addr = base_address + i * 4
            out.append(f"0x{addr:016x}: 0x{instr:08x}  {instr:032b}")
        return '\n'.join(out)

    # ------------------------------------------------------------------
    # Pass 1: label collection
    # ------------------------------------------------------------------

    def _first_pass(self, lines: list[str], base_address: int) -> None:
        self.address = base_address
        self.labels.clear()
        self.relocations.clear()
        self.global_symbols.clear()
        self.data_section.clear()
        self.current_section = 'text'

        for line in lines:
            line = self._strip_comment(line.strip())
            if not line:
                continue

            # Label definition
            if ':' in line and '[' not in line and not line.startswith('.'):
                label, line = line.split(':', 1)
                self.labels[label.strip()] = self.address
                line = line.strip()
                if not line:
                    continue

            # Directive
            if line.startswith('.'):
                self._directives.handle(line)
                continue

            # Count instruction
            if self.current_section == 'text':
                self.address += 4

    # ------------------------------------------------------------------
    # Pass 2: encoding
    # ------------------------------------------------------------------

    def _second_pass(self, lines: list[str], base_address: int) -> None:
        self.address = base_address
        self.machine_code.clear()
        self.data_section.clear()   # Prevent double-accumulation from pass 1
        self.current_section = 'text'

        for line in lines:
            try:
                encoded = self._encode_line(line.strip())
                if encoded is not None:
                    self.machine_code.append(encoded)
                    self.address += 4
            except Exception as exc:
                print(f"Error on line '{line.strip()}': {exc}", file=sys.stderr)
                raise

    def _encode_line(self, line: str) -> int | None:
        line = self._strip_comment(line)
        if not line:
            return None

        # Label definition — record address and continue with remainder
        if ':' in line and '[' not in line and not line.startswith('.'):
            label, line = line.split(':', 1)
            self.labels[label.strip()] = self.address  # refresh (pass 2 may differ after .align)
            line = line.strip()
            if not line:
                return None

        if line.startswith('.'):
            self._directives.handle(line)
            return None

        # Tokenise: replace commas with spaces so '[X1, #8]' → '[X1  #8]'
        # then split on whitespace to get individual tokens
        parts = line.replace(',', ' ').split()
        if not parts:
            return None

        mnem = parts[0].lower()
        ops = parts[1:]  # individual whitespace-split tokens

        return self._dispatch(mnem, ops)

    # ------------------------------------------------------------------
    # Instruction dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, mnem: str, ops: list[str]) -> int:
        # Data-processing
        if mnem in DATA_PROC_DISPATCH:
            return DATA_PROC_DISPATCH[mnem](mnem, ops)

        # Memory
        if mnem in MEMORY_DISPATCH:
            return MEMORY_DISPATCH[mnem](mnem, ops)

        # ADR / ADRP need label context
        if mnem in ('adr', 'adrp'):
            return encode_adr_adrp(mnem, ops, self.labels, self.address, self.relocations)

        # Branch instructions that need label context
        if mnem in ('b', 'bl'):
            return encode_b_bl(mnem, ops, self.labels, self.address, self.relocations)

        if mnem.startswith('b.'):
            return encode_b_cond(mnem, ops, self.labels, self.address, self.relocations)

        if mnem in ('br', 'blr', 'ret'):
            return encode_br_blr_ret(mnem, ops)

        if mnem in ('cbz', 'cbnz'):
            return encode_cbz_cbnz(mnem, ops, self.labels, self.address, self.relocations)

        if mnem in ('tbz', 'tbnz'):
            return encode_tbz_tbnz(mnem, ops, self.labels, self.address, self.relocations)

        raise ValueError(f"Unknown instruction: '{mnem}'")

    # ------------------------------------------------------------------
    # Relocation resolution
    # ------------------------------------------------------------------

    def _resolve_relocations(self, base_address: int) -> None:
        for offset, label, rel_type in self.relocations:
            if label not in self.labels:
                print(f"Warning: Undefined label '{label}'", file=sys.stderr)
                continue

            idx = (offset - base_address) // 4
            if idx >= len(self.machine_code):
                continue

            instr = self.machine_code[idx]
            target = self.labels[label]

            if rel_type in ('b', 'bl'):
                offset_val = ((target - offset) >> 2) & 0x3FFFFFF
                instr = (instr & 0xFC000000) | offset_val
            elif rel_type == 'bcond':
                offset_val = ((target - offset) >> 2) & 0x7FFFF
                instr = (instr & 0xFF00001F) | (offset_val << 5)
            elif rel_type == 'cb':
                offset_val = ((target - offset) >> 2) & 0x7FFFF
                instr = (instr & 0xFF00001F) | (offset_val << 5)
            elif rel_type == 'tb':
                offset_val = ((target - offset) >> 2) & 0x3FFF
                instr = (instr & 0xFFF8001F) | (offset_val << 5)
            elif rel_type in ('adr', 'adrp'):
                offset_val = target - offset
                if rel_type == 'adrp':
                    offset_val >>= 12
                immlo = offset_val & 0x3
                immhi = (offset_val >> 2) & 0x7FFFF
                instr = (instr & 0x9F00001F) | (immlo << 29) | (immhi << 5)

            self.machine_code[idx] = instr

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_comment(line: str) -> str:
        """Strip trailing comments (; or //).  '#' is NOT a comment marker in ARM64."""
        for marker in (';', '//'):
            if marker in line:
                line = line[:line.index(marker)]
        return line.strip()
