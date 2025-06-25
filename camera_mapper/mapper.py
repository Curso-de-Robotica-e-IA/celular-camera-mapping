from camera_mapper.fsm.fsm import CameraMapperFSM
from camera_mapper.fsm.model import CameraMapperModel


class CameraMapper:
    def __init__(self, device_ip: str):
        self.device_ip = device_ip
        self.model = CameraMapperModel(self.device_ip)
        self.fsm = CameraMapperFSM(self.model)

    def map(self):
        while not (self.fsm.is_finished() or self.fsm.is_general_error()):
            self.fsm.next_state()
