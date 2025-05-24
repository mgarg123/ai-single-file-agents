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
client = Groq(api_key=groq_api_key) # Corrected: Changed api_api_key to api_key

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
            input=input_data,
            encoding='utf-8' # Explicitly set encoding to UTF-8
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
def git_commit(message: str = None):
    """Record changes to the repository. If no message is provided, an AI will draft one based on staged changes.
    Args:
        message (str, optional): The commit message. If None, AI will generate one.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git commit output.
    """
    final_message = message
    if not final_message:
        # Check if there are any staged changes using git diff --cached --quiet --exit-code
        # This command exits with 0 if no differences, 1 if differences (staged changes exist)
        _, _, staged_check_returncode = _run_git_command(["diff", "--cached", "--quiet", "--exit-code"])

        if staged_check_returncode == 0: # If returncode is 0, it means no staged changes
            error_msg = "[red]Error: No changes are staged for commit. Please stage files first (e.g., `git add .`).[/]"
            console.print(Panel(error_msg, title="[bold red]Git Commit Error[/]", border_style="red"))
            return error_msg, None

        # If we reach here, there are staged changes, proceed to get details for LLM
        _, staged_files_output, _ = _run_git_command(["diff", "--staged", "--name-only"])
        _, diff_stat_output, _ = _run_git_command(["diff", "--staged", "--stat"])

        console.print(Panel("[blue]No commit message provided. Drafting one using AI...[/]", title="[bold blue]AI Commit Message[/]", border_style="blue"))

        llm_prompt = f"""
        You are an AI assistant specialized in generating concise and informative Git commit messages.
        Based on the following staged changes, provide a commit message.
        The message should consist of a short, imperative subject line (max 72 characters) and an optional, more detailed body.
        The body should explain *what* changed and *why*, but keep it brief and to the point.

        Staged Files:
        {staged_files_output}

        Change Summary:
        {diff_stat_output}

        Respond ONLY with a JSON object containing "subject" and "body" (body can be an empty string if not needed).
        Example:
        {{"subject": "feat: Add new user authentication", "body": "This commit introduces a new user authentication module to improve security and user experience."}}
        """
        
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": llm_prompt},
                    {"role": "user", "content": "Generate a commit message for the staged changes."}
                ],
                response_format={"type": "json_object"}
            )
            llm_response_content = response.choices[0].message.content.strip()
            
            console.print(f"[yellow]LLM raw message output:[/] {llm_response_content}")

            parsed_message = json.loads(llm_response_content)
            subject = parsed_message.get("subject", "feat: Automated commit")
            body = parsed_message.get("body", "")

            final_message = f"{subject}\n\n{body}".strip()
            console.print(Panel(f"[green]AI drafted commit message:[/green]\n[bold cyan]{final_message}[/bold cyan]", title="[bold green]AI Drafted Message[/]", border_style="green"))

        except json.JSONDecodeError as e:
            error_msg = f"[red]Error parsing AI generated message: {e}. Using a default message.[/]"
            console.print(Panel(error_msg, title="[bold red]AI Message Error[/]", border_style="red"))
            final_message = "feat: Automated commit (AI failed to parse message)"
        except Exception as e:
            error_msg = f"[red]Error generating AI commit message: {e}. Using a default message.[/]"
            console.print(Panel(error_msg, title="[bold red]AI Message Error[/]", border_style="red"))
            final_message = "feat: Automated commit (AI generation failed)"

    if not final_message: # Fallback if AI also failed to produce a message
        error_msg = "[red]Error: Commit message is empty after AI attempt. Please provide one manually.[/]"
        console.print(Panel(error_msg, title="[bold red]Git Commit Error[/]", border_style="red"))
        return error_msg, None

    summary_msg, output, returncode = _run_git_command(["commit", "-m", final_message])
    
    if returncode == 0:
        commit_hash_match = re.search(r'\[(\w+)\s', output)
        commit_hash = commit_hash_match.group(1) if commit_hash_match else "unknown"
        
        message = f"[green]Changes committed successfully![/]\n[bold]Commit:[/bold] [cyan]{commit_hash}[/]\n[bold]Message:[/bold] '{final_message.splitlines()[0]}...'"
        console.print(Panel(message, title="[bold green]Git Commit[/]", border_style="green"))
        return f"Committed changes with message: '{final_message.splitlines()[0]}...' (Hash: {commit_hash})", output
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

@tool
def git_diff(file_path: str = None):
    """Show changes between commits, working tree and index, or between two branches, with formatted output.
    Args:
        file_path (str, optional): Path to a specific file to diff. If None, shows all changes.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git diff output.
    """
    command_args = ["diff"]
    if file_path:
        command_args.append(file_path)
    
    summary_msg, output, returncode = _run_git_command(command_args)

    if returncode != 0:
        console.print(Panel(f"[red]Error getting Git diff:[/]\n{summary_msg}", title="[bold red]Git Diff Error[/]", border_style="red"))
        return summary_msg, output
    
    if not output:
        message = "[green]No differences found.[/]"
        console.print(Panel(message, title="[bold blue]Git Diff[/]", border_style="green"))
        return "No differences found.", output
    else:
        diff_lines = output.splitlines()
        formatted_diff = Text()
        
        for line in diff_lines:
            if line.startswith("diff --git"):
                formatted_diff.append(line + "\n", style="bold magenta")
            elif line.startswith("index ") or line.startswith("--- ") or line.startswith("+++ "):
                formatted_diff.append(line + "\n", style="cyan")
            elif line.startswith("@@"):
                formatted_diff.append(line + "\n", style="blue")
            elif line.startswith("+"):
                formatted_diff.append(line + "\n", style="green")
            elif line.startswith("-"):
                formatted_diff.append(line + "\n", style="red")
            else:
                formatted_diff.append(line + "\n", style="white") # Context lines
        
        title = f"[bold blue]Git Diff[/]"
        if file_path:
            title += f" for [cyan]{file_path}[/]"
        console.print(Panel(formatted_diff, title=title, border_style="blue", expand=True))
        return "Git diff displayed with formatted output. See console for details.", output

@tool
def git_merge(branch_name: str, no_ff: bool = False):
    """Integrate changes from one branch into the current branch.
    Args:
        branch_name (str): The name of the branch to merge into the current branch.
        no_ff (bool, optional): If True, creates a merge commit even if a fast-forward merge is possible. Defaults to False.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git merge output.
    """
    if not branch_name:
        error_msg = "[red]Error: Branch name to merge cannot be empty.[/]"
        console.print(Panel(error_msg, title="[bold red]Git Merge Error[/]", border_style="red"))
        return error_msg, None

    command_args = ["merge", branch_name]
    if no_ff:
        command_args.append("--no-ff")
    
    summary_msg, output, returncode = _run_git_command(command_args)

    if returncode == 0:
        message = f"[green]Successfully merged branch '[cyan]{branch_name}[/]' into current branch.[/]"
        if "Already up to date." in output:
            message = f"[yellow]Branch '[cyan]{branch_name}[/]' is already up to date with current branch.[/]"
        console.print(Panel(message, title="[bold green]Git Merge[/]", border_style="green"))
        return f"Merged branch '{branch_name}'.", output
    else:
        # Check for merge conflicts
        if "conflict" in output.lower() or "Automatic merge failed" in output:
            error_msg = f"[red]Merge conflicts detected when merging '[cyan]{branch_name}[/]'. Please resolve conflicts manually.[/]\n"
            error_msg += "[yellow]Use `git status` to see conflicted files, resolve them, then `git add` and `git commit`.[/]"
            console.print(Panel(error_msg, title="[bold red]Git Merge Conflict![/]", border_style="red"))
            return f"Merge conflicts detected with '{branch_name}'.", output
        else:
            console.print(Panel(f"[red]Error merging branch '{branch_name}':[/]\n{summary_msg}", title="[bold red]Git Merge Error[/]", border_style="red"))
            return summary_msg, output

@tool
def git_reset(mode: str = 'soft', target: str = 'HEAD'):
    """Undo changes by moving the HEAD pointer and optionally modifying the index and working directory.
    Args:
        mode (str, optional): The reset mode ('soft', 'mixed', 'hard'). 'soft' keeps changes staged, 'mixed' unstages them, 'hard' discards them. Defaults to 'soft'.
        target (str, optional): The commit to reset to. Defaults to 'HEAD' (the last commit).
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git reset output.
    """
    valid_modes = ['soft', 'mixed', 'hard']
    if mode not in valid_modes:
        error_msg = f"[red]Error: Invalid reset mode '{mode}'. Choose from {', '.join(valid_modes)}.[/]"
        console.print(Panel(error_msg, title="[bold red]Git Reset Error[/]", border_style="red"))
        return error_msg, None

    if mode == 'hard':
        console.print(Panel("[bold red]WARNING: A 'hard' reset will discard all uncommitted changes in your working directory and index. This action is irreversible. Are you sure you want to proceed? (y/n)[/]", title="[bold red]Confirm Hard Reset![/]", border_style="red"))
        response = input().strip().lower()
        if response != "y":
            cancel_msg = "[yellow]Hard reset cancelled by user.[/]"
            console.print(Panel(cancel_msg, title="[bold yellow]Git Reset[/]", border_style="yellow"))
            return cancel_msg, None
    
    command_args = ["reset", f"--{mode}", target]
    summary_msg, output, returncode = _run_git_command(command_args)

    if returncode == 0:
        message = f"[green]Successfully performed a '{mode}' reset to '{target}'.[/]"
        console.print(Panel(message, title="[bold green]Git Reset[/]", border_style="green"))
        return f"Performed '{mode}' reset to '{target}'.", output
    else:
        console.print(Panel(f"[red]Error performing reset:[/]\n{summary_msg}", title="[bold red]Git Reset Error[/]", border_style="red"))
        return summary_msg, output

@tool
def git_stash(action: str = 'save', message: str = None, stash_id: str = None):
    """Temporarily save changes that are not ready to be committed.
    Args:
        action (str, optional): The stash action ('save', 'list', 'pop', 'apply', 'drop'). Defaults to 'save'.
        message (str, optional): A descriptive message for 'save' action.
        stash_id (str, optional): The ID of the stash to 'pop', 'apply', or 'drop' (e.g., 'stash@{0}').
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git stash output.
    """
    command_args = ["stash"]
    
    if action == 'save':
        if message:
            command_args.extend(["push", "-m", message])
        else:
            command_args.append("save")
        
        summary_msg, output, returncode = _run_git_command(command_args)
        if returncode == 0:
            message_panel = "[green]Changes successfully stashed.[/]"
            if "No local changes to save" in output:
                message_panel = "[yellow]No local changes to stash.[/]"
            console.print(Panel(message_panel, title="[bold green]Git Stash Save[/]", border_style="green"))
            return "Changes stashed.", output
        else:
            console.print(Panel(f"[red]Error stashing changes:[/]\n{summary_msg}", title="[bold red]Git Stash Error[/]", border_style="red"))
            return summary_msg, output
    
    elif action == 'list':
        summary_msg, output, returncode = _run_git_command(["stash", "list"])
        if returncode != 0:
            console.print(Panel(f"[red]Error listing stashes:[/]\n{summary_msg}", title="[bold red]Git Stash List Error[/]", border_style="red"))
            return summary_msg, output
        
        if not output:
            console.print(Panel("[yellow]No stashes found.[/]", title="[bold blue]Git Stash List[/]", border_style="yellow"))
            return "No stashes found.", output
        
        table = Table(title="[bold blue]Git Stash List[/]", box=box.ROUNDED)
        table.add_column("ID", style="cyan", justify="left")
        table.add_column("Branch", style="magenta", justify="left")
        table.add_column("Message", style="white", justify="left")

        for line in output.splitlines():
            match = re.match(r'(stash@\{\d+\}): On (.+): (.+)', line)
            if match:
                stash_id_val, branch, msg = match.groups()
                table.add_row(stash_id_val, branch, msg)
        console.print(table)
        return "Stash list displayed. See console for details.", output

    elif action in ['pop', 'apply', 'drop']:
        if not stash_id:
            error_msg = f"[red]Error: 'stash_id' is required for '{action}' action (e.g., 'stash@{{0}}').[/]"
            console.print(Panel(error_msg, title="[bold red]Git Stash Error[/]", border_style="red"))
            return error_msg, None
        
        if action == 'drop':
            console.print(Panel(f"[yellow]Are you sure you want to permanently drop stash '{stash_id}'? This action is irreversible. (y/n)[/]", title="[bold yellow]Confirm Stash Drop![/]", border_style="yellow"))
            response = input().strip().lower()
            if response != "y":
                cancel_msg = "[yellow]Stash drop cancelled by user.[/]"
                console.print(Panel(cancel_msg, title="[bold yellow]Git Stash[/]", border_style="yellow"))
                return cancel_msg, None

        command_args.extend([action, stash_id])
        summary_msg, output, returncode = _run_git_command(command_args)
        
        if returncode == 0:
            message = f"[green]Successfully performed '{action}' on stash '{stash_id}'.[/]"
            console.print(Panel(message, title=f"[bold green]Git Stash {action.capitalize()}[/]", border_style="green"))
            return f"Stash '{stash_id}' {action}ed successfully.", output
        else:
            console.print(Panel(f"[red]Error performing '{action}' on stash '{stash_id}':[/]\n{summary_msg}", title=f"[bold red]Git Stash {action.capitalize()} Error[/]", border_style="red"))
            return summary_msg, output
    else:
        error_msg = f"[red]Error: Invalid stash action '{action}'. Choose from 'save', 'list', 'pop', 'apply', 'drop'.[/]"
        console.print(Panel(error_msg, title="[bold red]Git Stash Error[/]", border_style="red"))
        return error_msg, None

@tool
def git_branch_delete(branch_name: str, force: bool = False):
    """Delete a local branch.
    Args:
        branch_name (str): The name of the branch to delete.
        force (bool, optional): If True, force delete the branch even if it's not fully merged. Defaults to False.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git branch delete output.
    """
    if not branch_name:
        error_msg = "[red]Error: Branch name to delete cannot be empty.[/]"
        console.print(Panel(error_msg, title="[bold red]Git Branch Delete Error[/]", border_style="red"))
        return error_msg, None
    
    command_args = ["branch"]
    if force:
        console.print(Panel(f"[bold red]WARNING: Force deleting branch '[cyan]{branch_name}[/]' will discard any unmerged changes. This action is irreversible. Are you sure? (y/n)[/]", title="[bold red]Confirm Force Delete Branch![/]", border_style="red"))
        response = input().strip().lower()
        if response != "y":
            cancel_msg = "[yellow]Branch deletion cancelled by user.[/]"
            console.print(Panel(cancel_msg, title="[bold yellow]Git Branch Delete[/]", border_style="yellow"))
            return cancel_msg, None
        command_args.append("-D")
    else:
        command_args.append("-d")
    
    command_args.append(branch_name)
    
    summary_msg, output, returncode = _run_git_command(command_args)

    if returncode == 0:
        message = f"[green]Successfully deleted branch '[cyan]{branch_name}[/]'."
        console.print(Panel(message, title="[bold green]Git Branch Delete[/]", border_style="green"))
        return f"Branch '{branch_name}' deleted successfully.", output
    else:
        console.print(Panel(f"[red]Error deleting branch '{branch_name}':[/]\n{summary_msg}", title="[bold red]Git Branch Delete Error[/]", border_style="red"))
        return summary_msg, output

@tool
def git_remote_add(name: str, url: str):
    """Add a new remote repository.
    Args:
        name (str): The name for the new remote (e.g., 'upstream').
        url (str): The URL of the remote repository.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git remote add output.
    """
    if not name or not url:
        error_msg = "[red]Error: Remote name and URL cannot be empty.[/]"
        console.print(Panel(error_msg, title="[bold red]Git Remote Add Error[/]", border_style="red"))
        return error_msg, None
    
    summary_msg, output, returncode = _run_git_command(["remote", "add", name, url])

    if returncode == 0:
        message = f"[green]Successfully added remote '[cyan]{name}[/]' with URL '[blue]{url}[/]'."
        console.print(Panel(message, title="[bold green]Git Remote Add[/]", border_style="green"))
        return f"Remote '{name}' added successfully.", output
    else:
        console.print(Panel(f"[red]Error adding remote '{name}':[/]\n{summary_msg}", title="[bold red]Git Remote Add Error[/]", border_style="red"))
        return summary_msg, output

@tool
def git_remote_remove(name: str):
    """Remove a remote repository.
    Args:
        name (str): The name of the remote to remove.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git remote remove output.
    """
    if not name:
        error_msg = "[red]Error: Remote name to remove cannot be empty.[/]"
        console.print(Panel(error_msg, title="[bold red]Git Remote Remove Error[/]", border_style="red"))
        return error_msg, None
    
    console.print(Panel(f"[yellow]Are you sure you want to remove remote '[cyan]{name}[/]'? (y/n)[/]", title="[bold yellow]Confirm Remote Remove[/]", border_style="yellow"))
    response = input().strip().lower()
    if response != "y":
        cancel_msg = "[yellow]Remote removal cancelled by user.[/]"
        console.print(Panel(cancel_msg, title="[bold yellow]Git Remote Remove[/]", border_style="yellow"))
        return cancel_msg, None

    summary_msg, output, returncode = _run_git_command(["remote", "remove", name])

    if returncode == 0:
        message = f"[green]Successfully removed remote '[cyan]{name}[/]'."
        console.print(Panel(message, title="[bold green]Git Remote Remove[/]", border_style="green"))
        return f"Remote '{name}' removed successfully.", output
    else:
        console.print(Panel(f"[red]Error removing remote '{name}':[/]\n{summary_msg}", title="[bold red]Git Remote Remove Error[/]", border_style="red"))
        return summary_msg, output

@tool
def git_clone(repo_url: str, directory: str = None):
    """Clone a repository into a new directory.
    Args:
        repo_url (str): The URL of the repository to clone.
        directory (str, optional): The name of the new directory to clone into. If None, uses repository name.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git clone output.
    """
    if not repo_url:
        error_msg = "[red]Error: Repository URL cannot be empty.[/]"
        console.print(Panel(error_msg, title="[bold red]Git Clone Error[/]", border_style="red"))
        return error_msg, None
    
    command_args = ["clone", repo_url]
    if directory:
        command_args.append(directory)
    
    console.print(Panel(f"[blue]Cloning repository from '[cyan]{repo_url}[/]'...", title="[bold blue]Git Clone[/]", border_style="blue"))
    summary_msg, output, returncode = _run_git_command(command_args)

    if returncode == 0:
        target_dir = directory if directory else os.path.basename(repo_url).replace(".git", "")
        message = f"[green]Successfully cloned repository to '[cyan]{target_dir}[/]'."
        console.print(Panel(message, title="[bold green]Git Clone[/]", border_style="green"))
        return f"Repository cloned to '{target_dir}'.", output
    else:
        console.print(Panel(f"[red]Error cloning repository:[/]\n{summary_msg}", title="[bold red]Git Clone Error[/]", border_style="red"))
        return summary_msg, output

@tool
def git_tag(tag_name: str, message: str = None, lightweight: bool = False):
    """Create a tag to mark a specific point in history.
    Args:
        tag_name (str): The name of the tag.
        message (str, optional): A descriptive message for an annotated tag. Required if lightweight is False.
        lightweight (bool, optional): If True, creates a lightweight (non-annotated) tag. Defaults to False.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git tag output.
    """
    if not tag_name:
        error_msg = "[red]Error: Tag name cannot be empty.[/]"
        console.print(Panel(error_msg, title="[bold red]Git Tag Error[/]", border_style="red"))
        return error_msg, None
    
    command_args = ["tag", tag_name]
    if not lightweight:
        command_args.insert(1, "-a") # Insert -a before tag_name
        if message:
            command_args.extend(["-m", message])
        else:
            error_msg = "[red]Error: A message is required for annotated tags (lightweight=False).[/]"
            console.print(Panel(error_msg, title="[bold red]Git Tag Error[/]", border_style="red"))
            return error_msg, None
    
    summary_msg, output, returncode = _run_git_command(command_args)

    if returncode == 0:
        tag_type = "lightweight" if lightweight else "annotated"
        message = f"[green]Successfully created {tag_type} tag '[cyan]{tag_name}[/]'."
        console.print(Panel(message, title="[bold green]Git Tag[/]", border_style="green"))
        return f"Created tag '{tag_name}'.", output
    else:
        console.print(Panel(f"[red]Error creating tag '{tag_name}':[/]\n{summary_msg}", title="[bold red]Git Tag Error[/]", border_style="red"))
        return summary_msg, output

@tool
def git_show(commit_hash: str = 'HEAD'):
    """Show information about a Git object (commit, tree, blob, tag). Most commonly used to inspect the details of a specific commit.
    Args:
        commit_hash (str, optional): The hash or reference of the commit/object to show. Defaults to 'HEAD'.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git show output.
    """
    summary_msg, output, returncode = _run_git_command(["show", commit_hash])

    if returncode != 0:
        console.print(Panel(f"[red]Error showing Git object '{commit_hash}':[/]\n{summary_msg}", title="[bold red]Git Show Error[/]", border_style="red"))
        return summary_msg, output
    
    title = f"[bold blue]Git Show: {commit_hash}[/]"
    # Re-using the diff formatting logic for git show as it often includes diffs
    diff_lines = output.splitlines()
    formatted_output = Text()
    
    for line in diff_lines:
        if line.startswith("diff --git"):
            formatted_output.append(line + "\n", style="bold magenta")
        elif line.startswith("index ") or line.startswith("--- ") or line.startswith("+++ "):
            formatted_output.append(line + "\n", style="cyan")
        elif line.startswith("@@"):
            formatted_output.append(line + "\n", style="blue")
        elif line.startswith("+"):
            formatted_output.append(line + "\n", style="green")
        elif line.startswith("-"):
            formatted_output.append(line + "\n", style="red")
        else:
            formatted_output.append(line + "\n", style="white") # Context lines and commit metadata
    
    console.print(Panel(formatted_output, title=title, border_style="blue", expand=True))
    return f"Details for '{commit_hash}' displayed. See console for full details.", output

@tool
def git_list_branches(all_branches: bool = False, remote_only: bool = False):
    """List all local and remote branches.
    Args:
        all_branches (bool, optional): If True, list both local and remote-tracking branches. Defaults to False.
        remote_only (bool, optional): If True, list only remote-tracking branches. Defaults to False.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git branch output.
    """
    command_args = ["branch"]
    if all_branches:
        command_args.append("-a")
    elif remote_only:
        command_args.append("-r")
    
    summary_msg, output, returncode = _run_git_command(command_args)

    if returncode != 0:
        console.print(Panel(f"[red]Error listing branches:[/]\n{summary_msg}", title="[bold red]Git List Branches Error[/]", border_style="red"))
        return summary_msg, output
    
    if not output:
        console.print(Panel("[yellow]No branches found.[/]", title="[bold blue]Git Branches[/]", border_style="yellow"))
        return "No branches found.", output

    table = Table(title="[bold blue]Git Branches[/]", box=box.ROUNDED)
    table.add_column("Branch Name", style="cyan", justify="left")
    table.add_column("Current", style="magenta", justify="center")

    for line in output.splitlines():
        line = line.strip()
        if line.startswith("*"):
            table.add_row(line[1:].strip(), "[green]Yes[/]")
        elif line.startswith("remotes/"):
            table.add_row(f"[dim]{line}[/]", "") # Dim remote branches
        else:
            table.add_row(line, "")
    
    console.print(table)
    return "Git branches listed. See console for details.", output

@tool
def git_rebase(base_branch: str):
    """Reapply commits on top of another base tip, creating a linear history.
    Note: Interactive rebase is not supported directly via this tool.
    Args:
        base_branch (str): The branch to rebase onto.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git rebase output.
    """
    if not base_branch:
        error_msg = "[red]Error: Base branch for rebase cannot be empty.[/]"
        console.print(Panel(error_msg, title="[bold red]Git Rebase Error[/]", border_style="red"))
        return error_msg, None
    
    console.print(Panel(f"[yellow]Rebasing current branch onto '[cyan]{base_branch}[/]'... This operation rewrites history. Proceed? (y/n)[/]", title="[bold yellow]Confirm Rebase[/]", border_style="yellow"))
    response = input().strip().lower()
    if response != "y":
        cancel_msg = "[yellow]Rebase cancelled by user.[/]"
        console.print(Panel(cancel_msg, title="[bold yellow]Git Rebase[/]", border_style="yellow"))
        return cancel_msg, None

    summary_msg, output, returncode = _run_git_command(["rebase", base_branch])

    if returncode == 0:
        message = f"[green]Successfully rebased current branch onto '[cyan]{base_branch}[/]'."
        console.print(Panel(message, title="[bold green]Git Rebase[/]", border_style="green"))
        return f"Rebased onto '{base_branch}'.", output
    else:
        if "conflict" in output.lower() or "could not apply" in output.lower():
            error_msg = f"[red]Rebase conflicts detected when rebasing onto '[cyan]{base_branch}[/]'. Please resolve conflicts manually.[/]\n"
            error_msg += "[yellow]Use `git status` to see conflicted files, resolve them, then `git rebase --continue` or `git rebase --abort`.[/]"
            console.print(Panel(error_msg, title="[bold red]Git Rebase Conflict![/]", border_style="red"))
            return f"Rebase conflicts detected with '{base_branch}'.", output
        else:
            console.print(Panel(f"[red]Error rebasing onto '{base_branch}':[/]\n{summary_msg}", title="[bold red]Git Rebase Error[/]", border_style="red"))
            return summary_msg, output

@tool
def git_blame(filename: str):
    """Show what revision and author last modified each line of a file.
    Args:
        filename (str): The path to the file to blame.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git blame output.
    """
    if not filename:
        error_msg = "[red]Error: Filename for blame cannot be empty.[/]"
        console.print(Panel(error_msg, title="[bold red]Git Blame Error[/]", border_style="red"))
        return error_msg, None
    
    summary_msg, output, returncode = _run_git_command(["blame", filename])

    if returncode != 0:
        console.print(Panel(f"[red]Error blaming file '{filename}':[/]\n{summary_msg}", title="[bold red]Git Blame Error[/]", border_style="red"))
        return summary_msg, output
    
    if not output:
        message = f"[yellow]No blame information found for '{filename}'. File might be empty or not tracked.[/]"
        console.print(Panel(message, title="[bold blue]Git Blame[/]", border_style="yellow"))
        return f"No blame information for '{filename}'.", output
    
    # Format blame output for better readability
    formatted_blame = Text()
    for line in output.splitlines():
        match = re.match(r'([0-9a-f]+)\s+\((.+?)\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+[+-]\d{4})\s+(\d+)\)\s*(.*)', line)
        if match:
            commit_hash, author, date, line_num, content = match.groups()
            formatted_blame.append(f"{commit_hash[:7]} ", style="cyan")
            formatted_blame.append(f"({author.strip():<15.15s} {date.split(' ')[0]} {line_num:>4}) ", style="magenta")
            formatted_blame.append(f"{content}\n", style="white")
        else:
            formatted_blame.append(line + "\n", style="white") # Fallback for lines that don't match pattern
    
    console.print(Panel(formatted_blame, title=f"[bold blue]Git Blame: {filename}[/]", border_style="blue", expand=True))
    return f"Git blame for '{filename}' displayed. See console for details.", output

@tool
def git_reflog():
    """Manage and show the reflog, which records updates to the tip of branches and other references in the local repository.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git reflog output.
    """
    summary_msg, output, returncode = _run_git_command(["reflog"])

    if returncode != 0:
        console.print(Panel(f"[red]Error getting Git reflog:[/]\n{summary_msg}", title="[bold red]Git Reflog Error[/]", border_style="red"))
        return summary_msg, output
    
    if not output:
        console.print(Panel("[yellow]No reflog entries found.[/]", title="[bold blue]Git Reflog[/]", border_style="yellow"))
        return "No reflog entries found.", output
    
    table = Table(title="[bold blue]Git Reflog[/]", box=box.ROUNDED)
    table.add_column("Ref", style="cyan", justify="left")
    table.add_column("HEAD@{index}", style="magenta", justify="left")
    table.add_column("Action", style="white", justify="left")

    for line in output.splitlines():
        match = re.match(r'(\w+)\s+(HEAD@\{\d+\}):\s+(.*)', line)
        if match:
            commit_hash, head_index, action = match.groups()
            table.add_row(commit_hash[:7], head_index, action)
        else:
            # Fallback for lines that don't perfectly match, or just print raw
            console.print(line)
    
    console.print(table)
    return "Git reflog displayed. See console for details.", output

@tool
def git_restore(file_path: str = '.', staged: bool = False, source_commit: str = None):
    """Restore working tree files. This command is used to discard unstaged changes in a file or to restore a file from the index.
    Args:
        file_path (str, optional): Path to the file or directory to restore. Use '.' for all changes. Defaults to ".".
        staged (bool, optional): If True, restore staged changes (unstage them). Defaults to False.
        source_commit (str, optional): The commit to restore the file from (e.g., 'HEAD~1'). If None, restores from index or last commit.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git restore output.
    """
    command_args = ["restore"]
    if staged:
        command_args.append("--staged")
    if source_commit:
        command_args.extend(["--source", source_commit])
    
    command_args.append(file_path)

    # Add a confirmation for potentially destructive operations (discarding unstaged changes)
    if not staged and not source_commit: # Only prompt if not unstaging or restoring from a specific commit
        if file_path == '.':
            console.print(Panel("[yellow]Are you sure you want to discard all unstaged changes in the current directory? This action is irreversible. (y/n)[/]", title="[bold yellow]Confirm Discard Changes[/]", border_style="yellow"))
            response = input().strip().lower()
            if response != "y":
                cancel_msg = "[yellow]Discard changes cancelled by user.[/]"
                console.print(Panel(cancel_msg, title="[bold yellow]Git Restore[/]", border_style="yellow"))
                return cancel_msg, None
        elif os.path.exists(file_path): # Only prompt if the file actually exists and is being discarded
            console.print(Panel(f"[yellow]Are you sure you want to discard unstaged changes in '{file_path}'? This action is irreversible. (y/n)[/]", title="[bold yellow]Confirm Discard Changes[/]", border_style="yellow"))
            response = input().strip().lower()
            if response != "y":
                cancel_msg = "[yellow]Discard changes cancelled by user.[/]"
                console.print(Panel(cancel_msg, title="[bold yellow]Git Restore[/]", border_style="yellow"))
                return cancel_msg, None

    summary_msg, output, returncode = _run_git_command(command_args)

    if returncode == 0:
        action_desc = "unstaged changes"
        if staged:
            action_desc = "staged changes (unstaged)"
        elif source_commit:
            action_desc = f"'{file_path}' from '{source_commit}'"
        
        message = f"[green]Successfully restored {action_desc} for '{file_path}'.[/]"
        console.print(Panel(message, title="[bold green]Git Restore[/]", border_style="green"))
        return f"Restored {action_desc} for '{file_path}'.", output
    else:
        console.print(Panel(f"[red]Error restoring '{file_path}':[/]\n{summary_msg}", title="[bold red]Git Restore Error[/]", border_style="red"))
        return summary_msg, output

@tool
def git_cherry_pick(commit_hash: str):
    """Apply the changes introduced by some existing commits. Useful for applying a specific commit from one branch to another.
    Args:
        commit_hash (str): The hash of the commit to cherry-pick.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git cherry-pick output.
    """
    if not commit_hash:
        error_msg = "[red]Error: Commit hash for cherry-pick cannot be empty.[/]"
        console.print(Panel(error_msg, title="[bold red]Git Cherry-Pick Error[/]", border_style="red"))
        return error_msg, None
    
    summary_msg, output, returncode = _run_git_command(["cherry-pick", commit_hash])

    if returncode == 0:
        message = f"[green]Successfully cherry-picked commit '[cyan]{commit_hash}[/]' onto the current branch.[/]"
        console.print(Panel(message, title="[bold green]Git Cherry-Pick[/]", border_style="green"))
        return f"Cherry-picked commit '{commit_hash}'.", output
    else:
        if "conflict" in output.lower() or "could not apply" in output.lower():
            error_msg = f"[red]Cherry-pick conflicts detected for commit '[cyan]{commit_hash}[/]'. Please resolve conflicts manually.[/]\n"
            error_msg += "[yellow]Use `git status` to see conflicted files, resolve them, then `git cherry-pick --continue` or `git cherry-pick --abort`.[/]"
            console.print(Panel(error_msg, title="[bold red]Git Cherry-Pick Conflict![/]", border_style="red"))
            return f"Cherry-pick conflicts detected for '{commit_hash}'.", output
        else:
            console.print(Panel(f"[red]Error cherry-picking commit '{commit_hash}':[/]\n{summary_msg}", title="[bold red]Git Cherry-Pick Error[/]", border_style="red"))
            return summary_msg, output

@tool
def git_clean(force: bool, directories: bool = False):
    """Remove untracked files from the working directory.
    WARNING: This command is destructive and cannot be undone.
    Args:
        force (bool): Must be True to actually remove files. Git requires -f or --force.
        directories (bool, optional): If True, also remove untracked directories. Defaults to False.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git clean output.
    """
    if not force:
        error_msg = "[red]Error: 'force' must be True to execute git clean. This is a safety measure.[/]"
        console.print(Panel(error_msg, title="[bold red]Git Clean Error[/]", border_style="red"))
        return error_msg, None
    
    command_args = ["clean", "-f"]
    if directories:
        command_args.append("-d")
    
    console.print(Panel("[bold red]WARNING: This will permanently remove untracked files and potentially directories. This action is irreversible. Are you absolutely sure? (y/n)[/]", title="[bold red]Confirm Git Clean![/]", border_style="red"))
    response = input().strip().lower()
    if response != "y":
        cancel_msg = "[yellow]Git clean cancelled by user.[/]"
        console.print(Panel(cancel_msg, title="[bold yellow]Git Clean[/]", border_style="yellow"))
        return cancel_msg, None

    summary_msg, output, returncode = _run_git_command(command_args)

    if returncode == 0:
        message = "[green]Successfully removed untracked files."
        if directories:
            message += " and directories."
        message += "[/]"
        console.print(Panel(message, title="[bold green]Git Clean[/]", border_style="green"))
        return "Untracked files cleaned.", output
    else:
        console.print(Panel(f"[red]Error cleaning untracked files:[/]\n{summary_msg}", title="[bold red]Git Clean Error[/]", border_style="red"))
        return summary_msg, output

@tool
def git_list_remotes(verbose: bool = False):
    """List the remote repositories you have configured.
    Args:
        verbose (bool, optional): If True, show URLs of remotes. Defaults to False.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git remote output.
    """
    command_args = ["remote"]
    if verbose:
        command_args.append("-v")
    
    summary_msg, output, returncode = _run_git_command(command_args)

    if returncode != 0:
        console.print(Panel(f"[red]Error listing remotes:[/]\n{summary_msg}", title="[bold red]Git List Remotes Error[/]", border_style="red"))
        return summary_msg, output
    
    if not output:
        console.print(Panel("[yellow]No remotes configured.[/]", title="[bold blue]Git Remotes[/]", border_style="yellow"))
        return "No remotes configured.", output
    
    table = Table(title="[bold blue]Git Remotes[/]", box=box.ROUNDED)
    if verbose:
        table.add_column("Name", style="cyan", justify="left")
        table.add_column("URL", style="magenta", justify="left")
        table.add_column("Type", style="white", justify="left")
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 3:
                name, url, type_ = parts[0], parts[1], parts[2].strip('()')
                table.add_row(name, url, type_)
    else:
        table.add_column("Name", style="cyan", justify="left")
        for line in output.splitlines():
            table.add_row(line.strip())
    
    console.print(table)
    return "Git remotes listed. See console for details.", output

@tool
def git_config_get(key: str, scope: str = 'local'):
    """Get a Git configuration value (e.g., user name, email, default editor).
    Args:
        key (str): The configuration key to retrieve (e.g., 'user.name', 'user.email').
        scope (str, optional): The scope of the configuration ('local', 'global', 'system'). Defaults to 'local'.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git config output.
    """
    if not key:
        error_msg = "[red]Error: Configuration key cannot be empty.[/]"
        console.print(Panel(error_msg, title="[bold red]Git Config Get Error[/]", border_style="red"))
        return error_msg, None
    
    valid_scopes = ['local', 'global', 'system']
    if scope not in valid_scopes:
        error_msg = f"[red]Error: Invalid scope '{scope}'. Choose from {', '.join(valid_scopes)}.[/]"
        console.print(Panel(error_msg, title="[bold red]Git Config Get Error[/]", border_style="red"))
        return error_msg, None
    
    command_args = ["config", f"--{scope}", "--get", key]
    summary_msg, output, returncode = _run_git_command(command_args)

    if returncode == 0:
        value = output.strip()
        message = f"[green]Git config '{key}' ({scope} scope): '[cyan]{value if value else 'Not set'}[/]'[/]"
        console.print(Panel(message, title="[bold green]Git Config Get[/]", border_style="green"))
        return f"Git config '{key}' is '{value}'.", output
    else:
        if "unknown option" in summary_msg.lower() or "not found" in summary_msg.lower():
            error_msg = f"[yellow]Git config key '{key}' not found in '{scope}' scope.[/]"
            console.print(Panel(error_msg, title="[bold yellow]Git Config Get[/]", border_style="yellow"))
            return error_msg, output
        else:
            console.print(Panel(f"[red]Error getting Git config '{key}':[/]\n{summary_msg}", title="[bold red]Git Config Get Error[/]", border_style="red"))
            return summary_msg, output

@tool
def git_list_tags(pattern: str = None):
    """List existing tags in the repository.
    Args:
        pattern (str, optional): A pattern to filter tags (e.g., 'v*'). Defaults to None.
    Returns:
        Tuple[str, str]: A string summary for the LLM and the raw git tag output.
    """
    command_args = ["tag"]
    if pattern:
        command_args.extend(["-l", pattern])
    
    summary_msg, output, returncode = _run_git_command(command_args)

    if returncode != 0:
        console.print(Panel(f"[red]Error listing tags:[/]\n{summary_msg}", title="[bold red]Git List Tags Error[/]", border_style="red"))
        return summary_msg, output
    
    if not output:
        console.print(Panel("[yellow]No tags found.[/]", title="[bold blue]Git Tags[/]", border_style="yellow"))
        return "No tags found.", output
    
    table = Table(title="[bold blue]Git Tags[/]", box=box.ROUNDED)
    table.add_column("Tag Name", style="cyan", justify="left")

    for line in output.splitlines():
        table.add_row(line.strip())
    
    console.print(table)
    return "Git tags listed. See console for details.", output


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
Command: "commit my changes"
Total operations: 1
Step 1: {{"tool": "git_commit", "args": {{"message": null}}, "done": true}}
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

<example>
Command: "show differences for file.txt"
Total operations: 1
Step 1: {{"tool": "git_diff", "args": {{"file_path": "file.txt"}}, "done": true}}
</example>

<example>
Command: "merge feature/new-feature into current branch"
Total operations: 1
Step 1: {{"tool": "git_merge", "args": {{"branch_name": "feature/new-feature"}}, "done": true}}
</example>

<example>
Command: "undo last commit but keep changes staged"
Total operations: 1
Step 1: {{"tool": "git_reset", "args": {{"mode": "soft", "target": "HEAD~1"}}, "done": true}}
</example>

<example>
Command: "stash my current changes with message 'WIP for feature X'"
Total operations: 1
Step 1: {{"tool": "git_stash", "args": {{"action": "save", "message": "WIP for feature X"}}, "done": true}}
</example>

<example>
Command: "list all stashes"
Total operations: 1
Step 1: {{"tool": "git_stash", "args": {{"action": "list"}}, "done": true}}
</example>

<example>
Command: "apply the latest stash"
Total operations: 1
Step 1: {{"tool": "git_stash", "args": {{"action": "apply", "stash_id": "stash@{0}"}}, "done": true}}
</example>

<example>
Command: "pop stash number 1"
Total operations: 1
Step 1: {{"tool": "git_stash", "args": {{"action": "pop", "stash_id": "stash@{1}"}}, "done": true}}
</example>

<example>
Command: "drop stash 2"
Total operations: 1
Step 1: {{"tool": "git_stash", "args": {{"action": "drop", "stash_id": "stash@{2}"}}, "done": true}}
</example>

<example>
Command: "delete branch old-feature"
Total operations: 1
Step 1: {{"tool": "git_branch_delete", "args": {{"branch_name": "old-feature"}}, "done": true}}
</example>

<example>
Command: "add a new remote named 'upstream' with url 'https://github.com/user/repo.git'"
Total operations: 1
Step 1: {{"tool": "git_remote_add", "args": {{"name": "upstream", "url": "https://github.com/user/repo.git"}}, "done": true}}
</example>

<example>
Command: "remove remote 'old-remote'"
Total operations: 1
Step 1: {{"tool": "git_remote_remove", "args": {{"name": "old-remote"}}, "done": true}}
</example>

<example>
Command: "clone repository 'https://github.com/user/another-repo.git' into 'my-new-repo'"
Total operations: 1
Step 1: {{"tool": "git_clone", "args": {{"repo_url": "https://github.com/user/another-repo.git", "directory": "my-new-repo"}}, "done": true}}
</example>

<example>
Command: "create a new tag v1.0.0 with message 'Release version 1.0'"
Total operations: 1
Step 1: {{"tool": "git_tag", "args": {{"tag_name": "v1.0.0", "message": "Release version 1.0"}}, "done": true}}
</example>

<example>
Command: "show details of commit abcdef1"
Total operations: 1
Step 1: {{"tool": "git_show", "args": {{"commit_hash": "abcdef1"}}, "done": true}}
</example>

<example>
Command: "list all branches including remotes"
Total operations: 1
Step 1: {{"tool": "git_list_branches", "args": {{"all_branches": true}}, "done": true}}
</example>

<example>
Command: "rebase current branch onto main"
Total operations: 1
Step 1: {{"tool": "git_rebase", "args": {{"base_branch": "main"}}, "done": true}}
</example>

<example>
Command: "show who changed each line in README.md"
Total operations: 1
Step 1: {{"tool": "git_blame", "args": {{"filename": "README.md"}}, "done": true}}
</example>

<example>
Command: "show reflog"
Total operations: 1
Step 1: {{"tool": "git_reflog", "args": {{}}, "done": true}}
</example>

<example>
Command: "discard unstaged changes in my_file.txt"
Total operations: 1
Step 1: {{"tool": "git_restore", "args": {{"file_path": "my_file.txt"}}, "done": true}}
</example>

<example>
Command: "cherry-pick commit 1a2b3c4"
Total operations: 1
Step 1: {{"tool": "git_cherry_pick", "args": {{"commit_hash": "1a2b3c4"}}, "done": true}}
</example>

<example>
Command: "clean untracked files and directories"
Total operations: 1
Step 1: {{"tool": "git_clean", "args": {{"force": true, "directories": true}}, "done": true}}
</example>

<example>
Command: "list remotes verbosely"
Total operations: 1
Step 1: {{"tool": "git_list_remotes", "args": {{"verbose": true}}, "done": true}}
</example>

<example>
Command: "get my global user email"
Total operations: 1
Step 1: {{"tool": "git_config_get", "args": {{"key": "user.email", "scope": "global"}}, "done": true}}
</example>

<example>
Command: "list all tags starting with v2"
Total operations: 1
Step 1: {{"tool": "git_list_tags", "args": {{"pattern": "v2*"}}, "done": true}}
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
