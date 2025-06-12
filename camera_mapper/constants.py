from pathlib import Path

PATH_TO_BASE_FOLDER = Path.cwd()
PATH_TO_META_FOLDER = PATH_TO_BASE_FOLDER.joinpath("meta")
PATH_TO_OUTPUT_FOLDER = PATH_TO_BASE_FOLDER.joinpath("output")
PATH_TO_TMP_FOLDER = PATH_TO_BASE_FOLDER.joinpath("tmp")
SIZE_IN_SCREEN = 720

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

MAPPING_REQUIREMENTS = {
    "STATE_REQUIRES": {
        "CAM": ["main", "selfie"],
        "MODE": ["photo", "portrait"],
    },
    "COMMAND_ACTION_AVAILABLE": [
        "CLICK_MENU",
        "CLICK_ACTION",
    ],
    "ITENS_TO_MAPPING": [
        "CAM",
        "MODE",
        "ASPECT_RATIO_MENU",
        "FLASH",
        "TAKE_PICTURE",
        "TOUCH",
    ],
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

STEPS = [
    "mapping_start_screen",
    "mapping_touch_for_all_screens",
    "mapping_screens_combinations_for_cam_and_mode",
    "mapping_menu_itens_animation_in_each_screen",
    "mapping_menu_action_animation_in_each_screen",
]
