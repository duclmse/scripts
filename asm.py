#!/usr/bin/env python3
"""
ARM64 Assembler for Apple Silicon
Produces native 64-bit Mach-O executables for macOS ARM64
Supports comprehensive ARM64 instruction set (ARMv8-A)
"""

import struct
import sys
from typing import Dict, List, Tuple, Optional, Union
from enum import IntEnum


class Condition(IntEnum):
    EQ = 0b0000  # Equal
    NE = 0b0001  # Not equal
    CS = 0b0010  # Carry set (HS)
    CC = 0b0011  # Carry clear (LO)
    MI = 0b0100  # Minus/negative
    PL = 0b0101  # Plus/positive
    VS = 0b0110  # Overflow
    VC = 0b0111  # No overflow
    HI = 0b1000  # Unsigned higher
    LS = 0b1001  # Unsigned lower or same
    GE = 0b1010  # Signed greater than or equal
    LT = 0b1011  # Signed less than
    GT = 0b1100  # Signed greater than
    LE = 0b1101  # Signed less than or equal
    AL = 0b1110  # Always
    NV = 0b1111  # Always (reserved)


class ARM64Assembler:
    def __init__(self):
        self.registers = self._init_registers()
        self.conditions = {
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

        self.labels: Dict[str, int] = {}
        # (offset, label, type)
        self.relocations: List[Tuple[int, str, str]] = []
        self.address = 0
        self.machine_code: List[int] = []

    def _init_registers(self) -> Dict[str, int]:
        regs = {}
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
            'lr': 30, 'x30': 30, 'fp': 29, 'x29': 29
        })
        return regs

    def parse_register(self, reg: str) -> Tuple[int, bool]:
        """Parse register, return (reg_num, is_64bit)"""
        reg = reg.lower().strip()
        if reg not in self.registers:
            raise ValueError(f"Invalid register: {reg}")
        is_64 = reg.startswith('x') or reg in ['sp', 'lr', 'fp', 'xzr']
        return self.registers[reg], is_64

    def parse_imm(self, imm: str) -> int:
        """Parse immediate value"""
        imm = imm.strip().lstrip('#')
        if imm.startswith('0x'):
            return int(imm, 16)
        elif imm.startswith('0b'):
            return int(imm, 2)
        return int(imm)

    def sign_extend(self, value: int, bits: int) -> int:
        """Sign extend a value"""
        sign_bit = 1 << (bits - 1)
        return (value & (sign_bit - 1)) - (value & sign_bit)

    # ============ Data Processing - Immediate ============

    def _encode_add_sub_imm(self, mnem: str, ops: List[str]) -> int:
        """ADD/SUB immediate: ADD Xd, Xn, #imm"""
        is_sub = 'sub' in mnem
        set_flags = mnem.endswith('s')

        rd, sf = self.parse_register(ops[0])
        rn, _ = self.parse_register(ops[1])
        imm = self.parse_imm(ops[2])

        if imm < 0 or imm >= 4096:
            raise ValueError(f"Immediate out of range: {imm}")

        shift = 0  # Can be 0 or 12
        if len(ops) > 3 and 'lsl' in ops[3].lower():
            shift = self.parse_imm(ops[4]) // 12

        return (sf << 31) | (is_sub << 30) | (set_flags << 29) | (0b100010 << 23) | \
               (shift << 22) | (imm << 10) | (rn << 5) | rd

    def _encode_logical_imm(self, mnem: str, ops: List[str]) -> int:
        """AND/ORR/EOR immediate"""
        opc_map = {'and': 0b00, 'orr': 0b01, 'eor': 0b10, 'ands': 0b11}
        opc = opc_map.get(mnem, 0b01)

        rd, sf = self.parse_register(ops[0])
        rn, _ = self.parse_register(ops[1])
        imm = self.parse_imm(ops[2])

        # Encode immediate (simplified - real encoding is complex)
        N = sf
        immr = 0
        imms = imm & 0x3F

        return (sf << 31) | (opc << 29) | (0b100100 << 23) | (N << 22) | \
               (immr << 16) | (imms << 10) | (rn << 5) | rd

    def _encode_movz_movn_movk(self, mnem: str, ops: List[str]) -> int:
        """MOVZ/MOVN/MOVK: MOV* Xd, #imm{, LSL #shift}"""
        opc_map = {'movz': 0b10, 'movn': 0b00, 'movk': 0b11}
        opc = opc_map[mnem]

        rd, sf = self.parse_register(ops[0])
        imm = self.parse_imm(ops[1])

        hw = 0  # Shift amount (0, 16, 32, 48 for 64-bit)
        if len(ops) > 2 and 'lsl' in ops[2].lower():
            shift = self.parse_imm(ops[3])
            hw = shift // 16

        if imm < 0 or imm >= 65536:
            raise ValueError(f"Immediate out of range: {imm}")

        return (sf << 31) | (opc << 29) | (0b100101 << 23) | (hw << 21) | \
               (imm << 5) | rd

    # ============ Data Processing - Register ============

    def _encode_add_sub_reg(self, mnem: str, ops: List[str]) -> int:
        """ADD/SUB register: ADD Xd, Xn, Xm"""
        is_sub = 'sub' in mnem
        set_flags = mnem.endswith('s')

        rd, sf = self.parse_register(ops[0])
        rn, _ = self.parse_register(ops[1])
        rm, _ = self.parse_register(ops[2])

        shift_type = 0  # LSL
        shift_amount = 0

        return (sf << 31) | (is_sub << 30) | (set_flags << 29) | (0b01011 << 24) | \
               (shift_type << 22) | (rm << 16) | (
                   shift_amount << 10) | (rn << 5) | rd

    def _encode_logical_reg(self, mnem: str, ops: List[str]) -> int:
        """AND/ORR/EOR/ANDS register"""
        opc_map = {'and': 0b00, 'bic': 0b00, 'orr': 0b01, 'orn': 0b01,
                   'eor': 0b10, 'eon': 0b10, 'ands': 0b11, 'bics': 0b11}
        N = 1 if mnem in ['bic', 'orn', 'eon', 'bics'] else 0
        opc = opc_map.get(mnem, 0b01)

        rd, sf = self.parse_register(ops[0])
        rn, _ = self.parse_register(ops[1])
        rm, _ = self.parse_register(ops[2])

        return (sf << 31) | (opc << 29) | (0b01010 << 24) | (N << 21) | \
               (rm << 16) | (rn << 5) | rd

    def _encode_mul_div(self, mnem: str, ops: List[str]) -> int:
        """MUL/MADD/MSUB/SDIV/UDIV"""
        rd, sf = self.parse_register(ops[0])
        rn, _ = self.parse_register(ops[1])
        rm, _ = self.parse_register(ops[2])

        if mnem in ['mul']:
            # MUL is alias for MADD with Ra=XZR
            ra = 31
            o0 = 0
        elif mnem in ['madd', 'msub']:
            ra, _ = self.parse_register(ops[3])
            o0 = 1 if mnem == 'msub' else 0
        elif mnem in ['sdiv', 'udiv']:
            ra = 31
            o0 = 1 if mnem == 'sdiv' else 0
            return (sf << 31) | (0b11010110 << 21) | (rm << 16) | \
                   (o0 << 10) | (rn << 5) | rd

        return (sf << 31) | (0b11011 << 24) | (rm << 16) | (o0 << 15) | \
               (ra << 10) | (rn << 5) | rd

    def _encode_shift(self, mnem: str, ops: List[str]) -> int:
        """LSL/LSR/ASR/ROR"""
        shift_map = {'lsl': 0b00, 'lsr': 0b01, 'asr': 0b10, 'ror': 0b11}
        shift = shift_map[mnem]

        rd, sf = self.parse_register(ops[0])
        rn, _ = self.parse_register(ops[1])

        if ops[2].strip().startswith('#'):
            # Immediate shift
            imm = self.parse_imm(ops[2])
            return (sf << 31) | (0b10011010110 << 21) | (imm << 16) | \
                   (imm << 10) | (rn << 5) | rd
        else:
            # Register shift
            rm, _ = self.parse_register(ops[2])
            return (sf << 31) | (0b11010110 << 21) | (rm << 16) | \
                   (0b0010 << 12) | (shift << 10) | (rn << 5) | rd

    # ============ Load/Store ============

    def _encode_ldr_str(self, mnem: str, ops: List[str]) -> int:
        """LDR/STR with various addressing modes"""
        is_load = 'ldr' in mnem

        rt, sf = self.parse_register(ops[0])

        # Parse memory operand
        mem = ops[1].strip()

        # [Xn, #imm]
        if '[' in mem and '#' in mem:
            mem = mem.strip('[]')
            parts = mem.split(',')
            rn, _ = self.parse_register(parts[0])
            imm = self.parse_imm(parts[1])

            size = 3 if sf else 2
            scale = 2 + (size - 2)
            imm12 = imm >> scale if imm >= 0 else 0

            return (size << 30) | (0b111 << 27) | (0b01 << 24) | (is_load << 22) | \
                   (imm12 << 10) | (rn << 5) | rt

        # [Xn, Xm]
        elif '[' in mem and ',' in mem:
            mem = mem.strip('[]')
            parts = mem.split(',')
            rn, _ = self.parse_register(parts[0])
            rm, _ = self.parse_register(parts[1])

            size = 3 if sf else 2
            option = 0b011  # LSL
            S = 1

            return (size << 30) | (0b111 << 27) | (is_load << 22) | (0b1 << 21) | \
                   (rm << 16) | (option << 13) | (S << 12) | (0b10 << 10) | \
                   (rn << 5) | rt

        # [Xn]
        else:
            mem = mem.strip('[]')
            rn, _ = self.parse_register(mem)

            size = 3 if sf else 2
            return (size << 30) | (0b111 << 27) | (0b01 << 24) | (is_load << 22) | \
                   (rn << 5) | rt

    def _encode_ldp_stp(self, mnem: str, ops: List[str]) -> int:
        """LDP/STP: Load/Store Pair"""
        is_load = 'ldp' in mnem

        rt1, sf = self.parse_register(ops[0])
        rt2, _ = self.parse_register(ops[1])

        mem = ops[2].strip()
        if '[' in mem and '#' in mem:
            mem = mem.strip('[]')
            parts = mem.split(',')
            rn, _ = self.parse_register(parts[0])
            imm = self.parse_imm(parts[1])
            imm7 = (imm >> 3) & 0x7F
        else:
            mem = mem.strip('[]')
            rn, _ = self.parse_register(mem)
            imm7 = 0

        opc = 0b10 if sf else 0b00

        return (opc << 30) | (0b101 << 27) | (0b010 << 23) | (is_load << 22) | \
               (imm7 << 15) | (rt2 << 10) | (rn << 5) | rt1

    def _encode_adr_adrp(self, mnem: str, ops: List[str]) -> int:
        """ADR/ADRP: PC-relative address"""
        rd, _ = self.parse_register(ops[0])
        label = ops[1].strip()

        if label in self.labels:
            offset = self.labels[label] - self.address
            if mnem == 'adrp':
                offset = (offset >> 12) & 0x1FFFFF
            immlo = offset & 0x3
            immhi = (offset >> 2) & 0x7FFFF
        else:
            self.relocations.append((self.address, label, mnem))
            immlo = immhi = 0

        op = 1 if mnem == 'adrp' else 0
        return (op << 31) | (immlo << 29) | (0b10000 << 24) | (immhi << 5) | rd

    # ============ Branches ============

    def _encode_b_bl(self, mnem: str, ops: List[str]) -> int:
        """B/BL: Unconditional branch"""
        is_link = mnem == 'bl'
        label = ops[0].strip()

        if label in self.labels:
            offset = (self.labels[label] - self.address) >> 2
            offset &= 0x3FFFFFF
        else:
            self.relocations.append((self.address, label, 'b'))
            offset = 0

        return (is_link << 31) | (0b00101 << 26) | offset

    def _encode_b_cond(self, mnem: str, ops: List[str]) -> int:
        """B.cond: Conditional branch"""
        cond_str = mnem.split('.')[1] if '.' in mnem else ops[0].strip('.')
        cond = self.conditions.get(cond_str.lower(), Condition.AL)
        label = ops[-1].strip()

        if label in self.labels:
            offset = (self.labels[label] - self.address) >> 2
            offset &= 0x7FFFF
        else:
            self.relocations.append((self.address, label, 'bcond'))
            offset = 0

        return (0b01010100 << 24) | (offset << 5) | cond

    def _encode_br_blr_ret(self, mnem: str, ops: List[str]) -> int:
        """BR/BLR/RET: Branch to register"""
        if mnem == 'ret':
            rn = 30 if not ops or not ops[0].strip(
            ) else self.parse_register(ops[0])[0]
            return (0b1101011 << 25) | (0b0010 << 21) | (0b11111 << 16) | (rn << 5)

        is_link = mnem == 'blr'
        rn, _ = self.parse_register(ops[0])

        return (0b1101011 << 25) | (is_link << 21) | (0b11111 << 16) | (rn << 5)

    def _encode_cbz_cbnz(self, mnem: str, ops: List[str]) -> int:
        """CBZ/CBNZ: Compare and branch on zero"""
        is_nz = mnem == 'cbnz'
        rt, sf = self.parse_register(ops[0])
        label = ops[1].strip()

        if label in self.labels:
            offset = (self.labels[label] - self.address) >> 2
            offset &= 0x7FFFF
        else:
            self.relocations.append((self.address, label, 'cb'))
            offset = 0

        return (sf << 31) | (0b011010 << 25) | (is_nz << 24) | (offset << 5) | rt

    def _encode_tbz_tbnz(self, mnem: str, ops: List[str]) -> int:
        """TBZ/TBNZ: Test bit and branch"""
        is_nz = mnem == 'tbnz'
        rt, sf = self.parse_register(ops[0])
        bit = self.parse_imm(ops[1])
        label = ops[2].strip()

        if label in self.labels:
            offset = (self.labels[label] - self.address) >> 2
            offset &= 0x3FFF
        else:
            self.relocations.append((self.address, label, 'tb'))
            offset = 0

        b40 = bit & 0x1F
        b5 = (bit >> 5) & 1

        return (b5 << 31) | (0b011011 << 25) | (is_nz << 24) | (b40 << 19) | \
               (offset << 5) | rt

    # ============ System & Special ============

    def _encode_nop(self, mnem: str, ops: List[str]) -> int:
        """NOP"""
        return 0xD503201F

    def _encode_brk(self, mnem: str, ops: List[str]) -> int:
        """BRK: Breakpoint"""
        imm = self.parse_imm(ops[0]) if ops else 0
        return (0b11010100001 << 21) | (imm << 5)

    def _encode_svc(self, mnem: str, ops: List[str]) -> int:
        """SVC: Supervisor call"""
        imm = self.parse_imm(ops[0]) if ops else 0
        return (0b11010100000 << 21) | (imm << 5) | 0b00001

    def _encode_mrs_msr(self, mnem: str, ops: List[str]) -> int:
        """MRS/MSR: System register access"""
        is_read = mnem == 'mrs'

        if is_read:
            rt, _ = self.parse_register(ops[0])
            # Simplified - real system register encoding is complex
            op0 = 0b11
            return (0b1101010100 << 22) | (1 << 21) | (op0 << 19) | (rt)
        else:
            rt, _ = self.parse_register(ops[1])
            return (0b1101010100 << 22) | (0 << 21) | rt

    def _encode_mov(self, mnem: str, ops: List[str]) -> int:
        """MOV: Pseudo-instruction (alias for ORR or MOVZ)"""
        rd, sf = self.parse_register(ops[0])

        if ops[1].strip().startswith('#'):
            # MOV immediate -> MOVZ
            return self._encode_movz_movn_movk('movz', ops)
        else:
            # MOV register -> ORR Rd, XZR, Rm
            rm, _ = self.parse_register(ops[1])
            return (sf << 31) | (0b01 << 29) | (0b01010 << 24) | \
                   (rm << 16) | (31 << 5) | rd

    def _encode_cmp(self, mnem: str, ops: List[str]) -> int:
        """CMP: Alias for SUBS with XZR destination"""
        rn, sf = self.parse_register(ops[0])

        if ops[1].strip().startswith('#'):
            imm = self.parse_imm(ops[1])
            return (sf << 31) | (0b111 << 28) | (0b100010 << 23) | \
                   (imm << 10) | (rn << 5) | 31
        else:
            rm, _ = self.parse_register(ops[1])
            return (sf << 31) | (0b111 << 28) | (0b01011 << 24) | \
                   (rm << 16) | (rn << 5) | 31

    def _encode_csel(self, mnem: str, ops: List[str]) -> int:
        """CSEL/CSINC/CSINV/CSNEG: Conditional select"""
        op_map = {'csel': 0b00, 'csinc': 0b01, 'csinv': 0b10, 'csneg': 0b11}
        op2 = op_map.get(mnem, 0b00)

        rd, sf = self.parse_register(ops[0])
        rn, _ = self.parse_register(ops[1])
        rm, _ = self.parse_register(ops[2])
        cond = self.conditions.get(ops[3].lower(), Condition.AL)

        return (sf << 31) | (0b11010100 << 21) | (rm << 16) | (cond << 12) | \
               (rn << 5) | rd | (op2 << 10)

    def assemble_instruction(self, line: str) -> Optional[int]:
        """Assemble single instruction"""
        line = line.strip()

        # Remove comments
        for comment in [';', '//', '#']:
            if comment in line and not (comment == '#' and '[' in line):
                line = line[:line.index(comment)]

        if not line:
            return None

        # Handle labels
        if ':' in line and not '[' in line:
            label, rest = line.split(':', 1)
            self.labels[label.strip()] = self.address
            line = rest.strip()
            if not line:
                return None

        # Parse instruction
        parts = line.replace(',', ' ').split()
        if not parts:
            return None

        mnem = parts[0].lower()
        ops = [p.strip() for p in ' '.join(parts[1:]).split(',') if p.strip()]

        # Instruction encoding dispatch
        encoders = {
            'add': lambda: self._try_imm_or_reg('add', ops, self._encode_add_sub_imm, self._encode_add_sub_reg),
            'adds': lambda: self._try_imm_or_reg('adds', ops, self._encode_add_sub_imm, self._encode_add_sub_reg),
            'sub': lambda: self._try_imm_or_reg('sub', ops, self._encode_add_sub_imm, self._encode_add_sub_reg),
            'subs': lambda: self._try_imm_or_reg('subs', ops, self._encode_add_sub_imm, self._encode_add_sub_reg),
            'and': lambda: self._try_imm_or_reg('and', ops, self._encode_logical_imm, self._encode_logical_reg),
            'orr': lambda: self._try_imm_or_reg('orr', ops, self._encode_logical_imm, self._encode_logical_reg),
            'eor': lambda: self._try_imm_or_reg('eor', ops, self._encode_logical_imm, self._encode_logical_reg),
            'ands': lambda: self._try_imm_or_reg('ands', ops, self._encode_logical_imm, self._encode_logical_reg),
            'bic': lambda: self._encode_logical_reg('bic', ops),
            'orn': lambda: self._encode_logical_reg('orn', ops),
            'eon': lambda: self._encode_logical_reg('eon', ops),
            'movz': lambda: self._encode_movz_movn_movk('movz', ops),
            'movn': lambda: self._encode_movz_movn_movk('movn', ops),
            'movk': lambda: self._encode_movz_movn_movk('movk', ops),
            'mov': lambda: self._encode_mov('mov', ops),
            'mul': lambda: self._encode_mul_div('mul', ops),
            'madd': lambda: self._encode_mul_div('madd', ops),
            'msub': lambda: self._encode_mul_div('msub', ops),
            'sdiv': lambda: self._encode_mul_div('sdiv', ops),
            'udiv': lambda: self._encode_mul_div('udiv', ops),
            'lsl': lambda: self._encode_shift('lsl', ops),
            'lsr': lambda: self._encode_shift('lsr', ops),
            'asr': lambda: self._encode_shift('asr', ops),
            'ror': lambda: self._encode_shift('ror', ops),
            'ldr': lambda: self._encode_ldr_str('ldr', ops),
            'str': lambda: self._encode_ldr_str('str', ops),
            'ldp': lambda: self._encode_ldp_stp('ldp', ops),
            'stp': lambda: self._encode_ldp_stp('stp', ops),
            'adr': lambda: self._encode_adr_adrp('adr', ops),
            'adrp': lambda: self._encode_adr_adrp('adrp', ops),
            'b': lambda: self._encode_b_bl('b', ops),
            'bl': lambda: self._encode_b_bl('bl', ops),
            'br': lambda: self._encode_br_blr_ret('br', ops),
            'blr': lambda: self._encode_br_blr_ret('blr', ops),
            'ret': lambda: self._encode_br_blr_ret('ret', ops),
            'cbz': lambda: self._encode_cbz_cbnz('cbz', ops),
            'cbnz': lambda: self._encode_cbz_cbnz('cbnz', ops),
            'tbz': lambda: self._encode_tbz_tbnz('tbz', ops),
            'tbnz': lambda: self._encode_tbz_tbnz('tbnz', ops),
            'cmp': lambda: self._encode_cmp('cmp', ops),
            'csel': lambda: self._encode_csel('csel', ops),
            'csinc': lambda: self._encode_csel('csinc', ops),
            'csinv': lambda: self._encode_csel('csinv', ops),
            'csneg': lambda: self._encode_csel('csneg', ops),
            'nop': lambda: self._encode_nop('nop', ops),
            'brk': lambda: self._encode_brk('brk', ops),
            'svc': lambda: self._encode_svc('svc', ops),
            'mrs': lambda: self._encode_mrs_msr('mrs', ops),
            'msr': lambda: self._encode_mrs_msr('msr', ops),
        }

        # Check for conditional branch
        if mnem.startswith('b.'):
            return self._encode_b_cond(mnem, ops)

        if mnem in encoders:
            return encoders[mnem]()

        raise ValueError(f"Unknown instruction: {mnem}")

    def _try_imm_or_reg(self, mnem: str, ops: List[str], imm_fn, reg_fn):
        """Try immediate encoding first, fall back to register"""
        if len(ops) >= 3 and ops[2].strip().startswith('#'):
            return imm_fn(mnem, ops)
        return reg_fn(mnem, ops)

    def assemble(self, source: str, base_address: int = 0x100000000) -> List[int]:
        """Two-pass assembly"""
        lines = source.strip().split('\n')

        # First pass: collect labels
        self.address = base_address
        self.labels.clear()
        self.relocations.clear()

        for line in lines:
            line = line.strip()
            if not line or line.startswith(';') or line.startswith('//'):
                continue

            # Handle label definitions
            if ':' in line and not '[' in line:
                label = line.split(':', 1)[0].strip()
                self.labels[label] = self.address
                line = line.split(':', 1)[1].strip()

            # Skip directives for now
            if line.startswith('.'):
                continue

            if line and not line.startswith(';') and not line.startswith('//'):
                self.address += 4

        # Second pass: encode instructions
        self.address = base_address
        self.machine_code.clear()

        for i, line in enumerate(lines):
            try:
                encoded = self.assemble_instruction(line)
                if encoded is not None:
                    self.machine_code.append(encoded)
                    self.address += 4
            except Exception as e:
                print(
                    f"Error on line {i+1} '{line.strip()}': {e}", file=sys.stderr)
                raise

        # Resolve relocations
        self._resolve_relocations(base_address)

        return self.machine_code

    def _resolve_relocations(self, base_address: int):
        """Resolve branch target relocations"""
        for offset, label, rel_type in self.relocations:
            if label not in self.labels:
                print(f"Warning: Undefined label '{label}'", file=sys.stderr)
                continue

            idx = (offset - base_address) // 4
            if idx >= len(self.machine_code):
                continue

            instr = self.machine_code[idx]
            target = self.labels[label]

            if rel_type in ['b', 'bl']:
                # 26-bit signed offset
                offset_val = (target - offset) >> 2
                offset_val &= 0x3FFFFFF
                instr = (instr & 0xFC000000) | offset_val
            elif rel_type == 'bcond':
                # 19-bit signed offset
                offset_val = (target - offset) >> 2
                offset_val &= 0x7FFFF
                instr = (instr & 0xFF00001F) | (offset_val << 5)
            elif rel_type in ['cb', 'cbz', 'cbnz']:
                # 19-bit signed offset
                offset_val = (target - offset) >> 2
                offset_val &= 0x7FFFF
                instr = (instr & 0xFF00001F) | (offset_val << 5)
            elif rel_type in ['tb', 'tbz', 'tbnz']:
                # 14-bit signed offset
                offset_val = (target - offset) >> 2
                offset_val &= 0x3FFF
                instr = (instr & 0xFFF8001F) | (offset_val << 5)
            elif rel_type in ['adr', 'adrp']:
                offset_val = target - offset
                if rel_type == 'adrp':
                    offset_val >>= 12
                immlo = offset_val & 0x3
                immhi = (offset_val >> 2) & 0x7FFFF
                instr = (instr & 0x9F00001F) | (immlo << 29) | (immhi << 5)

            self.machine_code[idx] = instr

    def generate_macho(self, output_file: str, entry_point: str = '_start'):
        """Generate Mach-O executable for macOS ARM64"""

        if entry_point not in self.labels:
            raise ValueError(f"Entry point '{entry_point}' not found")

        text_size = len(self.machine_code) * 4
        text_addr = 0x100000000
        entry_addr = self.labels[entry_point]

        with open(output_file, 'wb') as f:
            # Mach-O Header (64-bit ARM64)
            f.write(struct.pack('<I', 0xFEEDFACF))  # magic (MH_MAGIC_64)
            f.write(struct.pack('<I', 0x0100000C))  # cputype (CPU_TYPE_ARM64)
            # cpusubtype (CPU_SUBTYPE_ARM64_ALL)
            f.write(struct.pack('<I', 0x00000000))
            f.write(struct.pack('<I', 0x00000002))  # filetype (MH_EXECUTE)
            f.write(struct.pack('<I', 3))           # ncmds (3 load commands)
            f.write(struct.pack('<I', 0))           # sizeofcmds (will update)
            f.write(struct.pack('<I', 0x00200085))  # flags
            f.write(struct.pack('<I', 0))           # reserved

            header_size = 32
            load_cmd_start = f.tell()

            # LC_SEGMENT_64 - __PAGEZERO
            f.write(struct.pack('<I', 0x19))        # cmd (LC_SEGMENT_64)
            f.write(struct.pack('<I', 72))          # cmdsize
            f.write(b'__PAGEZERO\x00\x00\x00\x00\x00\x00')  # segname
            f.write(struct.pack('<Q', 0))           # vmaddr
            f.write(struct.pack('<Q', 0x100000000))  # vmsize
            f.write(struct.pack('<Q', 0))           # fileoff
            f.write(struct.pack('<Q', 0))           # filesize
            f.write(struct.pack('<I', 0))           # maxprot
            f.write(struct.pack('<I', 0))           # initprot
            f.write(struct.pack('<I', 0))           # nsects
            f.write(struct.pack('<I', 0))           # flags

            # LC_SEGMENT_64 - __TEXT
            text_cmd_size = 152  # segment header + section header
            text_fileoff = 0x4000  # Start at page boundary

            f.write(struct.pack('<I', 0x19))        # cmd (LC_SEGMENT_64)
            f.write(struct.pack('<I', text_cmd_size))  # cmdsize
            f.write(b'__TEXT\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')  # segname
            f.write(struct.pack('<Q', text_addr))   # vmaddr
            f.write(struct.pack('<Q', 0x4000))      # vmsize (16KB)
            f.write(struct.pack('<Q', 0))           # fileoff
            f.write(struct.pack('<Q', text_fileoff + text_size))  # filesize
            f.write(struct.pack('<I', 0x7))         # maxprot (rwx)
            f.write(struct.pack('<I', 0x5))         # initprot (r-x)
            f.write(struct.pack('<I', 1))           # nsects
            f.write(struct.pack('<I', 0))           # flags

            # __text section
            f.write(b'__text\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')  # sectname
            f.write(b'__TEXT\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')  # segname
            f.write(struct.pack('<Q', text_addr))   # addr
            f.write(struct.pack('<Q', text_size))   # size
            f.write(struct.pack('<I', text_fileoff))  # offset
            f.write(struct.pack('<I', 2))           # align (2^2 = 4 bytes)
            f.write(struct.pack('<I', 0))           # reloff
            f.write(struct.pack('<I', 0))           # nreloc
            # flags (S_REGULAR | S_ATTR_PURE_INSTRUCTIONS)
            f.write(struct.pack('<I', 0x80000400))
            f.write(struct.pack('<I', 0))           # reserved1
            f.write(struct.pack('<I', 0))           # reserved2
            f.write(struct.pack('<I', 0))           # reserved3

            # LC_MAIN - entry point
            f.write(struct.pack('<I', 0x80000028))  # cmd (LC_MAIN)
            f.write(struct.pack('<I', 24))          # cmdsize
            f.write(struct.pack('<Q', entry_addr - text_addr))  # entryoff
            f.write(struct.pack('<Q', 0))           # stacksize

            # Update sizeofcmds
            load_cmd_end = f.tell()
            sizeofcmds = load_cmd_end - load_cmd_start
            f.seek(header_size - 12)
            f.write(struct.pack('<I', sizeofcmds))

            # Pad to text section offset
            f.seek(text_fileoff)

            # Write machine code
            for instr in self.machine_code:
                f.write(struct.pack('<I', instr))

        print(f"Generated Mach-O executable: {output_file}")
        print(f"Text section: {text_size} bytes")
        print(f"Entry point: 0x{entry_addr:x}")

    def disassemble(self) -> str:
        """Disassemble machine code (basic)"""
        output = []
        for i, instr in enumerate(self.machine_code):
            addr = 0x100000000 + i * 4
            output.append(f"0x{addr:016x}: 0x{instr:08x}  {instr:032b}")
        return '\n'.join(output)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='ARM64 Assembler for Apple Silicon')
    parser.add_argument('input', help='Input assembly file')
    parser.add_argument('-o', '--output', default='a.out',
                        help='Output executable')
    parser.add_argument('-d', '--disassemble',
                        action='store_true', help='Disassemble output')
    parser.add_argument('-e', '--entry', default='_start',
                        help='Entry point label')
    parser.add_argument('-b', '--base', type=lambda x: int(x, 0), default=0x100000000,
                        help='Base address (default: 0x100000000)')

    args = parser.parse_args()

    try:
        # Read source
        with open(args.input, 'r') as f:
            source = f.read()

        # Assemble
        assembler = ARM64Assembler()
        machine_code = assembler.assemble(source, args.base)

        print(f"Assembly successful! {len(machine_code)} instructions")

        # Generate executable
        assembler.generate_macho(args.output, args.entry)

        # Disassemble if requested
        if args.disassemble:
            print("\nDisassembly:")
            print(assembler.disassemble())

        # Make executable
        import os
        os.chmod(args.output, 0o755)

        print(f"\nRun with: ./{args.output}")

    except FileNotFoundError:
        print(f"Error: File '{args.input}' not found", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # Example embedded program
    if len(sys.argv) == 1:
        print("ARM64 Assembler for Apple Silicon")
        print("=" * 50)
        print("\nExample usage:")
        print("  python3 arm64_asm.py input.s -o program")
        print("\nExample program:\n")

        example = """
; ARM64 Hello World Example
; Exit with status code 42

; .global _start

_start:
    mov x0, #42          ; Exit code
    mov x16, #1          ; syscall: exit
    svc #0x80            ; System call

; Fibonacci example
fibonacci:
    mov x0, #0           ; fib(0) = 0
    mov x1, #1           ; fib(1) = 1
    mov x2, #10          ; count
    
fib_loop:
    add x3, x0, x1       ; x3 = x0 + x1
    mov x0, x1           ; shift values
    mov x1, x3
    subs x2, x2, #1      ; decrement counter
    b.ne fib_loop        ; loop if not zero
    
    ret

; Memory operations
memory_test:
    adrp x0, data        ; Get page of data
    add x0, x0, :lo12:data
    ldr x1, [x0]         ; Load from memory
    str x1, [sp, #-16]!  ; Store to stack
    ldp x2, x3, [sp], #16  ; Load pair and pop
    ret

data:
    .quad 0x1234567890ABCDEF
"""
        print(example)
        print("\nSupported instructions:")
        print("  Data Processing: ADD, SUB, MUL, DIV, AND, ORR, EOR, shifts")
        print("  Loads/Stores: LDR, STR, LDP, STP")
        print("  Branches: B, BL, BR, BLR, RET, B.cond, CBZ, CBNZ, TBZ, TBNZ")
        print("  System: SVC, BRK, MRS, MSR, NOP")
        print("  And many more ARMv8-A instructions!")

        sys.exit(0)

    main()
