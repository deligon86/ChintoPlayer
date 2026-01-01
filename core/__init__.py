import re
# from kivymd.app import MDApp
import logging


"""
def get_running_app():
    return MDApp.get_running_app()
"""

def format_string(string_value: str):
    pattern = r'[^\w]'
    value = re.sub(pattern, "", string_value)
    return value


logging.basicConfig(
    filename="app_logs.log",
    format='[{levelname}] [{asctime}] {message}',
    style='{',
    datefmt='%Y-%m-%d %H:%M:%S',
    filemode='w'
)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
