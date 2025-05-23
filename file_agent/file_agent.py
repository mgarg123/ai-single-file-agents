import os
import sys
import json
import re
import inspect
import datetime
from rich.console import Console
from rich.table import Table
from rich import box
from groq import Groq
from collections import Counter
import shutil
import psutil

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

# ==== TOOL FUNCTIONS ====


@tool
def check_os():
    """Check the current operating system. Returns a string summary and None."""
    import platform
    os_name = platform.system()
    if os_name == "Windows":
        os_details = f"Windows {platform.release()}"
    elif os_name == "Linux":
        os_details = f"Linux {platform.release()}"
    elif os_name == "Darwin":
        os_details = f"macOS {platform.mac_ver()[0]}"
    else:
        os_details = f"Unknown OS: {os_name}"
    return f"[green]Current operating system: {os_details}[/]", None

@tool
def system_resources(resource: str):
    """
    Returns system resource usage including free RAM and available disk space based on the passed resource type that is either RAM or DISK.
    """

    try:
        # Memory info
        mem = psutil.virtual_memory()
        total_ram = mem.total / (1024 ** 3)
        free_ram = mem.available / (1024 ** 3)

        # Disk info (use root path)
        disk = psutil.disk_usage('/')
        total_disk = disk.total / (1024 ** 3)
        free_disk = disk.free / (1024 ** 3)

        # Display table using rich
        table = Table(title="System Resources", title_style="bold green")
        table.add_column("Resource", style="cyan", justify="left")
        table.add_column("Total (GB)", justify="right")
        table.add_column("Free (GB)", justify="right")

        table.add_row("RAM", f"{total_ram:.2f}", f"{free_ram:.2f}")
        table.add_row("Disk", f"{total_disk:.2f}", f"{free_disk:.2f}")

        if "ram" in resource.lower():
            console.print(f"Total RAM: {total_ram:.2f}", f"\nFree RAM: {free_ram:.2f}")
        elif "disk" in resource.lower():
            console.print(f"Total Disk Space: {total_disk:.2f}", f"\nFree Space: {free_disk:.2f}")
        else:
            console.print(table)
            
        return "✅ System resources displayed above.", None

    except Exception as e:
        return f"[red]Error retrieving system resources:[/] {str(e)}", None

@tool
def get_root_directory():
    """Get the topmost root directory for the current operating system. Returns a string summary and the root directory path."""
    import os
    import platform
    if platform.system() == "Windows":
        # On Windows, use the drive letter of the current directory
        root = os.path.abspath(os.sep)
    else:
        # On Unix-like systems (Linux, macOS), root is '/'
        root = "/"
    return f"[green]Topmost root directory: {root}[/]", root

@tool
def get_command_line_directory():
    """Get the absolute path of the directory from which the script is invoked. Returns a string summary and the absolute path."""
    import os
    import sys
    # Get the directory of the script being run (sys.argv[0] is the script path)
    script_path = os.path.abspath(sys.argv[0])
    script_dir = os.path.dirname(script_path)
    return f"[green]Command-line directory: {script_dir}[/]", script_dir

@tool
def list_files(path="."):
    """List all files (not directories) in the given directory. Returns a string summary and a list of filenames. If no path is provided, use current directory."""
    import os
    
    # Normalize the path
    normalized_path = normalize_path(path)
    if not os.path.isdir(normalized_path):
        return f"[red]Directory not found or inaccessible:[/] {normalized_path}", []
    
    try:
        table = Table(title=f"Files in {normalized_path.replace('\\\\', '\\')}")
        table.add_column("Filename", style="cyan")
        files = [f for f in os.listdir(normalized_path) if os.path.isfile(os.path.join(normalized_path, f))]
        for file in files:
            table.add_row(file)
        console.print(table)
        return f"Files in {normalized_path.replace('\\\\', '\\')}: {', '.join(files) if files else 'None'}", files
    except OSError as e:
        return f"[red]Error listing files in {normalized_path}:[/] {str(e)}", []

@tool
def view_file(path=".", filename=None):
    """Show contents of a file in the given directory. Returns a string summary and None."""
    if not filename:
        return "[red]No filename provided.[/]", None
    full = os.path.join(path, filename)
    if not os.path.isfile(full):
        return f"[red]File not found:[/] {full}", None
    with open(full, "r") as f:
        content = f.read()
    console.rule(f"[bold green]{full}")
    console.print(content, highlight=True)
    return f"Content of {full} displayed.", None

@tool
def rename_file(path=".", filename=None, new_filename=None):
    """Rename a file at the given path to the specified new filename. Returns a string summary and None."""
    if not filename:
        return "[red]No filename provided.[/]", None
    if not new_filename:
        return "[red]No new filename provided.[/]", None

    # Resolve full path to the existing file
    full_path = os.path.abspath(os.path.join(path, filename))

    # Ensure it's a file
    if not os.path.isfile(full_path):
        return f"[red]File not found:[/] {full_path}", None

    # Determine the directory containing the file
    file_dir = os.path.dirname(full_path)

    # Clean and validate the new filename (no folders, just name)
    new_basename = os.path.basename(new_filename.strip())
    safe_new_name = re.sub(r'[^\w\-\.]', '_', new_basename)
    if not safe_new_name:
        return "[red]Invalid new filename provided.[/]", None

    # Construct full path for the new filename in same folder
    new_full_path = os.path.join(file_dir, safe_new_name)

    try:
        os.rename(full_path, new_full_path)
        return f"[green]Renamed:[/] {full_path} → {new_full_path}", None
    except OSError as e:
        return f"[red]Error renaming file:[/] {str(e)}", None


@tool
def find_frequent_word(path=".", filename=None):
    """Find the most frequently repeated word in the specified file. Returns a string summary and None."""
    if not filename:
        return "[red]No filename provided.[/]", None
    full = os.path.join(path, filename)
    if not os.path.isfile(full):
        return f"[red]File not found:[/] {full}", None
    with open(full, "r") as f:
        content = f.read()
    words = re.findall(r'\b\w+\b', content.lower())
    if not words:
        return "[red]No words found in the file.[/]", None
    word_counts = Counter(words)
    most_common = word_counts.most_common(1)
    word, count = most_common[0]
    return f"[green]Most frequent word in {full}: '{word}' (appears {count} times)[/]", None

@tool
def create_file(path=".", filename=None, content=None):
    """Create a new file with the specified content in the given directory. Returns a string summary and None."""
    if not filename:
        return "[red]No filename provided.[/]", None
    if content is None:
        content = ""
    full = os.path.join(path, filename)
    if os.path.exists(full):
        return f"[red]File already exists:[/] {full}", None
    try:
        os.makedirs(path, exist_ok=True)
        with open(full, "w") as f:
            f.write(content)
        return f"[green]File created:[/] {full}", None
    except OSError as e:
        return f"[red]Error creating file:[/] {str(e)}", None

@tool
def search_file_content(path=".", filename=None, keyword=None):
    """Search for a keyword in the file's content and return matching lines. Returns a string summary and None."""
    if not filename:
        return "[red]No filename provided.[/]", None
    if not keyword:
        return "[red]No keyword provided.[/]", None
    full = os.path.join(path, filename)
    if not os.path.isfile(full):
        return f"[red]File not found:[/] {full}", None
    with open(full, "r") as f:
        lines = f.readlines()
    matches = [f"Line {i+1}: {line.strip()}" for i, line in enumerate(lines) if keyword.lower() in line.lower()]
    if not matches:
        return f"[yellow]No matches found for '{keyword}' in {full}[/]", None
    result = f"[green]Found '{keyword}' in {len(matches)} line(s) in {full}:[/]\n" + "\n".join(matches)
    return result, None

@tool
def delete_file(path=".", filename=None):
    """Delete the specified file in the given directory after user confirmation. Returns a string summary and None."""
    if not filename:
        return "[red]No filename provided.[/]", None
    full = os.path.join(path, filename)
    if not os.path.isfile(full):
        return f"[red]File not found:[/] {full}", None
    try:
        console.print(f"[yellow]Are you sure you want to delete {full}? (y/n)[/]")
        response = input().strip().lower()
        if response != "y":
            return f"[yellow]Deletion of {full} cancelled.[/]", None
        os.remove(full)
        return f"[green]File deleted:[/] {full}", None
    except OSError as e:
        return f"[red]Error deleting file:[/] {str(e)}", None
    except EOFError:
        return f"[red]No input provided. Deletion of {full} cancelled.[/]", None

@tool
def file_exists(path=".", filename=None):
    """Check if a file exists in the given directory. Returns a string summary and None."""
    if not filename:
        return "[red]No filename provided.[/]", None
    full = os.path.join(path, filename)
    exists = os.path.isfile(full)
    return f"[green]File {'exists' if exists else 'does not exist'}:[/] {full}", None

@tool
def add_content_to_file(path=".", filename=None, content=None, append=True):
    """Add content to a file in the given directory. If append is True, appends content; if False, overwrites. Returns a string summary and None."""
    if not filename:
        return "[red]No filename provided.[/]", None
    if content is None:
        return "[red]No content provided.[/]", None
    full = os.path.join(path, filename)
    if not os.path.isfile(full):
        return f"[red]File not found:[/] {full}", None
    try:
        mode = "a" if append else "w"
        with open(full, mode) as f:
            f.write(content)
        action = "appended to" if append else "overwritten in"
        return f"[green]Content {action}:[/] {full}", None
    except OSError as e:
        return f"[red]Error adding content to file:[/] {str(e)}", None

@tool
def copy_file(source_path=".", filename=None, dest_path="."):
    """Copy a file from source_path to dest_path. Returns a string summary and None."""
    if not filename:
        return "[red]No filename provided.[/]", None
    source_full = os.path.join(source_path, filename)
    dest_full = os.path.join(dest_path, filename)
    if not os.path.isfile(source_full):
        return f"[red]Source file not found:[/] {source_full}", None
    try:
        os.makedirs(dest_path, exist_ok=True)
        with open(source_full, "rb") as src, open(dest_full, "wb") as dst:
            dst.write(src.read())
        return f"[green]File copied:[/] {source_full} → {dest_full}", None
    except OSError as e:
        return f"[red]Error copying file:[/] {str(e)}", None

@tool
def move_file(source_path=".", filename=None, dest_path="."):
    """Move a file from source_path to dest_path. Returns a string summary and None."""
    if not filename:
        return "[red]No filename provided.[/]", None
    source_full = os.path.join(source_path, filename)
    dest_full = os.path.join(dest_path, filename)
    if not os.path.isfile(source_full):
        return f"[red]Source file not found:[/] {source_full}", None
    try:
        os.makedirs(dest_path, exist_ok=True)
        os.rename(source_full, dest_full)
        return f"[green]File moved:[/] {source_full} → {dest_full}", None
    except OSError as e:
        return f"[red]Error moving file:[/] {str(e)}", None

@tool
def create_directory(path="."):
    """Create a new directory at the specified path. Returns a string summary and None."""
    try:
        os.makedirs(path, exist_ok=True)
        return f"[green]Directory created:[/] {path}", None
    except OSError as e:
        return f"[red]Error creating directory:[/] {str(e)}", None

@tool
def delete_directory(path="."):
    """Delete a directory at the specified path, even if it is not empty, after user confirmation. Returns a string summary and None."""
    if not os.path.isdir(path):
        return f"[red]Directory not found:[/] {path}", None
    try:
        console.print(f"[yellow]Are you sure you want to delete the directory '{path}' and all of its contents? (y/n)[/]")
        response = input().strip().lower()
        if response != "y":
            return f"[yellow]Deletion of {path} cancelled.[/]", None
        shutil.rmtree(path)
        return f"[green]Directory and its contents deleted:[/] {path}", None
    except Exception as e:
        return f"[red]Error deleting directory:[/] {str(e)}", None

@tool
def search_files_by_name(path=".", pattern=None):
    """Search for files by name matching the pattern in the given directory. Returns a string summary and a list of matching filenames."""
    if not pattern:
        return "[red]No pattern provided.[/]", []
    if not os.path.isdir(path):
        return f"[red]Directory not found:[/] {path}", []
    try:
        pattern = pattern.replace("*", ".*").replace("?", ".")
        regex = re.compile(pattern, re.IGNORECASE)
        matches = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)) and regex.match(f)]
        if not matches:
            return f"[yellow]No files found matching '{pattern}' in {path}[/]", []
        table = Table(title=f"Files matching '{pattern}' in {path}")
        table.add_column("Filename", style="cyan")
        for match in matches:
            table.add_row(match)
        console.print(table)
        return f"[green]Found {len(matches)} file(s) matching '{pattern}' in {path}:[/] {', '.join(matches)}", matches
    except re.error as e:
        return f"[red]Invalid pattern:[/] {str(e)}", []

@tool
def replace_text_in_file(path=".", filename=None, old_text=None, new_text=None):
    """Replace all occurrences of old_text with new_text in the specified file. Returns a string summary and None."""
    if not filename:
        return "[red]No filename provided.[/]", None
    if not old_text:
        return "[red]No text to replace provided.[/]", None
    if new_text is None:
        return "[red]No replacement text provided.[/]", None
    full = os.path.join(path, filename)
    if not os.path.isfile(full):
        return f"[red]File not found:[/] {full}", None
    try:
        with open(full, "r") as f:
            content = f.read()
        new_content = content.replace(old_text, new_text)
        with open(full, "w") as f:
            f.write(new_content)
        return f"[green]Replaced '{old_text}' with '{new_text}' in {full}[/]", None
    except OSError as e:
        return f"[red]Error replacing text in file:[/] {str(e)}", None

@tool
def count_lines_in_file(path=".", filename=None):
    """Count the total number of lines in the specified file. Returns a string summary and None."""
    if not filename:
        return "[red]No filename provided.[/]", None
    full = os.path.join(path, filename)
    if not os.path.isfile(full):
        return f"[red]File not found:[/] {full}", None
    try:
        with open(full, "r", encoding='utf-8', errors='ignore') as f:
            line_count = sum(1 for _ in f)
        return f"[green]File {full} contains {line_count} line(s)[/]", None
    except OSError as e:
        return f"[red]Error counting lines in file:[/] {str(e)}", None

@tool
def search_file_content(path=".", filename=None, search_term=None):
    """
    Search for text content in a file. Returns matching lines with numbers.
    Args:
        path: Directory path containing the file
        filename: Name of file to search
        search_term: Text to search for (case-insensitive)
    Returns:
        Tuple of (result message, list of matching lines)
    """
    if not filename:
        return "[red]No filename provided.[/]", []
    if not search_term:
        return "[red]No search term provided.[/]", []

    full_path = os.path.join(path, filename)
    if not os.path.isfile(full_path):
        return f"[red]File not found:[/] {full_path}", []

    try:
        matches = []
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                if search_term.lower() in line.lower():
                    matches.append(f"Line {line_num}: {line.strip()}")

        if not matches:
            return f"[yellow]No matches found for '{search_term}' in {filename}[/]", []
        
        console.print(f"[green]Found {len(matches)} match(es) for '{search_term}' in {filename}:[/]")
        for match in matches:
            console.print(match)
            
        return f"Searched for '{search_term}' in {filename}", matches
    except Exception as e:
        return f"[red]Error searching file:[/] {str(e)}", []

@tool
def list_directories(path="."):
    """List all directories (not files) in the given directory. Returns a string summary and a list of directory names."""
    if not os.path.isdir(path):
        return f"[red]Directory not found:[/] {path}", []
    table = Table(title=f"Directories in {path}")
    table.add_column("Directory", style="cyan")
    dirs = [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
    for directory in dirs:
        table.add_row(directory)
    console.print(table)
    return f"[green]Directories in {path}: {', '.join(dirs)}[/]", dirs

@tool
def get_file_metadata(path=".", filename=None, attribute="all"):
    """Display metadata (size, creation date, modification date, permissions) for a file. Specify attribute ('size', 'creation_time', 'modification_time', 'permissions', or 'all') to filter output. Returns a string summary and None."""
    if not filename:
        return "[red]No filename provided.[/]", None
    full = os.path.join(path, filename)
    if not os.path.isfile(full):
        return f"[red]File not found:[/] {full}", None
    try:
        stats = os.stat(full)
        size_bytes = stats.st_size
        if size_bytes < 1024:
            size_str = f"{size_bytes} bytes"
        elif size_bytes < 1024 * 1024:
            size_str = f"{size_bytes / 1024:.2f} KB"
        else:
            size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
        creation_time = datetime.datetime.fromtimestamp(stats.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
        modification_time = datetime.datetime.fromtimestamp(stats.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        permissions = oct(stats.st_mode & 0o777)[2:]
        
        metadata = {
            "size": size_str,
            "creation_time": creation_time,
            "modification_time": modification_time,
            "permissions": permissions
        }
        
        if attribute != "all" and attribute not in metadata:
            return f"[red]Invalid metadata attribute: {attribute}. Use 'size', 'creation_time', 'modification_time', 'permissions', or 'all'.[/]", None
        
        if attribute != "all":
            value = metadata[attribute]
            return f"[green]{attribute.capitalize()} for {full}: {value}[/]", None
        
        table = Table(title=f"Metadata for {full}")
        table.add_column("Attribute", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Size", size_str)
        table.add_row("Creation Time", creation_time)
        table.add_row("Modification Time", modification_time)
        table.add_row("Permissions", permissions)
        console.print(table)
        return f"[green]Metadata displayed for {full}[/]", None
    except OSError as e:
        return f"[red]Error getting file metadata:[/] {str(e)}", None

def normalize_path(path: str) -> str:
    """Normalize a path, handling relative paths and Windows drive letters. Returns the normalized path."""
    import platform
    import os
    
    lower_path = path.lower().strip()
    # Handle relative path aliases
    if lower_path in ("previous directory", "parent directory", ".."):
        return ".."
    if lower_path in ("previous to previous directory", "two levels up", "../.."):
        return "../.."
    
    # Handle Windows drive letters (e.g., 'C:', 'D:', 'C:\\')
    if platform.system() == "Windows":
        if re.match(r'^[a-zA-Z]:$', lower_path):  # Matches 'C:', 'D:'
            return f"{path.rstrip(':')}\\"
        if re.match(r'^[a-zA-Z]:\\$', lower_path):  # Matches 'C:\', 'D:\'
            return path
    
    # Normalize path to absolute, resolving any relative components
    try:
        normalized = os.path.abspath(path)
        return normalized
    except OSError:
        return path

def generate_tools_doc():
    tool_docs = []
    for name, info in TOOL_REGISTRY.items():
        doc = info["doc"] or "No description."
        sig = info["signature"]
        tool_docs.append(f"- {name}{sig}: {doc}")
    return "Available tools:\n" + "\n".join(tool_docs)

def print_available_tools():
    console.rule("[bold green]🛠️ Available Tools")
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
You are an AI agent that chooses tools to execute based on a user's command, handling both single-step and multi-step tasks to achieve a final solution.

Available tools:
{{AVAILABLE_TOOLS}}

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
Choose appropriate validation based on operation type:
- After create_file → use file_exists to confirm creation (if needed)
- After rename_file → use file_exists on NEW filename to confirm rename (if needed) 
- After delete_file → use file_exists to confirm file gone (if needed)
- After add_content_to_file → use view_file to verify content (if needed)
- After copy_file → use file_exists on destination to confirm copy (if needed)
- After move_file → use file_exists on destination and check source gone (if needed)
- After create_directory → check directory exists with os.path.isdir (if needed)
- After delete_directory → check directory gone with os.path.isdir (if needed)
- After replace_text_in_file → use view_file to verify content (if needed)
- After count_lines_in_file → no validation needed
- After list_directories → no validation needed
- After get_file_metadata → no validation 
- After check_os -> no validation
- After get_root_directory -> no validation
- After get_command_line_directory -> no validation
- After system_resources -> no validation
- Only validate when critical or when command specifically requests verification
</instruction>

<instruction>
Handle errors gracefully:
- If tool says "already exists", treat as SUCCESS and move to next step
- If tool fails or user cancels deletion (e.g., 'Deletion cancelled' from delete_file or delete_directory), continue to next operation unless it's critical
- Never repeat successful operations
- If command unclear, return {{"tool": "done", "args": {{}}, "done": true}}
</instruction>

<instruction>
For delete_file and delete_directory:
- These tools prompt the user for confirmation (y/n)
- If the user responds with 'n' or provides no input, the tool returns a 'cancelled' message
- Treat 'cancelled' as a non-critical failure and proceed to the next operation in multi-step tasks
</instruction>
</instructions>

<examples>
<example>
Command: "create test.txt then add 'Hello' then rename to final.txt then find frequent word then list files"
Total operations: 5

Step 1: {{"tool": "create_file", "args": {{"filename": "test.txt", "content": ""}}, "done": false}}
Step 2: {{"tool": "add_content_to_file", "args": {{"filename": "test.txt", "content": "Hello"}}, "done": false}}
Step 3: {{"tool": "rename_file", "args": {{"filename": "test.txt", "new_filename": "final.txt"}}, "done": false}}
Step 4: {{"tool": "find_frequent_word", "args": {{"filename": "final.txt"}}, "done": false}}
Step 5: {{"tool": "list_files", "args": {{"path": "."}}, "done": true}}
</example>

<example>
Command: "delete old.txt then create new.txt with content 'backup data'"
Total operations: 2

Step 1: {{"tool": "delete_file", "args": {{"filename": "old.txt"}}, "done": false}}
Step 2: {{"tool": "create_file", "args": {{"filename": "new.txt", "content": "backup data"}}, "done": true}}
</example>

<example>
Command: "check if config.txt exists then view its content"
Total operations: 2

Step 1: {{"tool": "file_exists", "args": {{"filename": "config.txt"}}, "done": false}}
Step 2: {{"tool": "view_file", "args": {{"filename": "config.txt"}}, "done": true}}
</example>

<example>
Command: "create directory data then move file.txt to data then search for *.txt in data"
Total operations: 3

Step 1: {{"tool": "create_directory", "args": {{"path": "data"}}, "done": false}}
Step 2: {{"tool": "move_file", "args": {{"filename": "file.txt", "source_path": ".", "dest_path": "data"}}, "done": false}}
Step 3: {{"tool": "search_files_by_name", "args": {{"path": "data", "pattern": "*.txt"}}, "done": true}}
</example>

<example>
Command: "delete test.txt then create test.txt with 'Hello world' then get size of test.txt"
Total operations: 3

Step 1: {{"tool": "delete_file", "args": {{"filename": "test.txt"}}, "done": false}}
Step 2: {{"tool": "create_file", "args": {{"filename": "test.txt", "content": "Hello world"}}, "done": false}}
Step 3: {{"tool": "get_file_metadata", "args": {{"filename": "test.txt", "attribute": "size"}}, "done": true}}
</example>
<example>
Command: "list all files in C: directory"
Total operations: 1
Step 1: {{"tool": "list_files", "args": {{path": "C:\\"}}, "done": true}}
</example>
<example>
Command: "search for 'error' in log.txt"
Total operations: 1
Step 1: {{"tool": "search_file_content", "args": {{"filename": "log.txt", "search_term": "error"}}, "done": true}}
</example>
</examples>

Return ONLY valid JSON. No markdown, explanations, or extra text.
"""

def choose_tool(natural_language_input, conversation_history=None):
    if conversation_history is None:
        conversation_history = []
    
    current_dir = os.getcwd()
    system_content = (
        f"You are a tool-choosing assistant operating in a filesystem.\n"
        f"Your current working directory is: {current_dir}\n\n"
        f"{TOOLS_DOC}\n"
        f"Interpret relative paths like 'previous directory' as '..', "
         "'previous to previous directory' or 'two levels up' as '../..'.\n"
        f"Analyze the user's command to determine if it is a single-step or multi-step task.\n"
        f"For single-step tasks, execute the tool, validate with file_exists or os.path.isdir (for directories), and set done to true.\n"
        f"For multi-step tasks, execute tools sequentially, validate with file_exists or os.path.isdir, and set done to true only in the final validation step.\n"
        f"Match command keywords to tools (e.g., 'list' for list_files, 'delete' for delete_file, 'copy' for copy_file).\n"
        f"Use conversation history to track progress and avoid repeating actions unnecessarily.\n"
        f"Respond ONLY with a valid JSON object."
    )
    
    messages = [
        {"role": "system", "content": system_content},
        *conversation_history,
        {"role": "user", "content": f"User's request: {natural_language_input}"}
    ]
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
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
    console.rule("[bold blue]🔧 AI File Agent (Natural Language CLI)")

    if len(sys.argv) < 2:
        console.print("[yellow]Usage:[/] uv run file_agent.py 'your command here'")
        return

    user_input = " ".join(sys.argv[1:])

    if user_input.lower() == "list-tools":
        print_available_tools()
        return
    
    conversation_history = []
    max_iterations = 15
    last_tool = None
    validation_count = 0

    for _ in range(max_iterations):
        tool, args, done, history = choose_tool(user_input, conversation_history)
        
        if tool == "done":
            console.print("[green]Task completed.[/]")
            break
        
        if tool == last_tool and "not found" in conversation_history[-1]["content"].lower():
            console.print("[red]Task failed: Repeated action with no progress.[/]")
            conversation_history.append({"role": "assistant", "content": "Cannot proceed. Please check the file or clarify the command."})
            break

        if tool in TOOL_REGISTRY:
            tool_entry = TOOL_REGISTRY[tool]

            for key in ["path", "source_path", "dest_path"]:
                if key in args:
                    args[key] = normalize_path(args[key])
        
            try:
                func = tool_entry["function"]
                result, _ = func(**args)
                console.print(result)
                conversation_history = history + [{"role": "assistant", "content": result}]

                # Heuristics for marking completion or validation
                # ONLY mark done if user_input does NOT contain "and then"
                if tool in [
                    "view_file", "find_frequent_word", "search_file_content",
                    "search_files_by_name", "count_lines_in_file", "get_file_metadata"
                ]:
                    done = done or (" and then " not in user_input.lower())

                if tool in ["delete_file", "delete_directory", "file_exists", "create_directory"]:
                    if "cancelled" not in result.lower():
                        validation_count += 1

                if tool in ["delete_directory"] and "cancelled" in result.lower():
                    continue

            except Exception as e:
                console.print(f"[red]Error executing tool '{tool}': {e}[/]")
                break

        else:
            console.print(f"[red]Unknown tool:[/] {tool}")
            conversation_history = history + [{"role": "assistant", "content": f"Unknown tool: {tool}. Please clarify your command."}]
            done = True
            console.print("[green]Task completed.[/]")
            break
        
        last_tool = tool
        
        if done:
            console.print("[green]Task completed.[/]")
            break
        
        if validation_count > len(user_input.lower().split(" and then ")) + 1:
            console.print("[red]Task failed: Too many validation steps.[/]")
            break

if __name__ == "__main__":
    main()

