"""ARM64 enumerations"""

from enum import IntEnum


class Condition(IntEnum):
    EQ = 0b0000  # Equal
    NE = 0b0001  # Not equal
    CS = 0b0010  # Carry set  (alias: HS)
    CC = 0b0011  # Carry clear (alias: LO)
    MI = 0b0100  # Minus / negative
    PL = 0b0101  # Plus / positive or zero
    VS = 0b0110  # Overflow
    VC = 0b0111  # No overflow
    HI = 0b1000  # Unsigned higher
    LS = 0b1001  # Unsigned lower or same
    GE = 0b1010  # Signed ≥
    LT = 0b1011  # Signed <
    GT = 0b1100  # Signed >
    LE = 0b1101  # Signed ≤
    AL = 0b1110  # Always
    NV = 0b1111  # Always (reserved)
