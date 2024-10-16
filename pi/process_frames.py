from pathlib import Path
from time import sleep

import cv2
from sewar.full_ref import mse

from device import Device
from pi.process_image import ProcessImage
from utils import create_or_replace_dir, get_command_in_command_list


class ProcessFrames:
    """
    The ProcessFrames class is designed to handle video frame extraction, comparison, and analysis,
    as well as orchestrating interactions with a device in a testing or automation scenario.
    It supports tasks such as video processing, animation detection, and updating state information
    based on visual input from a series of frames.
    """

    def __init__(
        self, device_target_dir: Path, mapping_requirements: dict, device: Device, process_img: ProcessImage
    ) -> None:
        """
        Initialize the ProcessFrames class with required parameters.

        Args:
            device_target_dir (Path): The target directory for device-related data.
            mapping_requirements (dict): Requirements for command mapping.
            device (Device): The device object to interact with.
            process_img (ProcessImage): The image processing object.
        """

        self.__device = device
        self.__device_target_dir = device_target_dir
        self.__process_image = process_img
        self.__mapping_requirements = mapping_requirements

        self.__HIGH_STATE = 50
        self.__LOW_STATE = 0
        self.__MIN_ANIMATION_TIME_S = 0.3

    def __split_frames(self, base_path: Path, folder_name: str) -> None:
        """
        Split a video file into individual frames and save them as images.

        Args:
            base_path (Path): The base directory containing the video.
            folder_name (str): The folder name where the video is stored.
        """

        full_path = base_path.joinpath(folder_name)

        vidObj = cv2.VideoCapture(
            str(full_path.joinpath("video.mp4")),
        )

        count = 0
        success = 1

        out_full_path = full_path.joinpath("frames")
        create_or_replace_dir(out_full_path)

        while success:
            # vidObj object calls read
            # function extract frames
            success, image = vidObj.read()
            # Saves the frames with frame-count
            if success:
                cv2.imwrite(str(out_full_path.joinpath(f"frame_{count}.png")), image)
                count += 1

    def __get_fps_for_video(self, base_path: Path, folder_name: str) -> int:
        """
        Retrieve the frames per second (FPS) of a video file.

        Args:
            base_path (Path): The base directory containing the video.
            folder_name (str): The folder name where the video is stored.

        Returns:
            int: The FPS value of the video.
        """

        full_path = base_path.joinpath(folder_name)

        vidObj = cv2.VideoCapture(
            str(full_path.joinpath("video.mp4")),
        )

        return vidObj.get(cv2.CAP_PROP_FPS)

    def __compare_frames(self, device_target_dir: Path, command_name: str) -> list[float]:
        """
        Compare consecutive frames and compute the mean squared error (MSE).

        Args:
            device_target_dir (Path): The directory containing the frames to compare.
            command_name (str): The name of the command executed.

        Returns:
            list[float]: A list of MSE values for the compared frames.
        """

        frame_compare = []

        file_images_dir = device_target_dir.joinpath(command_name, "frames")

        file_images_list = list(file_images_dir.rglob("*.png"))

        def sort_by_number(file_name: Path):
            return int(file_name.parts.split(".")[0].split("_")[-1])

        file_images_list = sorted(file_images_list, key=sort_by_number)

        if len(file_images_list) > 1:
            base_image = cv2.imread(str(file_images_list[0]))

        for i in range(1, len(file_images_list)):
            new_image = cv2.imread(str(file_images_list[i]))

            frame_compare.append(mse(base_image, new_image))

            base_image = new_image

        return frame_compare

    def __calculate_moving_average(self, frame_compare: list[float], window_size: int) -> list[float]:
        """
        Calculate the moving average of frame comparison values.

        Args:
            frame_compare (list[float]): The list of frame comparison values.
            window_size (int): The size of the moving window for averaging.

        Returns:
            list[float]: The list of moving average values.
        """

        # Initialize an empty list to store moving averages
        moving_averages = []

        # Loop through the array to consider
        # every window of size 3
        lst_val = None
        for i in range(len(frame_compare) - window_size + 1):
            # Store elements from i to i+window_size
            # in list to get the current window
            window = frame_compare[i : i + window_size]

            # Calculate the average of current window
            window_average = round(sum(window) / window_size, 2)

            # Store the average of current
            # window in moving average list
            moving_averages.append(window_average)
            lst_val = window_average

        for i in range(window_size):
            moving_averages.append(lst_val)

        return moving_averages

    def __calculate_threshold_for_frames(self, frame_compare: list[float]) -> int:
        """
        Calculate a threshold value based on frame comparison data.

        Args:
            frame_compare (list[float]): The list of frame comparison values.

        Returns:
            int: The calculated threshold value.
        """

        return sum(frame_compare) / len(frame_compare)

    def __calculate_states(self, state_list: list[int], fps_video: int) -> list[tuple[int, int, float]]:
        """
        Calculate state transitions and their durations in the video.

        Args:
            state_list (list[int]): The list of frame states (high/low).
            fps_video (int): The frames per second (FPS) of the video.

        Returns:
            list[tuple[int, int, float]]: A list of tuples containing the start, end, and duration of states.
        """

        lst_state = self.__LOW_STATE
        start = None
        animation_list = []

        for i in range(len(state_list)):
            if lst_state != state_list[i]:
                print("change state of screen to", state_list[i], "in frame", i)

            if start is None:
                if lst_state == self.__LOW_STATE and state_list[i] == self.__HIGH_STATE:
                    start = i
            else:
                if lst_state == self.__HIGH_STATE and state_list[i] == self.__LOW_STATE:
                    animation_time = (i - start) / fps_video
                    if animation_time > self.__MIN_ANIMATION_TIME_S:
                        print("animation seconds:", animation_time)
                        animation_list.append((start, i, animation_time))
                        start = None

            lst_state = state_list[i]

        return animation_list

    def __state_buffer(self, frame_compare: list[float], try_to_change: int) -> tuple[list[float], list[float]]:
        """
        Generate a list of states for each frame based on a threshold.

        Args:
            frame_compare (list[float]): The list of frame comparison values.
            try_to_change (int): The number of frames to confirm a state change.

        Returns:
            tuple[list[float], list[float]]: The state list and corresponding thresholds.
        """

        state = 0
        count = 0

        state_list = []
        threshold_ref_list = []

        threshold = self.__calculate_threshold_for_frames(frame_compare)

        for elem in frame_compare:
            if state == 0:
                if elem > threshold:
                    count += 1
                else:
                    count = 0

                if count > try_to_change:
                    state = 1
                    count = 0
            else:
                if elem < threshold:
                    count += 1
                else:
                    count = 0

                if count > try_to_change:
                    state = 0
                    count = 0

            state_list.append(state * self.__HIGH_STATE)
            threshold_ref_list.append(threshold)

        return state_list, threshold_ref_list

    def __join_sleep_time(
        self, labeled_icons: dict, type_command: str, command_name_upper: str, sleep_time: float
    ) -> None:
        """
        Join or update the sleep time for a command in the labeled icons.

        Args:
            labeled_icons (dict): The labeled icons structure with command information.
            type_command (str): The type of command being executed.
            command_name_upper (str): The uppercase command name.
            sleep_time (float): The calculated sleep time for the command.
        """

        prev_value = 0
        if type_command in labeled_icons["COMMAND_CHANGE_SEQUENCE"][command_name_upper]["COMMAND_SLEEPS"]:
            prev_value = labeled_icons["COMMAND_CHANGE_SEQUENCE"][command_name_upper]["COMMAND_SLEEPS"][type_command]

        labeled_icons["COMMAND_CHANGE_SEQUENCE"][command_name_upper]["COMMAND_SLEEPS"][type_command] = max(
            prev_value, round(sleep_time * 1.2, 2)
        )

    def __calculate_path_for_frame_with_menu_open(
        self, state_list: list[int], path_base: Path, open_animation_time: float
    ) -> Path:
        """
        Determine the path for the frame when the menu is open.

        Args:
            state_list (list[int]): The list of states for each frame.
            path_base (Path): The base directory path for the frames.
            open_animation_time (float): The time when the menu open animation occurs.

        Returns:
            Path: The path of the frame with the menu open.
        """

        opened_menu_frame_idx = open_animation_time + (len(state_list) - 1 - open_animation_time) // 2

        opened_menu_frame_idx = min(opened_menu_frame_idx, open_animation_time + 5)

        return path_base.joinpath("frames", f"frame_{opened_menu_frame_idx}.png")

    def __execute_interaction_with_device(
        self, path_base: Path, command_target_cam: str, file_name: str
    ) -> tuple[list[int], tuple[int, int, float]]:
        """
        Execute a command interaction with the device and process the video frames.

        Args:
            path_base (Path): The base directory for device interaction.
            command_target_cam (str): The target command for the camera.
            file_name (str): The name of the file to save the video frames.

        Returns:
            tuple[list[int], tuple[int, int, float]]: The state list and animation data.
        """
        record_len_s = 5
        self.__device.start_record_in_device(record_len_s)
        sleep(1)
        record_len_s -= 1
        self.__device.click_by_coordinates_in_device(command_target_cam)

        sleep(record_len_s * 1.1)
        self.__device.get_video_in_device(path_base, file_name)
        self.__split_frames(path_base, file_name)
        self.__device.delete_video_in_device()
        sleep(2)

        frames_diff = self.__compare_frames(path_base, file_name)
        moving_avg = self.__calculate_moving_average(frames_diff, 4)
        state_list, threshold_ref_list = self.__state_buffer(moving_avg, 3)

        animations = self.__calculate_states(
            state_list,
            self.__get_fps_for_video(path_base, file_name),
        )[0]

        return state_list, animations

    def cam_and_mode_gradle_remapping(self, labeled_icons: dict, reference_cam: str, reference_mode: str) -> None:
        """
        Remap camera and mode commands for different camera configurations.

        Args:
            labeled_icons (dict): The labeled icons structure with command information.
            reference_cam (str): The reference camera name.
            reference_mode (str): The reference mode name.
        """

        for cur_cam in self.__mapping_requirements["STATE_REQUIRES"]["CAM"]:
            if cur_cam != reference_cam:
                command_target_cam_name = f"cam {cur_cam}"
                command_target_cam = get_command_in_command_list(
                    labeled_icons["COMMANDS"],
                    command_target_cam_name,
                    reference_cam,
                    reference_mode,
                )
                file_name = f"{cur_cam} {reference_mode}"
                state_list, animations = self.__execute_interaction_with_device(
                    self.__device_target_dir, command_target_cam, file_name
                )

                print(command_target_cam["command_name"], animations)

                command_name_full = command_target_cam["command_name"]
                command_name_upper = command_name_full.split(" ")[0].upper()

                self.__join_sleep_time(labeled_icons, "CLICK_ACTION", command_name_upper, animations[2])

                opened_menu_img_path = self.__calculate_path_for_frame_with_menu_open(
                    state_list, self.__device_target_dir.joinpath(file_name), animations[1]
                )

                self.__process_image.process_screen_step_by_step(
                    labeled_icons, opened_menu_img_path, cur_cam, reference_mode
                )

                input(
                    f"Check if the device has the camera open with the configuration: Cam={cur_cam}, Mode={reference_mode}\nPress enter after check"
                )

            for cur_mode in self.__mapping_requirements["STATE_REQUIRES"]["MODE"]:
                if cur_mode != reference_mode:
                    command_target_mode_name = f"mode {cur_mode}"
                    command_target_mode = get_command_in_command_list(
                        labeled_icons["COMMANDS"], command_target_mode_name, cur_cam, reference_mode
                    )

                    file_name = f"{cur_cam} {cur_mode}"
                    state_list, animations = self.__execute_interaction_with_device(
                        self.__device_target_dir, command_target_mode, file_name
                    )

                    print(command_target_mode["command_name"], animations)

                    command_name_full = command_target_mode["command_name"]
                    command_name_upper = command_name_full.split(" ")[0].upper()

                    self.__join_sleep_time(labeled_icons, command_name_upper, animations[2])

                    opened_menu_img_path = self.__calculate_path_for_frame_with_menu_open(
                        state_list, self.__device_target_dir.joinpath(file_name), animations[1]
                    )

                    self.__process_image.process_screen_step_by_step(
                        labeled_icons, opened_menu_img_path, cur_cam, cur_mode
                    )

                    input(
                        f"Check if the device has the camera open with the configuration: Cam={cur_cam}, Mode={reference_mode}\nPress enter after check..."
                    )

    def mapping_menu_actions_in_each_group(self, labeled_icons: dict, groups: dict) -> None:
        """
        Map and execute menu actions for each group of commands.

        Args:
            labeled_icons (dict): The labeled icons structure with command information.
            groups (dict): The groups of commands to map and execute.
        """
        for cur_group in groups:
            # to requirements
            print("Goto require state")
            for comm_to in cur_group["to_requirements"]:
                self.__device.click_by_coordinates_in_device(comm_to)
                command_type_upper = comm_to["command_name"].upper().split(" ")[0]
                sleep_time = labeled_icons["COMMAND_CHANGE_SEQUENCE"][command_type_upper]["COMMAND_SLEEPS"][
                    "CLICK_ACTION"
                ]
                sleep(sleep_time)

            current_cam = cur_group["requirements"]["cam"]
            current_mode = cur_group["requirements"]["mode"]

            for command in cur_group["commands"]:
                command_name_full = command["command_name"]
                command_name_upper = command_name_full.split(" ")[0].upper()
                current_base_dir = self.__device_target_dir.joinpath(f"{current_cam} {current_mode}")

                state_list, animations = self.__execute_interaction_with_device(
                    current_base_dir, command, command_name_full
                )

                print(command["command_name"], animations)

                self.__join_sleep_time(labeled_icons, "CLICK_MENU", command_name_upper, animations[2])

                opened_menu_img_path = self.__calculate_path_for_frame_with_menu_open(
                    state_list,
                    current_base_dir.joinpath(command_name_full),
                    animations[1],
                )

                print(f"Labeling options in {command_name_full} for config {current_cam} {current_mode}...")

                self.__process_image.process_screen_step_by_step(
                    labeled_icons, opened_menu_img_path, current_cam, current_mode
                )

                input(
                    f"Check if the device has the camera open with the configuration: Cam={current_cam}, Mode={current_mode}\nPress enter after check..."
                )

            input(
                "Check if the device has the camera open with the configuration: Cam=Main, Mode=Photo\nPress enter after check..."
            )

    def calculate_menu_actions_animations_in_each_group(self, labeled_icons: dict, groups: dict) -> None:
        """
        Calculate menu action animations for each group of commands.

        Args:
            labeled_icons (dict): The labeled icons structure with command information.
            groups (dict): The groups of commands to map and execute animations.
        """

        for cur_group in groups:
            # to requirements
            print("Goto require state")
            for comm_to in cur_group["to_requirements"]:
                self.__device.click_by_coordinates_in_device(comm_to)
                command_type_upper = comm_to["command_name"].upper().split(" ")[0]
                sleep_time = labeled_icons["COMMAND_CHANGE_SEQUENCE"][command_type_upper]["COMMAND_SLEEPS"][
                    "CLICK_ACTION"
                ]
                sleep(sleep_time)

            current_cam = cur_group["requirements"]["cam"]
            current_mode = cur_group["requirements"]["mode"]
            dir_for_mode = f"{current_cam} {current_mode}"

            print(f"Camera state Cam={current_cam}, Mode={current_mode}")

            for command in cur_group["commands"]:
                full_command_name = command["command_name"]
                command_name_type = full_command_name.split(" ")[0]

                # get child for this combination
                options_for_this_menu = []
                for item in labeled_icons["COMMANDS"]:
                    if (
                        command_name_type in item["command_name"]
                        and (full_command_name not in item["command_name"])
                        and current_cam in item["requirements"]["cam"]
                        and current_mode in item["requirements"]["mode"]
                    ):
                        options_for_this_menu.append(item)

                for action in options_for_this_menu:
                    full_child_name = action["command_name"]
                    print(f"Apply Transition: {full_command_name} -> {full_child_name}")

                    current_target_path = self.__device_target_dir.joinpath(dir_for_mode, full_command_name)
                    file_name = full_child_name.replace(":", "_")
                    record_len_s = 5

                    self.__device.start_record_in_device(record_len_s)
                    sleep(1)
                    record_len_s -= 1

                    self.__device.click_by_coordinates_in_device(command)

                    sleep_time_menu = labeled_icons["COMMAND_CHANGE_SEQUENCE"][(command_name_type.upper())][
                        "COMMAND_SLEEPS"
                    ]["CLICK_MENU"]
                    sleep(sleep_time_menu)

                    self.__device.click_by_coordinates_in_device(action)

                    sleep(record_len_s * 1.1)
                    self.__device.get_video_in_device(current_target_path, file_name)
                    self.__split_frames(current_target_path, file_name)
                    self.__device.delete_video_in_device()
                    sleep(2)

                    frames_diff = self.__compare_frames(current_target_path, file_name)
                    moving_avg = self.__calculate_moving_average(frames_diff, 4)
                    state_list, threshold_ref_list = self.__state_buffer(moving_avg, 3)

                    animations = self.__calculate_states(
                        state_list,
                        self.__get_fps_for_video(current_target_path, file_name),
                    )

                    print(command["command_name"], animations)

                    command_name_full = command["command_name"]
                    command_name_upper = command_name_full.split(" ")[0].upper()

                    menu_sleep_time = 0

                    if len(animations) == 1:
                        menu_sleep_time = labeled_icons["COMMAND_CHANGE_SEQUENCE"][command_name_upper][
                            "COMMAND_SLEEPS"
                        ]["CLICK_MENU"]
                        animations = animations[0]
                    else:
                        animations = animations[1]

                    self.__join_sleep_time(
                        labeled_icons, "CLICK_ACTION", command_name_upper, animations[2] * 1.5 - menu_sleep_time
                    )

            # return_to_base
            print("Return to base state")
            for comm_to in cur_group["return_to_base"]:
                self.__device.click_by_coordinates_in_device(comm_to)
                command_type_upper = comm_to["command_name"].upper().split(" ")[0]
                sleep_time = labeled_icons["COMMAND_CHANGE_SEQUENCE"][command_type_upper]["COMMAND_SLEEPS"][
                    "CLICK_ACTION"
                ]
                sleep(sleep_time)
