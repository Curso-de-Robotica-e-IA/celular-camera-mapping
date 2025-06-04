from pathlib import Path
import cv2

from camera_mapper.constants import SIZE_IN_SCREEN
from camera_mapper.screen_processing.image_processing import (
    draw_clickable_elements,
    load_image,
    proportional_resize,
)

from typing import Dict, List, Tuple
import numpy as np


def click_on_image(image_path: str) -> List[np.ndarray]:
    """
    Opens an image and allows the user to click on it to select points.
    The clicked points are returned as a list of tuples (x, y).
    Args:
        image_path (str): The path to the image file.
    Returns:
        List[np.ndarray]: A list of tuples representing the clicked points (x, y).
    """
    clicked_points = []

    def mouse_callback(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            clicked_points.append((x, y))

    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Image '{image_path}' not found")
    original_height = img.shape[0]
    resized_image = proportional_resize(img, target_height=SIZE_IN_SCREEN)
    cv2.namedWindow("Click Points")
    cv2.setMouseCallback("Click Points", mouse_callback)

    cv2.imshow("Click Points", resized_image)
    while True:
        if cv2.waitKey(20) & 0xFF == 27:  # Optional: Press 'Esc' to quit
            break

    cv2.destroyAllWindows()
    # Convert clicked points to original image coordinates
    clicked_points = [
        (
            int(x * original_height / resized_image.shape[0]),
            int(y * original_height / resized_image.shape[0]),
        )
        for x, y in clicked_points
    ]
    return np.array(clicked_points, dtype=np.int32)


def find_nearest_element_to_click(
    click: np.ndarray, clickables: Dict[str, np.ndarray]
) -> str:
    """
    Finds the nearest clickable element to the clicked point.
    Args:
        click (np.ndarray): The point where the user clicked.
        clickables (Dict[str, np.ndarray]): A dictionary where keys are centroids of elements
                                             and values are their corresponding positions.
    Returns:
        str: The centroid of the nearest clickable element.
    """
    if not clickables:
        return None
    elements_centroids = [
        np.array(list(map(int, centroid.split(":")))) for centroid in clickables.keys()
    ]
    distances = [np.linalg.norm(element - click) for element in elements_centroids]
    nearest_index = np.argmin(distances)
    nearest_centroid = list(clickables.keys())[nearest_index]
    return nearest_centroid


def match_elements_to_clicks(
    clicks: List[np.ndarray], clickables: Dict[str, np.ndarray]
) -> Dict[str, Tuple[int, int]]:
    """
    Matches clicked points to clickable elements.
    Args:
        clicks (List[Tuple[int, int]]): A list of clicked points (x, y).
        clickables (Dict[str, np.ndarray]): A dictionary where keys are centroids of elements
                                             and values are their corresponding positions.
    Returns:
        Dict[str, Tuple[int, int]]: A dictionary where keys are centroids of clickable elements
                                     and values are the corresponding clicked points.
    """
    matched_elements = {}
    for click in clicks:
        nearest_element = find_nearest_element_to_click(click, clickables)
        if nearest_element:
            matched_elements[nearest_element] = clickables[nearest_element]
    return matched_elements


def confirm_labeling(
    image_path: Path, clickables: Dict[str, np.ndarray], label_name: str
) -> bool:
    """
    Displays the labeled image with clickable elements and asks the user to confirm the labels.
    Args:
        image_path (Path): The path to the image file.
        clickables (Dict[str, np.ndarray]): A dictionary where keys are centroids of elements
                                             and values are their corresponding positions.
        label_name (str): The name of the label to confirm.
    Returns:
        bool: True if the user confirms the labels, False otherwise.
    """
    print("Please confirm the action elements you have clicked")
    print("Press 'Esc' to exit screen.")
    image = load_image(image_path)
    labeled_image = draw_clickable_elements(image=image, clickables=clickables)
    resized_image = proportional_resize(labeled_image, target_height=SIZE_IN_SCREEN)
    cv2.namedWindow(f"Confirm {label_name}")
    cv2.imshow(f"Confirm {label_name}", resized_image)
    while True:
        if cv2.waitKey(20) & 0xFF == 27:  # Optional: Press 'Esc' to quit
            break
    cv2.destroyAllWindows()
    ans = input(f"Are all {label_name} correct ([y]/n)?: ")
    if "n" in ans.lower():
        print("Please re-mark the elements.")
        ans = False
    else:
        print(f"Found {(len(clickables))} {label_name}.")
        ans = True
    return ans
