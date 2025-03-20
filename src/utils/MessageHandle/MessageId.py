import uuid


class MessageId:
    def __init__(self, sender_id: str):
        self.sender_id = sender_id
        self.message_id = uuid.uuid4().hex

    def __str__(self):
        return self.message_id

