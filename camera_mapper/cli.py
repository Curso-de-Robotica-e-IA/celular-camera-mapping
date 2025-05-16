from rich.console import Console
from typer import Context, Exit, Option, Typer

from camera_mapper import __version__
from camera_mapper.camera_mapper import CameraMapper

app = Typer(add_completion=False)
console = Console()


def version_func(flag: bool):
    if flag:
        print("Camera Mapper CLI version:", __version__)
        raise Exit(code=0)


@app.callback(invoke_without_command=True)
def camapper(
    ctx: Context,
    version: bool = Option(
        None, "--version", "-v", callback=version_func, is_eager=True
    ),
    device_brand: str = Option(
        None,
        "--brand",
        "-b",
        help="Device brand Model name (e.g., Samsung-A34, Motorola-G53, etc.)",
    ),
    device_ip: str = Option(
        None,
        "--ip",
        "-i",
        help="Device IP address (e.g., 127.0.0.1:5555)",
    ),
    start_step: int = Option(
        0,
        "--start-step",
        "-s",
        help="Step number for start mapping (e.g., 0, 1, 2, 3, etc.)",
    ),
) -> None:
    message = "Welcome to [bold blue]Camera Mapper[/bold blue], the CLI to map icons of your camera app Android Device."
    """Camera Mapper CLI."""
    if ctx.invoked_subcommand:
        return

    console.print(message)

    mapper = CameraMapper(device_brand, device_ip, start_step)
    mapper.main_loop()
