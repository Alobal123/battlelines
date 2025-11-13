from dataclasses import dataclass

@dataclass
class Health:
    current: int
    max_hp: int

    def clamp(self) -> None:
        if self.current < 0:
            self.current = 0
        if self.current > self.max_hp:
            self.current = self.max_hp

    def is_alive(self) -> bool:
        return self.current > 0
