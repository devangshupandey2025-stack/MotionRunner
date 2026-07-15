from dataclasses import dataclass
import math

@dataclass
class Landmark:
    x: float
    y: float
    z: float
    visibility: float

    def distance_to(self, other: 'Landmark') -> float:
        return math.sqrt(
            (self.x - other.x) ** 2 +
            (self.y - other.y) ** 2 +
            (self.z - other.z) ** 2
        )

    def midpoint(self, other: 'Landmark') -> 'Landmark':
        return Landmark(
            x=(self.x + other.x) / 2,
            y=(self.y + other.y) / 2,
            z=(self.z + other.z) / 2,
            visibility=min(self.visibility, other.visibility),
        )

    def to_tuple(self) -> tuple:
        return (self.x, self.y)

    def __add__(self, other: 'Landmark') -> 'Landmark':
        return Landmark(
            x=self.x + other.x,
            y=self.y + other.y,
            z=self.z + other.z,
            visibility=min(self.visibility, other.visibility),
        )

    def __truediv__(self, scalar: float) -> 'Landmark':
        return Landmark(
            x=self.x / scalar,
            y=self.y / scalar,
            z=self.z / scalar,
            visibility=self.visibility,
        )


def angle_between(a: Landmark, b: Landmark, c: Landmark) -> float:
    ab = (a.x - b.x, a.y - b.y)
    cb = (c.x - b.x, c.y - b.y)
    dot = ab[0] * cb[0] + ab[1] * cb[1]
    mag_ab = math.sqrt(ab[0] ** 2 + ab[1] ** 2)
    mag_cb = math.sqrt(cb[0] ** 2 + cb[1] ** 2)
    if mag_ab * mag_cb == 0:
        return 0.0
    cos_angle = max(-1.0, min(1.0, dot / (mag_ab * mag_cb)))
    return math.degrees(math.acos(cos_angle))
