from enum import Enum


class RepeatMode(Enum):
    ONE = "one"
    OFF = "off"
    ALL = "all"
    ONCE = "once"


class ShuffleMode(Enum):
    OFF = "off"
    ON = "on"


class QueueStatus(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    STOPPED = "stopped"


