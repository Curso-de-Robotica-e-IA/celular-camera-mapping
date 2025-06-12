import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.etree.ElementTree import ElementTree

import cv2
import numpy as np

from camera_mapper.constants import (
    ASPECT_RATIO_MENU_NAMES,
    CAMERA,
    CAPTURE_NAMES,
    FLASH_MENU_NAMES,
    MODE,
    PATH_TO_META_FOLDER,
    PATH_TO_OUTPUT_FOLDER,
    PATH_TO_TMP_FOLDER,
    SWITCH_CAM_NAMES,
)
from camera_mapper.device import Device
from camera_mapper.image_labeling import (
    click_on_image,
    confirm_labeling,
    match_elements_to_clicks,
)
from camera_mapper.screen_processing.image_processing import (
    draw_clickable_elements,
    find_contours_in_image,
    load_image,
    merge_bounds,
    separate_xml_from_image_clickables,
)
from camera_mapper.screen_processing.xml_processing import (
    clickable_elements,
    find_element,
)
from camera_mapper.utils import create_or_replace_dir


class CameraMapperModel:
    def __init__(self, ip) -> None:
        """
        Initializes the CameraMapper class with the IP address of the device

        Args:
            ip (str): The IP address of the device.
        """

        self.__ip = ip
        self.device = Device()
        self.device_objects_dir: Optional[Path] = None
        self.device_output_dir: Optional[Path] = None
        self.__camera_app_open_attempts = 0
        self.__error: Optional[Exception] = None
        self.xml_clickables: Dict[str, np.ndarray] = {}
        self.xml_elements: Dict[str, np.ndarray] = {}
        self.image_clickables: Dict[str, np.ndarray] = {}
        self.mapping_elements: Dict[str, Optional[np.ndarray]] = {
            # Basics
            "CAM": None,
            "TAKE_PICTURE": None,
            "TOUCH": None,
            # Depending on the device
            "MODE": None,
            "ASPECT_RATIO_MENU": None,
            "ASPECT_RATIO_3_4": None,
            "ASPECT_RATIO_9_16": None,
            "ASPECT_RATIO_1_1": None,
            "ASPECT_RATIO_FULL": None,
            "FLASH_MENU": None,
            "FLASH_ON": None,
            "FLASH_OFF": None,
            "FLASH_AUTO": None,
        }
        self.state = "IDLE"

    def current_state(self) -> None:
        """
        Prints the current state of the model.
        """
        print("\n================================")
        print(f"\nState machine's current state: {self.state}")

    # region: error_handling
    def raise_error(self) -> None:
        """
        Raises the stored error if it exists.
        Raises:
            Exception: If an error has been stored, it raises that error.
        """
        print(self.__error)
        if self.__error is not None:
            raise self.__error

    def in_error(self) -> bool:
        """
        Checks if there is an error stored in the model.
        Returns:
            bool: True if there is an error, False otherwise.
        """
        return self.__error is not None

    # endregion: error_handling

    # region: device_connection
    def connect_device(self) -> None:
        """
        Connects to the device using the provided IP address.
        """
        self.device.connect_device(self.__ip)
        if self.device.properties is None:
            self.__error = ValueError("Device properties are not available.")
            return
        model_property = self.device.properties.get("model")
        if model_property is None:
            self.__error = ValueError("Device model property is not available.")
            return
        device_target = model_property.lower().replace(" ", "_").title()
        self.device_objects_dir = Path.joinpath(PATH_TO_META_FOLDER, device_target)
        self.device_output_dir = Path.joinpath(PATH_TO_OUTPUT_FOLDER, device_target)

    def connected(self):
        """
        Checks if the device is connected.
        Returns:
            bool: True if the device is connected, False otherwise.
        """
        is_connected = len(self.device.manager) > 0
        if not is_connected:
            self.__error = ConnectionError(
                "Device not connected. Please check the IP address."
            )
        return is_connected

    def create_tmp_dir(self) -> None:
        """
        Creates a temporary directory for storing screenshots and XML files.
        """
        create_or_replace_dir(PATH_TO_TMP_FOLDER)
        if not PATH_TO_TMP_FOLDER.exists():
            self.__error = FileNotFoundError(
                f"Temporary folder {PATH_TO_TMP_FOLDER} could not be created."
            )

    # endregion: device_connection

    # region: Camera application open loop
    def open_camera(self) -> None:
        """
        Opens the camera application on the device.
        """
        if self.device.actions is None:
            self.__error = ValueError("Device actions are not available.")
            return
        time.sleep(2)
        self.device.actions.camera.open()
        time.sleep(2)  # Wait for the camera app to open

    def check_camera_app(self) -> bool:
        """
        Checks if the camera application is open on the device.
        If not, it attempts to open it again.
        """
        if self.device.info is None:
            self.__error = ValueError("Device info is not available.")
            return False
        current_activity = self.device.info.actual_activity().lower()
        camera_opened = "cam" in current_activity
        self.__camera_app_open_attempts += 1
        if not camera_opened and self.__camera_app_open_attempts > 3:
            self.__error = RuntimeError(
                f"Failed to open camera app after {self.__camera_app_open_attempts} attempts."
            )
        return camera_opened

    # endregion: Camera application open loop

    # region: Screen capture loop
    def capture_screen(self):
        """
        Captures the current screen of the device and saves it to a temporary folder.
        """
        self.device.screen_shot(path=PATH_TO_TMP_FOLDER, tag=f"{CAMERA}_{MODE}")
        self.device.save_screen_gui_xml(path=PATH_TO_TMP_FOLDER)

    def process_screen_gui_xml(
        self, xml: ElementTree, image: np.ndarray
    ) -> Tuple[Dict[str, np.ndarray], Dict[str, np.ndarray]]:
        """
        Processes the GUI XML of the captured screen to extract clickable elements and labeled icons.
        Args:
            xml (ElementTree): The XML ElementTree representing the GUI of the captured screen.
            image (np.ndarray): The captured screen image.
        Returns:
            Tuple[Dict[str, np.ndarray], Dict[str, np.ndarray]]:
                A dictionary where keys are XML elements and values are their bounds.
        """
        clickables, elements = clickable_elements(xml)
        if not clickables:
            self.__error = ValueError(
                "No clickable elements found in the screen GUI XML."
            )
        try:
            cv2.imwrite(
                str(PATH_TO_TMP_FOLDER.joinpath("xml_clickable_elements.png")),
                draw_clickable_elements(image, clickables),
            )
        except Exception as e:
            self.__error = e
        return clickables, elements

    def process_screen_image(self, image: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Processes the captured screen image to extract information such as actions and menus.
        Args:
            image (np.ndarray): The captured screen image.
        Returns:
            Dict[str, np.ndarray]: A dictionary where keys are centroids of clickable elements
                                   and values are their bounds after processing the image.
        """
        contours = find_contours_in_image(image)
        if contours is None:
            self.__error = ValueError("No contours found in the screen image.")
            return {}
        contours = separate_xml_from_image_clickables(contours, self.xml_clickables)
        try:
            cv2.imwrite(
                str(PATH_TO_TMP_FOLDER.joinpath("image_clickable_elements.png")),
                draw_clickable_elements(image, contours),
            )
        except Exception as e:
            self.__error = e
        return contours

    def process_screen(self) -> None:
        """
        Processes the captured screen image to extract information such as actions and menus.
        """
        try:
            image = load_image(
                PATH_TO_TMP_FOLDER.joinpath(f"original_{CAMERA}_{MODE}.png")
            )
            xml_tree = ElementTree(
                file=PATH_TO_TMP_FOLDER.joinpath("device_screen_gui.xml")
            )
        except Exception as e:
            self.__error = e
            return

        self.xml_clickables, self.xml_elements = self.process_screen_gui_xml(
            xml_tree, image
        )
        self.image_clickables = self.process_screen_image(image)

    # endregion: Screen capture loop

    # region: Basic actions mapping
    @staticmethod
    def get_xml_element_and_centroid(
        element_names: List[str], xml_elements: Dict[str, np.ndarray]
    ) -> Tuple[str, np.ndarray]:
        """
        Retrieves the centroid of the first found element from the provided names,
        or returns an empty array if none are found.
        Args:
            element_names (List[str]): A list of element names to search for.
            xml_elements (Dict[str, np.ndarray]): A dictionary of XML elements with their bounds.
        """
        for name in element_names:
            found_name, found_box = find_element(name, xml_elements)
            if found_name:
                return found_name, found_box.mean(axis=0).astype(np.int32)
        return "", np.array([], dtype=np.int32)

    def map_xml_basic_actions(self) -> None:
        """
        Maps the basic actions from XML captured.
        """
        if self.device.properties is None:
            self.__error = ValueError("Device properties are not available.")
            return
        device_centroid = self.device.properties.get("centroid", None)
        self.mapping_elements["TOUCH"] = np.array(device_centroid, dtype=np.int32)
        cam_name, cam_centroid = self.get_xml_element_and_centroid(
            SWITCH_CAM_NAMES, self.xml_elements
        )
        take_name, take_centroid = self.get_xml_element_and_centroid(
            CAPTURE_NAMES, self.xml_elements
        )
        if cam_name:
            self.mapping_elements["CAM"] = cam_centroid
            self.xml_elements.pop(cam_name)
        if take_name:
            self.mapping_elements["TAKE_PICTURE"] = take_centroid
            self.xml_elements.pop(take_name)

    # endregion: Basic actions mapping

    # region: Aspect Ratio actions mapping
    def map_xml_aspect_ratio(self) -> None:
        """
        Maps the aspect ratio from XML captured.
        """
        found_name, found_centroid = self.get_xml_element_and_centroid(
            ASPECT_RATIO_MENU_NAMES, self.xml_elements
        )
        if found_name and found_centroid is not None:
            self.mapping_elements["ASPECT_RATIO_MENU"] = found_centroid
            self.xml_elements.pop(found_name)

    def process_aspect_ratio_menu(self) -> Dict[str, np.ndarray]:
        """
        Processes the aspect ratio menu from the XML elements.
        Returns:
            Dict[str, ndarray]: A dictionary with centroids of aspect ratio elements.
        """
        self.device.save_screen_gui_xml(path=PATH_TO_TMP_FOLDER)
        xml_tree = ElementTree(
            file=PATH_TO_TMP_FOLDER.joinpath("device_screen_gui.xml")
        )
        _, elements = clickable_elements(xml_tree)
        if not elements:
            self.__error = ValueError(
                "No clickable elements found in the screen GUI XML."
            )
            return {"": np.array([])}
        return elements

    def map_aspect_ratio_actions(self) -> None:
        """
        Maps the aspect ratio actions from the XML captured.
        """
        aspect_ratio_menu = self.mapping_elements.get("ASPECT_RATIO_MENU")
        if aspect_ratio_menu is None or self.device.actions is None:
            self.__error = ValueError(
                "Aspect ratio menu or device actions are not available."
            )
            return
        self.device.actions.click_by_coordinates(*aspect_ratio_menu)
        time.sleep(1)
        NAMES_DICT = {
            "1:1": ["1:1", "1_1", "SQUARE"],
            "3:4": ["3:4", "3_4", "NORMAL"],
            "9:16": ["9:16", "9_16", "WIDE"],
            "FULL": ["FULL"],
        }
        elements = self.process_aspect_ratio_menu()
        for name_kind, names in NAMES_DICT.items():
            for name in names:
                found_name, found_box = find_element(name, elements)
                if found_name and found_box is not None:
                    centroid = found_box.mean(axis=0).astype(np.int32)
                    self.mapping_elements[
                        f"ASPECT_RATIO_{name_kind.replace(':', '_')}"
                    ] = centroid
        self.device.actions.click_by_coordinates(*self.mapping_elements["TOUCH"])  # type: ignore
        time.sleep(0.5)

    # endregion: Aspect Ratio actions mapping

    # region: Flash actions mapping
    def map_xml_flash(self) -> None:
        """
        Maps the aspect ratio from XML captured.
        """
        found_name, found_centroid = self.get_xml_element_and_centroid(
            FLASH_MENU_NAMES, self.xml_elements
        )
        if found_name and found_centroid is not None:
            self.mapping_elements["FLASH_MENU"] = found_centroid
            self.xml_elements.pop(found_name)

    def process_flash_menu(self) -> Dict[str, np.ndarray]:
        """
        Processes the aspect ratio menu from the XML elements.
        Returns:
            Dict[str, ndarray]: A dictionary with centroids of aspect ratio elements.
        """
        self.device.save_screen_gui_xml(path=PATH_TO_TMP_FOLDER)
        xml_tree = ElementTree(
            file=PATH_TO_TMP_FOLDER.joinpath("device_screen_gui.xml")
        )
        _, elements = clickable_elements(xml_tree)
        if not elements:
            self.__error = ValueError(
                "No clickable elements found in the screen GUI XML."
            )
            return {"": np.array([])}
        return elements

    def map_flash_actions(self) -> None:
        """
        Maps the aspect ratio actions from the XML captured.
        """
        flash_menu = self.mapping_elements.get("FLASH_MENU")
        if flash_menu is None or self.device.actions is None:
            self.__error = ValueError(
                "Aspect ratio menu or device actions are not available."
            )
            return
        time.sleep(1)
        self.device.actions.click_by_coordinates(*flash_menu)
        time.sleep(0.5)
        NAMES = ["AUTO", "ON", "OFF"]
        elements = self.process_flash_menu()
        for name in NAMES:
            found_name, found_box = find_element(name, elements)
            if found_name and found_box is not None:
                centroid = found_box.mean(axis=0).astype(np.int32)
                self.mapping_elements[f"FLASH_{name.replace(':', '_')}"] = centroid
        self.device.actions.click_by_coordinates(*self.mapping_elements["TOUCH"])  # type: ignore

    # endregion: Flash actions mapping

    def success_message(self):
        print(self.mapping_elements)
        print("Device mapping completed successfully.")
