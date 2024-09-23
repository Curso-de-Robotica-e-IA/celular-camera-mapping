from dataclasses import dataclass


@dataclass(unsafe_hash=True)
class Point:
    x: int
    y: int

    def to_tuple(self):
        return (self.x, self.y)
