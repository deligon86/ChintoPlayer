from typing import Callable


class SongAction:

    def __init__(self, label: str, callback: Callable, callback_args: tuple = None):
        self.label = label
        self.callback = callback
        self.callback_args = callback_args

