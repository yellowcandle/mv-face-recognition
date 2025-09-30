from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class ROI:
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float
    area: int

    def __post_init__(self):
        if self.x2 <= self.x1:
            raise ValueError(f"x2 ({self.x2}) must be > x1 ({self.x1})")
        if self.y2 <= self.y1:
            raise ValueError(f"y2 ({self.y2}) must be > y1 ({self.y1})")

        computed_area = (self.x2 - self.x1) * (self.y2 - self.y1)
        if abs(self.area - computed_area) > 1:
            self.area = computed_area

    def expand(self, ratio: float, frame_width: int, frame_height: int) -> "ROI":
        if ratio < 1.0:
            raise ValueError(f"expand ratio must be >= 1.0, got {ratio}")

        center_x = (self.x1 + self.x2) / 2
        center_y = (self.y1 + self.y2) / 2

        current_width = self.x2 - self.x1
        current_height = self.y2 - self.y1

        new_width = current_width * ratio
        new_height = current_height * ratio

        new_x1 = int(max(0, center_x - new_width / 2))
        new_y1 = int(max(0, center_y - new_height / 2))
        new_x2 = int(min(frame_width, center_x + new_width / 2))
        new_y2 = int(min(frame_height, center_y + new_height / 2))

        new_area = (new_x2 - new_x1) * (new_y2 - new_y1)

        return ROI(
            x1=new_x1,
            y1=new_y1,
            x2=new_x2,
            y2=new_y2,
            confidence=self.confidence,
            area=new_area,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "confidence": self.confidence,
            "area": self.area,
        }
