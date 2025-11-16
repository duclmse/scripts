"""Shared type inference for converting raw string values to Python types"""


class ValueConverter:
    @staticmethod
    def infer(value: str) -> int | float | str | None:
        """Convert a string to the most specific type: int, float, str, or None for empty."""
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass
        return value
