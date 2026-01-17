from typing import Callable


class BaseAction:

    def __init__(self, label: str, callback: Callable, callback_args: tuple = None):
        self.label = label
        self.callback = callback
        self.callback_args = callback_args


class SongAction(BaseAction):
    """
    Used by song item widget more button
    """


class PlaylistAction(BaseAction):
    """
    Used by playlist buttons
    """
