"""Exception types for chat flow control."""
from typing import Optional


class ChatCancelled(Exception):
    """Raised inside ChatService.process_message when cancellation is requested.

    The supervisor catches this and emits a `cancelled` event. The
    conversation_id lets the supervisor persist a cancelled assistant message
    even if cancellation arrived mid-pipeline.
    """

    def __init__(self, conversation_id: Optional[str] = None, reason: str = "user"):
        self.conversation_id = conversation_id
        self.reason = reason
        super().__init__(
            f"chat cancelled (reason={reason}, conversation={conversation_id})"
        )


class QuestionTimeout(Exception):
    """Raised when a server `question` event is not answered within the timeout window."""
