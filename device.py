import os
import re
import shutil
import subprocess
from threading import Thread


class Device:
    def __init__(self):
        self.__ip_port = None

    def get_device_dimensions(self):
        result = subprocess.run(["adb", "-s", self.__ip_port, "shell", "wm", "size"], capture_output=True, text=True)
        dimensions = result.stdout.strip()
        pattern = r"(\d+)x(\d+)"
        match = re.search(pattern, dimensions)
        if match:
            width, height = match.groups()

            return int(width), int(height)

        else:
            return None

    def screen_shot(self):
        subprocess.run(
            [
                "adb",
                "-s",
                self.__ip_port,
                "shell",
                "screencap",
                "-p",
                "/sdcard/DCIM/Camera/screencap.png",
            ]
        )

    def get_screen_image(self, path_target):
        subprocess.run(["adb", "-s", self.__ip_port, "pull", "/sdcard/DCIM/Camera/screencap.png", path_target])

    def connect_device(self, ip_port):
        self.__ip_port = ip_port
        subprocess.run(f"adb connect {self.__ip_port}")

    def start_server(self):
        subprocess.run("adb start-server")

    def record_command_terminal(self, record_time_s):
        subprocess.run(
            [
                "adb",
                "-s",
                self.__ip_port,
                "shell",
                "screenrecord",
                "/sdcard/video.mp4",
                f"--time-limit={record_time_s}",
            ]
        )

    def start_record_in_device(self, record_time_s):

        obj = Thread(target=self.record_command_terminal, args=[record_time_s])
        obj.start()

    def get_video_in_device(self, base_path, folder_name):
        full_path = f"{base_path}\\{folder_name}"
        if os.path.exists(full_path):
            shutil.rmtree(full_path)

        os.mkdir(full_path)

        subprocess.run(
            [
                "adb",
                "-s",
                self.__ip_port,
                "pull",
                "/sdcard/video.mp4",
                f"{full_path}\\video.mp4",
            ]
        )

    def delete_video_in_device(self):
        subprocess.run(["adb", "-s", self.__ip_port, "shell", "rm", "/sdcard/video.mp4"])

    def get_screen_image(self, path, tag):
        subprocess.run(
            [
                "adb",
                "-s",
                self.__ip_port,
                "pull",
                f"/sdcard/DCIM/Camera/screencap.png",
                f"{path}\\screencap_{tag}.png",
            ]
        )

    def screen_shot(self):
        subprocess.run(
            [
                "adb",
                "-s",
                self.__ip_port,
                "shell",
                "screencap",
                "-p",
                "/sdcard/DCIM/Camera/screencap.png",
            ]
        )

    def click_by_coordinates_in_device(self, command):
        x = command["click_by_coordinates"]["start_x"]
        y = command["click_by_coordinates"]["start_y"]

        subprocess.run(
            f"adb -s {self.__ip_port} shell input swipe {x} {y} {x} {y}",
            shell=True,
        )
