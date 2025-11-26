from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone

from openhands.storage.data_models.conversation_status import ConversationStatus


@dataclass
class ConversationInfo:
    """Information about a conversation"""

    conversation_id: str
    title: str
    last_updated_at: datetime | None = None
    status: ConversationStatus = ConversationStatus.STOPPED
    selected_repository: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
