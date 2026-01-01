from enum import Enum


class ScannerState(Enum):
    SCAN = "scanning"
    STOP = "stop"
    COMPLETE = "completed"


class ScannerScanMode(Enum):
    SINGLE = "single"
    MANY = "many"
