import glob
import os
import shutil
from time import sleep
from sewar.full_ref import mse
import cv2

from device import Device
from pi.process_image import ProcessImage
from utils import create_or_replace_dir, get_command_in_command_list


class ProcessFrames:

    def __init__(self, device_target_dir, mapping_requirements, device: Device, process_img: ProcessImage) -> None:
        self.__device = device
        self.__device_target_dir = device_target_dir
        self.__process_image = process_img
        self.__mapping_requirements = mapping_requirements

        self.__HIGH_STATE = 50
        self.__LOW_STATE = 0
        self.__MIN_ANIMATION_TIME_S = 0.3

    def __split_frames(self, base_path, folder_name):
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

    def __get_fps_for_video(self, base_path, folder_name):
        full_path = f"{base_path}\\{folder_name}"

        vidObj = cv2.VideoCapture(
            f"{full_path}\\video.mp4",
        )

        return vidObj.get(cv2.CAP_PROP_FPS)

    def __compare_frames(self, device_target_dir, command_name):
        frame_compare = []

        file_images_list = glob.glob(f"{device_target_dir}\\{command_name}\\frames\\*.png")

        def sort_by_number(file_name):
            return int(file_name.split("\\")[-1].split(".")[0].split("_")[-1])

        file_images_list = sorted(file_images_list, key=sort_by_number)

        if len(file_images_list) > 1:
            base_image = cv2.imread(file_images_list[0])

        for i in range(1, len(file_images_list)):
            new_image = cv2.imread(file_images_list[i])

            frame_compare.append(mse(base_image, new_image))

            base_image = new_image

        return frame_compare

    def __calculate_moving_average(self, frame_compare, window_size):
        i = 0
        # Initialize an empty list to store moving averages
        moving_averages = []

        # Loop through the array to consider
        # every window of size 3
        lst_val = None
        while i < len(frame_compare) - window_size + 1:
            # Store elements from i to i+window_size
            # in list to get the current window
            window = frame_compare[i : i + window_size]

            # Calculate the average of current window
            window_average = round(sum(window) / window_size, 2)

            # Store the average of current
            # window in moving average list
            moving_averages.append(window_average)
            lst_val = window_average
            # Shift window to right by one position
            i += 1

        for i in range(window_size):
            moving_averages.append(lst_val)

        return moving_averages

    def __calculate_threshold_for_frames(self, frame_compare):
        return sum(frame_compare) / len(frame_compare)

    def __calculate_states(self, state_list, fps_video):
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

    def __state_buffer(self, frame_compare, try_to_change):
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

    def __join_sleep_time(self, labeled_icons, type_command, command_name_upper, sleep_time):
        prev_value = 0
        if type_command in labeled_icons["COMMAND_CHANGE_SEQUENCE"][command_name_upper]["COMMAND_SLEEPS"]:
            prev_value = labeled_icons["COMMAND_CHANGE_SEQUENCE"][command_name_upper]["COMMAND_SLEEPS"][type_command]

        labeled_icons["COMMAND_CHANGE_SEQUENCE"][command_name_upper]["COMMAND_SLEEPS"][type_command] = max(
            prev_value, round(sleep_time * 1.2, 2)
        )

    def __calculate_path_for_frame_with_menu_open(self, state_list, path_base, open_animation_time):
        opened_menu_frame_idx = open_animation_time + (len(state_list) - 1 - open_animation_time) // 2

        opened_menu_frame_idx = min(opened_menu_frame_idx, open_animation_time + 5)

        return f"{path_base}\\frames\\frame_{opened_menu_frame_idx}.png"

    def __execute_interaction_with_device(self, path_base, command_target_cam, file_name):
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

    def cam_and_mode_gradle_remapping(self, labeled_icons, current_cam, current_mode):

        for c in self.__mapping_requirements["STATE_REQUIRES"]["CAM"]:
            if c != current_cam:
                command_target_cam_name = f"cam {c}"
                command_target_cam = get_command_in_command_list(
                    labeled_icons["COMMANDS"],
                    command_target_cam_name,
                    current_cam,
                    current_mode,
                )
                file_name = f"{c} {current_mode}"
                state_list, animations = self.__execute_interaction_with_device(
                    self.__device_target_dir, command_target_cam, file_name
                )

                print(command_target_cam["command_name"], animations)

                command_name_full = command_target_cam["command_name"]
                command_name_upper = command_name_full.split(" ")[0].upper()

                self.__join_sleep_time(labeled_icons, "CLICK_ACTION", command_name_upper, animations[2])

                opened_menu_img_path = self.__calculate_path_for_frame_with_menu_open(
                    state_list, f"{self.__device_target_dir}\\{file_name}", animations[1]
                )

                self.__process_image.process_screen_step_by_step(labeled_icons, opened_menu_img_path, c, current_mode)

                input(
                    f"Check if the device has the camera open with the configuration: Cam={c}, Mode={current_mode}\nPress enter after check"
                )

            for m in self.__mapping_requirements["STATE_REQUIRES"]["MODE"]:
                if m != current_mode:
                    command_target_mode_name = f"mode {m}"
                    command_target_mode = get_command_in_command_list(
                        labeled_icons["COMMANDS"], command_target_mode_name, c, current_mode
                    )

                    file_name = f"{c} {m}"
                    state_list, animations = self.__execute_interaction_with_device(
                        self.__device_target_dir, command_target_mode, file_name
                    )

                    print(command_target_mode["command_name"], animations)

                    command_name_full = command_target_mode["command_name"]
                    command_name_upper = command_name_full.split(" ")[0].upper()

                    self.__join_sleep_time(labeled_icons, command_name_upper, animations[2])

                    opened_menu_img_path = self.__calculate_path_for_frame_with_menu_open(
                        state_list, f"{self.__device_target_dir}\\{file_name}", animations[1]
                    )

                    self.__process_image.process_screen_step_by_step(labeled_icons, opened_menu_img_path, c, m)

                    input(
                        f"Check if the device has the camera open with the configuration: Cam={c}, Mode={current_mode}\nPress enter after check..."
                    )

    def mapping_menu_actions_in_each_group(self, labeled_icons, groups):

        for g in groups:

            # to requirements
            for comm_to in g["to_requirements"]:
                self.__device.click_by_coordinates_in_device(comm_to)
                command_type_upper = comm_to["command_name"].upper().split(" ")[0]
                sleep_time = labeled_icons["COMMAND_CHANGE_SEQUENCE"][command_type_upper]["COMMAND_SLEEPS"][
                    "CLICK_ACTION"
                ]
                sleep(sleep_time)

            current_cam = g["requirements"]["cam"]
            current_mode = g["requirements"]["mode"]

            for command in g["commands"]:
                command_name_full = command["command_name"]
                command_name_upper = command_name_full.split(" ")[0].upper()
                current_base_dir = f"{self.__device_target_dir}\\{current_cam} {current_mode}"

                state_list, animations = self.__execute_interaction_with_device(
                    current_base_dir, command, command_name_full
                )

                print(command["command_name"], animations)

                self.__join_sleep_time(labeled_icons, "CLICK_MENU", command_name_upper, animations[2])

                opened_menu_img_path = self.__calculate_path_for_frame_with_menu_open(
                    state_list,
                    f"{current_base_dir}\\{command_name_full}",
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
                f"Check if the device has the camera open with the configuration: Cam=Main, Mode=Photo\nPress enter after check..."
            )

    def calculate_menu_actions_animations_in_each_group(self, labeled_icons, groups):
        for g in groups:
            current_cam = g["requirements"]["cam"]
            current_mode = g["requirements"]["mode"]
            dir_for_mode = f"{current_cam} {current_mode}"

            for command in g["commands"]:
                full_command_name = command["command_name"]
                command_name_type = full_command_name.split(" ")[0]

                # get child for this combination
                options_for_this_menu = []
                for item in labeled_icons["COMMANDS"]:
                    if (
                        command_name_type in item["command_name"]
                        and (not full_command_name in item["command_name"])
                        and current_cam in item["requirements"]["cam"]
                        and current_mode in item["requirements"]["mode"]
                    ):
                        options_for_this_menu.append(item)

                for action in options_for_this_menu:

                    current_target_path = f"{self.__device_target_dir}\\{dir_for_mode}\\{full_command_name}"

                    file_name = action["command_name"].replace(":", "_")

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

                    self.__join_sleep_time(labeled_icons, command_name_upper, animations[2] * 1.5 - menu_sleep_time)

        return labeled_icons
