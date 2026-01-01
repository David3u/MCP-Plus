import os
import json
import re
import subprocess
from typing import Dict, Any, List, Optional
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
from .prompts import SUBAGENT_SYSTEM_PROMPT, FINAL_GUIDANCE_TEMPLATE, TOOL_DEFINITIONS

load_dotenv()


class SubAgent:
    """
    A simple sub-agent that handles basic read and write operations.
    Uses a smaller/faster LLM for menial tasks.
    """
    
    def __init__(self, context_engine=None, log_dir=None):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY")
        )
        # Use a fast, cheap model for simple tasks
        self.model = os.getenv("SUBAGENT_MODEL", "moonshotai/kimi-k2-thinking")
        self.files_modified = []
        self.files_read = []
        self.context_engine = context_engine
        
        # Set up logging directory
        if log_dir is None:
            log_dir = os.path.expanduser("~/.mcp/context_mcp/subagent_logs")
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Tool history for current execution
        self.tool_history = []
        self.log_file_path = None
        
    def _get_file_tree(self, path: str, max_depth: int = 3, current_depth: int = 0) -> str:
        """Generate a simple file tree for context."""
        if current_depth >= max_depth:
            return ""
        
        tree = []
        try:
            items = sorted(os.listdir(path))
            for item in items:
                # Skip common ignores
                if item.startswith('.') or item in ['node_modules', '__pycache__', 'venv', '.git']:
                    continue
                
                item_path = os.path.join(path, item)
                indent = "  " * current_depth
                
                if os.path.isdir(item_path):
                    tree.append(f"{indent}{item}/")
                    tree.append(self._get_file_tree(item_path, max_depth, current_depth + 1))
                else:
                    tree.append(f"{indent}{item}")
        except PermissionError:
            pass
        
        return "\n".join(filter(None, tree))
    
    def _read_file(self, file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> Dict[str, Any]:
        """Read a file and return its contents. Optionally read specific line ranges."""
        try:
            abs_path = os.path.abspath(file_path)
            
            if not os.path.exists(abs_path):
                return {
                    "success": False,
                    "error": f"File does not exist: {abs_path}"
                }
            
            if not os.path.isfile(abs_path):
                return {
                    "success": False,
                    "error": f"Path is not a file: {abs_path}"
                }
            
            # Check file size (limit to 1MB for safety)
            file_size = os.path.getsize(abs_path)
            if file_size > 1_000_000:
                return {
                    "success": False,
                    "error": f"File too large ({file_size} bytes), max 1MB"
                }
            
            with open(abs_path, 'r', encoding='utf-8') as f:
                if start_line is not None or end_line is not None:
                    # Read specific lines
                    lines = f.readlines()
                    total_lines = len(lines)
                    
                    # Adjust indices (1-indexed to 0-indexed)
                    start_idx = (start_line - 1) if start_line else 0
                    end_idx = end_line if end_line else total_lines
                    
                    # Validate ranges
                    if start_idx < 0 or start_idx >= total_lines:
                        return {
                            "success": False,
                            "error": f"start_line {start_line} out of range (file has {total_lines} lines)"
                        }
                    if end_idx < start_idx or end_idx > total_lines:
                        return {
                            "success": False,
                            "error": f"end_line {end_line} out of range or less than start_line"
                        }
                    
                    content = ''.join(lines[start_idx:end_idx])
                else:
                    content = f.read()
            
            self.files_read.append(file_path)
            
            return {
                "success": True,
                "path": abs_path,
                "content": content,
                "size": file_size
            }
        except UnicodeDecodeError:
            return {
                "success": False,
                "error": "File is not a text file (encoding error)"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error reading file: {str(e)}"
            }
    
    def _write_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """Write content to a file."""
        try:
            abs_path = os.path.abspath(file_path)
            
            # Create parent directories if they don't exist
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            
            with open(abs_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.files_modified.append(file_path)
            
            return {
                "success": True,
                "path": abs_path,
                "bytes_written": len(content.encode('utf-8'))
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error writing file: {str(e)}"
            }
    
    def _list_directory(self, dir_path: str) -> Dict[str, Any]:
        """List contents of a directory."""
        try:
            abs_path = os.path.abspath(dir_path)
            
            if not os.path.exists(abs_path):
                return {
                    "success": False,
                    "error": f"Directory does not exist: {abs_path}"
                }
            
            if not os.path.isdir(abs_path):
                return {
                    "success": False,
                    "error": f"Path is not a directory: {abs_path}"
                }
            
            items = []
            for item in sorted(os.listdir(abs_path)):
                item_path = os.path.join(abs_path, item)
                items.append({
                    "name": item,
                    "type": "directory" if os.path.isdir(item_path) else "file",
                    "size": os.path.getsize(item_path) if os.path.isfile(item_path) else None
                })
            
            return {
                "success": True,
                "path": abs_path,
                "items": items
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error listing directory: {str(e)}"
            }
    
    def _replace_file_content(
        self, 
        file_path: str, 
        old_text: str = None, 
        new_text: str = None,
        replacements: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Replace text in an existing file. Supports single or multiple replacements.
        
        Args:
            file_path: Path to the file
            old_text: Text to find (for single replacement)
            new_text: Text to replace with (for single replacement)
            replacements: List of {"old": "...", "new": "..."} dicts (for multiple replacements)
        """
        try:
            abs_path = os.path.abspath(file_path)
            
            if not os.path.exists(abs_path):
                return {
                    "success": False,
                    "error": f"File does not exist: {abs_path}"
                }
            
            if not os.path.isfile(abs_path):
                return {
                    "success": False,
                    "error": f"Path is not a file: {abs_path}"
                }
            
            # Read the file
            with open(abs_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Build list of replacements
            if replacements:
                replace_list = replacements
            elif old_text is not None and new_text is not None:
                replace_list = [{"old": old_text, "new": new_text}]
            else:
                return {
                    "success": False,
                    "error": "Must provide either (old_text, new_text) or replacements list"
                }
            
            # Track results
            results = []
            total_replacements = 0
            new_content = content
            
            for r in replace_list:
                old = r.get("old", "")
                new = r.get("new", "")
                
                if old not in new_content:
                    results.append({
                        "old": old[:50] + "..." if len(old) > 50 else old,
                        "found": False
                    })
                    continue
                
                count = new_content.count(old)
                new_content = new_content.replace(old, new)
                total_replacements += count
                results.append({
                    "old": old[:50] + "..." if len(old) > 50 else old,
                    "found": True,
                    "count": count
                })
            
            if total_replacements == 0:
                return {
                    "success": False,
                    "error": "No replacements made - none of the target texts were found",
                    "details": results
                }
            
            # Write back
            with open(abs_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            self.files_modified.append(file_path)
            
            return {
                "success": True,
                "path": abs_path,
                "total_replacements": total_replacements,
                "details": results
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error replacing file content: {str(e)}"
            }
    
    def _search_files(
        self, 
        query: str = None,
        queries: List[str] = None,
        file_pattern: Optional[str] = None, 
        is_regex: bool = False,
        working_dir: str = "."
    ) -> Dict[str, Any]:
        """
        Search for text in files using grep. Supports multiple queries and regex.
        
        Args:
            query: Single search query
            queries: List of search queries (searches for any match)
            file_pattern: Optional file glob pattern (e.g., '*.py')
            is_regex: If True, treat queries as regex patterns
            working_dir: Directory to search in
        """
        try:
            abs_path = os.path.abspath(working_dir)
            
            # Build query list
            query_list = queries if queries else ([query] if query else [])
            if not query_list:
                return {
                    "success": False,
                    "error": "Must provide either 'query' or 'queries'"
                }
            
            all_matches = []
            
            for q in query_list:
                # Build grep command
                if is_regex:
                    cmd = ["grep", "-rn", "-E", "--color=never", q, abs_path]
                else:
                    cmd = ["grep", "-rn", "-F", "--color=never", q, abs_path]
                
                # Add file pattern if specified
                if file_pattern:
                    cmd.extend(["--include", file_pattern])
                
                # Exclude common directories
                excludes = [".git", "node_modules", "__pycache__", "venv", ".venv"]
                for exclude in excludes:
                    cmd.extend(["--exclude-dir", exclude])
                
                # Run grep
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    # Parse results
                    for line in result.stdout.strip().split('\n'):
                        if ':' in line:
                            parts = line.split(':', 2)
                            if len(parts) >= 3:
                                file_path = parts[0].replace(abs_path + '/', '')
                                line_num = parts[1]
                                content = parts[2]
                                all_matches.append({
                                    "query": q,
                                    "file": file_path,
                                    "line": line_num,
                                    "content": content[:200]  # Truncate long lines
                                })
            
            # Deduplicate by file+line
            seen = set()
            unique_matches = []
            for m in all_matches:
                key = (m["file"], m["line"])
                if key not in seen:
                    seen.add(key)
                    unique_matches.append(m)
            
            return {
                "success": True,
                "queries": query_list,
                "is_regex": is_regex,
                "matches": unique_matches[:50],  # Limit to 50 matches
                "total_matches": len(unique_matches)
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Search timed out (>10 seconds)"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error searching files: {str(e)}"
            }
    
    def _call_context_engine(self, question: str, working_dir: str = ".") -> Dict[str, Any]:
        """Call the context engine to answer questions about the codebase."""
        try:
            if self.context_engine is None:
                return {
                    "success": False,
                    "error": "Context engine not available"
                }
            
            abs_path = os.path.abspath(working_dir)
            
            # Call the context engine
            result = self.context_engine.get_context(question, abs_path)
            
            return {
                "success": True,
                "question": question,
                "answer": result
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error calling context engine: {str(e)}"
            }
    
    def _execute_tool(self, tool_name: str, arguments: Dict[str, Any], working_dir: str) -> Dict[str, Any]:
        """Execute a tool call and log it."""
        # Log the tool call
        tool_call_log = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "tool_name": tool_name,
            "arguments": arguments
        }
        
        # Execute the tool
        if tool_name == "read_file":
            file_path = os.path.join(working_dir, arguments["path"])
            result = self._read_file(
                file_path,
                arguments.get("start_line"),
                arguments.get("end_line")
            )
        elif tool_name == "write_file":
            file_path = os.path.join(working_dir, arguments["path"])
            result = self._write_file(file_path, arguments["content"])
        elif tool_name == "replace_file_content":
            file_path = os.path.join(working_dir, arguments["path"])
            result = self._replace_file_content(
                file_path,
                old_text=arguments.get("old_text"),
                new_text=arguments.get("new_text"),
                replacements=arguments.get("replacements")
            )
        elif tool_name == "search_files":
            result = self._search_files(
                query=arguments.get("query"),
                queries=arguments.get("queries"),
                file_pattern=arguments.get("file_pattern"),
                is_regex=arguments.get("is_regex", False),
                working_dir=working_dir
            )
        elif tool_name == "context_engine":
            result = self._call_context_engine(arguments["question"], working_dir)
        elif tool_name == "list_directory":
            dir_path = os.path.join(working_dir, arguments["path"])
            result = self._list_directory(dir_path)
        else:
            result = {"success": False, "error": f"Unknown tool: {tool_name}"}
        
        # Add result to log
        tool_call_log["result"] = result
        self.tool_history.append(tool_call_log)
        
        return result
    
    def execute_task(self, task: str, context_path: str = ".") -> str:
        """
        Execute a basic task using the sub-agent.
        
        Args:
            task: The task description in natural language
            context_path: Path to use as context (defaults to current directory)
        
        Returns:
            Formatted response from the sub-agent
        """
        abs_path = os.path.abspath(context_path)
        
        if not os.path.exists(abs_path):
            return f"Error: Context path {abs_path} does not exist."
        
        # Reset tracking
        self.files_modified = []
        self.files_read = []
        self.tool_history = []
        
        # Create log file for this execution
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        log_filename = f"subagent_{timestamp}.json"
        self.log_file_path = os.path.join(self.log_dir, log_filename)
        
        # Get file tree for context
        file_tree = self._get_file_tree(abs_path)
        
        # Build system prompt from template
        system_prompt = SUBAGENT_SYSTEM_PROMPT.format(
            working_directory=abs_path,
            file_tree=file_tree,
            task=task
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Please complete this task: {task}"}
        ]
        
        tools = TOOL_DEFINITIONS
        max_iterations = 15  # Increased to allow for more complex tasks
        iteration = 0
        execution_log = []
        
        while iteration < max_iterations:
            iteration += 1
            
            try:
                # Call the LLM with tools
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    temperature=0.1,
                    max_tokens=4000
                )
                
                assistant_message = response.choices[0].message
                
                # Check if there are tool calls
                if assistant_message.tool_calls:
                    # Add assistant message to conversation
                    messages.append({
                        "role": "assistant",
                        "content": assistant_message.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            }
                            for tc in assistant_message.tool_calls
                        ]
                    })
                    
                    # Execute each tool call
                    for tool_call in assistant_message.tool_calls:
                        tool_name = tool_call.function.name
                        arguments = json.loads(tool_call.function.arguments)
                        
                        # Execute the tool
                        result = self._execute_tool(tool_name, arguments, abs_path)
                        
                        # Add tool result to messages
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(result)
                        })
                else:
                    # No more tool calls, agent is done
                    final_message = assistant_message.content or "Done."
                    execution_log.append(final_message)
                    
                    # Ask for brief summary
                    messages.append({
                        "role": "assistant",
                        "content": final_message
                    })
                    messages.append({
                        "role": "user",
                        "content": "1-2 sentences: what did you do?"
                    })
                    
                    # Get final summary
                    final_response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=0.1,
                        max_tokens=1000
                    )
                    
                    final_summary = final_response.choices[0].message.content
                    execution_log.append(f"\n\n**Summary:** {final_summary}")
                    
                    break
                
            except Exception as e:
                execution_log.append(f"\n**Error:** {str(e)}\n")
                break
        
        if iteration >= max_iterations:
            execution_log.append(f"\n**Warning:** Reached maximum iterations ({max_iterations}). Task may be incomplete.\n")
        
        # Write tool history to log file
        log_data = {
            "task": task,
            "context_path": abs_path,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "model": self.model,
            "iterations": iteration,
            "tool_history": self.tool_history,
            "files_modified": self.files_modified,
            "files_read": self.files_read
        }
        
        try:
            with open(self.log_file_path, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            execution_log.append(f"\n**Warning:** Failed to write log file: {str(e)}\n")
        
        # Format concise response
        files_str = ", ".join(self.files_modified) if self.files_modified else "none"
        
        final_response = f"""{"".join(execution_log)}

**Modified:** {files_str}
**Log:** {self.log_file_path}"""
        
        return final_response
