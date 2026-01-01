# mcp_plus

A lightweight, open suite of MCP tools designed to enhance LLM capabilities.

---

## Overview

**mcp_plus** is a Model Context Protocol (MCP) server that extends AI agents with powerful, purpose-built tools for codebase understanding, task delegation, multi-agent coordination, and project management. Built to be **open** and **lightweight**, it runs as a single FastMCP server and integrates seamlessly with any MCP-compatible client.

---

## Tools

| Function | Description |
|----------|-------------|
| `context_engine` | Ask natural language questions about any codebase. Returns comprehensive analysis including file trees, relevant code snippets, and architectural insights. |
| `subagent` | Delegates basic tasks to a smaller, faster LLM that can read/write files autonomously. |
| `chatroom_send_message` | Post a message to a project's chatroom |
| `chatroom_read_messages` | Read recent messages from the chatroom |
| `todo_list` | View all todos for a project |
| `todo_update` | Add, complete, or remove todos |

### Context Engine
Fast context retrieval tool for codebases to enable llm's to learn about your codebase with speed and accuracy.

### Subagent
Small, fast LLM that can read/write files autonomously to delegate basic tasks to, allowing the main model to focus on higher-level and more complex tasks.

### Chatroom
Multi-agent coordination tool for codebases to enable llm's to work together on the same codebase with speed and accuracy.

### Todo 
Incase your cli/ide doesn't have one.

---

## Installation

### Prerequisites
- Python 3.8+
- OpenRouter API key

## Configuration

Add to your MCP client configuration:

```json
{
  "mcpServers": {
    "mcp_plus": {
      "command": "/path/to/mcp_plus/venv/bin/python",
      "args": ["/path/to/mcp_plus/mcp_server.py"],
      "env": {
        "OPENROUTER_API_KEY": "your_api_key_here",
        "MODEL_NAME": "google/gemini-2.5-flash-lite",  
        "SUBAGENT_MODEL": "moonshotai/kimi-k2-thinking" 
      }
    }
  }
}
```

Or run directly:

```bash
./run_server.sh
```

---

## License

MIT

---