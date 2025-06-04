import math
from pathlib import Path
from typing import Dict

import cv2
import numpy as np

from camera_mapper.entities import ClickableBox, Point
from camera_mapper.utils import show_image_in_thread


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

    return max(abs(c_x1 - c_x2) - (w1 + w2) / 2, abs(c_y1 - c_y2) - (h1 + h2) / 2)


def agglomerative_cluster(
    contours: cv2.typing.MatLike, threshold_distance: int
) -> cv2.typing.MatLike:
    """
    Perform agglomerative clustering to merge contours that are within a certain distance of each other.

    Args:
        contours (cv2.typing.MatLike): A list of contours.
        threshold_distance (int): The distance threshold for merging contours.

    Returns:
        cv2.typing.MatLike: The clustered contours.
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

        if min_distance < threshold_distance:
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

    threshold = math.sqrt((image.shape[0] / 100) ** 2 + (image.shape[1] / 100) ** 2)

    filters_contours = agglomerative_cluster(contours_list, threshold)

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
    image: np.ndarray, clickables: Dict[str, np.ndarray]
) -> np.ndarray:
    """
    Draw clickable elements on an image.

    Args:
        image (np.ndarray): The image to draw on.
        clickables (Dict[str, np.ndarray]): A dictionary of clickable elements with their bounds.

    Returns:
        np.ndarray: The image with clickable elements highlighted.
    """
    new_image = image.copy()

    for bounds in clickables.values():
        cv2.rectangle(new_image, bounds[0], bounds[1], (0, 255, 0), 2)
        cv2.putText(
            new_image,
            "",
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


class ImageProcessing:
    """
    The ImageProcessing class is designed to handle image processing tasks,
    particularly for detecting and managing clickable regions within an image.
    It is primarily focused on detecting contours (shapes) in the image and providing step-by-step
    interactions for user input, which helps to label and map detected regions. Below is a description
    of the key functionalities provided by this class:
    """

    def __init__(self, size_in_screen: int, mapping_requirements: dict) -> None:
        """
        Initialize the ImageProcessing object.

        Args:
            size_in_screen (int): The size of the image on the screen.
            mapping_requirements (dict): A dictionary containing the mapping requirements.
        """

        self.__size_in_screen = size_in_screen
        self.__mapping_requirements = mapping_requirements

    def __merge_contours(
        self, contour1: cv2.typing.MatLike, contour2: cv2.typing.MatLike
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

    def __calculate_contour_distance(
        self, contour1: cv2.typing.MatLike, contour2: cv2.typing.MatLike
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

        return max(abs(c_x1 - c_x2) - (w1 + w2) / 2, abs(c_y1 - c_y2) - (h1 + h2) / 2)

    def __agglomerative_cluster(
        self, contours: cv2.typing.MatLike, threshold_distance: int
    ) -> cv2.typing.MatLike:
        """
        Perform agglomerative clustering to merge contours that are within a certain distance of each other.

        Args:
            contours (cv2.typing.MatLike): A list of contours.
            threshold_distance (int): The distance threshold for merging contours.

        Returns:
            cv2.typing.MatLike: The clustered contours.
        """

        current_contours = contours
        while len(current_contours) > 1:
            min_distance = None
            min_coordinate = None

            for x in range(len(current_contours) - 1):
                for y in range(x + 1, len(current_contours)):
                    distance = self.__calculate_contour_distance(
                        current_contours[x], current_contours[y]
                    )
                    if min_distance is None:
                        min_distance = distance
                        min_coordinate = (x, y)
                    elif distance < min_distance:
                        min_distance = distance
                        min_coordinate = (x, y)

            if min_distance < threshold_distance:
                index1, index2 = min_coordinate
                current_contours[index1] = self.__merge_contours(
                    current_contours[index1], current_contours[index2]
                )
                current_contours.pop(index2)
            else:
                break

        return current_contours

    def __find_contours_in_image(self, image: cv2.typing.MatLike) -> list[ClickableBox]:
        """
        Find contours in an image and return a list of clickable boxes.

        Args:
            image (cv2.typing.MatLike): The input image.

        Returns:
            list[ClickableBox]: A list of clickable boxes derived from the contours.
        """

        edged = cv2.Canny(image, 30, 200)
        contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

        contours_list = []
        for elem in contours:
            contours_list.append(elem)

        threshold = math.sqrt((image.shape[0] / 100) ** 2 + (image.shape[1] / 100) ** 2)

        filters_contours = self.__agglomerative_cluster(contours_list, threshold)

        detect_list = []

        for cnt in filters_contours:
            x, y, w, h = cv2.boundingRect(cnt)
            min_x, min_y = (x, y)
            max_x, max_y = (x + w, y + h)
            cx = int((x + (w / 2)))
            cy = int((y + (h / 2)))

            detect_item = ClickableBox(
                "", Point(min_x, min_y), Point(max_x, max_y), Point(cx, cy)
            )
            detect_list.append(detect_item)

        return detect_list

    def __show_clickable_itens(
        self,
        image: cv2.typing.MatLike,
        detect_box: list[ClickableBox],
        size_in_screen: int,
    ) -> None:
        """
        Display clickable items on the image.

        Args:
            image (cv2.typing.MatLike): The input image.
            detect_box (list[ClickableBox]): A list of detected clickable boxes.
            size_in_screen (int): The size of the image on the screen.
        """

        new_image = image.copy()
        for box in detect_box:
            if len(box.label) > 1:
                cv2.putText(
                    new_image,
                    box.label,
                    box.min_point.to_tuple(),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.3,
                    color=(0, 255, 0),
                    thickness=2,
                )

            cv2.rectangle(
                new_image,
                box.min_point.to_tuple(),
                box.max_point.to_tuple(),
                color=(255, 0, 0),
                thickness=2,
            )
            cv2.circle(
                new_image, box.centroid.to_tuple(), 10, color=(0, 0, 255), thickness=4
            )

        scale = size_in_screen / image.shape[0]
        new_image = cv2.resize(new_image, (0, 0), fx=scale, fy=scale)

        cv2.imshow("camera", new_image)

        cv2.waitKey(0)

        cv2.destroyAllWindows()

    def __process_detection_in_screen_step_by_step(
        self,
        base_image: cv2.typing.MatLike,
        detect_box: list[ClickableBox],
        size_in_screen: int,
        command_to_mapping: dict,
        labeled_icons: dict,
        current_cam: str,
        current_mode: str,
    ) -> None:
        """
        Process an image for clickable regions and label them step by step.

        Args:
        - labeled_icons (dict): A dictionary to store labeled icons and commands.
        - image_path (Path): The path to the image file.
        - current_cam (str): The current camera being used.
        - current_mode (str): The current mode of the system.
        """

        scale = size_in_screen / base_image.shape[0]
        for box in detect_box:
            image = base_image.copy()

            cv2.rectangle(
                image,
                box.min_point.to_tuple(),
                box.max_point.to_tuple(),
                color=(0, 0, 255),
                thickness=2,
            )
            image = cv2.resize(image, (0, 0), fx=scale, fy=scale)

            while True:
                try:
                    show_image_in_thread("Box icon", image)
                    label_name = (input("Is a valid item? (y/n)")).lower()
                    cv2.destroyAllWindows()

                    if "y" in label_name:
                        command = {}
                        print("Select the item type in list:\n")
                        for i, elem in enumerate(
                            command_to_mapping["ITENS_TO_MAPPING"]
                        ):
                            print(f"[{i}] -", elem)

                        idx = None
                        while idx is None:
                            try:
                                input_idx = int(input("Select index: "))
                                idx = input_idx
                            except Exception as e:
                                print(e)

                        command_label = command_to_mapping["ITENS_TO_MAPPING"][idx]

                        print("Select the command action type in list:\n")
                        for i, elem in enumerate(
                            command_to_mapping["COMMAND_ACTION_AVAILABLE"]
                        ):
                            print(f"[{i}] -", elem)

                        act_idx = None
                        while act_idx is None:
                            try:
                                input_idx = int(input("Select index: "))
                                act_idx = input_idx
                            except Exception as e:
                                print(e)

                        command_full_name = ""
                        if (
                            command_to_mapping["COMMAND_ACTION_AVAILABLE"][act_idx]
                            == "CLICK_MENU"
                        ):
                            command_full_name = command_label.lower() + " menu"
                        elif command_label == "TAKE_PICTURE":
                            labeled_icons["COMMAND_CHANGE_SEQUENCE"]["TAKE_PICTURE"][
                                "COMMAND_SLEEPS"
                            ]["CLICK_ACTION"] = 3
                            command_full_name = command_label.lower().replace("_", " ")
                        else:
                            command_value = input("Typing the command value:")
                            command_full_name = (
                                command_label.lower() + f" {command_value}"
                            )

                        command["command_name"] = command_full_name
                        command["click_by_coordinates"] = {
                            "start_x": box.centroid.x,
                            "start_y": box.centroid.y,
                        }

                        command["requirements"] = {
                            "cam": current_cam,
                            "mode": current_mode,
                        }

                        apply_to = ["ON", "OFF"]

                        for flow_type in apply_to:
                            value = f"COMMAND_SEQUENCE {flow_type}"
                            if (
                                command_to_mapping["COMMAND_ACTION_AVAILABLE"][act_idx]
                                not in labeled_icons["COMMAND_CHANGE_SEQUENCE"][
                                    command_label
                                ][value]
                            ):
                                labeled_icons["COMMAND_CHANGE_SEQUENCE"][command_label][
                                    value
                                ].append(
                                    command_to_mapping["COMMAND_ACTION_AVAILABLE"][
                                        act_idx
                                    ]
                                )

                        labeled_icons["COMMANDS"].append(command)

                    break
                except KeyboardInterrupt:
                    print("\n\nClean selection for current item\n")

    def process_screen_step_by_step(
        self, labeled_icons: dict, image_path: Path, current_cam: str, current_mode: str
    ) -> None:
        """
        Process an image for clickable regions and label them step by step.

        Parameters:
        - labeled_icons (dict): A dictionary to store labeled icons and commands.
        - image_path (Path): The path to the image file.
        - current_cam (str): The current camera being used.
        - current_mode (str): The current mode of the system.
        """

        image = cv2.imread(str(image_path))

        detect_boxes_from_contours = self.__find_contours_in_image(image)

        self.__show_clickable_itens(
            image, detect_boxes_from_contours, self.__size_in_screen
        )

        self.__process_detection_in_screen_step_by_step(
            image,
            detect_boxes_from_contours,
            self.__size_in_screen,
            self.__mapping_requirements,
            labeled_icons,
            current_cam,
            current_mode,
        )
