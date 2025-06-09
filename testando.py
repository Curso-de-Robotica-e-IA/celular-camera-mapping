from camera_mapper.fsm.model import CameraMapperModel
from camera_mapper.fsm.fsm import CameraMapperFSM


def main():
    ip = "192.168.155.22"
    model = CameraMapperModel(ip, 0)
    fsm = CameraMapperFSM(model)
    while not (fsm.is_finished() or fsm.is_general_error()):
        fsm.next_state()


if __name__ == "__main__":
    main()
