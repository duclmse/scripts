"""Register tables, operand parsing, and helper functions"""

from dataclasses import dataclass
from asm.enums import Condition


# ---------------------------------------------------------------------------
# Module-level constants (built once, shared across all assembler instances)
# ---------------------------------------------------------------------------

def _build_registers() -> dict[str, int]:
    regs: dict[str, int] = {}
    for i in range(31):
        regs[f'x{i}'] = i
        regs[f'w{i}'] = i
    for i in range(32):
        regs[f'v{i}'] = i
        regs[f's{i}'] = i
        regs[f'd{i}'] = i
        regs[f'q{i}'] = i
    regs.update({
        'xzr': 31, 'wzr': 31, 'sp': 31,
        'lr': 30, 'x30': 30, 'fp': 29, 'x29': 29,
    })
    return regs


REGISTERS: dict[str, int] = _build_registers()

CONDITIONS: dict[str, Condition] = {
    'eq': Condition.EQ, 'ne': Condition.NE,
    'cs': Condition.CS, 'hs': Condition.CS,
    'cc': Condition.CC, 'lo': Condition.CC,
    'mi': Condition.MI, 'pl': Condition.PL,
    'vs': Condition.VS, 'vc': Condition.VC,
    'hi': Condition.HI, 'ls': Condition.LS,
    'ge': Condition.GE, 'lt': Condition.LT,
    'gt': Condition.GT, 'le': Condition.LE,
    'al': Condition.AL,
}


# ---------------------------------------------------------------------------
# Operand parsers
# ---------------------------------------------------------------------------

def parse_reg(reg: str) -> tuple[int, bool]:
    """Parse a register name into (number, is_64bit). Raises ValueError on bad input."""
    reg = reg.lower().strip().rstrip(',')
    if reg not in REGISTERS:
        raise ValueError(f"Unknown register: '{reg}'")
    is_64 = reg.startswith('x') or reg in ('sp', 'lr', 'fp', 'xzr')
    return REGISTERS[reg], is_64


def parse_imm(imm: str) -> int:
    """Parse an immediate value: #42, #0xFF, #0b1010, or bare integer."""
    imm = imm.strip().lstrip('#')
    if imm.startswith('0x') or imm.startswith('0X'):
        return int(imm, 16)
    if imm.startswith('0b') or imm.startswith('0B'):
        return int(imm, 2)
    return int(imm)


def sign_extend(value: int, bits: int) -> int:
    """Sign-extend a value from `bits` width to Python int."""
    sign_bit = 1 << (bits - 1)
    return (value & (sign_bit - 1)) - (value & sign_bit)


# ---------------------------------------------------------------------------
# Memory operand parser
# ---------------------------------------------------------------------------

@dataclass
class MemOperand:
    base: int           # base register number
    imm: int            # immediate offset (0 if register offset)
    reg_offset: int     # offset register number (-1 if immediate offset)
    pre_index: bool     # [Xn, #imm]!
    post_index: bool    # [Xn], #imm  (imm stored in .imm)
    is_64: bool         # is the base register 64-bit


def parse_mem(ops: list[str], start: int = 1) -> MemOperand:
    """
    Parse memory operand(s) starting at ops[start].

    Handles:
      [Xn]              → base only
      [Xn, #imm]        → unsigned offset
      [Xn, #imm]!       → pre-indexed
      [Xn], #imm        → post-indexed
      [Xn, Xm]          → register offset
    """
    # Reconstruct the memory portion (may span multiple comma-separated tokens
    # e.g. ["[sp", "#16]"] or ["[sp", "#-16]!"] or ["[sp]", "#16"])
    raw = ', '.join(ops[start:])

    post_imm = 0
    post_index = False

    # Post-indexed: [Xn], #imm
    if '],' in raw or (raw.endswith(']') is False and '], ' in raw):
        bracket_end = raw.index(']')
        mem_part = raw[:bracket_end + 1]
        rest = raw[bracket_end + 1:].strip().lstrip(',').strip()
        if rest:
            post_index = True
            post_imm = parse_imm(rest)
    else:
        mem_part = raw

    # Pre-indexed: ends with ]!
    pre_index = mem_part.strip().endswith('!')
    mem_part = mem_part.strip().rstrip('!').strip('[]')

    parts = [p.strip() for p in mem_part.split(',')]
    base_num, is_64 = parse_reg(parts[0])

    if len(parts) == 1:
        # [Xn] — base only
        return MemOperand(base_num, post_imm, -1, pre_index, post_index, is_64)

    second = parts[1].strip()
    if second.startswith('#') or second.lstrip('-').isdigit():
        imm = parse_imm(second)
        if post_index:
            imm = post_imm
        return MemOperand(base_num, imm, -1, pre_index, post_index, is_64)
    else:
        reg_num, _ = parse_reg(second)
        return MemOperand(base_num, 0, reg_num, pre_index, post_index, is_64)
