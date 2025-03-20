from enum import Enum, auto

class MessageSenderType(Enum):
    """
    消息发送者类型枚举
    """
    PRIVATE = auto()
    GROUP = auto()
