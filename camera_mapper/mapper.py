from camera_mapper.fsm.fsm import CameraMapperFSM
from camera_mapper.fsm.model import CameraMapperModel


class CameraMapper:
    def __init__(self, device_ip: str, device_hardware_version: str = "1.0.0") -> None:
        self.device_ip = device_ip
        self.device_hardware_version = device_hardware_version
        self.model = CameraMapperModel(self.device_ip, self.device_hardware_version)
        self.fsm = CameraMapperFSM(self.model)

    def map(self):
        while not (self.fsm.is_finished() or self.fsm.is_general_error()):
            self.fsm.next_state()
