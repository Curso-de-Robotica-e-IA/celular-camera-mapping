import json
import shutil
from pathlib import Path
from threading import Thread

import cv2


def show_image_in_thread(name: str, image: cv2.typing.MatLike) -> None:
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


def write_output_in_json(labeled_icons: dict, path_dir: Path, file_name: str) -> None:
    # Serializing json
    json_object = json.dumps(labeled_icons, indent=2)

    # Writing to sample.json
    target_path = path_dir.joinpath(f"{file_name}.json")
    with open(target_path, "w") as outfile:
        outfile.write(json_object)


def load_labeled_icons(path_dir: Path, file_name: str) -> dict:
    target_path = path_dir.joinpath(f"{file_name}.json")
    with open(target_path, "r") as file:
        return dict(json.load(file))


def create_or_replace_dir(path_dir: Path) -> None:
    if path_dir.exists():
        shutil.rmtree(path_dir)

    path_dir.mkdir()


def get_command_in_command_list(
    command_list: list[dict], command_name: str, current_cam: str, current_mode: str
) -> dict:
    for command in command_list:
        if command_name in command["command_name"]:
            if current_cam in command["requirements"]["cam"] and current_mode in command["requirements"]["mode"]:
                return command
