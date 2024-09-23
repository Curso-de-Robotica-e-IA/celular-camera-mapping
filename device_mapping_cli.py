import os
from time import sleep
from device import Device
from pi.process_image import ProcessImage
from utils import create_or_replace_dir, load_labeled_icons, write_output_in_json


class DeviceMappingCLI:
    def __init__(self, device_target, ip_port, current_step) -> None:
        self.__device_target = device_target
        self.__ip_port = ip_port
        path_to_base_folder = os.getcwd()
        self.__device_objects_dir = f"{path_to_base_folder}\\meta\\{device_target}"
        self.__device_output_dir = f"{path_to_base_folder}\\output\\{device_target}"
        self.__device_tmp_output_dir = f"{self.__device_output_dir}\\tmp"
        self.__size_in_screen = 800

        self.__mapping_requirements = {
            "STATE_REQUIRES": {"CAM": ["main", "selfie"], "MODE": ["photo", "portrait"]},
            "COMMAND_ACTION_AVAILABLE": [
                "CLICK_MENU",
                "CLICK_ACTION",
                "SWIPE_SLICE",
                "SWIPE_ACTION",
                "LONG_CLICK_MENU",
            ],
            "ITENS_TO_MAPPING": ["CAM", "MODE", "ASPECT_RATIO", "FLASH", "TAKE_PICTURE", "TOUCH"],
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
        self.__current_cam = "main"
        self.__current_mode = "photo"

        self.__current_step = current_step
        self.__total_steps = 10
        self.__labeled_icons = self.create_current_context_result()

        self.__device = Device()
        self.__process_img = ProcessImage(self.__size_in_screen)

    def __start_result_json(self):
        result_mapping = {"COMMAND_CHANGE_SEQUENCE": {}, "COMMANDS": []}

        for elem in self.__mapping_requirements["ITENS_TO_MAPPING"]:
            result_mapping["COMMAND_CHANGE_SEQUENCE"][elem] = {
                "COMMAND_SEQUENCE ON": [],
                "COMMAND_SEQUENCE OFF": [],
                "COMMAND_SLEEPS": {},
            }

        return result_mapping

    def create_current_context_result(self):
        if self.__current_step < 2:
            create_or_replace_dir(self.__device_output_dir)
            create_or_replace_dir(self.__device_tmp_output_dir)
            return self.__start_result_json()
        else:
            return load_labeled_icons(self.__device_tmp_output_dir, f"res_step_{self.__current_step}.json")

    def flush_current_step_progress(self):
        write_output_in_json(self.__labeled_icons, self.__device_tmp_output_dir, f"res_step_{self.__current_step}")
        self.__current_step += 1

    def step_1(self):
        print("Mapping start screen ...")
        create_or_replace_dir(self.__device_objects_dir)

        self.__device.screen_shot()
        self.__device.get_screen_image(self.__device_objects_dir, "start_screen")

        self.__process_img.process_screen_step_by_step(
            self.__labeled_icons,
            f"{self.__device_objects_dir}\\screencap_start_screen.png",
            self.__mapping_requirements,
            self.__current_cam,
            self.__current_mode,
        )

        self.flush_current_step_progress()

    def step_2(self):
        print("Mapping touch for all screens ...")
        dimension = self.__device.get_device_dimensions()

        if dimension:
            width = dimension[0]
            height = dimension[1]

            command = {}
            command["command_name"] = "touch"
            command["click_by_coordinates"] = {
                "start_x": width // 2,
                "start_y": height // 2,
            }

            command["requirements"] = {"cam": "main,selfie", "mode": "photo,portrait"}
            self.__labeled_icons["COMMANDS"].append(command)
            self.__labeled_icons["COMMAND_CHANGE_SEQUENCE"]["TOUCH"]["COMMAND_SEQUENCE ON"].append("CLICK_ACTION")

            self.__labeled_icons["COMMAND_CHANGE_SEQUENCE"]["TOUCH"]["COMMAND_SEQUENCE OFF"].append("CLICK_ACTION")

            self.__labeled_icons["COMMAND_CHANGE_SEQUENCE"]["TOUCH"]["COMMAND_SLEEPS"]["CLICK_ACTION"] = 2

            self.flush_current_step_progress()
        else:
            print("Error in get dimension of device")

    def main_loop(self):

        self.__device.start_server()
        self.__device.connect_device(self.__ip_port)
        sleep(5)

        for id in range(self.__current_step, self.__total_steps):
            method_name = f"step_{(id+1)}"
            cur_step = getattr(self, method_name)
            cur_step()


if __name__ == "__main__":
    cur_step = 0
    cur_device_name = "Samsung-A34"
    device_ip_port = "192.168.155.1:35125"
    cli_app = DeviceMappingCLI(cur_device_name, device_ip_port, cur_step)

    cli_app.main_loop()
