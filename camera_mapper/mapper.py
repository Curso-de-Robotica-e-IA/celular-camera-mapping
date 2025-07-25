from camera_mapper.fsm.fsm import CameraMapperFSM
from camera_mapper.fsm.model import CameraMapperModel


class CameraMapper:
    def __init__(
        self,
        device_ip: str,
        destiny_path: str = "",
        device_hardware_version: str = "1.0.0",
    ) -> None:
        """
        Args:
            device_ip (str): IP address of the device
            destiny_path (str, optional): Path to the destiny folder. Defaults to "".
            device_hardware_version (str, optional): Hardware version. Defaults to "1.0.0".
        """
        self.device_ip = device_ip
        self.device_hardware_version = device_hardware_version
        self.model = CameraMapperModel(
            self.device_ip, destiny_path, self.device_hardware_version
        )
        self.fsm = CameraMapperFSM(self.model)

    def map(self):
        """
        Starts the process to map the camera on the connected device and writes json arquive on destiny path folder.
        """
        while not (self.fsm.is_finished() or self.fsm.is_general_error()):
            self.fsm.next_state()
