import json
import math
import os
import subprocess
import easyocr
import cv2
import re
from dataclasses import dataclass
from threading import Thread
import numpy as np

@dataclass(unsafe_hash=True)
class Point:
    x:int
    y:int

    def to_tuple(self):
        return (self.x, self.y)

@dataclass(unsafe_hash=True)
class ClickableBox:
    label:str
    min_point:Point
    max_point:Point
    centroid: Point

    def to_dict(self):
        return{
            "label":self.label,
            "min_point": {
                "x": self.min_point.x, 
                "y": self.min_point.y
            },
            "max_point": {
                "x": self.max_point.x, 
                "y": self.max_point.y
            },
            "centroid": {
                "x": self.centroid.x, 
                "y": self.centroid.y
            }
        }
    
    @staticmethod
    def from_dict(dict_elem):
        return ClickableBox(
            dict_elem["label"],
            Point(dict_elem["min_point"]["x"],dict_elem["min_point"]["y"]),
            Point(dict_elem["max_point"]["x"],dict_elem["max_point"]["y"]),
            Point(dict_elem["centroid"]["x"],dict_elem["centroid"]["y"])
        )

class Command:
    command_name:str
    requirement_mode:str
    requirement_cam:str

def get_device_dimensions(ip_port):

    result = subprocess.run(["adb", "-s", ip_port, "shell", "wm", "size"], capture_output=True,
                            text=True)
    dimensions = result.stdout.strip()
    pattern = r"(\d+)x(\d+)"
    match = re.search(pattern, dimensions)
    if match:
        width, height = match.groups()

        return int(width), int(height)

    else:
        return None

def screen_shot(ip_port):
    subprocess.run(["adb", "-s", ip_port, "shell", "screencap", "-p", "/sdcard/DCIM/Camera/screencap.png"])

def get_screen_image(ip_port, path_target):
    subprocess.run(["adb", "-s", ip_port, "pull","/sdcard/DCIM/Camera/screencap.png", path_target])

def connect_device(ip_port):
    subprocess.run(f"adb connect {ip_port}")

def merge_contours(contour1, contour2):
    return np.concatenate((contour1, contour2), axis=0)

def calculate_contour_distance(contour1, contour2): 
    x1, y1, w1, h1 = cv2.boundingRect(contour1)
    c_x1 = x1 + w1/2
    c_y1 = y1 + h1/2

    x2, y2, w2, h2 = cv2.boundingRect(contour2)
    c_x2 = x2 + w2/2
    c_y2 = y2 + h2/2

    return max(abs(c_x1 - c_x2) - (w1 + w2)/2, abs(c_y1 - c_y2) - (h1 + h2)/2)

def agglomerative_cluster(contours, threshold_distance):
    current_contours = contours
    while len(current_contours) > 1:
        min_distance = None
        min_coordinate = None

        for x in range(len(current_contours)-1):
            for y in range(x+1, len(current_contours)):
                distance = calculate_contour_distance(current_contours[x], current_contours[y])
                if min_distance is None:
                    min_distance = distance
                    min_coordinate = (x, y)
                elif distance < min_distance:
                    min_distance = distance
                    min_coordinate = (x, y)

        if min_distance < threshold_distance:
            index1, index2 = min_coordinate
            current_contours[index1] = merge_contours(current_contours[index1], current_contours[index2])
            del current_contours[index2]
        else: 
            break

    return current_contours

def find_contours_in_image(image): 
    edged = cv2.Canny(image, 30, 200)
    contours, _ = cv2.findContours(edged,  
        cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    
    contours_list = []
    for elem in contours:
        contours_list.append(elem)

    threshold = math.sqrt((image.shape[0]/ 100)**2 + (image.shape[1]/ 100)**2)

    filters_contours = agglomerative_cluster(contours_list, threshold)

    detect_list = []

    for cnt in filters_contours:
        x,y,w,h = cv2.boundingRect(cnt)
        min_x, min_y = (x,y)
        max_x, max_y = (x+w,y+h)
        cx = int((x+(w/2)))
        cy = int((y + (h/ 2)))

        detect_item = ClickableBox('', Point(min_x, min_y), Point(max_x, max_y), Point(cx, cy))
        detect_list.append(detect_item)
    
    return detect_list

def show_clickable_itens(image, detect_box, size_in_screen):
    new_image = image.copy()
    for box in detect_box:
        if len(box.label) > 1:
            cv2.putText(new_image, box.label, box.min_point.to_tuple(), cv2.FONT_HERSHEY_SIMPLEX, 1.3, color=(0,255,0), thickness=2)

        cv2.rectangle(new_image, box.min_point.to_tuple(), box.max_point.to_tuple(), color=(255,0,0), thickness=2)
        cv2.circle(new_image, box.centroid.to_tuple(), 14, color=(0,0,255), thickness=6)

    scale = size_in_screen/image.shape[0]
    new_image = cv2.resize(new_image, (0,0), fx=scale, fy=scale)

    cv2.imshow('camera', new_image)

    cv2.waitKey(0)

    cv2.destroyAllWindows()

def processed_base_detection_in_screen_label_step_by_step(base_image, detect_box, size_in_screen, command_to_mapping):
    clickable_boxes = []
    scale = size_in_screen/base_image.shape[0]
    for box in detect_box:
        image = base_image.copy()

        cv2.rectangle(image, box.min_point.to_tuple(), box.max_point.to_tuple(), color=(0,0,255), thickness=2)
        image = cv2.resize(image, (0,0), fx=scale, fy=scale) 
        show_image_in_thread('Box icon', image)
        label_name = input('Select name to item or just enter to skip:')
        cv2.destroyAllWindows()
        if len(label_name) > 0:
            for i in  range(len(command_to_mapping)):
                print(f"[{i}] -", )
            box.label = label_name
            clickable_boxes.append(box)
        
    
    return clickable_boxes

def write_output_in_json(labeled_icons, file_name):
    data = {"COMMANDS":[]}
    for elem in labeled_icons:
        data["COMMANDS"].append(elem.to_dict())
    

    # Serializing json
    json_object = json.dumps(data, indent=2)
 
    # Writing to sample.json
    with open(f"{file_name}.json", "w") as outfile:
        outfile.write(json_object)

def show_image_in_thread(name, image):
    def draw(name, image):
        cv2.imshow(name, image)
        cv2.waitKey(0)
    
    show_thread = Thread(target=draw, args=(name, image,))
    show_thread.start()

if __name__ == '__main__':
    ip_port = "192.168.158.232:39367"
    image = cv2.imread('screencap.png')
    path_to_base_folder = os.getcwd()
    size_in_screen = 800

    current_cam = 'main'
    current_mode = 'photo'
    command_to_mapping = [
        "aspect_ratio menu",
        "flash menu",
        "mode portrait",
        "cam selfie",
        "zoom 1.0",
        "take picture"
    ]
    
    detect_boxes_from_contours = find_contours_in_image(image)
    show_clickable_itens(image, detect_boxes_from_contours, size_in_screen)
    labeled_icons = processed_base_detection_in_screen_label_step_by_step(image, 
                                                                     detect_boxes_from_contours, 
                                                                     size_in_screen, 
                                                                     command_to_mapping)
    write_output_in_json(labeled_icons, 'output')