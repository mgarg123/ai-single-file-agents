import os
import sys
import json
import re
import inspect
import subprocess
from rich.console import Console
from rich.table import Table
from rich import box
from rich.text import Text
from rich.panel import Panel
from groq import Groq

from dotenv import load_dotenv

load_dotenv()

console = Console()
groq_api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=groq_api_key)

TOOL_REGISTRY = {}

def tool(func):
    """Decorator to register a function as a tool with its docstring and signature."""
    TOOL_REGISTRY[func.__name__] = {
        "function": func,
        "doc": inspect.getdoc(func),
        "signature": str(inspect.signature(func))
    }
    return func

def _run_git_command(command_args: list, cwd: str = None, input_data: str = None):
    """Helper function to run git commands and capture output.
    Returns:
        Tuple[str, str, int]: (user_facing_message, raw_git_output, return_code)
    """
    try:
        process = subprocess.run(
            ["git"] + command_args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False, # Do not raise CalledProcessError automatically
            input=input_data
        )
        
        raw_output = process.stdout.strip()
        error_output = process.stderr.strip()

        if process.returncode != 0:
            if "not a git repository" in error_output.lower():
                return "[red]Error: Not a Git repository. Please initialize one first.[/]", raw_output, process.returncode
            return f"[red]Git Error: {error_output}[/]", raw_output, process.returncode
        
        return "[green]Git command executed successfully.[/]", raw_output, process.returncode
    except FileNotFoundError:
        return "[red]Error: Git command not found. Please ensure Git is installed and in your PATH.[/]", "", 127
    except Exception as e:
        return f"[red]An unexpected error occurred while running Git command: {str(e)}[/]", "", 1

# ==== TOOL FUNCTIONS ====

@tool
def git_status():
    """Show the working tree status, including staged, unstaged, and untracked files, and branch information.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git status output.
    """
    # Use --porcelain to get machine-readable output for parsing
    summary_msg, output, returncode = _run_git_command(["status", "--porcelain"])

    if returncode != 0:
        console.print(Panel(f"[red]Error getting Git status:[/]\n{summary_msg}", title="[bold red]Git Status Error[/]", border_style="red"))
        return summary_msg, output

    staged_changes = []
    unstaged_changes = []
    untracked_files_list = []

    for line in output.splitlines():
        if len(line) < 3: # Skip malformed lines
            continue
        
        index_status = line[0]
        worktree_status = line[1]
        filepath = line[3:].strip()

        # Files staged for commit (X is not ' ' or '?')
        if index_status != ' ' and index_status != '?':
            staged_changes.append(filepath)
        
        # Files with changes not staged for commit (Y is not ' ' or '?')
        # This includes files that are both staged and unstaged (e.g., 'MM')
        if worktree_status != ' ' and worktree_status != '?':
            unstaged_changes.append(filepath)
        
        # Untracked files (X and Y are '??')
        if index_status == '?' and worktree_status == '?':
            untracked_files_list.append(filepath)

    # Ensure unique entries and sort for consistent display
    staged_changes = sorted(list(set(staged_changes)))
    unstaged_changes = sorted(list(set(unstaged_changes)))
    untracked_files_list = sorted(list(set(untracked_files_list)))

    output_panels = []
    llm_summary_parts = []

    if staged_changes:
        table = Table(title="[bold green]Staged Changes (Ready for Commit)[/]", box=box.ROUNDED)
        table.add_column("File", style="green", justify="left")
        for f in staged_changes:
            table.add_row(f)
        output_panels.append(table)
        llm_summary_parts.append(f"{len(staged_changes)} files staged")

    if unstaged_changes:
        table = Table(title="[bold yellow]Changes Not Staged for Commit[/]", box=box.ROUNDED)
        table.add_column("File", style="yellow", justify="left")
        for f in unstaged_changes:
            table.add_row(f)
        output_panels.append(table)
        llm_summary_parts.append(f"{len(unstaged_changes)} files with unstaged changes")

    if untracked_files_list:
        table = Table(title="[bold red]Untracked Files[/]", box=box.ROUNDED)
        table.add_column("File", style="red", justify="left")
        for f in untracked_files_list:
            table.add_row(f)
        output_panels.append(table)
        llm_summary_parts.append(f"{len(untracked_files_list)} untracked files")

    # Suggested Commands
    suggested_commands = []
    if staged_changes:
        suggested_commands.append("[green]To finalize these changes:[/green] `git commit -m \"Your descriptive message\"`")
    if unstaged_changes:
        suggested_commands.append("[yellow]To prepare these changes for commit:[/yellow] `git add .` or `git add <filename>`")
        suggested_commands.append("[yellow]To discard these unstaged changes:[/yellow] `git restore .` or `git restore <filename>`")
    if untracked_files_list:
        suggested_commands.append("[red]To start tracking these files:[/red] `git add .` or `git add <filename>`")
        suggested_commands.append("[red]To permanently remove untracked files:[/red] `git clean -fd` (use with caution!)")

    if suggested_commands:
        # Use Text.from_markup to explicitly parse the rich markup
        commands_text = Text.from_markup("\n".join(suggested_commands))
        output_panels.append(Panel(commands_text, title="[bold cyan]Suggested Next Steps[/]", border_style="cyan"))

    if not output_panels:
        console.print(Panel("[green]No changes detected. Working tree is clean.[/]", title="[bold blue]Git Status[/]", border_style="green"))
        return "Git status: No changes detected. Working tree is clean.", output
    else:
        # Get current branch info for a more complete status
        branch_info_summary, branch_output, branch_returncode = _run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])
        current_branch = branch_output if branch_returncode == 0 else "unknown branch"
        
        console.print(Panel(f"[bold]On branch:[/bold] [blue]{current_branch}[/]", title="[bold blue]Git Status Summary[/]", border_style="blue"))
        for panel in output_panels:
            console.print(panel)
        
        llm_summary = "Git status displayed. " + ", ".join(llm_summary_parts) + f" (on branch: {current_branch}). See console for details."
        return llm_summary, output

@tool
def git_add(files: str = '.'):
    """Add file contents to the index (stage files).
    Args:
        files (str, optional): Files or directories to add. Use '.' for all changes. Defaults to ".".
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git add output.
    """
    summary_msg, output, returncode = _run_git_command(["add", files])
    
    if returncode == 0:
        message = f"[green]Successfully staged: '{files}'[/]"
        console.print(Panel(message, title="[bold green]Git Add[/]", border_style="green"))
        return f"Files '{files}' staged successfully.", output
    else:
        console.print(Panel(f"[red]Error staging files:[/]\n{summary_msg}", title="[bold red]Git Add Error[/]", border_style="red"))
        return summary_msg, output

@tool
def git_commit(message: str):
    """Record changes to the repository.
    Args:
        message (str): The commit message.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git commit output.
    """
    if not message:
        error_msg = "[red]Error: Commit message cannot be empty.[/]"
        console.print(Panel(error_msg, title="[bold red]Git Commit Error[/]", border_style="red"))
        return error_msg, None

    summary_msg, output, returncode = _run_git_command(["commit", "-m", message])
    
    if returncode == 0:
        commit_hash_match = re.search(r'\[(\w+)\s', output)
        commit_hash = commit_hash_match.group(1) if commit_hash_match else "unknown"
        
        message = f"[green]Changes committed successfully![/]\n[bold]Commit:[/bold] [cyan]{commit_hash}[/]\n[bold]Message:[/bold] '{message}'"
        console.print(Panel(message, title="[bold green]Git Commit[/]", border_style="green"))
        return f"Committed changes with message: '{message}' (Hash: {commit_hash})", output
    else:
        console.print(Panel(f"[red]Error committing changes:[/]\n{summary_msg}", title="[bold red]Git Commit Error[/]", border_style="red"))
        return summary_msg, output

@tool
def git_revert_last_commit():
    """Undo the changes introduced by the last commit, creating a new commit that reverts them.
    Prompts for user confirmation.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git revert output.
    """
    console.print(Panel("[yellow]Are you sure you want to revert the last commit? This will create a new commit that undoes the changes. (y/n)[/]", title="[bold yellow]Confirm Revert[/]", border_style="yellow"))
    response = input().strip().lower()
    if response != "y":
        cancel_msg = "[yellow]Revert cancelled by user.[/]"
        console.print(Panel(cancel_msg, title="[bold yellow]Git Revert[/]", border_style="yellow"))
        return cancel_msg, None
    
    summary_msg, output, returncode = _run_git_command(["revert", "HEAD", "--no-edit"])
    
    if returncode == 0:
        message = "[green]Last commit successfully reverted. A new commit has been created.[/]"
        console.print(Panel(message, title="[bold green]Git Revert[/]", border_style="green"))
        return "Last commit reverted successfully.", output
    else:
        console.print(Panel(f"[red]Error reverting last commit:[/]\n{summary_msg}", title="[bold red]Git Revert Error[/]", border_style="red"))
        return summary_msg, output

@tool
def git_create_branch(branch_name: str, base_branch: str = None):
    """Create a new branch.
    Args:
        branch_name (str): The name of the new branch.
        base_branch (str, optional): The branch to base the new branch on. If None, uses current branch. Defaults to None.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git branch output.
    """
    if not branch_name:
        error_msg = "[red]Error: Branch name cannot be empty.[/]"
        console.print(Panel(error_msg, title="[bold red]Git Branch Error[/]", border_style="red"))
        return error_msg, None
    
    command_args = ["branch", branch_name]
    if base_branch:
        command_args.append(base_branch)
    
    summary_msg, output, returncode = _run_git_command(command_args)
    
    if returncode == 0:
        message = f"[green]Branch '[cyan]{branch_name}[/]' created successfully."
        if base_branch:
            message += f" (based on '[blue]{base_branch}[/]').[/]"
        else:
            message += f" (based on current branch).[/]"
        console.print(Panel(message, title="[bold green]Git Create Branch[/]", border_style="green"))
        return f"Branch '{branch_name}' created successfully.", output
    else:
        console.print(Panel(f"[red]Error creating branch '{branch_name}':[/]\n{summary_msg}", title="[bold red]Git Branch Error[/]", border_style="red"))
        return summary_msg, output

@tool
def git_fetch():
    """Download objects and refs from another repository.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git fetch output.
    """
    summary_msg, output, returncode = _run_git_command(["fetch"])
    
    if returncode == 0:
        message = "[green]Successfully fetched latest changes from remote repositories.[/]"
        console.print(Panel(message, title="[bold green]Git Fetch[/]", border_style="green"))
        return "Fetched latest changes.", output
    else:
        console.print(Panel(f"[red]Error fetching changes:[/]\n{summary_msg}", title="[bold red]Git Fetch Error[/]", border_style="red"))
        return summary_msg, output

@tool
def git_pull(branch: str = 'main', remote: str = 'origin'):
    """Fetch from and integrate with another repository or a local branch.
    Args:
        branch (str, optional): The branch to pull. Defaults to 'main'.
        remote (str, optional): The remote repository to pull from. Defaults to 'origin'.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git pull output.
    """
    summary_msg, output, returncode = _run_git_command(["pull", remote, branch])
    
    if returncode == 0:
        message = f"[green]Successfully pulled changes from '[blue]{remote}/{branch}[/]'."
        if "Already up to date." in output:
            message += "\n[yellow]Repository is already up to date.[/]"
        console.print(Panel(message, title="[bold green]Git Pull[/]", border_style="green"))
        return f"Pulled changes from {remote}/{branch}.", output
    else:
        console.print(Panel(f"[red]Error pulling changes from '{remote}/{branch}':[/]\n{summary_msg}", title="[bold red]Git Pull Error[/]", border_style="red"))
        return summary_msg, output

@tool
def git_push(branch: str = 'main', remote: str = 'origin'):
    """Update remote refs along with associated objects.
    Args:
        branch (str, optional): The branch to push. Defaults to 'main'.
        remote (str, optional): The remote repository to push to. Defaults to 'origin'.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git push output.
    """
    summary_msg, output, returncode = _run_git_command(["push", remote, branch])
    
    if returncode == 0:
        message = f"[green]Successfully pushed changes to '[blue]{remote}/{branch}[/]'."
        console.print(Panel(message, title="[bold green]Git Push[/]", border_style="green"))
        return f"Pushed changes to {remote}/{branch}.", output
    else:
        console.print(Panel(f"[red]Error pushing changes to '{remote}/{branch}':[/]\n{summary_msg}", title="[bold red]Git Push Error[/]", border_style="red"))
        return summary_msg, output

@tool
def git_init():
    """Create an empty Git repository or reinitialize an existing one.
    Prompts for user confirmation if a .git directory already exists.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git init output.
    """
    if os.path.isdir(".git"):
        console.print(Panel("[yellow]A Git repository already exists in the current directory. Reinitialize? (y/n)[/]", title="[bold yellow]Confirm Git Init[/]", border_style="yellow"))
        response = input().strip().lower()
        if response != "y":
            cancel_msg = "[yellow]Git initialization cancelled by user.[/]"
            console.print(Panel(cancel_msg, title="[bold yellow]Git Init[/]", border_style="yellow"))
            return cancel_msg, None
    
    summary_msg, output, returncode = _run_git_command(["init"])
    
    if returncode == 0:
        message = "[green]Git repository initialized successfully in the current directory.[/]"
        console.print(Panel(message, title="[bold green]Git Init[/]", border_style="green"))
        return "Git repository initialized.", output
    else:
        console.print(Panel(f"[red]Error initializing Git repository:[/]\n{summary_msg}", title="[bold red]Git Init Error[/]", border_style="red"))
        return summary_msg, output

@tool
def git_log(num_commits: int = 5):
    """Show recent commit logs in a readable table format.
    Args:
        num_commits (int, optional): The number of recent commits to show. Defaults to 5.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git log output.
    """
    summary_msg, output, returncode = _run_git_command(["log", f"-n{num_commits}", "--pretty=format:%h|%an|%ad|%s", "--date=short"])

    if returncode != 0:
        console.print(Panel(f"[red]Error getting Git log:[/]\n{summary_msg}", title="[bold red]Git Log Error[/]", border_style="red"))
        return summary_msg, output

    table = Table(title=f"[bold blue]Last {num_commits} Commits[/]", box=box.ROUNDED)
    table.add_column("Hash", style="cyan", justify="left")
    table.add_column("Author", style="magenta", justify="left")
    table.add_column("Date", style="green", justify="left")
    table.add_column("Message", style="white", justify="left")

    if not output:
        console.print(Panel("[yellow]No commits found in this repository.[/]", title="[bold blue]Git Log[/]", border_style="yellow"))
        return "No commits found.", output

    for line in output.splitlines():
        parts = line.split('|', 3) # Split into 4 parts: hash, author, date, message
        if len(parts) == 4:
            table.add_row(parts[0], parts[1], parts[2], parts[3])
    
    console.print(table)
    return f"Displayed last {num_commits} commits. See console for details.", output

@tool
def git_checkout(branch_name: str):
    """Switch branches or restore working tree files.
    Args:
        branch_name (str): The name of the branch to checkout.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git checkout output.
    """
    if not branch_name:
        error_msg = "[red]Error: Branch name cannot be empty.[/]"
        console.print(Panel(error_msg, title="[bold red]Git Checkout Error[/]", border_style="red"))
        return error_msg, None
    
    summary_msg, output, returncode = _run_git_command(["checkout", branch_name])
    
    if returncode == 0:
        message = f"[green]Successfully switched to branch '[cyan]{branch_name}[/]'."
        console.print(Panel(message, title="[bold green]Git Checkout[/]", border_style="green"))
        return f"Switched to branch '{branch_name}'.", output
    else:
        console.print(Panel(f"[red]Error checking out to branch '{branch_name}':[/]\n{summary_msg}", title="[bold red]Git Checkout Error[/]", border_style="red"))
        return summary_msg, output

def generate_tools_doc():
    tool_docs = []
    for name, info in TOOL_REGISTRY.items():
        doc = info["doc"] or "No description."
        sig = info["signature"]
        tool_docs.append(f"- {name}{sig}: {doc}")
    return "Available tools:\n" + "\n".join(tool_docs)

def print_available_tools():
    console.rule("[bold green]🛠️ Available Git Tools")
    tools_doc = generate_tools_doc()
    
    table = Table(
        show_header=True,
        header_style="bold cyan",
        box=box.SQUARE
    )
    table.add_column("Tool", style="bold", overflow="fold", no_wrap=True)
    table.add_column("Description", style="")
    
    for line in tools_doc.splitlines():
        if line.strip().startswith("- "):
            try:
                name_sig, desc = line[2:].split(":", 1)
                table.add_row(name_sig.strip(), desc.strip())
                table.add_row("", "", end_section=True)
            except ValueError:
                continue
    
    console.print(table)

AVAILABLE_TOOLS = generate_tools_doc()

# === LLM Decision ===
TOOLS_DOC = f"""
You are an AI agent that chooses tools to execute based on a user's command, handling both single-step and multi-step tasks to achieve a final solution. Your primary function is to interact with a Git repository.

Below is the list of Available tools from which you need to select one which is relevant:
{AVAILABLE_TOOLS}

<instructions>
<instruction>
Respond with a JSON object containing:
- "tool": The tool to execute (or "done" if the task is complete)
- "args": The arguments for the tool (if applicable)
- "done": A boolean indicating if the task is complete
</instruction>

<instruction>
Parse FULL command and identify ALL operations separated by "then", "and then", "after", "next"
Count total operations in original command before starting execution
Execute operations sequentially: Operation 1 → Operation 2 → Operation 3 → done
Set "done": true ONLY after executing ALL operations from original command
</instruction>

<instruction>
Before each response, count: completed operations vs total operations in original command
If completed < total, continue to NEXT unfinished operation
Never stop until ALL operations from original command are executed
Track progress using conversation history, not hardcoded sequences
</instruction>

<instruction>
Choose appropriate validation tools from the above list before or after performing the operations to validate according to the need.
For example, after creating a branch, you might want to check out to it.
If validation is not required for the given operation then don't do the validation.
</instruction>

<instruction>
Handle errors gracefully:
- If a Git command fails (e.g., 'not a git repository', 'branch already exists'), treat as a non-critical failure and continue to the next step unless it's critical for subsequent steps.
- If a tool prompts for user confirmation and the user cancels (e.g., 'Revert cancelled'), treat as a non-critical failure and proceed to the next operation in multi-step tasks.
- Never repeat successful operations.
- If command unclear, return {{"tool": "done", "args": {{}}, "done": true}}
</instruction>
</instructions>

<examples>
<example>
Command: "show git status"
Total operations: 1
Step 1: {{"tool": "git_status", "args": {{}}, "done": true}}
</example>

<example>
Command: "add all files then commit with message 'Initial commit'"
Total operations: 2
Step 1: {{"tool": "git_add", "args": {{"files": "."}}, "done": false}}
Step 2: {{"tool": "git_commit", "args": {{"message": "Initial commit"}}, "done": true}}
</example>

<example>
Command: "create a new feature branch named 'my-feature'"
Total operations: 1
Step 1: {{"tool": "git_create_branch", "args": {{"branch_name": "my-feature"}}, "done": true}}
</example>

<example>
Command: "fetch latest changes then pull from origin main"
Total operations: 2
Step 1: {{"tool": "git_fetch", "args": {{}}, "done": false}}
Step 2: {{"tool": "git_pull", "args": {{"branch": "main", "remote": "origin"}}, "done": true}}
</example>

<example>
Command: "initialize a new git repository"
Total operations: 1
Step 1: {{"tool": "git_init", "args": {{}}, "done": true}}
</example>

<example>
Command: "show last 3 commits"
Total operations: 1
Step 1: {{"tool": "git_log", "args": {{"num_commits": 3}}, "done": true}}
</example>

<example>
Command: "checkout to develop branch"
Total operations: 1
Step 1: {{"tool": "git_checkout", "args": {{"branch_name": "develop"}}, "done": true}}
</example>
</examples>

Return ONLY valid JSON. No markdown, explanations, or extra text.
"""

def choose_tool(natural_language_input, conversation_history=None):
    if conversation_history is None:
        conversation_history = []
    
    current_dir = os.getcwd()
    system_content = (
        f"You are a tool-choosing assistant operating within a Git repository context.\n"
        f"Your current working directory is: {current_dir}\n\n"
        f"{TOOLS_DOC}\n"
        f"Analyze the user's command to determine if it is a single-step or multi-step task.\n"
        f"For single-step tasks, execute the tool and set done to true.\n"
        f"For multi-step tasks, execute tools sequentially and set done to true only in the final step.\n"
        f"Match command keywords to tools (e.g., 'status' for git_status, 'commit' for git_commit, 'create branch' for git_create_branch).\n"
        f"Use conversation history to track progress and avoid repeating actions unnecessarily.\n"
        f"Respond ONLY with a valid JSON object."
    )
    
    messages = [
        {"role": "system", "content": system_content},
        *conversation_history,
        {"role": "user", "content": f"User's request: {natural_language_input}"}
    ]
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile", # Using a capable model for complex parsing
        messages=messages
    )
    
    raw_output = response.choices[0].message.content.strip()
    
    console.print(f"[yellow]LLM raw output:[/] {raw_output}")
    
    try:
        match = re.search(r'\{(?:[^{}]|\{[^{}]*\})*\}', raw_output)
        if not match:
            console.print("[red]No valid JSON found in LLM response.[/]")
            messages.append({"role": "assistant", "content": "Invalid response. Please clarify your command."})
            return (
                "done",
                {},
                True,
                messages
            )
        
        json_str = match.group(0)
        parsed = json.loads(json_str)
        
        if "tool" not in parsed or "done" not in parsed:
            console.print("[red]Invalid JSON structure: Missing 'tool' or 'done' fields.[/]")
            messages.append({"role": "assistant", "content": "Invalid tool response. Please clarify your command."})
            return (
                "done",
                {},
                True,
                messages
            )
        
        return (
            parsed["tool"],
            parsed.get("args", {}),
            parsed.get("done", False),
            messages + [{"role": "assistant", "content": json_str}]
        )
    
    except json.JSONDecodeError as e:
        console.print(f"[red]Error parsing JSON from LLM response:[/] {str(e)}")
        console.print(f"[red]Raw output:[/] {raw_output}")
        messages.append({"role": "assistant", "content": "Error processing command. Please try again with a clearer instruction."})
        return (
            "done",
            {},
            True,
            messages
        )

# ==== CLI ====

def main():
    console.rule("[bold blue]🔧 AI Git Agent (Natural Language CLI)")

    if len(sys.argv) < 2:
        console.print("[yellow]Usage:[/] uv run git_agent/git_agent.py 'your command here'")
        return

    user_input = " ".join(sys.argv[1:])

    if user_input.lower() == "list-tools":
        print_available_tools()
        return
    
    conversation_history = []
    max_iterations = 10 # Limit iterations to prevent infinite loops
    
    # Simple operation counter for multi-step tasks
    # This is a heuristic; a more robust solution would involve LLM tracking
    total_operations = len(re.split(r'\s(?:then|and then|after|next)\s', user_input.lower()))
    completed_operations = 0

    for i in range(max_iterations):
        tool, args, done, history = choose_tool(user_input, conversation_history)
        conversation_history = history # Update history with LLM's response

        if tool == "done":
            console.print("[green]Task completed.[/]")
            break
        
        if tool not in TOOL_REGISTRY:
            console.print(f"[red]Unknown tool:[/] {tool}. Please clarify your command.")
            break

        tool_entry = TOOL_REGISTRY[tool]
        
        try:
            func = tool_entry["function"]
            # The tool functions now print their own formatted output
            result_summary, raw_output = func(**args) 
            
            # Append tool execution result summary to conversation history
            conversation_history.append({"role": "assistant", "content": result_summary})

            # Check for specific cancellation messages from tools
            if "cancelled by user" in result_summary.lower():
                console.print("[yellow]Operation cancelled. Proceeding to next step if available.[/]")
                # Do not increment completed_operations for cancelled tasks
                # and do not mark done prematurely
                continue 
            
            completed_operations += 1

            # Determine if the overall task is done
            # If the LLM explicitly says done=true, or if we've completed all parsed operations
            if done or completed_operations >= total_operations:
                console.print("[green]Task completed.[/]")
                break

        except Exception as e:
            console.print(f"[red]Error executing tool '{tool}': {e}[/]")
            conversation_history.append({"role": "assistant", "content": f"Error executing tool '{tool}': {e}"})
            break
    else:
        console.print("[red]Task did not complete within the maximum number of iterations.[/]")

if __name__ == "__main__":
    main()
