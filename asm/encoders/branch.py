"""Branch instruction encoders"""

from asm.enums import Condition
from asm.parser import parse_reg, parse_imm, CONDITIONS


def encode_b_bl(mnem: str, ops: list[str], labels: dict[str, int],
                address: int, relocations: list) -> int:
    """B/BL: unconditional branch (26-bit signed offset, in instructions)."""
    is_link = mnem == 'bl'
    label = ops[0].strip()

    if label in labels:
        offset = (labels[label] - address) >> 2
        if offset < -(1 << 25) or offset >= (1 << 25):
            raise ValueError(f"Branch to '{label}' is out of 26-bit range")
        offset &= 0x3FFFFFF
    else:
        relocations.append((address, label, mnem))
        offset = 0

    return (is_link << 31) | (0b00101 << 26) | offset


def encode_b_cond(mnem: str, ops: list[str], labels: dict[str, int],
                  address: int, relocations: list) -> int:
    """B.cond: conditional branch (19-bit signed offset, in instructions)."""
    cond_str = mnem.split('.')[1] if '.' in mnem else ops[0].strip('.')
    cond = int(CONDITIONS.get(cond_str.lower(), Condition.AL))
    label = ops[-1].strip()

    if label in labels:
        offset = (labels[label] - address) >> 2
        if offset < -(1 << 18) or offset >= (1 << 18):
            raise ValueError(f"Conditional branch to '{label}' is out of 19-bit range")
        offset &= 0x7FFFF
    else:
        relocations.append((address, label, 'bcond'))
        offset = 0

    return (0b01010100 << 24) | (offset << 5) | cond


def encode_br_blr_ret(mnem: str, ops: list[str]) -> int:
    """BR/BLR/RET: branch to register."""
    if mnem == 'ret':
        rn = 30 if not ops or not ops[0].strip() else parse_reg(ops[0])[0]
        return (0b1101011 << 25) | (0b0010 << 21) | (0b11111 << 16) | (rn << 5)

    is_link = mnem == 'blr'
    rn, _ = parse_reg(ops[0])
    return (0b1101011 << 25) | (is_link << 21) | (0b11111 << 16) | (rn << 5)


def encode_cbz_cbnz(mnem: str, ops: list[str], labels: dict[str, int],
                    address: int, relocations: list) -> int:
    """CBZ/CBNZ: compare and branch on zero/non-zero (19-bit offset)."""
    is_nz = mnem == 'cbnz'
    rt, sf = parse_reg(ops[0])
    label = ops[1].strip()
    sf_bit = 1 if sf else 0

    if label in labels:
        offset = (labels[label] - address) >> 2
        if offset < -(1 << 18) or offset >= (1 << 18):
            raise ValueError(f"CBZ/CBNZ branch to '{label}' is out of 19-bit range")
        offset &= 0x7FFFF
    else:
        relocations.append((address, label, 'cb'))
        offset = 0

    return (sf_bit << 31) | (0b011010 << 25) | (is_nz << 24) | (offset << 5) | rt


def encode_tbz_tbnz(mnem: str, ops: list[str], labels: dict[str, int],
                    address: int, relocations: list) -> int:
    """TBZ/TBNZ: test bit and branch (14-bit offset)."""
    is_nz = mnem == 'tbnz'
    rt, _ = parse_reg(ops[0])
    bit = parse_imm(ops[1])
    label = ops[2].strip()

    if label in labels:
        offset = (labels[label] - address) >> 2
        if offset < -(1 << 13) or offset >= (1 << 13):
            raise ValueError(f"TBZ/TBNZ branch to '{label}' is out of 14-bit range")
        offset &= 0x3FFF
    else:
        relocations.append((address, label, 'tb'))
        offset = 0

    b40 = bit & 0x1F
    b5 = (bit >> 5) & 1

    return (b5 << 31) | (0b011011 << 25) | (is_nz << 24) | (b40 << 19) | \
           (offset << 5) | rt
