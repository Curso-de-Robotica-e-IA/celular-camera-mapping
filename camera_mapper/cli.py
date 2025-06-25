from rich.console import Console
from typer import Context, Exit, Option, Typer

from camera_mapper import __version__, CameraMapper

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
    device_ip: str = Option(
        None,
        "--ip",
        "-i",
        help="Device IP address (e.g., 127.0.0.1:5555)",
    ),
) -> None:
    message = "Welcome to [bold blue]Camera Mapper[/bold blue], the CLI to map icons of your camera app Android Device."
    """Camera Mapper CLI."""
    if ctx.invoked_subcommand:
        return

    console.print(message)
    CameraMapper(device_ip).map()
