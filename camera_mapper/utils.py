import json
import shutil
from pathlib import Path
from threading import Thread

import cv2


def show_image_in_thread(name: str, image: cv2.typing.MatLike) -> None:
    """
    Displays an image in a separate thread using OpenCV. This allows the image display to run asynchronously without blocking the main thread.

    Args:
        name (str): The title of the window in which the image will be displayed.
        image (cv2.typing.MatLike): The image data to be shown, represented in OpenCV's format.

    """

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
    """
    Serializes a dictionary of labeled icons into a JSON file and writes it to a specified directory.

    Args:
        labeled_icons (dict): The dictionary containing labeled icons to be written into a JSON file.
        path_dir (Path): The directory path where the JSON file will be saved.
        file_name (str): The name of the file (without extension) in which the data will be saved.

    """
    # Serializing json
    json_object = json.dumps(labeled_icons, indent=2)

    # Writing to sample.json
    target_path = path_dir.joinpath(f"{file_name}.json")
    with open(target_path, "w") as outfile:
        outfile.write(json_object)


def load_labeled_icons(path_dir: Path, file_name: str) -> dict:
    """
    Loads a JSON file from a specified directory and returns its content as a dictionary.

    Args:
        path_dir (Path): The directory where the JSON file is located.
        file_name (str): The name of the file (without extension) to be loaded.

    """
    target_path = path_dir.joinpath(f"{file_name}.json")
    with open(target_path, "r") as file:
        return dict(json.load(file))


def create_or_replace_dir(path_dir: Path) -> None:
    """
    Checks if a directory exists, and if it does, removes it and creates a new one. If it doesn't exist, the method creates the directory.

    Args:
        path_dir (Path): The directory path to be created or replaced.
    """
    if path_dir.exists():
        shutil.rmtree(path_dir)

    path_dir.mkdir()


def get_command_in_command_list(
    command_list: list[dict], command_name: str, current_cam: str, current_mode: str
) -> dict | None:
    """
    Searches through a list of command dictionaries to find a command that matches the specified name, camera, and mode requirements.

    Args:
        command_list (list[dict]): A list of command dictionaries, where each dictionary contains information about a command.
        command_name (str): The name of the command to search for.
        current_cam (str): The current camera specification required by the command.
        current_mode (str): The current mode required by the command.

    Returns:
       dict: The command dictionary that matches the given parameters. If no match is found return `None`.
    """
    for command in command_list:
        if command_name in command["command_name"]:
            if (
                current_cam in command["requirements"]["cam"]
                and current_mode in command["requirements"]["mode"]
            ):
                return command
