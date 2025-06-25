# Camera Mapper
Camera Mapper is a general-purpose Android camera app mapper designed to automate tap/click positions on your device's screen. It supports both command-line interface (CLI) and API usage, making it flexible for various automation workflows.

**Requirements:**  
- Android Debug Bridge (ADB) installed
- Device's main camera faced down
- Ensure your Android device is connected via Wi-Fi debugging (ADB over network)

## Features
- Map and automate screen tap positions
- Use as a CLI tool or integrate via API
- Suitable for testing, automation, and scripting tasks

## CLI Usage

```sh
camapper -i [ANDROID-DEVICE-IP]
```

Replace `[ANDROID-DEVICE-IP]` with your device's actual IP address.

## API Usage

```python
from camera_mapper import CameraMapper

mapper = CameraMapper(device_ip="192.168.1.100")
mapper.map()
```

## Execution Flow
![Finite State Machine](assets/fsm.png)

## Output example
```json
{
    "CAM": [
        270,
        2090
    ],
    "TAKE_PICTURE": [
        540,
        2090
    ],
    "TOUCH": [
        540,
        1200
    ],
    "QUICK_CONTROLS": null,
    "ASPECT_RATIO_MENU": [
        756,
        200
    ],
    "ASPECT_RATIO_3_4": [
        180,
        200
    ],
    "ASPECT_RATIO_9_16": [
        540,
        200
    ],
    "ASPECT_RATIO_1_1": null,
    "ASPECT_RATIO_FULL": [
        900,
        200
    ],
    "FLASH_MENU": [
        108,
        200
    ],
    "FLASH_ON": [
        540,
        200
    ],
    "FLASH_OFF": [
        900,
        200
    ],
    "FLASH_AUTO": [
        180,
        200
    ],
    "PORTRAIT_MODE": [
        773,
        1892
    ],
    "BLUR_MENU": [
        979,
        1680
    ],
    "BLUR_BAR_MIDDLE": [
        530,
        2524
    ],
    "BLUR_STEP": [
        137
    ],
    "ZOOM_1": [
        639,
        1681
    ],
    "ZOOM_.5": [
        541,
        1681
    ]
}
```