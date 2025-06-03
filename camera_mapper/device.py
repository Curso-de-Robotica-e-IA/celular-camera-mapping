import shutil
from pathlib import Path
from threading import Thread

from device_manager import DeviceActions, DeviceInfo
from device_manager.manager_singleton import (
    DeviceManagerSingleton as DeviceManager,
)


class Device:
    """
    A class to manage ADB (Android Debug Bridge) commands for connecting to a device,
    recording the screen, taking screenshots, and interacting with the device.
    """

    DEVICE_VIDEO_PATH = "/sdcard/video.mp4"
    DEVICE_SCREENCAP_PATH = "/sdcard/DCIM/Camera/screencap.png"

    def __init__(self) -> None:
        """
        Initializes the DeviceController class with default paths for storing video and screenshot files on the device.
        """
        self.manager = DeviceManager()
        self.info: DeviceInfo = None
        self.actions: DeviceActions = None

    def connect_device(self, ip) -> None:
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
        except IndexError:
            raise ValueError(
                f"Device with IP: {ip} not found. Please check the IP and port."
            )

    def __record_command_terminal(
        self, manager: DeviceManager, record_time_s: float
    ) -> None:
        """
        Internal method to execute records the device screen for the specified duration and saves the video to the device.

        Args:
            record_time_s (float): The duration of the video recording in seconds.
        """
        manager.execute_adb_shell_command(
            command=f"screenrecord {self.DEVICE_VIDEO_PATH} --time-limit={record_time_s}"
        )

    def start_record_in_device(self, record_time_s: float) -> None:
        """
        Starts screen recording on the device asynchronously using a separate thread.

        Args:
            record_time_s (float): The duration of the video recording in seconds.
        """
        obj = Thread(target=self.__record_command_terminal, args=[record_time_s])
        obj.start()

    def get_video_in_device(self, base_path: Path, folder_name: str) -> None:
        """
        Pulls the recorded video file from the device and saves it to the specified folder on the local system.

        Args:
            base_path (Path): The base directory path on the local system.
            folder_name (str): The folder name where the video will be saved.
        """

        full_path = base_path.joinpath(folder_name)

        if full_path.exists():
            shutil.rmtree(full_path)

        full_path.mkdir()
        self.manager.execute_adb_command(
            command=f"pull {self.DEVICE_VIDEO_PATH} {str(full_path)}"
        )

    def delete_video_in_device(self) -> None:
        """
        Deletes the recorded video file from the device.
        """
        self.manager.execute_adb_shell_command(command=f"rm {self.DEVICE_VIDEO_PATH}")

    def screen_shot(self, path: Path, tag: str) -> None:
        """
        Takes a screenshot and pull it from the device, saving it to the specified local directory with a tag.

        Args:
            path (Path): The directory where the screenshot will be saved.
            tag (str): A tag to append to the screenshot file name.
        """
        self.manager.execute_adb_shell_command(
            command=f"screencap -p {self.DEVICE_SCREENCAP_PATH}"
        )
        self.actions.pull_file(
            remote_path=self.DEVICE_SCREENCAP_PATH,
            local_path=str(path.joinpath(f"screencap_{tag}.png")),
        )

    def save_screen_gui_xml(self, path: Path, tag: str) -> None:
        """
        Saves the current screen's GUI XML information from the device into
        device_screen_gui.xml file in the specified path with a tag.
        """
        xml_info = self.info.get_screen_gui_xml()
        if xml_info is None:
            raise ValueError("Failed to retrieve screen GUI XML information.")
        xml_file_path = path.joinpath(f"device_screen_gui_{tag}.xml")
        with open(xml_file_path, "w", encoding="utf-8") as file:
            file.write(xml_info)
