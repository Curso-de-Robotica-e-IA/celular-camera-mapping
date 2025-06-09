from xml.etree.ElementTree import ElementTree
from typing import Dict, Tuple

import numpy as np


def clickable_elements(
    xml_tree: ElementTree,
) -> Tuple[Dict[str, np.ndarray], Dict[str, np.ndarray]]:
    """
    Extract clickable elements from an XML tree.

    Args:
        xml_tree (ElementTree): The XML tree to process.

    Returns:
        Dict[str, np.ndarray]: A dictionary where keys are resource IDs of clickable elements
                        and values are their bounds.
        Tuple[Dict[str, np.ndarray], Dict[str, np.ndarray]]: A dictionary where keys are XML elements and values are their bounds.
    """
    clickables = {}
    elements = {}
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
                text = elem.get("text")
                description = elem.get("content-desc")
                name = text if len(text) > len(description) else description
                name = name.strip().replace(" ", "_").lower()
                elements[name] = np.array([begin, end], dtype=np.int32)
    return clickables, elements


def find_element(
    element: str, clickables: Dict[str, np.ndarray]
) -> Tuple[str, np.ndarray]:
    """
    Find an element in the clickable elements.

    Args:
        element (str): Part of the name element to find. Preferably a pattern.
        clickables (Dict[str, np.ndarray]): A dictionary of clickable elements with their bounds.

    Returns:
        Tuple[str, np.ndarray]: The name and bounds of the found element.
    """
    for name, bounds in clickables.items():
        pattern = element.strip().replace(" ", "_").lower()
        if pattern in name:
            return name, bounds
    return "", np.array([])  # Return empty if not found
