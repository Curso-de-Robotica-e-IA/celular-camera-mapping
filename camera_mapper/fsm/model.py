from pathlib import Path
import time
from typing import Dict, Tuple
from xml.etree.ElementTree import ElementTree

import cv2
import numpy as np

from camera_mapper.constants import (
    CAMERA,
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
    find_contours_in_image,
    load_image,
    merge_bounds,
    draw_clickable_elements,
    separate_xml_from_image_clickables,
)
from camera_mapper.screen_processing.xml_processing import (
    clickable_elements,
    find_element,
)
from camera_mapper.utils import create_or_replace_dir


class CameraMapperModel:
    def __init__(self, ip, current_step) -> None:
        """
        Initializes the CameraMapper class with the target device, IP address, and current step of the process.

        Args:
            ip (str): The IP address of the device.
            current_step (int): The starting step of the mapping process.
        """

        self.__ip = ip
        self.__device = Device()
        self.__device_objects_dir: Path = None
        self.__device_output_dir: Path = None
        self.__current_step = current_step
        self.__n_menus = 0
        self.__camera_app_open_attempts = 0
        self.__error: Exception = None
        self.__clickables: Dict[str, np.ndarray] = {}
        self.__action_check_done = False
        self.__action_elements: Dict[str, np.ndarray] = {}
        self.__xml_clickables: Dict[str, np.ndarray] = {}
        self.xml_elements: Dict[str, np.ndarray] = {}
        self.__image_clickables: Dict[str, np.ndarray] = {}
        self.mapping_elements = {
            # Basics
            "CAM": None,
            "TAKE_PICTURE": None,
            "TOUCH": None,
            # Depending on the device
            "MODE": None,
            "ASPECT_RATIO": None,
            "FLASH": None,
        }

    def current_state(self) -> str:
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
        self.__device.connect_device(self.__ip)
        device_target = (
            self.__device.properties.get("model").lower().replace(" ", "_").title()
        )
        self.__device_objects_dir = Path.joinpath(PATH_TO_META_FOLDER, device_target)
        self.__device_output_dir = Path.joinpath(PATH_TO_OUTPUT_FOLDER, device_target)

    def connected(self):
        """
        Checks if the device is connected.
        Returns:
            bool: True if the device is connected, False otherwise.
        """
        is_connected = len(self.__device.manager) > 0
        if not is_connected:
            self.__error = ConnectionError(
                f"Device {self.__device_target} not connected. Please check the IP address."
            )
        return is_connected

    # endregion: device_connection

    # region: Camera application open loop
    def open_camera(self) -> None:
        """
        Opens the camera application on the device.
        """
        self.__device.actions.camera.open()
        time.sleep(2)  # Wait for the camera app to open

    def check_camera_app(self) -> None:
        """
        Checks if the camera application is open on the device.
        If not, it attempts to open it again.
        """
        current_activity = self.__device.info.actual_activity().lower()
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
        create_or_replace_dir(PATH_TO_TMP_FOLDER)
        self.__device.screen_shot(path=PATH_TO_TMP_FOLDER, tag=f"{CAMERA}_{MODE}")
        self.__device.save_screen_gui_xml(
            path=PATH_TO_TMP_FOLDER, tag=self.__current_step
        )

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
                PATH_TO_TMP_FOLDER.joinpath("xml_clickable_elements.png"),
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
            return
        contours = separate_xml_from_image_clickables(contours, self.__xml_clickables)
        try:
            cv2.imwrite(
                PATH_TO_TMP_FOLDER.joinpath("image_clickable_elements.png"),
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
                file=PATH_TO_TMP_FOLDER.joinpath(
                    f"device_screen_gui_{self.__current_step}.xml"
                )
            )
        except Exception as e:
            self.__error = e
            return

        self.__xml_clickables, self.xml_elements = self.process_screen_gui_xml(
            xml_tree, image
        )
        self.__image_clickables = self.process_screen_image(image)

        clickables = merge_bounds(self.__image_clickables, self.__xml_clickables)
        try:
            cv2.imwrite(
                PATH_TO_TMP_FOLDER.joinpath("clickable_elements.png"),
                draw_clickable_elements(image, clickables),
            )
        except Exception as e:
            self.__error = e
        self.__clickables = clickables
        if self.__clickables is None:
            self.__error = ValueError(
                "No clickable elements found in the screen image."
            )

    # endregion: Screen capture loop

    # region: Basic actions mapping
    def mark_basic_actions(self) -> None:
        """
        Marks the basic actions from XML captured.
        """
        for name in SWITCH_CAM_NAMES:
            found_name, found_box = find_element(name, self.xml_elements)
            if found_name:
                self.mapping_elements["CAM"] = found_box
                break

    # endregion: Basic actions mapping

    # region: Action clickable elements check loop
    def mark_actions(self) -> None:
        """
        Marks the clickable elements in the captured screen image and allows the user to mark action elements.
        """
        self.__action_elements = {}
        print(
            "Please mark the action elements in the image by clicking on them with the mouse's left button."
        )
        print("Press 'Esc' to finish marking.")
        marked_points = click_on_image(
            PATH_TO_TMP_FOLDER.joinpath("clickable_elements.png")
        )
        if len(marked_points) == 0:
            self.__error = ValueError("No action elements were marked.")
            return
        self.__action_elements = match_elements_to_clicks(
            clicks=marked_points, clickables=self.__clickables
        )

    def confirm_actions(self) -> None:
        """
        Confirms the actions that have been clicked by the user by showing them on the screen and the user chooses to accept or not.
        """
        if not self.__action_elements:
            self.__error = ValueError("No action elements to confirm.")
            return
        self.__action_check_done = confirm_labeling(
            PATH_TO_TMP_FOLDER.joinpath(f"original_{CAMERA}_{MODE}.png"),
            self.__action_elements,
            label_name="Actions",
        )

    def actions_check_done(self) -> bool:
        """
        Checks if there are any actions on screen to be marked.
        Returns:
            bool: True if there are actions, False otherwise.
        """
        return self.__action_check_done

    # endregion: Action clickable elements check loop

    # region: Menu clickable elements check loop
    def has_menu(self) -> bool:
        """Checks if the current screen has a menu button displayed yet to be checked."""
        return self.__n_menus > 0

    def check_menu(self):
        raise NotImplementedError("Implement This Model Behavior.")

    # endregion: Menu clickable elements check loop

    def success_message(self):
        print("Device mapping completed successfully.")
