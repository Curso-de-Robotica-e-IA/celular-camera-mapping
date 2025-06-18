from camera_mapper.fsm.fsm import CameraMapperFSM
from camera_mapper.fsm.model import CameraMapperModel


def main():
    ip = "192.168.155.11"
    model = CameraMapperModel(ip)
    fsm = CameraMapperFSM(model)
    while not (fsm.is_finished() or fsm.is_general_error()):
        fsm.next_state()


if __name__ == "__main__":
    main()
