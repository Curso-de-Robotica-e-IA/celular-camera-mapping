import os
from time import sleep
from device import Device
from pi.process_frames import ProcessFrames
from pi.process_image import ProcessImage
from utils import create_or_replace_dir, load_labeled_icons, write_output_in_json, get_command_in_command_list


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
        self.__total_steps = 5
        self.__labeled_icons = self.create_current_context_result()

        self.__device = Device()
        self.__process_img = ProcessImage(self.__size_in_screen, self.__mapping_requirements)
        self.__process_frames = ProcessFrames(
            self.__device_objects_dir, self.__mapping_requirements, self.__device, self.__process_img
        )

    def __start_result_json(self):
        result_mapping = {"COMMAND_CHANGE_SEQUENCE": {}, "COMMANDS": []}

        for elem in self.__mapping_requirements["ITENS_TO_MAPPING"]:
            result_mapping["COMMAND_CHANGE_SEQUENCE"][elem] = {
                "COMMAND_SEQUENCE ON": [],
                "COMMAND_SEQUENCE OFF": [],
                "COMMAND_SLEEPS": {},
            }

        return result_mapping

    def __get_menu_groups_by_cam_mode(self):
        groups = []

        for c in self.__mapping_requirements["STATE_REQUIRES"]["CAM"]:
            for m in self.__mapping_requirements["STATE_REQUIRES"]["MODE"]:
                element = {
                    "commands": [],
                    "requirements": {"cam": c, "mode": m},
                    "to_requirements": [],
                    "return_to_base": [],
                }

                if c != self.__current_cam:
                    command_target_cam_name = f"cam {c}"
                    command_target_cam = get_command_in_command_list(
                        self.__labeled_icons["COMMANDS"],
                        command_target_cam_name,
                        self.__current_cam,
                        self.__current_mode,
                    )
                    element["to_requirements"].append(command_target_cam)

                if m != self.__current_mode:
                    command_target_mode_name = f"mode {m}"
                    command_target_mode = get_command_in_command_list(
                        self.__labeled_icons["COMMANDS"],
                        command_target_mode_name,
                        c,
                        self.__current_mode,
                    )
                    element["to_requirements"].append(command_target_mode)

                    # to return
                    command_target_mode_name = f"mode {self.__current_mode}"
                    command_target_mode = get_command_in_command_list(
                        self.__labeled_icons["COMMANDS"],
                        command_target_mode_name,
                        c,
                        m,
                    )
                    element["return_to_base"].append(command_target_mode)

                if c != self.__current_cam:
                    # return to base
                    command_target_cam_name = f"cam {self.__current_cam}"
                    command_target_cam = get_command_in_command_list(
                        self.__labeled_icons["COMMANDS"],
                        command_target_cam_name,
                        c,
                        self.__current_mode,
                    )
                    element["return_to_base"].append(command_target_cam)

                groups.append(element)

        for g in groups:
            for command in self.__labeled_icons["COMMANDS"]:
                if (
                    "menu" in command["command_name"]
                    and g["requirements"]["cam"] in command["requirements"]["cam"]
                    and g["requirements"]["mode"] in command["requirements"]["mode"]
                ):
                    g["commands"].append(command)

        return groups

    def create_current_context_result(self):
        if self.__current_step == 0:
            create_or_replace_dir(self.__device_output_dir)
            create_or_replace_dir(self.__device_tmp_output_dir)
            return self.__start_result_json()
        else:
            return load_labeled_icons(self.__device_tmp_output_dir, f"res_step_{(self.__current_step-1)}")

    def flush_current_step_progress(self):
        write_output_in_json(self.__labeled_icons, self.__device_tmp_output_dir, f"res_step_{self.__current_step}")
        self.__current_step += 1

    def step_0(self):
        print("Mapping start screen ...")
        current_dir = f"{self.__device_objects_dir}\\{self.__current_cam} {self.__current_mode}"
        create_or_replace_dir(self.__device_objects_dir)
        create_or_replace_dir(current_dir)

        self.__device.screen_shot()
        self.__device.get_screen_image(current_dir, "start_screen")

        self.__process_img.process_screen_step_by_step(
            self.__labeled_icons,
            f"{current_dir}\\screencap_start_screen.png",
            self.__current_cam,
            self.__current_mode,
        )

    def step_1(self):
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
        else:
            raise RuntimeError("Error in get dimension of device")

    def step_2(self):
        print("Mapping changes in cam and mode ...")

        self.__process_frames.cam_and_mode_gradle_remapping(
            self.__labeled_icons, self.__current_cam, self.__current_mode
        )

    def step_3(self):
        print("Calculate menu action animations in each combination ...")

        mapping_groups = self.__get_menu_groups_by_cam_mode()

        self.__process_frames.mapping_menu_actions_in_each_group(self.__labeled_icons, mapping_groups)

    def step_4(self):
        print("Calculate menu action in each combination ...")

        mapping_groups = self.__get_menu_groups_by_cam_mode()

        self.__process_frames.calculate_menu_actions_animations_in_each_group(self.__labeled_icons, mapping_groups)

    def main_loop(self):

        self.__device.start_server()
        self.__device.connect_device(self.__ip_port)
        sleep(5)

        for id in range(self.__current_step, self.__total_steps):

            method_name = f"step_{id}"

            print("Execute ", method_name)
            input(
                f"Check if the device has the camera open with the configuration: Cam={self.__current_cam}, Mode={self.__current_mode}\nPress enter after check..."
            )
            cur_step = getattr(self, method_name)
            cur_step()

            self.flush_current_step_progress()


if __name__ == "__main__":
    start_step = 3
    cur_device_name = "Samsung-A34"
    device_ip_port = "192.168.155.1:42007"
    cli_app = DeviceMappingCLI(cur_device_name, device_ip_port, start_step)

    cli_app.main_loop()
