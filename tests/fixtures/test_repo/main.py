"""Sample Python module for testing ingestion pipeline."""


class Calculator:
    """A simple calculator class."""

    def __init__(self, precision: int = 2) -> None:
        self.precision = precision

    def add(self, a: float, b: float) -> float:
        """Add two numbers."""
        return round(a + b, self.precision)

    def subtract(self, a: float, b: float) -> float:
        """Subtract b from a."""
        return round(a - b, self.precision)


def greet(name: str) -> str:
    """Return a greeting message."""
    return f"Hello, {name}!"


def compute_sum(numbers: list[int]) -> int:
    """Compute the sum of a list of integers."""
    total = 0
    for n in numbers:
        total += n
    return total
