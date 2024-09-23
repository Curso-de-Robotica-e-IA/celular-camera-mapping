import glob
import os
import shutil
from sewar.full_ref import mse
import cv2


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


def get_fps_for_video(base_path, folder_name):
    full_path = f"{base_path}\\{folder_name}"

    vidObj = cv2.VideoCapture(
        f"{full_path}\\video.mp4",
    )

    return vidObj.get(cv2.CAP_PROP_FPS)


def compare_frames(device_target_dir, command_name):
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


def calculate_moving_average(frame_compare, window_size):
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


def calculate_threshold_for_frames(frame_compare):
    return sum(frame_compare) / len(frame_compare)


def calculate_states(state_list, fps_video):
    lst_state = 0
    start = None
    animation_list = []

    for i in range(len(state_list)):
        if lst_state != state_list[i]:
            print("change state of screen to", state_list[i], "in frame", i)

        if start is None:
            if lst_state == 0 and state_list[i] == 50:
                start = i
        else:
            if lst_state == 50 and state_list[i] == 0:
                animation_time = (i - start) / fps_video
                if animation_time > 0.3:
                    print("animation seconds:", animation_time)
                    animation_list.append((start, i, animation_time))
                    start = None

        lst_state = state_list[i]

    return animation_list


def state_buffer(frame_compare, try_to_change):
    state = 0
    count = 0

    state_list = []
    threshold_ref_list = []

    threshold = calculate_threshold_for_frames(frame_compare)

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

        state_list.append(state * 50)
        threshold_ref_list.append(threshold)

    return state_list, threshold_ref_list
