"""
Simple file-based chatroom system for multi-agent coordination.

Each project directory gets its own chatroom where agents can post messages
and read what others have written. Messages are persisted to disk in JSON files.
"""

import os
import json
import hashlib
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path


class ChatroomManager:
    """
    Manages project chatrooms with file-based persistence.
    
    Each project (identified by absolute path) has its own chatroom.
    Messages are stored in chatrooms/{hash}.json files.
    """
    
    def __init__(self, chatrooms_dir: str = "chatrooms"):
        """
        Initialize the chatroom manager.
        
        Args:
            chatrooms_dir: Directory where chatroom JSON files are stored
        """
        self.chatrooms_dir = Path(chatrooms_dir)
        self.lock = threading.Lock()
        
        # Create chatrooms directory if it doesn't exist
        self.chatrooms_dir.mkdir(exist_ok=True)
    
    def _get_chatroom_file(self, project_path: str) -> Path:
        """
        Get the file path for a project's chatroom.
        
        Args:
            project_path: Absolute path to the project directory
            
        Returns:
            Path to the JSON file for this project's chatroom
        """
        # Create a hash of the project path to use as filename
        path_hash = hashlib.md5(project_path.encode()).hexdigest()
        return self.chatrooms_dir / f"{path_hash}.json"
    
    def _read_chatroom(self, project_path: str) -> Dict[str, Any]:
        """
        Read chatroom data from disk.
        
        Args:
            project_path: Absolute path to the project directory
            
        Returns:
            Dictionary containing chatroom data
        """
        chatroom_file = self._get_chatroom_file(project_path)
        
        if not chatroom_file.exists():
            # Create new chatroom
            return {
                "project_path": project_path,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "messages": []
            }
        
        with open(chatroom_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _write_chatroom(self, project_path: str, data: Dict[str, Any]) -> None:
        """
        Write chatroom data to disk.
        
        Args:
            project_path: Absolute path to the project directory
            data: Chatroom data dictionary to write
        """
        chatroom_file = self._get_chatroom_file(project_path)
        
        with open(chatroom_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def send_message(self, project_path: str, agent_name: str, message: str) -> Dict[str, Any]:
        """
        Send a message to a project's chatroom.
        
        Args:
            project_path: Absolute path to the project directory
            agent_name: Name/identifier of the agent sending the message
            message: The message content
            
        Returns:
            Dictionary with the new message and recent messages from the last 30 minutes
        """
        with self.lock:
            # Read current chatroom state
            chatroom_data = self._read_chatroom(project_path)
            
            # Create new message
            message_id = f"msg_{len(chatroom_data['messages']) + 1:06d}"
            new_message = {
                "message_id": message_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "agent_name": agent_name,
                "message": message
            }
            
            # Add to messages list
            chatroom_data["messages"].append(new_message)
            
            # Write back to disk
            self._write_chatroom(project_path, chatroom_data)
            
            # Get recent messages from the last 30 minutes (up to 4 messages)
            recent_messages = self._get_recent_messages(chatroom_data["messages"], minutes=30, limit=4)
            
            return {
                "new_message": new_message,
                "recent_messages": recent_messages
            }
    
    def _get_recent_messages(self, messages: List[Dict[str, Any]], minutes: int = 30, limit: int = 4) -> List[Dict[str, Any]]:
        """
        Get recent messages within a specified time window.
        
        Args:
            messages: List of all messages
            minutes: Time window in minutes (default: 30)
            limit: Maximum number of messages to return (default: 4)
            
        Returns:
            List of recent messages, most recent last
        """
        if not messages:
            return []
        
        # Calculate the cutoff time
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        
        # Filter messages within the time window
        recent = []
        for msg in reversed(messages):  # Start from most recent
            try:
                msg_time = datetime.fromisoformat(msg['timestamp'].replace('Z', '+00:00'))
                # Convert to UTC naive datetime for comparison
                if msg_time.replace(tzinfo=None) >= cutoff_time:
                    recent.insert(0, msg)  # Insert at beginning to maintain chronological order
                    if len(recent) >= limit:
                        break
                else:
                    break  # Stop when we hit older messages
            except (ValueError, KeyError):
                continue
        
        return recent
    
    def read_messages(self, project_path: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Read recent messages from a project's chatroom.
        
        Args:
            project_path: Absolute path to the project directory
            limit: Maximum number of recent messages to return (default: 50)
            
        Returns:
            List of message dictionaries, most recent last
        """
        with self.lock:
            chatroom_data = self._read_chatroom(project_path)
            messages = chatroom_data["messages"]
            
            # Return the most recent 'limit' messages
            if len(messages) > limit:
                return messages[-limit:]
            return messages
    
    def format_messages(self, messages: List[Dict[str, Any]]) -> str:
        """
        Format messages for display to agents.
        
        Args:
            messages: List of message dictionaries
            
        Returns:
            Formatted string with messages
        """
        if not messages:
            return "No messages in this chatroom yet."
        
        lines = [f"📬 Chatroom Messages ({len(messages)} total)\n"]
        lines.append("=" * 60)
        
        for msg in messages:
            timestamp = msg['timestamp'][:19]  # Remove milliseconds and Z
            lines.append(f"\n[{timestamp}] {msg['agent_name']}:")
            lines.append(f"  {msg['message']}")
        
        lines.append("\n" + "=" * 60)
        return "\n".join(lines)
