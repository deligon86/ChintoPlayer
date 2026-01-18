import sys
import os
import string
from PIL import Image
from io import BytesIO
from kivymd.app import MDApp
from kivy.core.image import Image as KivyImage


# string formatter
def clean_string(text: str, omit:list = None):
    """
    Removes the punctuation characters
    :param text:
    :param omit: The characters to exclude in the
    :return:
    """
    exclude = omit if omit is not None else string.punctuation
    transformer = str.maketrans('', '', exclude)
    return text.translate(transformer)


def format_duration(duration: int | float):
    """
    :param duration:
    :return:
    """
    if duration > 216000: # 1 hour
        hh, mm = divmod(duration, 60)
        mm, ss = divmod(mm, 60)
        return f"{int(hh)}:{int(mm)}:{int(ss)}"
    else:
        mm, ss = divmod(duration, 60)
        return f"{int(mm)}:{int(ss)}"


def running_app():
    """
    Gets the active application
    :return:
    """
    return MDApp.get_running_app()


def load_kivy_image_from_data(image_data, ext="png"):
    """
    Loads image from bytes
    :param image_data:
    :param ext:
    :return:
    """
    image = Image.open(BytesIO(image_data))
    out_buffer = BytesIO()
    image.save(out_buffer, format=ext.upper(), quality=85, optimize=True)
    core_image = KivyImage(BytesIO(image_data), ext=ext)

    return core_image


def _is_frozen() -> bool:
    """Check if the application is running as a 'frozen' executable (e.g., PyInstaller, cx_Freeze)."""
    # PyInstaller, cx_Freeze, and others set the 'frozen' attribute on the sys module.
    return getattr(sys, 'frozen', False)


def get_resource_base_path() -> str:
    """
    Determines the absolute base directory for application resources.

    :returns:
        The directory path where resources are located. This is the temporary
        directory (`_MEIPASS`) for frozen executables, or the script's
        directory for development/non-frozen environments.
    """
    if _is_frozen():
        # PyInstaller/cx_Freeze temporary resource directory
        # _MEIPASS is the most reliable variable across major bundlers.
        try:
            return sys._MEIPASS
        except AttributeError:
            # Fallback for highly unusual bundling scenarios
            return os.path.dirname(sys.executable)
    else:
        # Development environment: Use the directory of the main script.
        # os.path.realpath handles symlinks.
        try:
            # sys.argv[0] is the script path
            return os.path.dirname(os.path.realpath(sys.argv[0]))
        except IndexError:
            return os.path.abspath(".")

def resource_path(relative_path) -> str:
    """
    Resolves the absolute path for a resource file, working correctly
    in both development and 'frozen' production environments.

    :param relative_path: The path to the resource, relative to the base directory.

    :returns:
        The fully resolved absolute path to the resource.
    """
    base_path = get_resource_base_path()
    resolved_path = os.path.join(base_path, relative_path)

    return resolved_path
