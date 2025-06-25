import json
import shutil
import time

from doctr.models import ocr_predictor
from doctr.io import DocumentFile

from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.etree.ElementTree import ElementTree
from rich.console import Console

import cv2
import numpy as np

from camera_mapper.constants import (
    ASPECT_RATIO_MENU_NAMES,
    CAPTURE_NAMES,
    DEFAULT_BLUR_STEP,
    FLASH_MENU_NAMES,
    OBJECTS_OF_INTEREST,
    PATH_TO_TMP_FOLDER,
    QUICK_CONTROL_NAMES,
    SWITCH_CAM_NAMES,
)
from camera_mapper.device import Device
from camera_mapper.screen_processing.image_processing import (
    blur_patterns,
    draw_clickable_elements,
    get_blur_seekbar,
    get_middle_blur_circle_bar,
    load_image,
    search_for_patterns,
)
from camera_mapper.screen_processing.xml_processing import (
    clickable_elements,
    find_element,
)
from camera_mapper.utils import create_or_replace_dir


class CameraMapperModel:
    def __init__(self, ip: str, hardware_version: str = "1.0.0") -> None:
        """
        Initializes the CameraMapper class with the IP address of the device

        Args:
            ip (str): The IP address of the device.
        """

        self.__ip = ip
        self.__hardware_version = hardware_version
        self.console = Console()
        self.device = Device()
        self.__camera_app_open_attempts = 0
        self.__blur_button_idx = -1
        self.__error: Optional[Exception] = None
        self.xml_clickables: Dict[str, np.ndarray] = {}
        self.xml_elements: Dict[str, np.ndarray] = {}
        self.xml_portrait: Dict[str, np.ndarray] = {}
        self.image_clickables: Dict[str, np.ndarray] = {}
        self.ocr = ocr_predictor(pretrained=True)
        self.mapping_elements: Dict[str, Optional[np.ndarray]] = {
            # Device properties
            "HARDWARE_VERSION": None,
            "SOFTWARE_VERSION": None,
            "BRAND": None,
            "MODEL": None,
            "CAMERA_VERSION": None,
            # Basics
            "CAM": None,
            "TAKE_PICTURE": None,
            "TOUCH": None,
            "QUICK_CONTROLS": None,
            # Depending on the device
            "ASPECT_RATIO_MENU": None,
            "ASPECT_RATIO_3_4": None,
            "ASPECT_RATIO_9_16": None,
            "ASPECT_RATIO_1_1": None,
            "ASPECT_RATIO_FULL": None,
            "FLASH_MENU": None,
            "FLASH_ON": None,
            "FLASH_OFF": None,
            "FLASH_AUTO": None,
            "PORTRAIT_MODE": None,
            "BLUR_MENU": None,
            "BLUR_BAR_MIDDLE": None,
            "BLUR_BAR_BEFORE": None,
            "BLUR_BAR_NEXT": None,
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
        if self.device.actions is not None:
            self.device.actions.camera.close()
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
        self.mapping_elements["HARDWARE_VERSION"] = self.__hardware_version
        self.mapping_elements["SOFTWARE_VERSION"] = self.device.properties.get(
            "software_version", "Unknown"
        )
        self.mapping_elements["BRAND"] = self.device.properties.get("brand", "Unknown")
        self.mapping_elements["MODEL"] = model_property
        self.mapping_elements["CAMERA_VERSION"] = self.device.properties.get(
            "camera_version", "Unknown"
        )

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
        current_activity = self.device.info.actual_activity().lower()
        if "cam" in current_activity:
            self.device.actions.home_button()
            self.device.actions.camera.close()
            time.sleep(1)
        self.device.actions.camera.open()

    def check_camera_app(self) -> bool:
        """
        Checks if the camera application is open on the device.
        If not, it attempts to open it again.
        """
        if self.device.info is None:
            self.__error = ValueError("Device info is not available.")
            return False
        current_activity = self.device.info.actual_activity().lower()
        time.sleep(5)  # Allow some time for the activity to update
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
        self.device.screen_shot(path=PATH_TO_TMP_FOLDER, tag=f"{self.state}")
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

    def treat_zoom_clickables(
        self, clickables: Dict[str, np.ndarray]
    ) -> Dict[str, np.ndarray]:
        """
        Treats zoom-related clickables by adjusting them and renaming on Dict.
        Args:
            clickables (Dict[str, np.ndarray]): A dictionary of clickable elements.
        Returns:
            Dict[str, np.ndarray]: The modified dictionary with zoom-related clickables adjusted.
        """
        possible_dict = {}
        for key, value in clickables.items():
            if key[0].isdigit() or key[0] == ".":
                possible_dict[key.replace("X", "").replace("x", "")] = value
        zoom_1x = possible_dict["1"]
        new_dict = {"ZOOM_1": zoom_1x}
        for name, box in possible_dict.items():
            if name != "1":
                box_left_up = box[0][0]
                if box_left_up < zoom_1x[0][0]:
                    new_dict["ZOOM_." + name] = box
                else:
                    new_dict["ZOOM_" + name] = box
        return new_dict

    def apply_ocr_to_contours(self) -> Dict[str, np.ndarray]:
        """
        Applies OCR to the contours of clickable elements to extract text.
        Returns:
            Dict[str, np.ndarray]: A dictionary where keys are centroids of clickable elements
                                   and values are their bounds after applying OCR.
        """
        ocred = {}
        path = str(PATH_TO_TMP_FOLDER.joinpath(f"original_{self.state}.png"))
        img_doc = DocumentFile.from_images(path)
        result = self.ocr(img_doc)

        width = self.device.properties.get("width", 0)
        height = self.device.properties.get("height", 0)
        for line in result.pages[0].blocks[0].lines:
            for word in line.words:
                proc_word = word.value.strip().upper()
                if proc_word == "IX":
                    proc_word = "1X"
                if proc_word in OBJECTS_OF_INTEREST:
                    ocred[proc_word] = np.array(
                        [
                            [word.geometry[0][0] * width, word.geometry[0][1] * height],
                            [word.geometry[1][0] * width, word.geometry[1][1] * height],
                        ],
                        dtype=np.int32,
                    )
        found_zooms = self.treat_zoom_clickables(ocred)
        ocred.update(found_zooms)
        return ocred

    def process_screen_image(self, image: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Processes the captured screen image to extract information such as actions and menus.
        Args:
            image (np.ndarray): The captured screen image.
        Returns:
            Dict[str, np.ndarray]: A dictionary where keys are centroids of clickable elements
                                   and values are their bounds after processing the image.
        """
        contours = self.apply_ocr_to_contours()
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
                PATH_TO_TMP_FOLDER.joinpath(f"original_{self.state}.png")
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
        quick_control_name, quick_control_centroid = self.get_xml_element_and_centroid(
            QUICK_CONTROL_NAMES, self.xml_elements
        )
        if cam_name:
            self.mapping_elements["CAM"] = cam_centroid
            self.xml_elements.pop(cam_name)
        if take_name:
            self.mapping_elements["TAKE_PICTURE"] = take_centroid
            self.xml_elements.pop(take_name)
        if quick_control_name:
            self.mapping_elements["QUICK_CONTROLS"] = quick_control_centroid
            self.xml_elements.pop(quick_control_name)

    # endregion: Basic actions mapping

    # region: Aspect Ratio actions mapping
    def process_xml(self) -> Dict[str, np.ndarray]:
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
        elif self.mapping_elements["QUICK_CONTROLS"] is not None:
            self.device.actions.click_by_coordinates(
                *self.mapping_elements["QUICK_CONTROLS"]
            )
            time.sleep(1)
            elements = self.process_xml()
            found_name, found_centroid = self.get_xml_element_and_centroid(
                ASPECT_RATIO_MENU_NAMES, elements
            )
            if found_name and found_centroid is not None:
                self.mapping_elements["ASPECT_RATIO_MENU"] = found_centroid

        if found_name is None or found_centroid is None:
            self.__error = ValueError(
                "Aspect ratio menu not found in the XML elements."
            )

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
        time.sleep(0.5)
        NAMES_DICT = {
            "1:1": ["1:1", "1_1", "SQUARE", "1_by_1"],
            "3:4": ["3:4", "3_4", "NORMAL", "3_by_4"],
            "9:16": ["9:16", "9_16", "WIDE", "9_by_16"],
            "FULL": ["FULL"],
        }
        elements = self.process_xml()
        for name_kind, names in NAMES_DICT.items():
            for name in names:
                found_name, found_box = find_element(name, elements)
                if found_name and found_box is not None:
                    centroid = found_box.mean(axis=0).astype(np.int32)
                    self.mapping_elements[
                        f"ASPECT_RATIO_{name_kind.replace(':', '_')}"
                    ] = centroid
                    continue
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

        if found_name is None or found_centroid is None:
            self.__error = ValueError("Flash menu not found in the XML elements.")

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
        NAMES = ["_AUTO", "_ON", "_OFF"]
        elements = self.process_xml()
        for name in NAMES:
            found_name, found_box = find_element(name, elements)
            if found_name and found_box is not None:
                centroid = found_box.mean(axis=0).astype(np.int32)
                self.mapping_elements[f"FLASH_{name.replace('_', '')}"] = centroid
        self.device.actions.click_by_coordinates(*self.mapping_elements["TOUCH"])  # type: ignore

    # endregion: Flash actions mapping

    # region: Portrait Mode
    def find_portrait(self) -> None:
        """
        Finds the portrait mode button on the device screen.
        """
        pstr = "PORTRAIT"
        portrait_name, portrait_bounds = find_element(pstr, self.xml_elements)
        if portrait_name and portrait_bounds is not None:
            portrait_centroid = portrait_bounds.mean(axis=0).astype(np.int32)
            self.mapping_elements["PORTRAIT_MODE"] = portrait_centroid
        else:
            if pstr in self.image_clickables:
                portrait_centroid = (
                    self.image_clickables[pstr].mean(axis=0).astype(np.int32)
                )
                self.mapping_elements["PORTRAIT_MODE"] = portrait_centroid
            else:
                self.__error = ValueError(
                    "Portrait mode button not found in the XML or image clickables."
                )
                return

    def process_portrait_mode(self) -> None:
        """
        Processes the portrait mode by clicking on the portrait button and confirming the action.
        """
        time.sleep(2)
        self.device.actions.click_by_coordinates(
            *self.mapping_elements["PORTRAIT_MODE"]
        )
        time.sleep(2)
        self.map_blur_menu()

    def map_blur_menu(self) -> None:
        """
        Maps the blur menu in portrait mode by searching for it in the captured image.
        """
        self.capture_screen()
        image = load_image(PATH_TO_TMP_FOLDER.joinpath(f"original_{self.state}.png"))
        patterns = blur_patterns()
        bounds, self.__blur_button_idx = search_for_patterns(image, patterns)
        if self.__blur_button_idx < 0:
            self.__error = ValueError("Blur menu not found in the image.")
            return
        blur_centroid = np.mean(bounds, axis=0).astype(int)
        self.mapping_elements["BLUR_MENU"] = blur_centroid

    def map_blur_bar(self) -> None:
        """
        Maps the blur bar in portrait mode by clicking on the blur menu and adjusting the blur level.
        """
        if self.device.actions is not None:
            self.device.actions.click_by_coordinates(
                *self.mapping_elements["BLUR_MENU"]
            )
            time.sleep(1)
            self.capture_screen()
            image = load_image(
                PATH_TO_TMP_FOLDER.joinpath(f"original_{self.state}.png")
            )
            if self.__blur_button_idx in [1, 2, 3]:
                self.mapping_elements["BLUR_BAR_MIDDLE"] = get_middle_blur_circle_bar(
                    image
                )
                if self.mapping_elements["BLUR_BAR_MIDDLE"].size == 0:
                    self.__error = ValueError("Blur bar middle not found in the image.")
                    return
                self.mapping_elements["BLUR_BAR_BEFORE"] = self.mapping_elements[
                    "BLUR_BAR_MIDDLE"
                ].copy()
                self.mapping_elements["BLUR_BAR_NEXT"] = self.mapping_elements[
                    "BLUR_BAR_MIDDLE"
                ].copy()
                self.mapping_elements["BLUR_BAR_BEFORE"][0] -= DEFAULT_BLUR_STEP
                self.mapping_elements["BLUR_BAR_NEXT"][0] += DEFAULT_BLUR_STEP
            else:
                blur_seekbar = get_blur_seekbar(image)
                if blur_seekbar.get("x1") == -1:
                    self.__error = ValueError("Blur seekbar not found in the image.")
                    return
                self.mapping_elements["BLUR_BAR_MIDDLE"] = np.array(
                    [
                        blur_seekbar["x1"] + blur_seekbar["x2"] // 2,
                        blur_seekbar["y1"] + blur_seekbar["y2"] // 2,
                    ],
                    dtype=np.int32,
                )
                self.mapping_elements["BLUR_BAR_BEFORE"] = np.array(
                    [blur_seekbar["x1"], blur_seekbar["y1"]], dtype=np.int32
                )
                self.mapping_elements["BLUR_BAR_NEXT"] = np.array(
                    [blur_seekbar["x2"], blur_seekbar["y2"]], dtype=np.int32
                )

    # endregion: Portrait Mode

    # region: Zoom mapping
    def map_zoom(self) -> None:
        """
        Maps the zoom buttons on the device screen.
        """
        filter_zoom_clickables = [key for key in self.image_clickables if "ZOOM" in key]
        if not filter_zoom_clickables:
            self.__error = ValueError("No zoom buttons found in the image clickables.")
            return
        for key in filter_zoom_clickables:
            value = self.image_clickables[key]
            key = key.replace("..", ".")
            self.mapping_elements[key] = value.mean(axis=0).astype(np.int32)

    # endregion: Zoom mapping

    # region: Save mapping
    def save_mapping(self) -> None:
        """
        Saves the mapping elements to a JSON file.
        """
        to_save = {
            key: value.tolist() if isinstance(value, np.ndarray) else value
            for key, value in self.mapping_elements.items()
        }
        brand = (
            self.device.properties.get("brand", "Unknown")
            .lower()
            .replace(" ", "_")
            .replace("-", "_")
            .upper()
        )
        model = (
            self.device.properties.get("model", "Unknown")
            .lower()
            .replace(" ", "_")
            .replace("-", "_")
            .upper()
        )
        out_name = f"{brand}-{model}-mapping.json"
        full_path = Path().joinpath(out_name)
        with open(full_path, "w") as f:
            json.dump(to_save, f)
        self.console.print(f"Mapping saved to {full_path}")
        self.device.actions.camera.close()
        shutil.rmtree(PATH_TO_TMP_FOLDER, ignore_errors=True)

    # endregion: Save mapping
    def success_message(self):
        self.console.print("Device mapping completed successfully!")
