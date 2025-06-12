from transitions import State
from transitions.extensions import GraphMachine


class CameraMapperFSM(GraphMachine):
    def __init__(self, model) -> None:
        """Constructor of the base `CameraMapperFSM` class."""
        idle = State(
            name="idle",
            on_enter=["current_state"],
        )
        device_connection = State(
            name="device_connection",
            on_enter=["current_state", "connect_device"],
        )
        general_error = State(
            name="general_error",
            on_enter=["current_state", "raise_error"],
        )
        # Camera application open loop
        camera_open = State(
            name="camera_open",
            on_enter=["current_state", "open_camera"],
        )
        # Screen capture loop
        screen_capture = State(
            name="screen_capture",
            on_enter=["current_state", "capture_screen"],
            on_exit=["process_screen"],
        )
        # Map basic actions
        basic_marking = State(
            name="basic_marking",
            on_enter=["current_state", "mark_basic_actions"],
        )
        finished = State(
            name="finished",
            on_enter=["current_state", "success_message"],
        )

        states = [
            idle,
            device_connection,
            general_error,
            camera_open,
            screen_capture,
            basic_marking,
            finished,
        ]

        transitions = [
            {"trigger": "finished_to_idle", "source": "finished", "dest": "idle"},
            {
                "trigger": "idle_to_device_connection",
                "source": "idle",
                "dest": "device_connection",
            },
            {
                "trigger": "device_connection_to_general_error",
                "source": "device_connection",
                "dest": "general_error",
                "unless": ["connected"],
            },
            {
                "trigger": "device_connection_to_camera_open",
                "source": "device_connection",
                "dest": "camera_open",
                "conditions": ["connected"],
            },
            {
                "trigger": "camera_open_to_camera_open",
                "source": "camera_open",
                "dest": "camera_app_check",
                "unless": ["check_camera_app"],
            },
            {
                "trigger": "camera_open_to_general_error",
                "source": "camera_open",
                "dest": "general_error",
                "conditions": ["in_error"],
            },
            {
                "trigger": "camera_open_to_screen_capture",
                "source": "camera_open",
                "dest": "screen_capture",
                "conditions": ["check_camera_app"],
            },
            {
                "trigger": "screen_capture_to_general_error",
                "source": "screen_capture",
                "dest": "general_error",
                "conditions": ["in_error"],
            },
            {
                "trigger": "screen_capture_to_basic_marking",
                "source": "screen_capture",
                "dest": "basic_marking",
            },
            {
                "trigger": "basic_marking_to_finished",
                "source": "basic_marking",
                "dest": "finished",
            },
        ]

        super().__init__(
            model=model,
            states=states,
            transitions=transitions,
            initial=idle,
        )

    def __getattr__(self, item):
        """Method to get unlisted attributes of the class. If the attribute
        is not found, the method will return the class attribute.

        Args:
            item: The class attribute that should be retrieved.

        Returns:
            The class attribute.
        """
        return self.model.__getattribute__(item)

    def next_state(self):
        """Method for automatic execution of available transitions in each
        of the machine states.
        """
        available_transitions = self.get_triggers(self.state)
        available_transitions = available_transitions[len(self.states) :]
        for curr_transition in available_transitions:
            may_method_result = self.may_trigger(curr_transition)
            if may_method_result:
                self.trigger(curr_transition)
