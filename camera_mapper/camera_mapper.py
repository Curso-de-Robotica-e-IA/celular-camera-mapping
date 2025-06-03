from pathlib import Path

from camera_mapper.constants import (
    CAMERA,
    MAPPING_REQUIREMENTS,
    MODE,
    PATH_TO_META_FOLDER,
    PATH_TO_OUTPUT_FOLDER,
    PATH_TO_TMP_FOLDER,
    SIZE_IN_SCREEN,
    STEPS,
)
from camera_mapper.device import Device
from camera_mapper.core.frames_processing import FramesProcessing
from camera_mapper.screen_processing.image_processing import ImageProcessing
from camera_mapper.utils import (
    create_or_replace_dir,
    get_command_in_command_list,
    load_labeled_icons,
    write_output_in_json,
)


class CameraMapper:
    """
    A class to handle the process of mapping device screens, touch points, and menu items
    for different camera and mode configurations on an Android device.
    """

    def __init__(self, device_target, ip, current_step) -> None:
        """
        Initializes the CameraMapper class with the target device, IP address, and current step of the process.

        Args:
            device_target (str): The name of the device to be mapped.
            ip (str): The IP address of the device.
            current_step (int): The starting step of the mapping process.
        """

        self.__device_target = device_target
        self.__ip = ip
        self.__device_objects_dir = Path.joinpath(PATH_TO_META_FOLDER, device_target)
        self.__device_output_dir = Path.joinpath(PATH_TO_OUTPUT_FOLDER, device_target)

        self.__current_step = current_step

        self.__labeled_icons = self.create_current_context_result()

        self.__device = Device()
        self.__process_img = ImageProcessing(SIZE_IN_SCREEN, MAPPING_REQUIREMENTS)
        self.__process_frames = FramesProcessing(
            self.__device_objects_dir,
            MAPPING_REQUIREMENTS,
            self.__device,
            self.__process_img,
        )

    def __start_result_json(self):
        """
        Initializes a JSON structure to store command sequences and actions for mapping.

        Returns:
            dict: The initialized structure for command sequences.
        """

        result_mapping = {"COMMAND_CHANGE_SEQUENCE": {}, "COMMANDS": []}

        for elem in MAPPING_REQUIREMENTS["ITENS_TO_MAPPING"]:
            result_mapping["COMMAND_CHANGE_SEQUENCE"][elem] = {
                "COMMAND_SEQUENCE ON": [],
                "COMMAND_SEQUENCE OFF": [],
                "COMMAND_SLEEPS": {},
            }

        return result_mapping

    def __get_menu_groups_by_cam_mode(self):
        """
        Retrieves and organizes menu groups by camera and mode combinations,
        including commands to change between cameras and modes.

        Returns:
            list: A list of menu groups with commands and requirements for each camera and mode combination.
        """

        groups = []

        for cur_cam in MAPPING_REQUIREMENTS["STATE_REQUIRES"]["CAM"]:
            for cur_mode in MAPPING_REQUIREMENTS["STATE_REQUIRES"]["MODE"]:
                element = {
                    "commands": [],
                    "requirements": {"cam": cur_cam, "mode": cur_mode},
                    "to_requirements": [],
                    "return_to_base": [],
                }

                if cur_cam != CAMERA:
                    command_target_cam_name = f"cam {cur_cam}"
                    command_target_cam = get_command_in_command_list(
                        self.__labeled_icons["COMMANDS"],
                        command_target_cam_name,
                        CAMERA,
                        MODE,
                    )
                    element["to_requirements"].append(command_target_cam)

                if cur_mode != MODE:
                    command_target_mode_name = f"mode {cur_mode}"
                    command_target_mode = get_command_in_command_list(
                        self.__labeled_icons["COMMANDS"],
                        command_target_mode_name,
                        cur_cam,
                        MODE,
                    )
                    element["to_requirements"].append(command_target_mode)

                    # to return
                    command_target_mode_name = f"mode {MODE}"
                    command_target_mode = get_command_in_command_list(
                        self.__labeled_icons["COMMANDS"],
                        command_target_mode_name,
                        cur_cam,
                        cur_mode,
                    )
                    element["return_to_base"].append(command_target_mode)

                if cur_cam != CAMERA:
                    # return to base
                    command_target_cam_name = f"cam {CAMERA}"
                    command_target_cam = get_command_in_command_list(
                        self.__labeled_icons["COMMANDS"],
                        command_target_cam_name,
                        cur_cam,
                        MODE,
                    )
                    element["return_to_base"].append(command_target_cam)

                groups.append(element)

        for cur_group in groups:
            for command in self.__labeled_icons["COMMANDS"]:
                if (
                    "menu" in command["command_name"]
                    and cur_group["requirements"]["cam"]
                    in command["requirements"]["cam"]
                    and cur_group["requirements"]["mode"]
                    in command["requirements"]["mode"]
                ):
                    cur_group["commands"].append(command)

        return groups

    def create_current_context_result(self):
        """
        Creates the initial result for the current mapping step or loads it from the previous step.

        Returns:
            dict: The result of the current mapping context.
        """

        if self.__current_step == 0:
            create_or_replace_dir(self.__device_output_dir)
            create_or_replace_dir(PATH_TO_TMP_FOLDER)
            return self.__start_result_json()
        else:
            return load_labeled_icons(
                PATH_TO_TMP_FOLDER, f"res_step_{(self.__current_step - 1)}"
            )

    def flush_current_step_progress(self):
        """
        Saves the progress of the current mapping step to a temporary directory and increments the step counter.
        """

        write_output_in_json(
            self.__labeled_icons,
            PATH_TO_TMP_FOLDER,
            f"res_step_{self.__current_step}",
        )
        self.__current_step += 1

    def mapping_start_screen(self):
        """
        Maps the start screen of the device by capturing a screenshot and processing it for further steps.
        """

        print("Mapping start screen ...")
        current_dir = self.__device_objects_dir.joinpath(f"{CAMERA} {MODE}")
        create_or_replace_dir(self.__device_objects_dir)
        create_or_replace_dir(current_dir)

        self.__device.screen_shot()
        self.__device.get_screen_image(current_dir, "start_screen")

        self.__process_img.process_screen_step_by_step(
            self.__labeled_icons,
            current_dir.joinpath("screencap_start_screen.png"),
            CAMERA,
            MODE,
        )

    def mapping_touch_for_all_screens(self):
        """
        Maps touch interactions for all screens by determining screen dimensions and touch coordinates.
        """

        print("Mapping touch for all screens ...")
        try:
            width, height = self.__device.info.get_screen_dimensions()

            command = {}
            command["command_name"] = "touch"
            command["click_by_coordinates"] = {
                "start_x": width // 2,
                "start_y": height // 2,
            }

            command["requirements"] = {"cam": "main,selfie", "mode": "photo,portrait"}
            self.__labeled_icons["COMMANDS"].append(command)
            self.__labeled_icons["COMMAND_CHANGE_SEQUENCE"]["TOUCH"][
                "COMMAND_SEQUENCE ON"
            ].append("CLICK_ACTION")

            self.__labeled_icons["COMMAND_CHANGE_SEQUENCE"]["TOUCH"][
                "COMMAND_SEQUENCE OFF"
            ].append("CLICK_ACTION")

            self.__labeled_icons["COMMAND_CHANGE_SEQUENCE"]["TOUCH"]["COMMAND_SLEEPS"][
                "CLICK_ACTION"
            ] = 2
        except IndexError:
            raise RuntimeError("Error in get dimension of device")

    def mapping_screens_combinations_for_cam_and_mode(self):
        """
        Maps screen combinations for different camera and mode settings, processing the remapping of frames.
        """

        print("Mapping changes in cam and mode ...")

        self.__process_frames.cam_and_mode_gradle_remapping(
            self.__labeled_icons, CAMERA, MODE
        )

    def mapping_menu_itens_animation_in_each_screen(self):
        """
        Maps menu items and their animations for each screen and camera/mode combination.
        """

        print("Calculate menu itens and animations in each combination ...")

        mapping_groups = self.__get_menu_groups_by_cam_mode()

        self.__process_frames.mapping_menu_actions_in_each_group(
            self.__labeled_icons, mapping_groups
        )

    def mapping_menu_action_animation_in_each_screen(self):
        """
        Maps menu actions and their animations for each screen and camera/mode combination.
        """

        print("Calculate menu action in each combination ...")

        mapping_groups = self.__get_menu_groups_by_cam_mode()

        self.__process_frames.calculate_menu_actions_animations_in_each_group(
            self.__labeled_icons, mapping_groups
        )

    def main_loop(self):
        """
        Executes the mapping process by looping through each step, waiting for user input before proceeding.
        """

        self.__device.connect_device(self.__ip)

        for method_name in STEPS[self.__current_step :]:
            print("Execute ", method_name)
            input(
                f"Check if the device has the camera open with the configuration: Cam={CAMERA}, Mode={MODE}\nPress enter after check..."
            )
            cur_step = getattr(self, method_name)
            cur_step()

            self.flush_current_step_progress()

        print("Write final output ...")
        write_output_in_json(
            self.__labeled_icons,
            self.__device_output_dir,
            f"{self.__device_target}_mapping",
        )
