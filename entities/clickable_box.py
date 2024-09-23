from dataclasses import dataclass
from entities.point import Point


@dataclass(unsafe_hash=True)
class ClickableBox:
    label: str
    min_point: Point
    max_point: Point
    centroid: Point

    def to_dict(self):
        return {
            "label": self.label,
            "min_point": {"x": self.min_point.x, "y": self.min_point.y},
            "max_point": {"x": self.max_point.x, "y": self.max_point.y},
            "centroid": {"x": self.centroid.x, "y": self.centroid.y},
        }

    @staticmethod
    def from_dict(dict_elem):
        return ClickableBox(
            dict_elem["label"],
            Point(dict_elem["min_point"]["x"], dict_elem["min_point"]["y"]),
            Point(dict_elem["max_point"]["x"], dict_elem["max_point"]["y"]),
            Point(dict_elem["centroid"]["x"], dict_elem["centroid"]["y"]),
        )
