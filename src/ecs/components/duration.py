from dataclasses import dataclass

@dataclass(slots=True)
class Duration:
    value: float  # seconds
