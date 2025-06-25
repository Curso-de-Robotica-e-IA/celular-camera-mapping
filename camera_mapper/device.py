import time
from pathlib import Path
from typing import Optional, TypedDict

from device_manager import DeviceActions, DeviceInfo
from device_manager.device_info import DeviceProperties
from device_manager.manager_singleton import DeviceManagerSingleton as DeviceManager


class MapperProperties(DeviceProperties, TypedDict, total=False):
    software_version: Optional[str]
    brand: Optional[str]
    model: Optional[str]
    width: Optional[int]
    height: Optional[int]
    centroid: Optional[tuple[int, int]]
    camera_version: Optional[str]


class Device:
    """
    A class to manage ADB (Android Debug Bridge) commands for connecting to a device,
    recording the screen, taking screenshots, and interacting with the device.
    """

    DEVICE_SCREENCAP_PATH = "/sdcard/DCIM/Camera/screencap.png"

    def __init__(self) -> None:
        """
        Initializes the DeviceController class with default paths for storing video and screenshot files on the device.
        """
        self.manager = DeviceManager()
        self.properties: Optional[MapperProperties] = None
        self.info: Optional[DeviceInfo] = None
        self.actions: Optional[DeviceActions] = None

    def connect_device(self, ip: str) -> None:
        """
        Connects to an Android device via ADB using the given IP and port.

        Args:
            ip (str): The IP and port of the device to connect.
        """
        visible_devices = self.manager.connector.visible_devices()
        matched_device = [
            device.serial_number for device in visible_devices if device.ip == ip
        ]
        try:
            matched_device = matched_device[0]
            connected = self.manager.connect_devices(matched_device)
            if not connected:
                raise ConnectionError(
                    f"Failed to connect to device with IP: {ip}. Please check the connection."
                )
            self.info = self.manager.get_device_info(matched_device)
            self.actions = self.manager.get_device_actions(matched_device)
            self.properties = self.get_properties()
        except IndexError:
            raise ValueError(
                f"Device with IP: {ip} not found. Please check the IP and port."
            )

    def screen_shot(self, path: Path, tag: str) -> None:
        """
        Takes a screenshot and pull it from the device, saving it to the specified local directory with a tag.

        Args:
            path (Path): The directory where the screenshot will be saved.
            tag (str): A tag to append to the screenshot file name.
        """
        self.manager.execute_adb_command(
            command=f"screencap -p {self.DEVICE_SCREENCAP_PATH}", shell=True
        )
        time.sleep(1)
        if self.actions is None:
            raise RuntimeError(
                "Device actions are not initialized. Please connect to a device first."
            )
        self.actions.pull_file(
            remote_path=self.DEVICE_SCREENCAP_PATH,
            local_path=str(path.joinpath(f"original_{tag}.png")),
        )
        time.sleep(1)

    def save_screen_gui_xml(self, path: Path) -> None:
        """
        Saves the current screen's GUI XML information from the device into
        device_screen_gui.xml file in the specified path with a tag.
        """
        if self.info is None:
            raise RuntimeError(
                "Device info is not initialized. Please connect to a device first."
            )
        xml_info = self.info.get_screen_gui_xml()
        if xml_info is None:
            raise ValueError("Failed to retrieve screen GUI XML information.")
        xml_file_path = path.joinpath("device_screen_gui.xml")
        with open(xml_file_path, "w", encoding="utf-8") as file:
            file.write(xml_info)

    def get_properties(self) -> MapperProperties:
        """
        Retrieves the device properties such as hardware version, width, and camera version.

        Returns:
            MapperProperties: An instance containing the device properties.
        """
        if self.info is None or self.actions is None:
            raise RuntimeError(
                "Device info is not initialized. Please connect to a device first."
            )
        manager_properties = self.info.get_properties()
        width, height = self.info.get_screen_dimensions()
        centroid = (width // 2, height // 2)
        package_name = self.actions.camera.package()
        camera_package = self.info.app(package=package_name)
        camera_version = camera_package.get_property("versionName")
        return MapperProperties(
            software_version=manager_properties.get("android_version"),
            brand=manager_properties.get("brand"),
            model=manager_properties.get("model"),
            width=width,
            height=height,
            centroid=centroid,
            camera_version=camera_version,
        )
