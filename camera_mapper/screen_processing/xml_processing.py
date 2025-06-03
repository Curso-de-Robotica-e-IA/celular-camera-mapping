from xml.etree.ElementTree import ElementTree
from typing import Dict

import numpy as np


def clickable_elements(xml_tree: ElementTree) -> Dict[str, np.ndarray]:
    """
    Extract clickable elements from an XML tree.

    Args:
        xml_tree (ElementTree): The XML tree to process.

    Returns:
        Dict[str, np.ndarray]: A dictionary where keys are resource IDs of clickable elements
                        and values are their bounds.
    """
    clickables = {}
    for elem in xml_tree.iter():
        if elem.get("clickable") == "true":
            bounds = elem.get("bounds")
            if bounds:
                begin, end = bounds.strip("[]").split("][")
                begin = list(map(int, begin.split(",")))
                end = list(map(int, end.split(",")))
                centroid = ((begin[0] + end[0]) // 2, (begin[1] + end[1]) // 2)
                centroid = f"{centroid[0]}:{centroid[1]}"
                clickables[centroid] = np.array([begin, end], dtype=np.int32)
    return clickables
