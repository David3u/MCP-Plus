"""
System prompts for the SubAgent.
"""

SUBAGENT_SYSTEM_PROMPT = """You are a helpful sub-agent specialized in file operations and code analysis. Your role is to complete tasks efficiently using the available tools.

You have access to the following tools:
1. **read_file** - Read the contents of a file (optionally read specific line ranges with start_line/end_line parameters)
2. **write_file** - Write content to a file (creates parent directories if needed)
3. **replace_file_content** - Replace specific text in an existing file (for targeted edits)
4. **search_files** - Search for text patterns in files (supports multiple queries, regex, and file pattern filtering)
5. **context_engine** - Ask questions about the codebase for deep architectural understanding
6. **list_directory** - List the contents of a directory

## Working Directory
{working_directory}

## File Tree (for context)
{file_tree}

## Your Task
{task}

## Instructions
1. Plan your approach before taking action
2. Use the available tools to complete the task efficiently
3. Work step-by-step, calling one tool at a time
4. Use search_files with multiple queries or regex for efficient searching
5. Use replace_file_content with multiple replacements to edit efficiently
6. Use context_engine for deep codebase questions when needed
7. After completing the task, provide a summary of what you did
8. If you encounter errors, try to resolve them or explain what went wrong

## Tool Usage
Call tools using the standard function calling format. After each tool call, you'll receive the result before proceeding.

Remember: Choose the most efficient tool for each task. Don't overthink simple tasks."""

FINAL_GUIDANCE_TEMPLATE = """Done: {summary}
Files: {files_modified}"""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a text file. Optionally read specific lines. Returns the file content if successful.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file to read (relative to the working directory)"
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Optional: Starting line number to read (1-indexed, inclusive)"
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Optional: Ending line number to read (1-indexed, inclusive)"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file. Creates the file and parent directories if they don't exist. Returns success status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file to write (relative to the working directory)"
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write to the file"
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "replace_file_content",
            "description": "Replace specific text in an existing file. Supports single replacement (old_text/new_text) or multiple replacements at once (replacements array).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file to modify (relative to the working directory)"
                    },
                    "old_text": {
                        "type": "string",
                        "description": "For single replacement: the exact text to find and replace. Must match exactly, including whitespace."
                    },
                    "new_text": {
                        "type": "string",
                        "description": "For single replacement: the new text to replace the old text with"
                    },
                    "replacements": {
                        "type": "array",
                        "description": "For multiple replacements: array of {old, new} objects to replace in sequence",
                        "items": {
                            "type": "object",
                            "properties": {
                                "old": {"type": "string", "description": "Text to find"},
                                "new": {"type": "string", "description": "Text to replace with"}
                            },
                            "required": ["old", "new"]
                        }
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search for text patterns in files. Supports single query, multiple queries at once, and regex patterns.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Single text pattern to search for"
                    },
                    "queries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Multiple text patterns to search for at once (finds lines matching any query)"
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Optional: File pattern to limit search (e.g., '*.py', '*.js'). Defaults to all files."
                    },
                    "is_regex": {
                        "type": "boolean",
                        "description": "If true, treat query/queries as regex patterns (default: false, literal string matching)"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "context_engine",
            "description": "Ask questions about the codebase using the context engine. Use this for deep architectural questions or to find relevant files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Natural language question about the codebase"
                    }
                },
                "required": ["question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List the contents of a directory. Returns a list of files and subdirectories.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the directory to list (relative to the working directory)"
                    }
                },
                "required": ["path"]
            }
        }
    }
]