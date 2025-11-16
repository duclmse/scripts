"""Assembler directive handler"""

import struct
import sys
from asm.parser import parse_imm


class DirectiveHandler:
    """
    Processes assembler directives, updating the caller-supplied assembler state
    in place (via callbacks / mutable references).
    """

    def __init__(self, assembler):
        self._asm = assembler

    def handle(self, line: str) -> None:
        parts = line.split(None, 1)
        directive = parts[0].lower()
        args = parts[1].strip() if len(parts) > 1 else ''

        handler = self._HANDLERS.get(directive)
        if handler:
            handler(self, args)
        # Unknown directives are silently ignored (metadata like .type, .size…)

    # ------------------------------------------------------------------
    # Individual directive handlers
    # ------------------------------------------------------------------

    def _handle_global(self, args: str) -> None:
        self._asm.global_symbols.append(args.strip())

    def _handle_text(self, _args: str) -> None:
        self._asm.current_section = 'text'

    def _handle_data(self, _args: str) -> None:
        self._asm.current_section = 'data'

    def _handle_section(self, args: str) -> None:
        name = args.strip().strip('"')
        if '__TEXT' in name or '__text' in name:
            self._asm.current_section = 'text'
        else:
            self._asm.current_section = 'data'

    def _handle_align(self, args: str) -> None:
        """`.align N` — align to 2^N bytes (power-of-2 alignment)."""
        align_bytes = 1 << int(args.strip())
        self._pad_to_alignment(align_bytes)

    def _handle_p2align(self, args: str) -> None:
        """`.p2align N` — align to 2^N bytes."""
        align_bytes = 1 << int(args.strip())
        self._pad_to_alignment(align_bytes)

    def _handle_balign(self, args: str) -> None:
        """`.balign N` — align to N bytes (byte alignment, not power-of-2)."""
        align_bytes = int(args.strip())
        self._pad_to_alignment(align_bytes)

    def _pad_to_alignment(self, align_bytes: int) -> None:
        while self._asm.address % align_bytes != 0:
            self._asm.address += 4
            if self._asm.current_section == 'text':
                self._asm.machine_code.append(0xD503201F)  # NOP

    def _handle_quad(self, args: str) -> None:
        value = parse_imm(args.strip())
        self._asm.data_section.append(struct.pack('<Q', value & 0xFFFFFFFFFFFFFFFF))

    def _handle_word(self, args: str) -> None:
        value = parse_imm(args.strip())
        self._asm.data_section.append(struct.pack('<I', value & 0xFFFFFFFF))

    def _handle_short(self, args: str) -> None:
        value = parse_imm(args.strip())
        self._asm.data_section.append(struct.pack('<H', value & 0xFFFF))

    def _handle_byte(self, args: str) -> None:
        value = parse_imm(args.strip())
        self._asm.data_section.append(struct.pack('<B', value & 0xFF))

    def _handle_ascii(self, args: str) -> None:
        string = args.strip().strip('"')
        self._asm.data_section.append(string.encode('ascii'))

    def _handle_asciz(self, args: str) -> None:
        string = args.strip().strip('"')
        self._asm.data_section.append(string.encode('ascii') + b'\x00')

    def _handle_space(self, args: str) -> None:
        size = int(args.strip())
        self._asm.data_section.append(b'\x00' * size)

    _HANDLERS = {
        '.global': _handle_global,
        '.globl':  _handle_global,
        '.text':   _handle_text,
        '.data':   _handle_data,
        '.section': _handle_section,
        '.align':  _handle_align,
        '.p2align': _handle_p2align,
        '.balign': _handle_balign,
        '.quad':   _handle_quad,
        '.8byte':  _handle_quad,
        '.word':   _handle_word,
        '.long':   _handle_word,
        '.4byte':  _handle_word,
        '.short':  _handle_short,
        '.2byte':  _handle_short,
        '.byte':   _handle_byte,
        '.1byte':  _handle_byte,
        '.ascii':  _handle_ascii,
        '.asciz':  _handle_asciz,
        '.string': _handle_asciz,
        '.space':  _handle_space,
        '.skip':   _handle_space,
        # Metadata — explicitly ignored
        '.type':   lambda self, _: None,
        '.size':   lambda self, _: None,
        '.ident':  lambda self, _: None,
        '.file':   lambda self, _: None,
    }
