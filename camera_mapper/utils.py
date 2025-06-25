import shutil
from pathlib import Path


def create_or_replace_dir(path_dir: Path) -> None:
    """
    Checks if a directory exists, and if it does, removes it and creates a new one. If it doesn't exist, the method creates the directory.

    Args:
        path_dir (Path): The directory path to be created or replaced.
    """
    if path_dir.exists():
        shutil.rmtree(path_dir)

    path_dir.mkdir()


def get_command_in_command_list(
    command_list: list[dict], command_name: str, current_cam: str, current_mode: str
) -> dict | None:
    """
    Searches through a list of command dictionaries to find a command that matches the specified name, camera, and mode requirements.

    Args:
        command_list (list[dict]): A list of command dictionaries, where each dictionary contains information about a command.
        command_name (str): The name of the command to search for.
        current_cam (str): The current camera specification required by the command.
        current_mode (str): The current mode required by the command.

    Returns:
       dict: The command dictionary that matches the given parameters. If no match is found return `None`.
    """
    for command in command_list:
        if command_name in command["command_name"]:
            if (
                current_cam in command["requirements"]["cam"]
                and current_mode in command["requirements"]["mode"]
            ):
                return command
