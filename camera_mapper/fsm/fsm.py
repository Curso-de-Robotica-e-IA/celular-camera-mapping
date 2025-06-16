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
        tmp_dir = State(
            name="tmp_dir",
            on_enter=["current_state", "create_tmp_dir"],
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
        basic_xml_mapping = State(
            name="basic_xml_mapping",
            on_enter=["current_state", "map_xml_basic_actions"],
        )
        # Map aspect ratio
        xml_aspect_ratio = State(
            name="xml_aspect_ratio",
            on_enter=["current_state", "map_xml_aspect_ratio"],
        )
        aspect_ratio_actions = State(
            name="aspect_ratio_actions",
            on_enter=["current_state", "map_aspect_ratio_actions"],
        )
        # Map flash actions
        xml_flash = State(
            name="xml_flash",
            on_enter=["current_state", "map_xml_flash"],
        )
        flash_actions = State(
            name="flash_actions",
            on_enter=["current_state", "map_flash_actions"],
        )
        # Start Mapping portrait
        portrait_finding = State(
            name="portrait_finding",
            on_enter=["current_state", "find_portrait"],
        )
        portrait_mode_processing = State(
            name="portrait_mode_processing",
            on_enter=["current_state", "process_portrait_mode"],
        )
        finished = State(
            name="finished",
            on_enter=["current_state", "success_message"],
        )

        states = [
            idle,
            device_connection,
            general_error,
            tmp_dir,
            camera_open,
            screen_capture,
            basic_xml_mapping,
            xml_aspect_ratio,
            aspect_ratio_actions,
            xml_flash,
            flash_actions,
            portrait_finding,
            portrait_mode_processing,
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
                "trigger": "device_connection_to_tmp_dir",
                "source": "device_connection",
                "dest": "tmp_dir",
                "conditions": ["connected"],
            },
            {
                "trigger": "tmp_dir_to_camera_open",
                "source": "tmp_dir",
                "dest": "camera_open",
                "unless": ["in_error"],
            },
            {
                "trigger": "tmp_dir_to_general_error",
                "source": "tmp_dir",
                "dest": "general_error",
                "unless": ["connected"],
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
                "trigger": "screen_capture_to_basic_xml_mapping",
                "source": "screen_capture",
                "dest": "basic_xml_mapping",
            },
            {
                "trigger": "basic_xml_mapping_to_xml_aspect_ratio",
                "source": "basic_xml_mapping",
                "dest": "xml_aspect_ratio",
            },
            {
                "trigger": "xml_aspect_ratio_to_aspect_ratio_actions",
                "source": "xml_aspect_ratio",
                "dest": "aspect_ratio_actions",
            },
            {
                "trigger": "aspect_ratio_actions_to_xml_flash",
                "source": "aspect_ratio_actions",
                "dest": "xml_flash",
            },
            {
                "trigger": "xml_flash_to_flash_actions",
                "source": "xml_flash",
                "dest": "flash_actions",
            },
            {
                "trigger": "flash_actions_to_portrait_finding",
                "source": "flash_actions",
                "dest": "portrait_finding",
            },
            {
                "trigger": "portrait_finding_to_portrait_mode_processing",
                "source": "portrait_finding",
                "dest": "portrait_mode_processing",
            },
            {
                "trigger": "portrait_mode_processing_to_finished",
                "source": "portrait_mode_processing",
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
