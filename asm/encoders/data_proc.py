"""Data-processing instruction encoders (immediate + register)"""

from asm.enums import Condition
from asm.parser import parse_reg, parse_imm, CONDITIONS


# ---------------------------------------------------------------------------
# Bitmask immediate encoding
# ---------------------------------------------------------------------------

def _encode_bitmask_imm(imm: int, sf: int) -> tuple[int, int, int]:
    """
    Encode a bitmask immediate into (N, immr, imms).

    A valid bitmask immediate is a non-zero, non-all-ones value that can be
    expressed as a repeated pattern of bits whose set-bits form a single
    contiguous run (when viewed circularly within the pattern element).

    Raises ValueError if imm is not a valid bitmask immediate.
    """
    width = 64 if sf else 32
    mask = (1 << width) - 1
    imm &= mask

    if imm == 0 or imm == mask:
        raise ValueError(f"Cannot encode {imm:#x} as bitmask immediate (all-zeros or all-ones)")

    for size in (2, 4, 8, 16, 32, 64):
        if size > width:
            continue
        elem_mask = (1 << size) - 1
        element = imm & elem_mask

        # Check all elements are identical (imm is a replication of element)
        replicated = 0
        for i in range(width // size):
            replicated |= element << (i * size)
        if replicated != imm:
            continue

        # Element must not be all-zeros or all-ones
        if element == 0 or element == elem_mask:
            continue

        ones = bin(element).count('1')
        target = (1 << ones) - 1  # canonical form: ones in LSB

        for rotation in range(size):
            rotated = ((element >> rotation) | (element << (size - rotation))) & elem_mask
            if rotated == target:
                N = 1 if size == 64 else 0
                immr = rotation
                imms = (~(size - 1) & 0x3F) | (ones - 1)
                return N, immr, imms

    raise ValueError(f"Cannot encode {imm:#x} as a bitmask immediate")


# ---------------------------------------------------------------------------
# Immediate encoders
# ---------------------------------------------------------------------------

def encode_add_sub_imm(mnem: str, ops: list[str]) -> int:
    """ADD/SUB/ADDS/SUBS Rd, Rn, #imm{, LSL #0|12}"""
    is_sub = 'sub' in mnem
    set_flags = mnem.endswith('s')

    rd, sf = parse_reg(ops[0])
    rn, _ = parse_reg(ops[1])
    imm = parse_imm(ops[2])

    if imm < 0 or imm >= 4096:
        raise ValueError(f"Immediate {imm} out of range for ADD/SUB (0-4095)")

    shift = 0
    if len(ops) > 3 and 'lsl' in ops[3].lower():
        # ops[4] = '#12' or '#0'
        shift = parse_imm(ops[4]) // 12

    sf_bit = 1 if sf else 0
    return (sf_bit << 31) | (is_sub << 30) | (set_flags << 29) | (0b100010 << 23) | \
           (shift << 22) | (imm << 10) | (rn << 5) | rd


def encode_logical_imm(mnem: str, ops: list[str]) -> int:
    """AND/ORR/EOR/ANDS Rd, Rn, #imm"""
    opc_map = {'and': 0b00, 'orr': 0b01, 'eor': 0b10, 'ands': 0b11}
    opc = opc_map[mnem]

    rd, sf = parse_reg(ops[0])
    rn, _ = parse_reg(ops[1])
    imm = parse_imm(ops[2])

    sf_bit = 1 if sf else 0
    N, immr, imms = _encode_bitmask_imm(imm, sf_bit)

    return (sf_bit << 31) | (opc << 29) | (0b100100 << 23) | (N << 22) | \
           (immr << 16) | (imms << 10) | (rn << 5) | rd


def encode_movz_movn_movk(mnem: str, ops: list[str]) -> int:
    """MOVZ/MOVN/MOVK Rd, #imm{, LSL #shift}"""
    opc_map = {'movz': 0b10, 'movn': 0b00, 'movk': 0b11}
    opc = opc_map[mnem]

    rd, sf = parse_reg(ops[0])
    imm = parse_imm(ops[1])

    hw = 0
    if len(ops) > 2 and 'lsl' in ops[2].lower():
        hw = parse_imm(ops[3]) // 16

    if imm < 0 or imm >= 65536:
        raise ValueError(f"Immediate {imm} out of range for MOVZ/MOVN/MOVK (0-65535)")

    sf_bit = 1 if sf else 0
    return (sf_bit << 31) | (opc << 29) | (0b100101 << 23) | (hw << 21) | \
           (imm << 5) | rd


# ---------------------------------------------------------------------------
# Register encoders
# ---------------------------------------------------------------------------

def encode_add_sub_reg(mnem: str, ops: list[str]) -> int:
    """ADD/SUB/ADDS/SUBS Rd, Rn, Rm"""
    is_sub = 'sub' in mnem
    set_flags = mnem.endswith('s')

    rd, sf = parse_reg(ops[0])
    rn, _ = parse_reg(ops[1])
    rm, _ = parse_reg(ops[2])

    sf_bit = 1 if sf else 0
    return (sf_bit << 31) | (is_sub << 30) | (set_flags << 29) | (0b01011 << 24) | \
           (rm << 16) | (rn << 5) | rd


def encode_logical_reg(mnem: str, ops: list[str]) -> int:
    """AND/ORR/EOR/ANDS/BIC/ORN/EON/BICS Rd, Rn, Rm"""
    opc_map = {'and': 0b00, 'bic': 0b00, 'orr': 0b01, 'orn': 0b01,
               'eor': 0b10, 'eon': 0b10, 'ands': 0b11, 'bics': 0b11}
    N = 1 if mnem in ('bic', 'orn', 'eon', 'bics') else 0
    opc = opc_map[mnem]

    rd, sf = parse_reg(ops[0])
    rn, _ = parse_reg(ops[1])
    rm, _ = parse_reg(ops[2])

    sf_bit = 1 if sf else 0
    # shift=0 (LSL), imm6=0 (no shift amount)
    return (sf_bit << 31) | (opc << 29) | (0b01010 << 24) | (0b00 << 22) | \
           (N << 21) | (rm << 16) | (0b000000 << 10) | (rn << 5) | rd


def encode_mul_div(mnem: str, ops: list[str]) -> int:
    """MUL/MADD/MSUB/SDIV/UDIV"""
    rd, sf = parse_reg(ops[0])
    rn, _ = parse_reg(ops[1])
    rm, _ = parse_reg(ops[2])
    sf_bit = 1 if sf else 0

    if mnem in ('sdiv', 'udiv'):
        o1 = 1 if mnem == 'sdiv' else 0
        return (sf_bit << 31) | (0b11010110 << 21) | (rm << 16) | \
               (0b0001 << 12) | (o1 << 11) | (rn << 5) | rd

    if mnem == 'mul':
        ra, o0 = 31, 0
    else:  # madd / msub
        ra, _ = parse_reg(ops[3])
        o0 = 1 if mnem == 'msub' else 0

    return (sf_bit << 31) | (0b11011 << 24) | (rm << 16) | (o0 << 15) | \
           (ra << 10) | (rn << 5) | rd


def encode_shift(mnem: str, ops: list[str]) -> int:
    """LSL/LSR/ASR/ROR with immediate or register operand."""
    rd, sf = parse_reg(ops[0])
    rn, _ = parse_reg(ops[1])
    sf_bit = 1 if sf else 0
    width = 64 if sf else 32
    N = sf_bit  # N == sf for bitfield instructions

    if ops[2].strip().startswith('#'):
        # Immediate shift — encoded as bitfield aliases
        n = parse_imm(ops[2])
        if mnem == 'lsl':
            # UBFM Rd, Rn, #(-n MOD width), #(width-1-n)
            immr = (-n) % width
            imms = width - 1 - n
            opc = 0b10  # UBFM
        elif mnem == 'lsr':
            # UBFM Rd, Rn, #n, #(width-1)
            immr = n
            imms = width - 1
            opc = 0b10  # UBFM
        elif mnem == 'asr':
            # SBFM Rd, Rn, #n, #(width-1)
            immr = n
            imms = width - 1
            opc = 0b00  # SBFM
        else:  # ror — EXTR Rd, Rn, Rn, #n
            return (sf_bit << 31) | (0b00 << 29) | (0b100111 << 23) | (N << 22) | \
                   (rn << 16) | (n << 10) | (rn << 5) | rd

        return (sf_bit << 31) | (opc << 29) | (0b100110 << 23) | (N << 22) | \
               (immr << 16) | (imms << 10) | (rn << 5) | rd

    else:
        # Register shift — encoded as LSLV/LSRV/ASRV/RORV
        shift_map = {'lsl': 0b00, 'lsr': 0b01, 'asr': 0b10, 'ror': 0b11}
        shift = shift_map[mnem]
        rm, _ = parse_reg(ops[2])
        return (sf_bit << 31) | (0b11010110 << 21) | (rm << 16) | \
               (0b0010 << 12) | (shift << 10) | (rn << 5) | rd


# ---------------------------------------------------------------------------
# Pseudo-instructions and special forms
# ---------------------------------------------------------------------------

def encode_mov(mnem: str, ops: list[str]) -> int:
    """MOV pseudo-instruction: immediate → MOVZ; register → ORR Rd, XZR, Rm"""
    rd, sf = parse_reg(ops[0])
    sf_bit = 1 if sf else 0

    if ops[1].strip().startswith('#'):
        return encode_movz_movn_movk('movz', ops)

    rm, _ = parse_reg(ops[1])
    return (sf_bit << 31) | (0b01 << 29) | (0b01010 << 24) | \
           (0b00 << 22) | (rm << 16) | (0b000000 << 10) | (31 << 5) | rd


def encode_cmp(mnem: str, ops: list[str]) -> int:
    """CMP/CMN: alias for SUBS/ADDS with XZR destination"""
    rn, sf = parse_reg(ops[0])
    sf_bit = 1 if sf else 0
    is_cmn = mnem == 'cmn'
    is_sub = not is_cmn  # CMP → SUBS, CMN → ADDS

    if ops[1].strip().startswith('#'):
        imm = parse_imm(ops[1])
        return (sf_bit << 31) | (is_sub << 30) | (0b1 << 29) | (0b100010 << 23) | \
               (imm << 10) | (rn << 5) | 31
    else:
        rm, _ = parse_reg(ops[1])
        return (sf_bit << 31) | (is_sub << 30) | (0b1 << 29) | (0b01011 << 24) | \
               (rm << 16) | (rn << 5) | 31


def encode_csel(mnem: str, ops: list[str]) -> int:
    """CSEL/CSINC/CSINV/CSNEG Rd, Rn, Rm, cond"""
    # S (bit 30) and o2 (bit 10) encode the variant
    op_map = {
        'csel':  (0, 0),
        'csinc': (0, 1),
        'csinv': (1, 0),
        'csneg': (1, 1),
    }
    S, o2 = op_map[mnem]

    rd, sf = parse_reg(ops[0])
    rn, _ = parse_reg(ops[1])
    rm, _ = parse_reg(ops[2])
    cond = int(CONDITIONS.get(ops[3].lower().rstrip(','), Condition.AL))
    sf_bit = 1 if sf else 0

    return (sf_bit << 31) | (S << 30) | (0b11010100 << 21) | (rm << 16) | \
           (cond << 12) | (o2 << 10) | (rn << 5) | rd


# ---------------------------------------------------------------------------
# System / special instructions
# ---------------------------------------------------------------------------

def encode_nop(_mnem: str, _ops: list[str]) -> int:
    return 0xD503201F


def encode_brk(_mnem: str, ops: list[str]) -> int:
    imm = parse_imm(ops[0]) if ops else 0
    return (0b11010100001 << 21) | (imm << 5)


def encode_svc(_mnem: str, ops: list[str]) -> int:
    imm = parse_imm(ops[0]) if ops else 0
    return (0b11010100000 << 21) | (imm << 5) | 0b00001


def encode_mrs_msr(mnem: str, ops: list[str]) -> int:
    """MRS/MSR: system-register access (simplified encoding)."""
    is_read = mnem == 'mrs'
    if is_read:
        rt, _ = parse_reg(ops[0])
        return (0b1101010100 << 22) | (1 << 21) | (0b11 << 19) | rt
    else:
        rt, _ = parse_reg(ops[1])
        return (0b1101010100 << 22) | rt


# ---------------------------------------------------------------------------
# Dispatch helper
# ---------------------------------------------------------------------------

def _try_imm_or_reg(mnem: str, ops: list[str], imm_fn, reg_fn) -> int:
    """Use immediate encoder if ops[2] starts with '#', else register encoder."""
    if len(ops) >= 3 and ops[2].strip().startswith('#'):
        return imm_fn(mnem, ops)
    return reg_fn(mnem, ops)


DATA_PROC_DISPATCH: dict[str, object] = {
    'add':   lambda m, o: _try_imm_or_reg(m, o, encode_add_sub_imm, encode_add_sub_reg),
    'adds':  lambda m, o: _try_imm_or_reg(m, o, encode_add_sub_imm, encode_add_sub_reg),
    'sub':   lambda m, o: _try_imm_or_reg(m, o, encode_add_sub_imm, encode_add_sub_reg),
    'subs':  lambda m, o: _try_imm_or_reg(m, o, encode_add_sub_imm, encode_add_sub_reg),
    'and':   lambda m, o: _try_imm_or_reg(m, o, encode_logical_imm, encode_logical_reg),
    'orr':   lambda m, o: _try_imm_or_reg(m, o, encode_logical_imm, encode_logical_reg),
    'eor':   lambda m, o: _try_imm_or_reg(m, o, encode_logical_imm, encode_logical_reg),
    'ands':  lambda m, o: _try_imm_or_reg(m, o, encode_logical_imm, encode_logical_reg),
    'bic':   encode_logical_reg,
    'orn':   encode_logical_reg,
    'eon':   encode_logical_reg,
    'bics':  encode_logical_reg,
    'movz':  encode_movz_movn_movk,
    'movn':  encode_movz_movn_movk,
    'movk':  encode_movz_movn_movk,
    'mov':   encode_mov,
    'mul':   encode_mul_div,
    'madd':  encode_mul_div,
    'msub':  encode_mul_div,
    'sdiv':  encode_mul_div,
    'udiv':  encode_mul_div,
    'lsl':   encode_shift,
    'lsr':   encode_shift,
    'asr':   encode_shift,
    'ror':   encode_shift,
    'cmp':   encode_cmp,
    'cmn':   encode_cmp,
    'csel':  encode_csel,
    'csinc': encode_csel,
    'csinv': encode_csel,
    'csneg': encode_csel,
    'nop':   encode_nop,
    'brk':   encode_brk,
    'svc':   encode_svc,
    'mrs':   encode_mrs_msr,
    'msr':   encode_mrs_msr,
}
