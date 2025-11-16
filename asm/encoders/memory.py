"""Memory (load/store) instruction encoders"""

from asm.parser import parse_reg, parse_imm, parse_mem


def encode_ldr_str(mnem: str, ops: list[str]) -> int:
    """LDR/STR with unsigned-offset, register-offset, pre- or post-indexed addressing."""
    is_load = 'ldr' in mnem
    rt, sf = parse_reg(ops[0])
    sf_bit = 1 if sf else 0
    size = 3 if sf else 2  # 64-bit → size=3, 32-bit → size=2

    mem = parse_mem(ops, start=1)

    if mem.reg_offset >= 0:
        # [Xn, Xm] — register offset
        option = 0b011  # LSL / LSX extend
        S = 1
        return (size << 30) | (0b111 << 27) | (is_load << 22) | (0b1 << 21) | \
               (mem.reg_offset << 16) | (option << 13) | (S << 12) | (0b10 << 10) | \
               (mem.base << 5) | rt

    if mem.post_index:
        # [Xn], #imm — post-indexed (unscaled signed offset in bits 20:12)
        simm9 = mem.imm & 0x1FF
        return (size << 30) | (0b111 << 27) | (is_load << 22) | \
               (simm9 << 12) | (0b01 << 10) | (mem.base << 5) | rt

    if mem.pre_index:
        # [Xn, #imm]! — pre-indexed
        simm9 = mem.imm & 0x1FF
        return (size << 30) | (0b111 << 27) | (is_load << 22) | \
               (simm9 << 12) | (0b11 << 10) | (mem.base << 5) | rt

    # [Xn, #imm] — unsigned scaled offset
    scale = size  # bytes = 2^scale (4 for 32-bit, 8 for 64-bit)
    imm12 = (mem.imm >> scale) & 0xFFF
    return (size << 30) | (0b111 << 27) | (0b01 << 24) | (is_load << 22) | \
           (imm12 << 10) | (mem.base << 5) | rt


def encode_ldp_stp(mnem: str, ops: list[str]) -> int:
    """LDP/STP: load/store pair with signed-scaled offset."""
    is_load = 'ldp' in mnem

    rt1, sf = parse_reg(ops[0])
    rt2, _ = parse_reg(ops[1])
    sf_bit = 1 if sf else 0

    mem = parse_mem(ops, start=2)

    # Scale: 3 bits for 64-bit (divide by 8), 2 bits for 32-bit (divide by 4)
    scale = 3 if sf else 2
    imm7 = (mem.imm >> scale) & 0x7F

    opc = 0b10 if sf else 0b00

    if mem.post_index:
        index_bits = 0b001
    elif mem.pre_index:
        index_bits = 0b011
    else:
        index_bits = 0b010  # signed offset

    return (opc << 30) | (0b101 << 27) | (index_bits << 23) | (is_load << 22) | \
           (imm7 << 15) | (rt2 << 10) | (mem.base << 5) | rt1


def encode_adr_adrp(mnem: str, ops: list[str], labels: dict[str, int],
                    address: int, relocations: list) -> int:
    """ADR/ADRP: PC-relative address computation."""
    rd, _ = parse_reg(ops[0])
    label = ops[1].strip()
    is_adrp = mnem == 'adrp'

    if label in labels:
        offset = labels[label] - address
        if is_adrp:
            offset >>= 12
        immlo = offset & 0x3
        immhi = (offset >> 2) & 0x7FFFF
    else:
        relocations.append((address, label, mnem))
        immlo = immhi = 0

    op = 1 if is_adrp else 0
    return (op << 31) | (immlo << 29) | (0b10000 << 24) | (immhi << 5) | rd


MEMORY_DISPATCH: dict[str, object] = {
    'ldr':  encode_ldr_str,
    'str':  encode_ldr_str,
    'ldp':  encode_ldp_stp,
    'stp':  encode_ldp_stp,
}
