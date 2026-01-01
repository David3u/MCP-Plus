"""
Simplified file-based todo list using hierarchical numeric IDs (e.g., 1, 2, 2.1, 2.2).

Format: [id][status] task_content
- Status: [ ] pending, [~] in progress, [x] completed
- IDs support decimals for subtasks: 1, 2, 2.1, 2.1.1, etc.
"""

import json
import hashlib
import threading
import re
from typing import List, Dict, Any, Tuple
from pathlib import Path


class TodoManager:
    """Manages project todo lists with hierarchical IDs and file-based persistence."""
    
    # Status markers
    STATUS_PENDING = "pending"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    
    # Status display mappings
    STATUS_TO_MARKER = {
        STATUS_PENDING: "[ ]",
        STATUS_IN_PROGRESS: "[~]",
        STATUS_COMPLETED: "[x]"
    }
    
    MARKER_TO_STATUS = {
        "[ ]": STATUS_PENDING,
        "[~]": STATUS_IN_PROGRESS,
        "[x]": STATUS_COMPLETED
    }
    
    # Regex to parse task lines: [id][status] content
    TASK_PATTERN = re.compile(r'^\[([0-9.]+)\]\s*\[([ ~x])\]\s*(.+)$')
    
    def __init__(self, todos_dir: str = "todos"):
        self.todos_dir = Path(todos_dir)
        self.lock = threading.Lock()
        self.todos_dir.mkdir(exist_ok=True)
    
    def _get_todo_file(self, project_path: str) -> Path:
        path_hash = hashlib.md5(project_path.encode()).hexdigest()
        return self.todos_dir / f"{path_hash}.json"
    
    def _read_todos(self, project_path: str) -> List[Dict[str, Any]]:
        todo_file = self._get_todo_file(project_path)
        if not todo_file.exists():
            return []
        with open(todo_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _write_todos(self, project_path: str, todos: List[Dict[str, Any]]) -> None:
        todo_file = self._get_todo_file(project_path)
        with open(todo_file, 'w', encoding='utf-8') as f:
            json.dump(todos, f, indent=2, ensure_ascii=False)
    
    def _parse_id(self, id_str: str) -> Tuple[float, ...]:
        """Parse a hierarchical ID string into a sortable tuple."""
        parts = id_str.split('.')
        return tuple(int(p) for p in parts)
    
    def _sort_todos(self, todos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort todos by their hierarchical ID."""
        def sort_key(todo):
            try:
                return self._parse_id(todo["id"])
            except (ValueError, KeyError):
                return (float('inf'),)
        return sorted(todos, key=sort_key)
    
    def _parse_task_line(self, line: str) -> Dict[str, Any] | None:
        """Parse a single task line in format [id][status] content."""
        line = line.strip()
        match = self.TASK_PATTERN.match(line)
        if not match:
            return None
        
        task_id, status_char, content = match.groups()
        
        # Map status character to status string
        marker = f"[{status_char}]"
        status = self.MARKER_TO_STATUS.get(marker, self.STATUS_PENDING)
        
        return {
            "id": task_id,
            "status": status,
            "content": content.strip()
        }
    
    def update_tasks(self, project_path: str, tasks_text: str) -> str:
        """
        Update tasks from formatted text.
        
        Each line should be in format: [id][status] task_content
        - If ID exists, update the status (and content if changed)
        - If ID is new, add the task
        
        Returns the full formatted task list.
        """
        with self.lock:
            todos = self._read_todos(project_path)
            todo_map = {t["id"]: t for t in todos}
            
            # Parse each line
            lines = tasks_text.strip().split('\n')
            for line in lines:
                if not line.strip():
                    continue
                
                parsed = self._parse_task_line(line)
                if not parsed:
                    continue  # Skip malformed lines
                
                task_id = parsed["id"]
                
                if task_id in todo_map:
                    # Update existing task
                    todo_map[task_id]["status"] = parsed["status"]
                    todo_map[task_id]["content"] = parsed["content"]
                else:
                    # Add new task
                    todo_map[task_id] = parsed
            
            # Convert back to list and sort
            todos = list(todo_map.values())
            todos = self._sort_todos(todos)
            
            self._write_todos(project_path, todos)
            return self.format_todos(todos)
    
    def remove_tasks(self, project_path: str, task_ids: List[str]) -> str:
        """Remove tasks by ID and return the updated list."""
        with self.lock:
            todos = self._read_todos(project_path)
            ids_set = set(task_ids)
            todos = [t for t in todos if t["id"] not in ids_set]
            todos = self._sort_todos(todos)
            self._write_todos(project_path, todos)
            return self.format_todos(todos)
    
    def list_todos(self, project_path: str) -> List[Dict[str, Any]]:
        """List all todos, sorted by ID."""
        with self.lock:
            todos = self._read_todos(project_path)
            return self._sort_todos(todos)
    
    def format_todos(self, todos: List[Dict[str, Any]]) -> str:
        """Format todos for display."""
        if not todos:
            return "📋 No tasks."
        
        lines = []
        for todo in todos:
            task_id = todo.get("id", "?")
            status = todo.get("status", self.STATUS_PENDING)
            content = todo.get("content", todo.get("title", ""))
            
            marker = self.STATUS_TO_MARKER.get(status, "[ ]")
            
            # Add indentation based on depth (number of dots in ID)
            depth = task_id.count('.')
            indent = "  " * depth
            
            lines.append(f"{indent}[{task_id}]{marker} {content}")
        
        return "\n".join(lines)
