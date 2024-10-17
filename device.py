import re
import shutil
import subprocess
from pathlib import Path
from threading import Thread


class Device:
    """
    A class to manage ADB (Android Debug Bridge) commands for connecting to a device,
    recording the screen, taking screenshots, and interacting with the device.
    """

    def __init__(self):
        """
        Initializes the DeviceController class with default paths for storing video and screenshot files on the device.
        """
        self.__ip_port = None
        self.__device_video_path = "/sdcard/video.mp4"
        self.__device_screencap_path = "/sdcard/DCIM/Camera/screencap.png"

    def get_device_dimensions(self) -> tuple[int, int] | None:
        """
        Retrieves the device screen dimensions using ADB.

        Returns:
            tuple[int, int] | None: A tuple containing the width and height of the device screen if available,
            otherwise None.
        """
        result = subprocess.run(["adb", "-s", self.__ip_port, "shell", "wm", "size"], capture_output=True, text=True)
        dimensions = result.stdout.strip()
        pattern = r"(\d+)x(\d+)"
        match = re.search(pattern, dimensions)
        if match:
            width, height = match.groups()

            return int(width), int(height)

    def connect_device(self, ip_port) -> None:
        """
        Connects to an Android device via ADB using the given IP and port.

        Args:
            ip_port (str): The IP and port of the device to connect.
        """
        self.__ip_port = ip_port
        subprocess.run(f"adb connect {self.__ip_port}")

    def start_server(self) -> None:
        """
        Starts the ADB server to manage connections to devices.
        """
        subprocess.run("adb start-server")

    def __record_command_terminal(self, record_time_s: float) -> None:
        """
        Internal method to execute records the device screen for the specified duration and saves the video to the device.

        Args:
            record_time_s (float): The duration of the video recording in seconds.
        """
        subprocess.run(
            [
                "adb",
                "-s",
                self.__ip_port,
                "shell",
                "screenrecord",
                self.__device_video_path,
                f"--time-limit={record_time_s}",
            ]
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

        subprocess.run(
            [
                "adb",
                "-s",
                self.__ip_port,
                "pull",
                self.__device_video_path,
                str(full_path.joinpath("video.mp4")),
            ]
        )

    def delete_video_in_device(self) -> None:
        """
        Deletes the recorded video file from the device.
        """
        subprocess.run(["adb", "-s", self.__ip_port, "shell", "rm", self.__device_video_path])

    def get_screen_image(self, path: Path, tag: str) -> None:
        """
        Pulls a screenshot file from the device and saves it to the specified local directory with a tag.

        Args:
            path (Path): The directory where the screenshot will be saved.
            tag (str): A tag to append to the screenshot file name.
        """
        path.joinpath
        subprocess.run(
            [
                "adb",
                "-s",
                self.__ip_port,
                "pull",
                self.__device_screencap_path,
                str(path.joinpath(f"screencap_{tag}.png")),
            ]
        )

    def screen_shot(self):
        """
        Takes a screenshot of the device screen and saves it to the specified path on the device.
        """
        subprocess.run(
            [
                "adb",
                "-s",
                self.__ip_port,
                "shell",
                "screencap",
                "-p",
                self.__device_screencap_path,
            ]
        )

    def click_by_coordinates_in_device(self, command: dict) -> None:
        """
        Simulates a click on the device at the specified coordinates using the ADB input command.

        Args:
            command (dict): A dictionary containing the coordinates for the click. The keys are:
                - 'start_x': The X coordinate.
                - 'start_y': The Y coordinate.
        """

        x = command["click_by_coordinates"]["start_x"]
        y = command["click_by_coordinates"]["start_y"]

        subprocess.run(
            f"adb -s {self.__ip_port} shell input swipe {x} {y} {x} {y}",
            shell=True,
        )
