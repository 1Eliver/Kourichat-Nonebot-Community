from src.utils.MessageHandle.MessageSenderType import MessageSenderType
from src.utils.MessageHandle.MessageType import MessageType
from src.utils.MessageHandle.MessageId import MessageId


class KMessage:
    """
    改名KMessage，避免和NoneBot的Message冲突
    """
    def __init__(
        self, 
        message_id: MessageId, 
        message_type: MessageType, 
        sender_type: MessageSenderType,
        message_content: str
        ):
        self.message_id = message_id
        self.message_type = message_type
        self.sender_type = sender_type
        self.message_content = message_content