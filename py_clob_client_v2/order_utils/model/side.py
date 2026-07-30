from enum import Enum, IntEnum


class Side(IntEnum):
    BUY = 0
    SELL = 1


class SideString(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
