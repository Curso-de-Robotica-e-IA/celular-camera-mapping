import math

import cv2
import numpy as np

from entities import ClickableBox, Point
from utils import show_image_in_thread


class ProcessImage:
    def __init__(self, size_in_screen, mapping_requirements) -> None:
        self.__size_in_screen = size_in_screen
        self.__mapping_requirements = mapping_requirements

    def __merge_contours(self, contour1, contour2):
        return np.concatenate((contour1, contour2), axis=0)

    def __calculate_contour_distance(self, contour1, contour2):
        x1, y1, w1, h1 = cv2.boundingRect(contour1)
        c_x1 = x1 + w1 / 2
        c_y1 = y1 + h1 / 2

        x2, y2, w2, h2 = cv2.boundingRect(contour2)
        c_x2 = x2 + w2 / 2
        c_y2 = y2 + h2 / 2

        return max(abs(c_x1 - c_x2) - (w1 + w2) / 2, abs(c_y1 - c_y2) - (h1 + h2) / 2)

    def __agglomerative_cluster(self, contours, threshold_distance):
        current_contours = contours
        while len(current_contours) > 1:
            min_distance = None
            min_coordinate = None

            for x in range(len(current_contours) - 1):
                for y in range(x + 1, len(current_contours)):
                    distance = self.__calculate_contour_distance(current_contours[x], current_contours[y])
                    if min_distance is None:
                        min_distance = distance
                        min_coordinate = (x, y)
                    elif distance < min_distance:
                        min_distance = distance
                        min_coordinate = (x, y)

            if min_distance < threshold_distance:
                index1, index2 = min_coordinate
                current_contours[index1] = self.__merge_contours(current_contours[index1], current_contours[index2])
                del current_contours[index2]
            else:
                break

        return current_contours

    def __find_contours_in_image(self, image):
        edged = cv2.Canny(image, 30, 200)
        contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

        contours_list = []
        for elem in contours:
            contours_list.append(elem)

        threshold = math.sqrt((image.shape[0] / 100) ** 2 + (image.shape[1] / 100) ** 2)

        filters_contours = self.__agglomerative_cluster(contours_list, threshold)

        detect_list = []

        for cnt in filters_contours:
            x, y, w, h = cv2.boundingRect(cnt)
            min_x, min_y = (x, y)
            max_x, max_y = (x + w, y + h)
            cx = int((x + (w / 2)))
            cy = int((y + (h / 2)))

            detect_item = ClickableBox("", Point(min_x, min_y), Point(max_x, max_y), Point(cx, cy))
            detect_list.append(detect_item)

        return detect_list

    def __show_clickable_itens(self, image, detect_box, size_in_screen):
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
            cv2.circle(new_image, box.centroid.to_tuple(), 10, color=(0, 0, 255), thickness=4)

        scale = size_in_screen / image.shape[0]
        new_image = cv2.resize(new_image, (0, 0), fx=scale, fy=scale)

        cv2.imshow("camera", new_image)

        cv2.waitKey(0)

        cv2.destroyAllWindows()

    def __process_detection_in_screen_step_by_step(
        self,
        base_image,
        detect_box,
        size_in_screen,
        command_to_mapping,
        labeled_icons,
        current_cam,
        current_mode,
    ):
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

            while True:
                try:
                    show_image_in_thread("Box icon", image)
                    label_name = (input("Is a valid item? (y/n)")).lower()
                    cv2.destroyAllWindows()

                    if "y" in label_name:
                        command = {}
                        print("Select the item type in list:\n")
                        for i, elem in enumerate(command_to_mapping["ITENS_TO_MAPPING"]):
                            print(f"[{i}] -", elem)

                        idx = None
                        while idx is None:
                            try:
                                input_idx = int(input("Select index: "))
                                idx = input_idx
                            except Exception as e:
                                print(e)

                        command_label = command_to_mapping["ITENS_TO_MAPPING"][idx]

                        print("Select the command action type in list:\n")
                        for i, elem in enumerate(command_to_mapping["COMMAND_ACTION_AVAILABLE"]):
                            print(f"[{i}] -", elem)

                        act_idx = None
                        while act_idx is None:
                            try:
                                input_idx = int(input("Select index: "))
                                act_idx = input_idx
                            except Exception as e:
                                print(e)

                        command_full_name = ""
                        if command_to_mapping["COMMAND_ACTION_AVAILABLE"][act_idx] == "CLICK_MENU":
                            command_full_name = command_label.lower() + " menu"
                        elif command_label == "TAKE_PICTURE":
                            labeled_icons["COMMAND_CHANGE_SEQUENCE"]["TAKE_PICTURE"]["COMMAND_SLEEPS"][
                                "CLICK_ACTION"
                            ] = 3
                            command_full_name = command_label.lower().replace("_", " ")
                        else:
                            command_value = input("Typing the command value:")
                            command_full_name = command_label.lower() + f" {command_value}"

                        command["command_name"] = command_full_name
                        command["click_by_coordinates"] = {
                            "start_x": box.centroid.x,
                            "start_y": box.centroid.y,
                        }

                        command["requirements"] = {"cam": current_cam, "mode": current_mode}

                        apply_to = "on/off"

                        for t in apply_to.split("/"):
                            value = f"COMMAND_SEQUENCE {(t.upper())}"
                            if not (
                                command_to_mapping["COMMAND_ACTION_AVAILABLE"][act_idx]
                                in labeled_icons["COMMAND_CHANGE_SEQUENCE"][command_label][value]
                            ):
                                labeled_icons["COMMAND_CHANGE_SEQUENCE"][command_label][value].append(
                                    command_to_mapping["COMMAND_ACTION_AVAILABLE"][act_idx]
                                )

                        labeled_icons["COMMANDS"].append(command)

                    break
                except KeyboardInterrupt:
                    print("\n\nClean selection for current item\n")

        return labeled_icons

    def process_screen_step_by_step(self, labeled_icons, image_path, current_cam, current_mode):
        image = cv2.imread(image_path)

        detect_boxes_from_contours = self.__find_contours_in_image(image)

        self.__show_clickable_itens(image, detect_boxes_from_contours, self.__size_in_screen)

        labeled_icons = self.__process_detection_in_screen_step_by_step(
            image,
            detect_boxes_from_contours,
            self.__size_in_screen,
            self.__mapping_requirements,
            labeled_icons,
            current_cam,
            current_mode,
        )
