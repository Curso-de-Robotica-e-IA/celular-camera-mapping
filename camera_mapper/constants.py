from pathlib import Path

PATH_TO_BASE_FOLDER = Path.cwd()
PATH_TO_TMP_FOLDER = PATH_TO_BASE_FOLDER.joinpath("tmp")
SIZE_IN_SCREEN = 720
CLUSTER_THRESHOLD = 10


CAMERA = "main"
MODE = "photo"

SWITCH_CAM_NAMES = ["switch", "selfie", "main"]
CAPTURE_NAMES = ["take_picture", "capture", "photo"]
ASPECT_RATIO_MENU_NAMES = [
    "aspect_ratio",
    "ratio",
    "aspect",
    "3:4",
    "16:9",
    "1:1",
    "full",
]
FLASH_MENU_NAMES = ["flash", "on", "off", "auto"]
QUICK_CONTROL_NAMES = [
    "quick_control",
    "control",
    "quick",
]
OBJECTS_OF_INTEREST = [
    "PORTRAIT",
    "PHOTO",
    ".5",
    ".6",
    "1X",
    "2",
    "3",
    "4",
    "5",
    "6",
]
