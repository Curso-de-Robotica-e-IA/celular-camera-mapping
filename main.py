import json
import math
import os
import shutil
import subprocess
from time import sleep
import easyocr
import cv2
import re
from dataclasses import dataclass
from threading import Thread
import numpy as np


@dataclass(unsafe_hash=True)
class Point:
    x: int
    y: int

    def to_tuple(self):
        return (self.x, self.y)


@dataclass(unsafe_hash=True)
class ClickableBox:
    label: str
    min_point: Point
    max_point: Point
    centroid: Point

    def to_dict(self):
        return {
            "label": self.label,
            "min_point": {"x": self.min_point.x, "y": self.min_point.y},
            "max_point": {"x": self.max_point.x, "y": self.max_point.y},
            "centroid": {"x": self.centroid.x, "y": self.centroid.y},
        }

    @staticmethod
    def from_dict(dict_elem):
        return ClickableBox(
            dict_elem["label"],
            Point(dict_elem["min_point"]["x"], dict_elem["min_point"]["y"]),
            Point(dict_elem["max_point"]["x"], dict_elem["max_point"]["y"]),
            Point(dict_elem["centroid"]["x"], dict_elem["centroid"]["y"]),
        )


def get_device_dimensions(ip_port):

    result = subprocess.run(
        ["adb", "-s", ip_port, "shell", "wm", "size"], capture_output=True, text=True
    )
    dimensions = result.stdout.strip()
    pattern = r"(\d+)x(\d+)"
    match = re.search(pattern, dimensions)
    if match:
        width, height = match.groups()

        return int(width), int(height)

    else:
        return None


def screen_shot(ip_port):
    subprocess.run(
        [
            "adb",
            "-s",
            ip_port,
            "shell",
            "screencap",
            "-p",
            "/sdcard/DCIM/Camera/screencap.png",
        ]
    )


def get_screen_image(ip_port, path_target):
    subprocess.run(
        ["adb", "-s", ip_port, "pull", "/sdcard/DCIM/Camera/screencap.png", path_target]
    )


def connect_device(ip_port):
    subprocess.run(f"adb connect {ip_port}")


def merge_contours(contour1, contour2):
    return np.concatenate((contour1, contour2), axis=0)


def calculate_contour_distance(contour1, contour2):
    x1, y1, w1, h1 = cv2.boundingRect(contour1)
    c_x1 = x1 + w1 / 2
    c_y1 = y1 + h1 / 2

    x2, y2, w2, h2 = cv2.boundingRect(contour2)
    c_x2 = x2 + w2 / 2
    c_y2 = y2 + h2 / 2

    return max(abs(c_x1 - c_x2) - (w1 + w2) / 2, abs(c_y1 - c_y2) - (h1 + h2) / 2)


def agglomerative_cluster(contours, threshold_distance):
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
            del current_contours[index2]
        else:
            break

    return current_contours


def find_contours_in_image(image):
    edged = cv2.Canny(image, 30, 200)
    contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

    contours_list = []
    for elem in contours:
        contours_list.append(elem)

    threshold = math.sqrt((image.shape[0] / 100) ** 2 + (image.shape[1] / 100) ** 2)

    filters_contours = agglomerative_cluster(contours_list, threshold)

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


def show_clickable_itens(image, detect_box, size_in_screen):
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
            new_image, box.centroid.to_tuple(), 14, color=(0, 0, 255), thickness=6
        )

    scale = size_in_screen / image.shape[0]
    new_image = cv2.resize(new_image, (0, 0), fx=scale, fy=scale)

    cv2.imshow("camera", new_image)

    cv2.waitKey(0)

    cv2.destroyAllWindows()


def processed_base_detection_in_home_screen_step_by_step(
    base_image,
    detect_box,
    size_in_screen,
    command_to_mapping,
    current_cam,
    current_mode,
):
    result_mapping = {"COMMAND_CHANGE_SEQUENCE": {}, "COMMANDS": []}

    for elem in command_to_mapping["ITENS_TO_MAPPING"]:
        result_mapping["COMMAND_CHANGE_SEQUENCE"][elem] = {
            "COMMAND_SEQUENCE ON": [],
            "COMMAND_SEQUENCE OFF": [],
            "COMMAND_SLEEPS": {},
        }

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
        show_image_in_thread("Box icon", image)
        label_name = (input("Is a valid item? (y/n)")).lower()
        cv2.destroyAllWindows()

        if "y" in label_name:
            command = {}
            print("Select the item type in list:\n")
            for i, elem in enumerate(command_to_mapping["ITENS_TO_MAPPING"]):
                print(f"[{i}] -", elem)

            idx = int(input("Select index:\n"))

            command_label = command_to_mapping["ITENS_TO_MAPPING"][idx]

            print("Select the command action type in list:\n")
            for i, elem in enumerate(command_to_mapping["COMMAND_ACTION_AVAILABLE"]):
                print(f"[{i}] -", elem)

            act_idx = int(input("Select index:\n"))

            command_full_name = ""
            if command_to_mapping["COMMAND_ACTION_AVAILABLE"][act_idx] == "CLICK_MENU":
                command_full_name = command_label.lower() + " menu"
            elif command_label == "TAKE_PICTURE":
                command_full_name = command_label.lower()
            else:
                command_value = input("Typing the command value:")
                command_full_name = command_label.lower() + f" {command_value}"

            command["command_name"] = command_full_name
            command["click_by_coordinates"] = {
                "start_x": box.centroid.x,
                "start_y": box.centroid.y,
            }

            command["requirements"] = {"cam": current_cam, "mode": current_mode}

            apply_to = input("Is applicable in cases? (on/off):\n")

            for t in apply_to.split("/"):
                value = f"COMMAND_SEQUENCE {(t.upper())}"
                result_mapping["COMMAND_CHANGE_SEQUENCE"][command_label][value].append(
                    command_to_mapping["COMMAND_ACTION_AVAILABLE"][act_idx]
                )

            result_mapping["COMMANDS"].append(command)

    return result_mapping


def write_output_in_json(labeled_icons, path_dir, file_name):
    # Serializing json
    json_object = json.dumps(labeled_icons, indent=2)

    # Writing to sample.json
    with open(f"{path_dir}//{file_name}.json", "w") as outfile:
        outfile.write(json_object)


def load_labeled_icons(path_dir, file_name):
    with open(f"{path_dir}//{file_name}.json", "r") as file:
        return dict(json.load(file))


def show_image_in_thread(name, image):
    def draw(name, image):
        cv2.imshow(name, image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    show_thread = Thread(
        target=draw,
        args=(
            name,
            image,
        ),
    )
    show_thread.start()


def start_record_in_device(ip_port, record_time_s):
    def command_terminal(ip_port, record_time_s):
        subprocess.run(
            [
                "adb",
                "-s",
                ip_port,
                "shell",
                "screenrecord",
                "/sdcard/video.mp4",
                f"--time-limit={record_time_s}",
            ]
        )

    obj = Thread(target=command_terminal, args=[ip_port, record_time_s])
    obj.start()


def get_video_in_device(base_path, ip_port, folder_name):
    full_path = f"{base_path}\\{folder_name}"
    if os.path.exists(full_path):
        shutil.rmtree(full_path)

    os.mkdir(full_path)

    subprocess.run(
        [
            "adb",
            "-s",
            ip_port,
            "pull",
            "/sdcard/video.mp4",
            f"{full_path}\\video.mp4",
        ]
    )


def delete_video_in_device(ip_port):
    subprocess.run(["adb", "-s", ip_port, "shell", "rm", "/sdcard/video.mp4"])


def split_frames(base_path, folder_name):
    full_path = f"{base_path}\\{folder_name}"

    vidObj = cv2.VideoCapture(
        f"{full_path}\\video.mp4",
    )

    count = 0
    success = 1

    out_full_path = f"{base_path}\\{folder_name}\\frames"
    if os.path.exists(out_full_path):
        shutil.rmtree(out_full_path)

    os.mkdir(out_full_path)

    while success:
        # vidObj object calls read
        # function extract frames
        success, image = vidObj.read()
        # Saves the frames with frame-count
        if success:
            cv2.imwrite(f"{out_full_path}\\frame_{count}.png", image)
            count += 1


def touch_mapping(labeled_icons, ip_port):
    result = subprocess.run(
        f"adb -s {ip_port} shell wm size",
        capture_output=True,
        text=True,
    )
    dimensions = result.stdout.strip()
    pattern = r"(\d+)x(\d+)"
    match = re.search(pattern, dimensions)
    if match:
        width, height = match.groups()
        width = int(width)
        height = int(height)

        command = {}
        command["command_name"] = "touch"
        command["click_by_coordinates"] = {
            "start_x": width // 2,
            "start_y": height // 2,
        }

        command["requirements"] = {"cam": "main,selfie", "mode": "photo,portrait"}
        labeled_icons["COMMANDS"].append(command)
        labeled_icons["COMMAND_CHANGE_SEQUENCE"]["TOUCH"]["COMMAND_SEQUENCE ON"].append(
            "CLICK_ACTION"
        )

        labeled_icons["COMMAND_CHANGE_SEQUENCE"]["TOUCH"][
            "COMMAND_SEQUENCE OFF"
        ].append("CLICK_ACTION")


def connect_device(ip_port):
    subprocess.run(["adb", "connect", ip_port], capture_output=True, text=True)


def get_screen_image(ip_port, path, tag):

    subprocess.run(
        [
            "adb",
            "-s",
            ip_port,
            "pull",
            f"/sdcard/DCIM/Camera/screencap.png",
            f"{path}\\screencap_{tag}.png",
        ]
    )


def screen_shot(ip_port):
    subprocess.run(
        [
            "adb",
            "-s",
            ip_port,
            "shell",
            "screencap",
            "-p",
            "/sdcard/DCIM/Camera/screencap.png",
        ]
    )


def click_by_coordinates_in_device(ip_port, command):
    x = command["click_by_coordinates"]["start_x"]
    y = command["click_by_coordinates"]["start_y"]

    subprocess.run(
        f"adb -s {ip_port} shell input swipe {x} {y} {x} {y}",
        shell=True,
    )


def capture_open_menu_show(ip_port, device_target_dir, labeled_icons):
    record_len_s = 5
    for command in labeled_icons["COMMANDS"]:
        if "menu" in command["command_name"]:

            start_record_in_device(ip_port, record_len_s)
            sleep(1)
            click_by_coordinates_in_device(ip_port, command)
            sleep(record_len_s * 1.1)
            get_video_in_device(device_target_dir, ip_port, command["command_name"])
            split_frames(device_target_dir, command["command_name"])


if __name__ == "__main__":
    current_step = 2

    device_target = "Samsung-A34"
    subprocess.run("adb start-server")

    ip_port = "192.168.155.1:36089"
    connect_device(ip_port)

    path_to_base_folder = os.getcwd()

    device_target_dir = f"{path_to_base_folder}\\{device_target}"

    size_in_screen = 800

    mapping_requirements = {
        "STATE_REQUIRES": {"CAM": ["main", "self"], "MODE": ["photo", "portrait"]},
        "COMMAND_ACTION_AVAILABLE": [
            "CLICK_MENU",
            "CLICK_ACTION",
            "ADB_EVENT",
            "SWIPE_SLICE",
            "SWIPE_ACTION",
            "LONG_CLICK_MENU",
        ],
        "ITENS_TO_MAPPING": [
            "CAM",
            "MODE",
            "ASPECT_RATIO",
            "FLASH",
            "BLUR",
            "TAKE_PICTURE",
            "TOUCH",
            "ZOOM",
        ],
        "INFO_DEVICE": [
            "SERIAL_NUMBER_DEV",
            "MODEL_DEV",
            "BRAND_DEV",
            "ANDROID_VERSION_DEV",
            "HARDWARE_VERSION_DEV",
            "WIDTH_DEV",
            "CAMERA_VERSION_DEV",
            "CAM_DEFAULT",
            "MODE_DEFAULT",
            "ASPECT_RATIO_DEFAULT",
            "FLASH_DEFAULT",
            "BLUR_DEFAULT",
            "ZOOM_DEFAULT",
        ],
    }
    current_cam = "main"
    current_mode = "photo"

    labeled_icons = None

    if current_step == 1:
        if os.path.exists(device_target_dir):
            shutil.rmtree(device_target_dir)

        os.mkdir(device_target_dir)

        screen_shot(ip_port)
        get_screen_image(ip_port, device_target_dir, "initial")

        image = cv2.imread(f"{device_target_dir}\\screencap_initial.png")

        detect_boxes_from_contours = find_contours_in_image(image)
        show_clickable_itens(image, detect_boxes_from_contours, size_in_screen)
        labeled_icons = processed_base_detection_in_home_screen_step_by_step(
            image,
            detect_boxes_from_contours,
            size_in_screen,
            mapping_requirements,
            current_cam,
            current_mode,
        )

        touch_mapping(labeled_icons, ip_port)
        write_output_in_json(labeled_icons, device_target_dir, "initial_filter")
        current_step += 1

    if current_step == 2:
        if labeled_icons is None:
            labeled_icons = load_labeled_icons(device_target_dir, "initial_filter")

        capture_open_menu_show(ip_port, device_target_dir, labeled_icons)
