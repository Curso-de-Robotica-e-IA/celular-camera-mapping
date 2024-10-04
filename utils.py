import json
import os
import shutil
from threading import Thread

import cv2


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


def write_output_in_json(labeled_icons, path_dir, file_name):
    # Serializing json
    json_object = json.dumps(labeled_icons, indent=2)

    # Writing to sample.json
    with open(f"{path_dir}//{file_name}.json", "w") as outfile:
        outfile.write(json_object)


def load_labeled_icons(path_dir, file_name):
    with open(f"{path_dir}//{file_name}.json", "r") as file:
        return dict(json.load(file))


def create_or_replace_dir(path_dir):
    if os.path.exists(path_dir):
        shutil.rmtree(path_dir)

    os.mkdir(path_dir)


def get_command_in_command_list(command_list, command_name, current_cam, current_mode):
    for command in command_list:
        if command_name in command["command_name"]:
            if current_cam in command["requirements"]["cam"] and current_mode in command["requirements"]["mode"]:
                return command
