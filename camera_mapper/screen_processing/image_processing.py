from pathlib import Path
from typing import Dict, List, Tuple, TypedDict

import cv2
import numpy as np

from camera_mapper.constants import CLUSTER_THRESHOLD


class Line(TypedDict):
    x1: int
    y1: int
    x2: int
    y2: int


def load_image(image_path: Path) -> cv2.typing.MatLike:
    """
    Load an image from the specified path.

    Args:
        image_path (Path): The path to the image file.

    Returns:
        cv2.typing.MatLike: The loaded image.
    Raises:
        FileNotFoundError: If the image file does not exist or cannot be read.
    """
    return cv2.imread(str(image_path))


def merge_contours(
    contour1: cv2.typing.MatLike, contour2: cv2.typing.MatLike
) -> cv2.typing.MatLike:
    """
    Merge two contours into one.

    Args:
        contour1 (cv2.typing.MatLike): The first contour.
        contour2 (cv2.typing.MatLike): The second contour.

    Returns:
        cv2.typing.MatLike: The merged contour.
    """

    return np.concatenate((contour1, contour2), axis=0)


def calculate_contour_distance(
    contour1: cv2.typing.MatLike, contour2: cv2.typing.MatLike
) -> int:
    """
    Calculate the distance between two contours.

    Args:
        contour1 (cv2.typing.MatLike): The first contour.
        contour2 (cv2.typing.MatLike): The second contour.

    Returns:
        int: The calculated distance between the two contours.
    """

    x1, y1, w1, h1 = cv2.boundingRect(contour1)
    c_x1 = x1 + w1 / 2
    c_y1 = y1 + h1 / 2

    x2, y2, w2, h2 = cv2.boundingRect(contour2)
    c_x2 = x2 + w2 / 2
    c_y2 = y2 + h2 / 2

    return int(max(abs(c_x1 - c_x2) - (w1 + w2) / 2, abs(c_y1 - c_y2) - (h1 + h2) / 2))


def agglomerative_cluster(
    contours: List[np.ndarray], threshold_distance: int
) -> List[np.ndarray]:
    """
    Perform agglomerative clustering to merge contours that are within a certain distance of each other.

    Args:
        contours (list[np.ndarray]): A list of contours.
        threshold_distance (int): The distance threshold for merging contours.

    Returns:
        list[np.ndarray]: The clustered contours.
    """

    current_contours = contours
    while len(current_contours) > 1:
        min_distance = None
        min_coordinate = None

        for x in range(len(current_contours) - 1):
            for y in range(x + 1, len(current_contours)):
                distance = calculate_contour_distance(
                    current_contours[x], current_contours[y]
                )
                if min_distance is None:
                    min_distance = distance
                    min_coordinate = (x, y)
                elif distance < min_distance:
                    min_distance = distance
                    min_coordinate = (x, y)

        if (
            min_distance is not None
            and min_coordinate is not None
            and min_distance < threshold_distance
        ):
            index1, index2 = min_coordinate
            current_contours[index1] = merge_contours(
                current_contours[index1], current_contours[index2]
            )
            current_contours.pop(index2)
        else:
            break

    return current_contours


def find_contours_in_image(image: cv2.typing.MatLike) -> Dict[str, np.ndarray]:
    """
    Find contours in an image and return a list of clickable boxes.

    Args:
        image (cv2.typing.MatLike): The input image.

    Returns:
        Dict[str, np.ndarray]: A dictionary where keys are centroids of detected contours
                                and values are arrays containing the start and end points of the bounding rectangles.
    """

    edged = cv2.Canny(image, 30, 200)
    contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

    contours_list = []
    for elem in contours:
        contours_list.append(elem)

    filters_contours = agglomerative_cluster(contours_list, CLUSTER_THRESHOLD)

    detections = {}

    for cnt in filters_contours:
        x, y, w, h = cv2.boundingRect(cnt)
        begin = np.array([x, y])
        end = np.array([x + w, y + h])
        centroid = (begin + end) // 2
        centroid = f"{centroid[0]}:{centroid[1]}"
        detections[centroid] = np.array([begin, end], dtype=np.int32)

    return detections


def draw_clickable_elements(
    image: np.ndarray, clickables: Dict[str, np.ndarray], with_text: bool = False
) -> np.ndarray:
    """
    Draw clickable elements on an image.

    Args:
        image (np.ndarray): The image to draw on.
        clickables (Dict[str, np.ndarray]): A dictionary of clickable elements with their bounds.
        with_text (bool): Whether to include the index in the text label.

    Returns:
        np.ndarray: The image with clickable elements highlighted.
    """
    new_image = image.copy()

    for text, bounds in clickables.items():
        cv2.rectangle(new_image, bounds[0], bounds[1], (0, 255, 0), 2)
        cv2.putText(
            new_image,
            text if with_text else "",
            (bounds[0][0], bounds[0][1]),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            2,
        )
    return new_image


def centroid_in_bounds(centroid: str, bounds: np.ndarray) -> bool:
    """
    Check if a centroid is within the bounds defined by a bounding rectangle.

    Args:
        centroid (str): The centroid in the format "x:y".
        bounds (np.ndarray): An array containing the start and end points of the bounding rectangle.

    Returns:
        bool: True if the centroid is within the bounds, False otherwise.
    """
    x, y = map(int, centroid.split(":"))
    return bounds[0][0] <= x <= bounds[1][0] and bounds[0][1] <= y <= bounds[1][1]


def merge_bounds(
    from_image: Dict[str, np.ndarray], from_xml: Dict[str, np.ndarray]
) -> Dict[str, np.ndarray]:
    """
    Merge bounds from image and XML data.

    Args:
        from_image (Dict[str, np.ndarray]): Bounds extracted from the image.
        from_xml (Dict[str, np.ndarray]): Bounds extracted from the XML.

    Returns:
        Dict[str, np.ndarray]: Merged bounds.
    """
    uncommon_bounds = {}
    for image_centroid, image_bounds in from_image.items():
        found_common = False
        for xml_bounds in from_xml.values():
            if centroid_in_bounds(image_centroid, xml_bounds):
                found_common = True
                break
        if not found_common:
            uncommon_bounds[image_centroid] = image_bounds
    merged_bounds = {}
    merged_bounds.update(from_xml)
    merged_bounds.update(uncommon_bounds)
    return merged_bounds


def separate_xml_from_image_clickables(
    from_image: Dict[str, np.ndarray], from_xml: Dict[str, np.ndarray]
) -> Dict[str, np.ndarray]:
    """
    Separate XML clickables from image clickables.

    Args:
        from_image (Dict[str, np.ndarray]): Bounds extracted from the image.
        from_xml (Dict[str, np.ndarray]): Bounds extracted from the XML.

    Returns:
        Dict[str, np.ndarray]: Clickables that are only in the image.
    """
    uncommon_bounds = {}
    for image_centroid, image_bounds in from_image.items():
        found_common = False
        for xml_bounds in from_xml.values():
            if centroid_in_bounds(image_centroid, xml_bounds):
                found_common = True
                break
        if not found_common:
            uncommon_bounds[image_centroid] = image_bounds
    return uncommon_bounds


def proportional_resize(image, target_width=None, target_height=None):
    """
    Resize an image proportionally to fit within the specified target width and height.
    """
    height, width = image.shape[:2]

    if target_width is None and target_height is None:
        return image

    if target_width is None:
        scale_factor = target_height / height
    elif target_height is None:
        scale_factor = target_width / width
    else:
        scale_factor = min(target_width / width, target_height / height)

    new_width = int(width * scale_factor)
    new_height = int(height * scale_factor)

    resized_image = cv2.resize(
        image, (new_width, new_height), interpolation=cv2.INTER_AREA
    )

    return resized_image


def blur_patterns() -> List[cv2.typing.MatLike]:
    """
    Load and blur the patterns used for template matching.

    Returns:
        List[cv2.typing.MatLike]: The list of the image patterns of blur button.
    """
    patterns = []
    for i in range(4):
        pattern_path = Path(__file__).parent / "blur_buttons" / f"pattern_{i}.png"
        pattern = load_image(pattern_path)[:, :, 0]
        _, pattern = cv2.threshold(pattern, 200, 255, cv2.THRESH_BINARY)
        patterns.append(pattern)
    return patterns


def search_for_patterns(
    image: cv2.typing.MatLike, patterns: List[cv2.typing.MatLike]
) -> Tuple[np.ndarray, int]:
    """
    Search for the patterns in the image using template matching.

    Args:
        image (cv2.typing.MatLike): The input image.
        patterns (List[cv2.typing.MatLike]): The list of patterns to search for.

    Returns:
        Tuple[np.ndarray, int]: The bounding box of the patterns and its index if found, otherwise (-1, -1).
    """
    for i, pattern in enumerate(patterns):
        w, h = pattern.shape[::-1]
        _, image_threshed = cv2.threshold(image[:, :, 0], 200, 255, cv2.THRESH_BINARY)
        res = cv2.matchTemplate(image_threshed, pattern, cv2.TM_CCOEFF_NORMED)
        threshold = 0.8
        loc = np.where(res >= threshold)
        if np.any(loc):
            _, _, _, top_left = cv2.minMaxLoc(res)
            bottom_right = (top_left[0] + w, top_left[1] + h)
            return (np.array([top_left, bottom_right]), i)
    return (np.array([[-1, -1], [-1, -1]]), -1)


def get_middle_blur_circle_bar(image: cv2.typing.MatLike) -> np.ndarray:
    """
    Extracts the middle point of the blur bar from the given image.

    Args:
        image (cv2.typing.MatLike): Input image with a blur bar.

    Returns:
        np.ndarray: The middle point of the blur bar.
    """
    lower = np.array([0, 200, 254])
    upper = np.array([20, 205, 255])

    mask = cv2.inRange(image, lower, upper)
    edges = cv2.Canny(mask, 50, 150, apertureSize=3)

    # extract lines of the edges
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 15, 50, 3)

    # Get line with the maximum length
    if lines is not None:
        max_length = 0
        longest_line = lines[0][0]
        for line in lines:
            x1, y1, x2, y2 = line[0]
            length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
            if length > max_length:
                max_length = length
                longest_line = line[0]

        mid_point = (
            (longest_line[0] + longest_line[2]) // 2,
            (longest_line[1] + longest_line[3]) // 2,
        )
        mid_point = np.array(mid_point, dtype=np.int32)
        return mid_point
    return np.array([])


def get_blur_seekbar(image: cv2.typing.MatLike) -> Line:
    """
    Extracts the blur seek bar from the given image.

    Args:
        image (cv2.typing.MatLike): Input image with a blur seek bar.

    Returns:
        Line: The coordinates of the blur seek bar.
    """
    max_y, min_y = int(image.shape[0] * 0.75), int(image.shape[0] * 0.65)
    roi = image[min_y:max_y]
    lab_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2Lab)
    _, lab_roi[:, :, -1] = cv2.threshold(
        lab_roi[:, :, -1], 120, 255, cv2.THRESH_BINARY_INV
    )
    edges = cv2.Canny(lab_roi, 50, 150, apertureSize=3)

    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 50, None, 50, 10)
    longest_line = Line(x1=-1, y1=-1, x2=-1, y2=-1)
    if lines is not None:
        max_length = 0
        longest_line = lines[0][0]
        for line in lines:
            x1, y1, x2, y2 = line[0]
            length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
            if length > max_length:
                max_length = length
                longest_line = Line(x1=x1, y1=y1 + min_y, x2=x2, y2=y2 + min_y)
    return longest_line
