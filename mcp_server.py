from fastmcp import FastMCP
from context_engine.context_engine import ContextEngine
from chatroom import ChatroomManager
from todo import TodoManager
from subagent import SubAgent
import os
import json
from dotenv import load_dotenv

load_dotenv()

# Initialize the MCP server
mcp = FastMCP("MCP-plus")

# Initialize the chatroom manager with an absolute path
# Store chatrooms in MCP's standard data directory
mcp_data_dir = os.path.expanduser("~/.mcp/context_mcp")
chatrooms_dir = os.path.join(mcp_data_dir, "chatrooms")
os.makedirs(chatrooms_dir, exist_ok=True)  # Ensure the directory exists
chatroom_manager = ChatroomManager(chatrooms_dir=chatrooms_dir)

# Initialize the todo manager
todos_dir = os.path.join(mcp_data_dir, "todos")
os.makedirs(todos_dir, exist_ok=True)
todo_manager = TodoManager(todos_dir=todos_dir)

@mcp.tool()
def context_engine(question: str, path: str = ".") -> str:
    """
    The **best** tool for getting comprehensive codebase context and searching for specific files, code, or anything else in the codebase.

    **Core Principles:**
    - Ask focused questions for best results
    - Use for understanding, not for making changes
    - Trust the analysis 
    - Use over specific search tools if you do not know exact location or names of files.
    
    **When to Use:**
    - When starting out with a new codebase
    - Understanding how features work across multiple files
    - Finding where specific functionality is implemented
    - Architectural questions spanning multiple modules
    - Debugging by tracing code flow
    - When looking for a specific thing in the codebase without know the exact location of the file
    
    Examples:
        context_engine(question="How does user authentication work?", path="/project")
        context_engine(question="Where is the database connection configured?")
        context_engine(question="Explain the API endpoint structure")
    
    Args:
        question: The information you want to know in natural language
        path: Path to the codebase (defaults to current directory)
    
    Returns:
        Comprehensive markdown-formatted analysis with relevant code snippets
    """
    agent = ContextEngine()
    abs_path = os.path.abspath(path)
    
    if not os.path.exists(abs_path):
        return f"Error: Path {abs_path} does not exist."
    
    try:
        result = agent.get_codebase_context(question, abs_path)
        return result
    except Exception as e:
        import traceback
        return f"Error during analysis:\n{str(e)}\n\n{traceback.format_exc()}"

@mcp.tool()
def chatroom_send_message(project_path: str, agent_name: str, message: str) -> str:
    """
    Send a message to a project's chatroom for multi-agent coordination.
    
    Each project directory has its own chatroom where agents can communicate,
    coordinate tasks, and share updates. Messages are persisted to disk and
    survive server restarts.
    
    **Core Principles:**
    - Choose a unique and persistent agent name (e.g., "CodeWeaver", "ArchitectBot")
    - Timestamps are added automatically - don't include them in your message
    - Keep messages concise and actionable
    - Include relevant details: what you're doing, which files, and your scope
    - Announce before starting significant work to prevent conflicts
    - Update when completing work so others know areas are free
    
    **When to Use:**
    - Starting work on a shared codebase with other agents
    - Completing a significant piece of work others should know about
    - Claiming ownership of a file or module temporarily
    - Asking for help or input from other agents
    - Warning about breaking changes or refactors in progress
    
    **When NOT to Use:**
    - Working alone on a project (no other agents involved)
    - Trivial changes that don't affect others
    - Every small step (only major milestones)
    
    Examples:
        chatroom_send_message(
            project_path="/project",
            agent_name="RefactorNinja",
            message="Starting auth module refactor. Will update UserService and LoginController."
        )
        chatroom_send_message(
            project_path="/project",
            agent_name="DocBot",
            message="Finished API docs. Ready for review in /docs/api.md"
        )
    
    Args:
        project_path: Absolute path to the project directory
        agent_name: Your creative agent name (choose something memorable!)
        message: What you're working on or updates to share
    
    Returns:
        JSON with your new message and recent context (last 4 messages from past 30 min)
    """
    abs_path = os.path.abspath(project_path)
    
    if not os.path.exists(abs_path):
        return f"Error: Project path {abs_path} does not exist."
    
    try:
        result = chatroom_manager.send_message(abs_path, agent_name, message)
        # Format the response to show both the new message and recent context
        response = {
            "status": "Message sent successfully",
            "your_message": result["new_message"],
            "recent_context": result["recent_messages"]
        }
        return json.dumps(response, indent=2)
    except Exception as e:
        import traceback
        return f"Error sending message:\n{str(e)}\n\n{traceback.format_exc()}"

@mcp.tool()
def chatroom_read_messages(project_path: str, limit: int = 50) -> str:
    """
    Read recent messages from a project's chatroom.
    
    Check this regularly (every few turns) to stay coordinated with other agents
    and avoid duplicate work. Messages are shown in chronological order.
    
    Examples:
        chatroom_read_messages(project_path="/project")  # Get last 50 messages
        chatroom_read_messages(project_path="/project", limit=10)  # Just recent ones
    
    Args:
        project_path: Absolute path to the project directory
        limit: Maximum number of recent messages to return (default: 50)
    
    Returns:
        Formatted list of messages with timestamps and sender names
    """
    abs_path = os.path.abspath(project_path)
    
    if not os.path.exists(abs_path):
        return f"Error: Project path {abs_path} does not exist."
    
    try:
        messages = chatroom_manager.read_messages(abs_path, limit)
        return chatroom_manager.format_messages(messages)
    except Exception as e:
        import traceback
        return f"Error reading chatroom:\n{str(e)}\n\n{traceback.format_exc()}"

@mcp.tool()
def subagent(task: str, context_path: str = ".") -> str:
    """
    Delegate a task to a fast sub-agent with file read/write capabilities.
    
    The sub-agent uses a smaller, faster LLM optimized for file operations.
    It can autonomously plan and execute multi-step tasks.
    
    Best for:
    - Simple file modifications and insignificant refactoring
    - Creating boilerplate files
    - Search and replace across files
    - Code review and analysis
    - Reading/summarizing multiple files

    **Core Principles:**
    - Include important contextual details and specific instructions for the subagent
    
    **When NOT to use:**
    - The task requires reasoning or planning
    - The task requires access to external APIs or services
    - The task requires access running shell commands
    - The task requires touching possible sensitive files
    - The task is the main task
    - The details of how the task is implemented should be known
    
    Sub-agent tools:
    - read_file (with optional line ranges)
    - write_file
    - replace_file_content (supports multiple replacements)
    - search_files (supports multiple queries, regex)
    - context_engine (for deep codebase questions)
    - list_directory
    
    Examples:
        subagent(
            task="Add error handling to all API endpoints in src/api/",
            context_path="/project"
        )
        subagent(
            task="Create a README.md with project overview, installation, and usage sections"
        )
        subagent(
            task="Find all TODO comments and list them with file locations"
        )
    
    Args:
        task: Natural language description with all relevant context
        context_path: Working directory for the sub-agent (defaults to current)
    
    Returns:
        Summary of what the sub-agent did and files modified
    """
    try:
        # Initialize context engine for the subagent
        context_engine_instance = ContextEngine()
        agent = SubAgent(context_engine=context_engine_instance)
        result = agent.execute_task(task, context_path)
        return result
    except Exception as e:
        import traceback
        return f"Error executing sub-agent task:\n{str(e)}\n\n{traceback.format_exc()}"

@mcp.tool()
def todo(project_path: str, tasks: str = "", remove: str = "") -> str:
    """
    Use this tool to create and manage a structured task list for your current coding session. This helps you track progress, organize complex tasks, and demonstrate thoroughness to the user.
It also helps the user understand the progress of the task and overall progress of their requests.

## When to Use This Tool
Use this tool proactively in these scenarios:

1. Complex multistep tasks - When a task requires 3 or more distinct steps or actions
2. Non-trivial and complex tasks - Tasks that require careful planning or multiple operations
3. User explicitly requests todo list - When the user directly asks you to use the todo list
4. User provides multiple tasks - When users provide a list of things to be done (numbered or comma-separated)
5. After receiving new instructions - Immediately capture user requirements as todos. Feel free to edit the todo list based on new information.
6. After completing a task - Mark it complete and add any new follow-up tasks
7. When you start working on a new task, mark the todo as in_progress. Ideally you should only have one todo as in_progress at a time. Complete existing tasks before starting new ones.

## When NOT to Use This Tool

Skip using this tool when:
1. There is only a single, straightforward task
2. The task is trivial and tracking it provides no organizational benefit
3. The task can be completed in less than 3 trivial steps
4. The task is purely conversational or informational

NOTE that you should not use this tool if there is only one trivial task to do. In this case you are better off just doing the task directly.


**Format:** `[id][status] task_content`

**IDs:** Use decimals for subtasks: 1, 2, 2.1, 2.1.1, 3
- Break complex tasks into subtasks (e.g., 2 → 2.1, 2.2)

**Status Markers:**
- `[ ]` pending (new task)
- `[~]` in progress (actively working)
- `[x]` completed (done)

**Behavior:**
- New ID → adds task
- Existing ID → updates status
- Tasks are auto-sorted by ID
- Returns full task list after every update

**Examples:**
    # Add tasks
    todo(project_path="/project", tasks=\"\"\"
    [1][ ] Set up project structure
    [2][ ] Implement authentication
    [3][ ] Write tests
    \"\"\")
    
    # Update status and add subtasks
    todo(project_path="/project", tasks=\"\"\"
    [1][x] Set up project structure
    [2][~] Implement authentication
    [2.1][ ] Create login endpoint
    [2.2][ ] Add JWT tokens
    \"\"\")
    
    # Remove tasks
    todo(project_path="/project", remove="2.1, 2.2")
    
    # View current tasks (no arguments)
    todo(project_path="/project")

**Best Practices:**
- Only mark completed when fully done
- Use subtasks when a task becomes complex
- Keep task descriptions concise but clear
- Mark as in_progress [~] when actively working

Never show todo's in the raw `[id][status] task_content` format to the user. Use proper markdown formatting instead.

Args:
    project_path: Absolute path to the project directory
    tasks: Task lines in format [id][status] content (one per line)
    remove: Comma-separated IDs to remove (e.g., "2.1, 2.2, 3")

Returns:
    Full task list (always returned after any operation)
    """
    abs_path = os.path.abspath(project_path)
    if not os.path.exists(abs_path):
        return f"Error: Path {abs_path} does not exist."
    
    # Handle remove
    if remove:
        task_ids = [tid.strip() for tid in remove.split(',') if tid.strip()]
        return todo_manager.remove_tasks(abs_path, task_ids)
    
    # Handle add/update
    if tasks and tasks.strip():
        return todo_manager.update_tasks(abs_path, tasks)
    
    # Just list
    todos = todo_manager.list_todos(abs_path)
    return todo_manager.format_todos(todos)


if __name__ == "__main__":
    mcp.run()
