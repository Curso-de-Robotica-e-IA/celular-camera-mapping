from transitions import State
from transitions.extensions import GraphMachine


class CameraMapperFSM(GraphMachine):
    def __init__(self, model) -> None:
        """Constructor of the base `CameraMapperFSM` class."""
        idle = State(
            name="idle",
        )
        device_connection = State(
            name="device_connection",
            on_enter=["connect_device"],
        )
        connection_error = State(
            name="connection_error",
            on_enter=["raise_connection_error"],
        )
        screen_capture = State(
            name="screen_capture",
            on_enter=["capture_screen"],
        )
        actions_check = State(
            name="actions_check",
        )
        action_check = State(
            name="action_check",
            on_enter=["check_action"],
        )
        menu_check = State(
            name="menu_check",
        )
        menus_check = State(
            name="menus_check",
            on_enter=["check_menu"],
        )
        finished = State(
            name="finished",
            on_enter=["success_message"],
        )

        states = [
            idle,
            device_connection,
            connection_error,
            screen_capture,
            actions_check,
            action_check,
            menu_check,
            menus_check,
            finished,
        ]

        transitions = [
            {"trigger": "finished_to_idle", "source": "finished", "dest": "idle"},
            {
                "trigger": "idle_to_device_connection",
                "source": "idle",
                "dest": "device_connection",
                "after": ["connect_device"],
            },
            {
                "trigger": "device_connection_to_connection_error",
                "source": "device_connection",
                "dest": "connection_error",
                "unless": ["connected"],
            },
            {
                "trigger": "device_connection_to_screen_capture",
                "source": "device_connection",
                "dest": "screen_capture",
                "conditions": ["connected"],
            },
            {
                "trigger": "screen_capture_to_screen_capture",
                "source": "screen_capture",
                "dest": "screen_capture",
                "unless": ["visible_screen"],
            },
            {
                "trigger": "screen_capture_to_actions_check",
                "source": "screen_capture",
                "dest": "actions_check",
                "conditions": ["visible_screen"],
            },
            {
                "trigger": "actions_check_to_action_check",
                "source": "actions_check",
                "dest": "action_check",
                "conditions": ["has_action"],
            },
            {
                "trigger": "action_check_to_actions_check",
                "source": "action_check",
                "dest": "actions_check",
                "after": ["check_action"],
            },
            {
                "trigger": "actions_check_to_menus_check",
                "source": "actions_check",
                "dest": "menus_check",
                "unless": ["has_action"],
            },
            {
                "trigger": "menus_check_to_menu_check",
                "source": "menus_check",
                "dest": "menu_check",
                "conditions": ["has_menu"],
            },
            {
                "trigger": "menu_check_to_menus_check",
                "source": "menu_check",
                "dest": "menus_check",
                "after": ["check_menu"],
            },
            {
                "trigger": "menus_check_to_finished",
                "source": "menus_check",
                "dest": "finished",
                "unless": ["has_menu"],
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
