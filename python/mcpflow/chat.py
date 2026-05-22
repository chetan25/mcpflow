"""Chat management and orchestration."""

from typing import Any, Dict, List, Optional


class Message(dict):
    """Represents a message in a conversation."""

    def __init__(self, role: str, content: str, **kwargs: Any):
        """Initialize a message.
        
        Args:
            role: Message role (user, assistant, system)
            content: Message content
            **kwargs: Additional message properties
        """
        super().__init__(role=role, content=content, **kwargs)


class ChatManager:
    """Manages chat sessions and message flow."""

    def __init__(self):
        """Initialize chat manager."""
        self._sessions: Dict[str, List[Message]] = {}

    def create_session(self, session_id: str) -> None:
        """Create a new chat session.
        
        Args:
            session_id: Unique session identifier
        """
        self._sessions[session_id] = []

    def add_message(self, session_id: str, message: Message) -> None:
        """Add a message to a session.
        
        Args:
            session_id: Session identifier
            message: Message to add
        """
        if session_id not in self._sessions:
            self.create_session(session_id)
        self._sessions[session_id].append(message)

    def get_history(self, session_id: str) -> List[Message]:
        """Get message history for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of messages
        """
        return self._sessions.get(session_id, [])

    def clear_session(self, session_id: str) -> None:
        """Clear all messages from a session.
        
        Args:
            session_id: Session identifier
        """
        self._sessions[session_id] = []

    def delete_session(self, session_id: str) -> None:
        """Delete a chat session.
        
        Args:
            session_id: Session identifier
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
