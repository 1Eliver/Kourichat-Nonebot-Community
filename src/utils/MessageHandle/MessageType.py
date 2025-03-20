from enum import Enum, auto

class MessageType(Enum):
    """
    消息类型枚举
    参考：https://napneko.pages.dev/develop/msg
    """
    TEXT = auto()
    FACE = auto()
    IMAGE = auto()
    RECORD = auto()
    FILE = auto()
    ANIMATION_FACE = auto()
    

