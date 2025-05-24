import os
import sys
import json
import re
import hashlib
import inspect
import datetime
from rich.console import Console
from rich.table import Table
from rich import box
from rich.tree import Tree
from rich.text import Text
from groq import Groq
from collections import Counter
import shutil
import psutil
import filecmp
import tempfile
import difflib # Added import for difflib
import base64 # Added import for base64

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
    """Check the current operating system.
    Returns:
        Tuple[str, None]: A string summary of the operating system and None.
    """
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
    """Returns system resource usage including free RAM and available disk space.
    Args:
        resource (str): The type of resource to check, either "RAM" or "DISK".
    Returns:
        Tuple[str, None]: A string summary of the resource usage and None.
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
    """Get the topmost root directory for the current operating system.
    Returns:
        Tuple[str, str]: A string summary and the root directory path.
    """
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
    """Get the absolute path of the directory from which the script is invoked.
    Returns:
        Tuple[str, str]: A string summary and the absolute path of the command-line directory.
    """
    import os
    import sys
    # Get the directory of the script being run (sys.argv[0] is the script path)
    script_path = os.path.abspath(sys.argv[0])
    script_dir = os.path.dirname(script_path)
    return f"[green]Command-line directory: {script_dir}[/]", script_dir

@tool
def list_files(path="."):
    """List all files (not directories) in the given directory.
    Args:
        path (str, optional): The directory to list files from. Defaults to ".".
    Returns:
        Tuple[str, list]: A string summary and a list of filenames.
    """
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
    """Show contents of a file in the given directory.
    Args:
        path (str, optional): The directory containing the file. Defaults to ".".
        filename (str): The name of the file to view.
    Returns:
        Tuple[str, None]: A string summary and None.
    """
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
    """Rename a file at the given path to the specified new filename.
    Args:
        path (str, optional): The directory containing the file. Defaults to ".".
        filename (str): The current name of the file to rename.
        new_filename (str): The new name for the file.
    Returns:
        Tuple[str, None]: A string summary and None.
    """
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
    """Find the most frequently repeated word in the specified file.
    Args:
        path (str, optional): The directory containing the file. Defaults to ".".
        filename (str): The name of the file to analyze.
    Returns:
        Tuple[str, None]: A string summary and None.
    """
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
    """Create a new file with the specified content in the given directory.
    Args:
        path (str, optional): The directory where the file will be created. Defaults to ".".
        filename (str): The name of the file to create.
        content (str, optional): The content to write to the file. Defaults to "".
    Returns:
        Tuple[str, None]: A string summary and None.
    """
    if not filename:
        return "[red]No filename provided.[/]", None
    if content is None:
        content = ""
    full = os.path.join(path, filename)
    
    if os.path.exists(full):
        console.print(f"[yellow]File '{full}' already exists. Overwrite? (y/n)[/]")
        response = input().strip().lower()
        if response != "y":
            return f"[yellow]File creation cancelled[/]", None
        # Explicitly remove existing file before creating new one
        try:
            os.remove(full)
        except OSError as e:
            return f"[red]Error removing existing file:[/] {str(e)}", None
    
    try:
        os.makedirs(path, exist_ok=True)
        with open(full, "w") as f:
            f.write(content)
        return f"[green]File created:[/] {full}", None
    except OSError as e:
        return f"[red]Error creating file:[/] {str(e)}", None

@tool
def delete_file(path=".", filename=None):
    """Delete the specified file in the given directory after user confirmation.
    Args:
        path (str, optional): The directory containing the file. Defaults to ".".
        filename (str): The name of the file to delete.
    Returns:
        Tuple[str, None]: A string summary and None.
    """
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
    """Check if a file exists in the given directory.
    Args:
        path (str, optional): The directory to check. Defaults to ".".
        filename (str): The name of the file to check for existence.
    Returns:
        Tuple[str, bool]: A string summary and a boolean indicating if the file exists.
    """
    if not filename:
        return "[red]No filename provided.[/]", None
    full = os.path.join(path, filename)
    exists = os.path.isfile(full)
    return f"[green]File {'exists' if exists else 'does not exist'}:[/] {full}", exists

@tool
def add_content_to_file(path=".", filename=None, content=None, append=True):
    """Add content to a file in the given directory.
    Args:
        path (str, optional): The directory containing the file. Defaults to ".".
        filename (str): The name of the file to add content to.
        content (str): The content to add.
        append (bool, optional): If True, appends content; if False, overwrites. Defaults to True.
    Returns:
        Tuple[str, None]: A string summary and None.
    """
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
def copy_file(source_path=".", filename=None, dest_path=".", dest_filename=None):
    """Copy a file from source_path to dest_path.
    Optionally, rename the file in the destination using dest_filename.
    Args:
        source_path (str, optional): The directory containing the source file. Defaults to ".".
        filename (str): The name of the file to copy.
        dest_path (str, optional): The destination directory. Defaults to ".".
        dest_filename (str, optional): The new name for the file in the destination. If None, uses original filename. Defaults to None.
    Returns:
        Tuple[str, None]: A string summary and None.
    """
    if not filename:
        return "[red]No filename provided.[/]", None
    
    source_full = os.path.join(normalize_path(source_path), filename)
    
    if not os.path.isfile(source_full):
        return f"[red]Source file not found:[/] {source_full}", None
    
    # Determine the final destination file path
    final_dest_filename = dest_filename if dest_filename is not None else filename
    dest_full = os.path.join(normalize_path(dest_path), final_dest_filename)

    try:
        os.makedirs(os.path.dirname(dest_full), exist_ok=True) # Ensure destination directory exists
        shutil.copy2(source_full, dest_full) # Use shutil.copy2 for robust copying
        return f"[green]File copied:[/] {source_full} → {dest_full}", None
    except OSError as e:
        return f"[red]Error copying file:[/] {str(e)}", None

@tool
def move_file(source_path=".", filename=None, dest_path="."):
    """Move a file from source_path to dest_path.
    Args:
        source_path (str, optional): The directory containing the source file. Defaults to ".".
        filename (str): The name of the file to move.
        dest_path (str, optional): The destination directory. Defaults to ".".
    Returns:
        Tuple[str, None]: A string summary and None.
    """
    if not filename:
        return "[red]No filename provided.[/]", None
    source_full = os.path.join(normalize_path(source_path), filename)
    dest_full = os.path.join(normalize_path(dest_path), filename)
    if not os.path.isfile(source_full):
        return f"[red]Source file not found:[/] {source_full}", None
    try:
        os.makedirs(os.path.dirname(dest_full), exist_ok=True) # Ensure destination directory exists
        os.rename(source_full, dest_full)
        return f"[green]File moved:[/] {source_full} → {dest_full}", None
    except OSError as e:
        return f"[red]Error moving file:[/] {str(e)}", None

@tool
def create_directory(path="."):
    """Create a new directory at the specified path.
    Args:
        path (str, optional): The path where the directory will be created. Defaults to ".".
    Returns:
        Tuple[str, None]: A string summary and None.
    """
    normalized_path = normalize_path(path)
    if os.path.exists(normalized_path):
        console.print(f"[yellow]Directory '{normalized_path}' already exists. Overwrite? (y/n)[/]")
        response = input().strip().lower()
        if response != "y":
            return f"[yellow]Directory creation cancelled[/]", None
        # Remove existing directory and contents
        try:
            shutil.rmtree(normalized_path)
        except OSError as e:
            return f"[red]Error removing existing directory:[/] {str(e)}", None
    
    try:
        os.makedirs(normalized_path, exist_ok=True)
        return f"[green]Directory created:[/] {normalized_path}", None
    except OSError as e:
        return f"[red]Error creating directory:[/] {str(e)}", None

@tool
def delete_directory(path="."):
    """Delete a directory at the specified path, even if it is not empty, after user confirmation.
    Args:
        path (str, optional): The path of the directory to delete. Defaults to ".".
    Returns:
        Tuple[str, None]: A string summary and None.
    """
    normalized_path = normalize_path(path)
    if not os.path.isdir(normalized_path):
        return f"[red]Directory not found:[/] {normalized_path}", None
    try:
        console.print(f"[yellow]Are you sure you want to delete the directory '{normalized_path}' and all of its contents? (y/n)[/]")
        response = input().strip().lower()
        if response != "y":
            return f"[yellow]Deletion of {normalized_path} cancelled.[/]", None
        shutil.rmtree(normalized_path)
        return f"[green]Directory and its contents deleted:[/] {normalized_path}", None
    except Exception as e:
        return f"[red]Error deleting directory:[/] {str(e)}", None

@tool
def search_files_by_name(path=".", pattern=None):
    """Search for files by name matching the pattern in the given directory.
    Args:
        path (str, optional): The directory to search in. Defaults to ".".
        pattern (str): The filename pattern to search for (e.g., "*.txt", "report?.*").
    Returns:
        Tuple[str, list]: A string summary and a list of matching filenames.
    """
    if not pattern:
        return "[red]No pattern provided.[/]", []
    normalized_path = normalize_path(path)
    if not os.path.isdir(normalized_path):
        return f"[red]Directory not found:[/] {normalized_path}", []
    try:
        pattern = pattern.replace("*", ".*").replace("?", ".")
        regex = re.compile(pattern, re.IGNORECASE)
        matches = [f for f in os.listdir(normalized_path) if os.path.isfile(os.path.join(normalized_path, f)) and regex.match(f)]
        if not matches:
            return f"[yellow]No files found matching '{pattern}' in {normalized_path}[/]", []
        table = Table(title=f"Files matching '{pattern}' in {normalized_path}")
        table.add_column("Filename", style="cyan")
        for match in matches:
            table.add_row(match)
        console.print(table)
        return f"[green]Found {len(matches)} file(s) matching '{pattern}' in {normalized_path}:[/] {', '.join(matches)}", matches
    except re.error as e:
        return f"[red]Invalid pattern:[/] {str(e)}", []

@tool
def replace_text_in_file(path=".", filename=None, old_text=None, new_text=None):
    """Replace all occurrences of old_text with new_text in the specified file.
    Args:
        path (str, optional): The directory containing the file. Defaults to ".".
        filename (str): The name of the file to modify.
        old_text (str): The text to be replaced.
        new_text (str): The text to replace with.
    Returns:
        Tuple[str, None]: A string summary and None.
    """
    if not filename:
        return "[red]No filename provided.[/]", None
    if not old_text:
        return "[red]No text to replace provided.[/]", None
    if new_text is None:
        return "[red]No replacement text provided.[/]", None
    full = os.path.join(normalize_path(path), filename)
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
    """Count the total number of lines in the specified file.
    Args:
        path (str, optional): The directory containing the file. Defaults to ".".
        filename (str): The name of the file to count lines in.
    Returns:
        Tuple[str, None]: A string summary and None.
    """
    if not filename:
        return "[red]No filename provided.[/]", None
    full = os.path.join(normalize_path(path), filename)
    if not os.path.isfile(full):
        return f"[red]File not found:[/] {full}", None
    try:
        with open(full, "r", encoding='utf-8', errors='ignore') as f:
            line_count = sum(1 for _ in f)
        return f"[green]File {full} contains {line_count} line(s)[/]", None
    except OSError as e:
        return f"[red]Error counting lines in file:[/] {str(e)}", None

@tool
def find_large_files(min_size_mb: float, path="."):
    """Find files larger than specified MB size in a directory (searches recursively).
    Args:
        min_size_mb (float): Minimum file size in megabytes to search for.
        path (str, optional): Directory path to search in. Defaults to ".".
    Returns:
        Tuple[str, list]: A string summary and a list of large files (path, size in MB).
    """
    import os
    try:
        min_bytes = min_size_mb * 1024 * 1024
        large_files = []
        normalized_path = normalize_path(path)
        
        for root, _, files in os.walk(normalized_path):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    size = os.path.getsize(file_path)
                    if size > min_bytes:
                        large_files.append((file_path, size / (1024*1024)))
                except OSError:
                    continue

        if not large_files:
            return f"[yellow]No files larger than {min_size_mb}MB found in {normalized_path}[/]", []

        # Create table with Rich
        table = Table(title=f"Files larger than {min_size_mb}MB in {normalized_path}", box=box.ROUNDED)
        table.add_column("File Path", style="cyan")
        table.add_column("Size (MB)", justify="right")
        
        for path, size in sorted(large_files, key=lambda x: -x[1]):
            table.add_row(path, f"{size:.2f}")
        
        console.print(table)
        return f"Found {len(large_files)} files larger than {min_size_mb}MB in {normalized_path}", large_files

    except Exception as e:
        return f"[red]Error searching for large files:[/] {str(e)}", []

@tool
def search_text_across_files(pattern: str, directory="."):
    """Search for a regex pattern across all text files in a directory (searches recursively).
    Args:
        pattern (str): Regular expression pattern to search for.
        directory (str, optional): Root directory to search from. Defaults to ".".
    Returns:
        Tuple[str, list]: A string summary and a list of matches with line numbers.
    """
    import os
    try:
        compiled_pattern = re.compile(pattern, re.IGNORECASE)
        matches = []
        normalized_directory = normalize_path(directory)
        
        for root, _, files in os.walk(normalized_directory):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    # Skip binary files
                    with open(file_path, 'rb') as f:
                        if b'\x00' in f.read(1024):
                            continue
                    
                    # Try to read as text
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line_num, line in enumerate(f, 1):
                            if compiled_pattern.search(line):
                                matches.append({
                                    'file': file_path,
                                    'line': line_num,
                                    'content': line.strip()
                                })
                except (OSError, UnicodeDecodeError):
                    continue

        if not matches:
            return f"[yellow]No matches for pattern '{pattern}' found in {normalized_directory}[/]", []

        # Create table with Rich
        table = Table(title=f"Matches for '{pattern}' in {normalized_directory}", box=box.ROUNDED)
        table.add_column("File", style="cyan")
        table.add_column("Line", justify="right")
        table.add_column("Content", style="green")
        
        for match in matches[:50]:  # Limit to top 50 matches
            table.add_row(
                match['file'], 
                str(match['line']), 
                match['content'][:100] + "..." if len(match['content']) > 100 else match['content']
            )
        
        console.print(table)
        extra = f"\n[yellow](Showing first 50 of {len(matches)} matches)[/]" if len(matches) > 50 else ""
        return f"Found {len(matches)} matches for pattern '{pattern}' in {normalized_directory}{extra}", matches

    except re.error as e:
        return f"[red]Invalid regex pattern:[/] {str(e)}", []
    except Exception as e:
        return f"[red]Error during search:[/] {str(e)}", []

@tool
def search_file_content(path=".", filename=None, search_term=None):
    """Search for text content in a file.
    Args:
        path (str, optional): Directory path containing the file. Defaults to ".".
        filename (str): Name of file to search.
        search_term (str): Text to search for (case-insensitive).
    Returns:
        Tuple[str, list]: A string summary and a list of matching lines.
    """
    if not filename:
        return "[red]No filename provided.[/]", []
    if not search_term:
        return "[red]No search term provided.[/]", []

    full_path = os.path.join(normalize_path(path), filename)
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
    """List all directories (not files) in the given directory.
    Args:
        path (str, optional): The directory to list directories from. Defaults to ".".
    Returns:
        Tuple[str, list]: A string summary and a list of directory names.
    """
    normalized_path = normalize_path(path)
    if not os.path.isdir(normalized_path):
        return f"[red]Directory not found:[/] {normalized_path}", []
    table = Table(title=f"Directories in {normalized_path}")
    table.add_column("Directory", style="cyan")
    dirs = [d for d in os.listdir(normalized_path) if os.path.isdir(os.path.join(normalized_path, d))]
    for directory in dirs:
        table.add_row(directory)
    console.print(table)
    return f"[green]Directories in {normalized_path}: {', '.join(dirs)}[/]", dirs

@tool
def find_duplicate_files(dir_path="."):
    """Find duplicate files by content hash in a directory (searches recursively).
    Args:
        dir_path (str, optional): Directory path to search in. Defaults to ".".
    Returns:
        Tuple[str, dict]: A string summary and a dictionary of duplicate groups (hash: [paths]).
    """
    import hashlib
    from collections import defaultdict
    
    try:
        hashes = defaultdict(list)
        normalized_dir_path = normalize_path(dir_path)
        for root, _, files in os.walk(normalized_dir_path):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.isfile(file_path):
                    try:
                        with open(file_path, "rb") as f:
                            file_hash = hashlib.md5(f.read()).hexdigest()
                        hashes[file_hash].append(file_path)
                    except OSError:
                        continue

        duplicates = {h: paths for h, paths in hashes.items() if len(paths) > 1}
        if not duplicates:
            return f"[yellow]No duplicate files found in {normalized_dir_path}[/]", []

        table = Table(title=f"Duplicate Files in {normalized_dir_path}", box=box.ROUNDED)
        table.add_column("Hash", style="cyan")
        table.add_column("Files", style="yellow")
        
        for hash_val, paths in duplicates.items():
            table.add_row(hash_val[:8], "\n".join(paths))
        
        console.print(table)
        return f"Found {len(duplicates)} groups of duplicate files in {normalized_dir_path}", duplicates
    except Exception as e:
        return f"[red]Error finding duplicates:[/] {str(e)}", []

@tool
def remove_duplicates(dir_path="."):
    """Auto-remove redundant file copies with user confirmation.
    Keeps the first file in each duplicate group and deletes others.
    Args:
        dir_path (str, optional): Directory path to search for and remove duplicates. Defaults to ".".
    Returns:
        Tuple[str, None]: A string summary and None.
    """
    try:
        # First find duplicates
        result, duplicates = find_duplicate_files(dir_path)
        if "No duplicate" in result:
            return result, None
            
        console.print("[yellow]WARNING: This will delete duplicate files, keeping only the first copy in each group.[/]")
        console.print("[yellow]Are you sure you want to continue? (y/n)[/]")
        response = input().strip().lower()
        if response != "y":
            return "[yellow]Duplicate removal cancelled[/]", None

        total_removed = 0
        for hash_group, files in duplicates.items():
            # Keep first file, delete others
            keeper = files[0]
            for file in files[1:]:
                try:
                    os.remove(file)
                    total_removed += 1
                    console.print(f"[green]Removed duplicate:[/] {file}")
                except OSError as e:
                    console.print(f"[red]Error removing {file}:[/] {str(e)}")

        return f"[green]Removed {total_removed} duplicate files, keeping originals intact[/]", None
    except Exception as e:
        return f"[red]Error removing duplicates:[/] {str(e)}", None

@tool
def get_file_metadata(path=".", filename=None, attribute="all"):
    """Display metadata (size, creation date, modification date, permissions) for a file.
    Args:
        path (str, optional): The directory containing the file. Defaults to ".".
        filename (str): The name of the file to get metadata for.
        attribute (str, optional): Specific metadata attribute to display ('size', 'creation_time', 'modification_time', 'permissions', or 'all'). Defaults to "all".
    Returns:
        Tuple[str, None]: A string summary and None.
    """
    if not filename:
        return "[red]No filename provided.[/]", None
    full = os.path.join(normalize_path(path), filename)
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

@tool
def change_directory(path: str):
    """Change the current working directory to the specified path.
    Args:
        path (str): The path to change the current working directory to.
    Returns:
        Tuple[str, str]: A string summary and the new current directory path.
    """
    normalized_path = normalize_path(path)
    if not os.path.isdir(normalized_path):
        return f"[red]Directory not found or inaccessible:[/] {normalized_path}", None
    try:
        os.chdir(normalized_path)
        new_cwd = os.getcwd()
        return f"[green]Changed directory to:[/] {new_cwd}", new_cwd
    except OSError as e:
        return f"[red]Error changing directory to {normalized_path}:[/] {str(e)}", None

@tool
def list_directory_tree(path: str = ".", max_depth: int = 3):
    """List the hierarchical structure of files and directories recursively up to a specified depth.
    Args:
        path (str, optional): The root directory to start listing from. Defaults to ".".
        max_depth (int, optional): The maximum depth to traverse (0 for current directory only, 1 for current + immediate children, etc.). Defaults to 3.
    Returns:
        Tuple[str, list]: A string summary and a list of paths in the tree.
    """
    normalized_path = normalize_path(path)
    if not os.path.isdir(normalized_path):
        return f"[red]Directory not found or inaccessible:[/] {normalized_path}", []

    tree_root = Tree(f"[bold blue]{normalized_path}[/]", guide_style="bold bright_blue")
    all_paths = []

    def build_tree(current_path, current_tree, current_depth):
        if current_depth > max_depth:
            return

        try:
            for entry in os.listdir(current_path):
                full_path = os.path.join(current_path, entry)
                all_paths.append(full_path)
                if os.path.isdir(full_path):
                    branch = current_tree.add(Text(entry, style="bold green") + "/")
                    build_tree(full_path, branch, current_depth + 1)
                elif os.path.isfile(full_path):
                    current_tree.add(Text(entry, style="cyan"))
        except OSError as e:
            current_tree.add(Text(f"[red]Error accessing {current_path}: {str(e)}[/]", style="red"))

    build_tree(normalized_path, tree_root, 0)
    console.print(tree_root)
    return f"[green]Directory tree for {normalized_path} displayed (max depth: {max_depth}).[/]", all_paths

@tool
def get_directory_size(path: str = "."):
    """Calculate the total size of a directory, including all its subdirectories and files.
    Args:
        path (str, optional): The directory path to calculate size for. Defaults to ".".
    Returns:
        Tuple[str, int]: A string summary and the total size in bytes.
    """
    normalized_path = normalize_path(path)
    if not os.path.isdir(normalized_path):
        return f"[red]Directory not found or inaccessible:[/] {normalized_path}", None

    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(normalized_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                # Skip symbolic links that point to non-existent files
                if not os.path.islink(fp):
                    try:
                        total_size += os.path.getsize(fp)
                    except OSError:
                        # Ignore files that cannot be accessed (e.g., permission denied)
                        continue
    except Exception as e:
        return f"[red]Error calculating directory size for {normalized_path}:[/] {str(e)}", None

    def format_size(size_bytes):
        if size_bytes < 1024:
            return f"{size_bytes} bytes"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    formatted_size = format_size(total_size)
    console.print(f"[green]Total size of directory '{normalized_path}': {formatted_size}[/]")
    return f"Total size of directory '{normalized_path}': {formatted_size}", total_size

@tool
def set_file_permissions(path: str = ".", filename: str = None, permissions: str = None):
    """Set file permissions (e.g., '755', '644') for a specified file after user confirmation.
    Args:
        path (str, optional): Directory path containing the file. Defaults to ".".
        filename (str): Name of the file to set permissions for.
        permissions (str): Octal string representing permissions (e.g., '755' for rwxr-xr-x).
    Returns:
        Tuple[str, None]: A string summary and None.
    """
    if not filename:
        return "[red]No filename provided.[/]", None
    if not permissions:
        return "[red]No permissions provided.[/]", None

    full_path = os.path.join(normalize_path(path), filename)
    if not os.path.isfile(full_path):
        return f"[red]File not found:[/] {full_path}", None

    try:
        # Convert octal string (e.g., '755') to integer (e.g., 0o755)
        mode = int(permissions, 8)
    except ValueError:
        return f"[red]Invalid permissions format: '{permissions}'. Please use an octal string like '755'.[/]", None

    try:
        current_permissions = oct(os.stat(full_path).st_mode & 0o777)[2:]
        console.print(f"[yellow]Current permissions for '{full_path}': {current_permissions}[/]")
        console.print(f"[yellow]Are you sure you want to change permissions to '{permissions}' for '{full_path}'? (y/n)[/]")
        response = input().strip().lower()
        if response != "y":
            return f"[yellow]Setting permissions for {full_path} cancelled.[/]", None

        os.chmod(full_path, mode)
        new_permissions = oct(os.stat(full_path).st_mode & 0o777)[2:]
        return f"[green]Permissions for {full_path} changed from {current_permissions} to {new_permissions}[/]", None
    except OSError as e:
        return f"[red]Error setting permissions for {full_path}:[/] {str(e)}", None
    except EOFError:
        return f"[red]No input provided. Setting permissions for {full_path} cancelled.[/]", None

@tool
def copy_directory(source_path: str, destination_path: str):
    """Copy an entire directory tree from source_path to destination_path.
    If destination_path already exists and is not empty, it will prompt for overwrite.
    Args:
        source_path (str): The path of the directory to copy.
        destination_path (str): The path where the directory should be copied to.
    Returns:
        Tuple[str, None]: A string summary and None.
    """
    normalized_source = normalize_path(source_path)
    normalized_dest = normalize_path(destination_path)

    if not os.path.isdir(normalized_source):
        return f"[red]Source directory not found or inaccessible:[/] {normalized_source}", None
    
    if os.path.exists(normalized_dest):
        if os.listdir(normalized_dest): # Check if directory is not empty
            console.print(f"[yellow]Destination directory '{normalized_dest}' exists and is not empty. Overwrite? (y/n)[/]")
            response = input().strip().lower()
            if response != "y":
                return f"[yellow]Directory copy cancelled[/]", None
            try:
                shutil.rmtree(normalized_dest) # Remove existing non-empty directory
                console.print(f"[yellow]Removed existing destination directory: {normalized_dest}[/]")
            except OSError as e:
                return f"[red]Error removing existing destination directory:[/] {str(e)}", None
        else:
            # If it exists but is empty, shutil.copytree will handle it, but we can make it explicit
            pass 

    try:
        shutil.copytree(normalized_source, normalized_dest)
        return f"[green]Directory copied:[/] {normalized_source} → {normalized_dest}", None
    except shutil.Error as e:
        return f"[red]Error copying directory:[/] {str(e)}", None
    except OSError as e:
        return f"[red]Error copying directory:[/] {str(e)}", None
    except EOFError:
        return f"[red]No input provided. Directory copy cancelled.[/]", None

@tool
def move_directory(source_path: str, destination_path: str):
    """Move an entire directory from source_path to destination_path.
    If destination_path already exists, it will prompt for overwrite.
    Args:
        source_path (str): The path of the directory to move.
        destination_path (str): The path where the directory should be moved to.
    Returns:
        Tuple[str, None]: A string summary and None.
    """
    normalized_source = normalize_path(source_path)
    normalized_dest = normalize_path(destination_path)

    if not os.path.isdir(normalized_source):
        return f"[red]Source directory not found or inaccessible:[/] {normalized_source}", None
    
    if os.path.exists(normalized_dest):
        console.print(f"[yellow]Destination '{normalized_dest}' already exists. Overwrite? (y/n)[/]")
        response = input().strip().lower()
        if response != "y":
            return f"[yellow]Directory move cancelled[/]", None
        try:
            if os.path.isdir(normalized_dest):
                shutil.rmtree(normalized_dest)
            else:
                os.remove(normalized_dest)
            console.print(f"[yellow]Removed existing destination: {normalized_dest}[/]")
        except OSError as e:
            return f"[red]Error removing existing destination:[/] {str(e)}", None

    try:
        shutil.move(normalized_source, normalized_dest)
        return f"[green]Directory moved:[/] {normalized_source} → {normalized_dest}", None
    except shutil.Error as e:
        return f"[red]Error moving directory:[/] {str(e)}", None
    except OSError as e:
        return f"[red]Error moving directory:[/] {str(e)}", None
    except EOFError:
        return f"[red]No input provided. Directory move cancelled.[/]", None

@tool
def get_file_hash(filename: str, path: str = ".", algorithm: str = 'md5'):
    """Calculate the cryptographic hash of a specified file.
    Args:
        filename (str): The name of the file to hash.
        path (str, optional): The directory path containing the file. Defaults to ".".
        algorithm (str, optional): The hashing algorithm to use ('md5', 'sha1', 'sha256', 'sha512'). Defaults to 'md5'.
    Returns:
        Tuple[str, str]: A string summary and the hash value.
    """
    full_path = os.path.join(normalize_path(path), filename)
    if not os.path.isfile(full_path):
        return f"[red]File not found:[/] {full_path}", None

    hash_algorithms = {
        'md5': hashlib.md5,
        'sha1': hashlib.sha1,
        'sha256': hashlib.sha256,
        'sha512': hashlib.sha512
    }

    if algorithm.lower() not in hash_algorithms:
        return f"[red]Invalid hashing algorithm: '{algorithm}'. Choose from {', '.join(hash_algorithms.keys())}.[/]", None

    hasher = hash_algorithms[algorithm.lower()]()
    try:
        with open(full_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        file_hash = hasher.hexdigest()
        console.print(f"[green]Hash ({algorithm.upper()}) for '{full_path}': {file_hash}[/]")
        return f"Hash ({algorithm.upper()}) for '{full_path}': {file_hash}", file_hash
    except OSError as e:
        return f"[red]Error reading file for hashing:[/] {str(e)}", None

@tool
def create_archive(source_path: str, destination_directory: str = ".", archive_name: str = None, format: str = 'zip'):
    """Create an archive (e.g., zip, tar) from a file or directory.
    Args:
        source_path (str): The path to the file or directory to archive.
        destination_directory (str, optional): The directory where the archive file will be created. Defaults to ".".
        archive_name (str, optional): The base name of the archive file (e.g., 'my_archive'). If None, defaults to the base name of the source_path. The format extension will be added automatically. Defaults to None.
        format (str, optional): The archive format ('zip', 'tar', 'gztar', 'bztar', 'xztar'). Defaults to 'zip'.
    Returns:
        Tuple[str, str]: A string summary and the path to the created archive.
    """
    normalized_source = normalize_path(source_path)
    normalized_dest_dir = normalize_path(destination_directory)
    
    if not os.path.exists(normalized_source):
        return f"[red]Source path not found:[/] {normalized_source}", None
    
    if not os.path.isdir(normalized_dest_dir):
        try:
            os.makedirs(normalized_dest_dir, exist_ok=True)
        except OSError as e:
            return f"[red]Error creating destination directory '{normalized_dest_dir}':[/] {str(e)}", None

    if archive_name is None:
        archive_name = os.path.basename(normalized_source)

    try:
        root_dir_for_archive = os.path.dirname(normalized_source)
        base_dir_for_archive = os.path.basename(normalized_source)

        full_archive_base_name = os.path.join(normalized_dest_dir, archive_name)

        archive_full_path = shutil.make_archive(
            full_archive_base_name,
            format,
            root_dir=root_dir_for_archive,
            base_dir=base_dir_for_archive
        )
        console.print(f"[green]Archive created:[/] {archive_full_path}")
        return f"Archive created: {archive_full_path}", archive_full_path
    except ValueError as e:
        return f"[red]Invalid archive format or path issue:[/] {str(e)}", None
    except shutil.Error as e:
        return f"[red]Error creating archive:[/] {str(e)}", None
    except Exception as e:
        return f"[red]An unexpected error occurred during archiving:[/] {str(e)}", None

@tool
def extract_archive(archive_path: str, destination_path: str = "."):
    """Extract the contents of an archive file to a specified directory.
    Args:
        archive_path (str): The path to the archive file (e.g., 'my_archive.zip').
        destination_path (str, optional): The directory where the contents should be extracted. Defaults to ".".
    Returns:
        Tuple[str, str]: A string summary and the destination path.
    """
    normalized_archive = normalize_path(archive_path)
    normalized_dest = normalize_path(destination_path)

    if not os.path.isfile(normalized_archive):
        return f"[red]Archive file not found:[/] {normalized_archive}", None
    
    if not os.path.isdir(normalized_dest):
        try:
            os.makedirs(normalized_dest, exist_ok=True)
        except OSError as e:
            return f"[red]Error creating destination directory '{normalized_dest}':[/] {str(e)}", None

    try:
        shutil.unpack_archive(normalized_archive, normalized_dest)
        console.print(f"[green]Archive extracted:[/] {normalized_archive} → {normalized_dest}[/]")
        return f"Archive extracted: {normalized_archive} to {normalized_dest}", normalized_dest
    except shutil.ReadError:
        return f"[red]Error: Archive format not recognized or file is corrupted:[/] {normalized_archive}", None
    except Exception as e:
        return f"[red]Error extracting archive:[/] {str(e)}", None

@tool
def compare_files(file1_path: str, file2_path: str):
    """Compare the content of two files.
    Args:
        file1_path (str): The path to the first file.
        file2_path (str): The path to the second file.
    Returns:
        Tuple[str, bool]: A string summary and a boolean indicating if they are identical.
    """
    normalized_file1 = normalize_path(file1_path)
    normalized_file2 = normalize_path(file2_path)

    if not os.path.isfile(normalized_file1):
        return f"[red]File not found:[/] {normalized_file1}", False
    if not os.path.isfile(normalized_file2):
        return f"[red]File not found:[/] {normalized_file2}", False

    try:
        are_identical = filecmp.cmp(normalized_file1, normalized_file2, shallow=False)
        if are_identical:
            result_msg = f"[green]Files '{normalized_file1}' and '{normalized_file2}' are identical.[/]"
        else:
            result_msg = f"[yellow]Files '{normalized_file1}' and '{normalized_file2}' are different.[/]"
        console.print(result_msg)
        return result_msg, are_identical
    except Exception as e:
        return f"[red]Error comparing files:[/] {str(e)}", False

@tool
def create_temp_file(suffix: str = '', prefix: str = 'tmp', directory: str = None):
    """Create a temporary file. The file is created in a secure manner.
    Args:
        suffix (str, optional): The suffix for the file name (e.g., '.txt'). Defaults to ''.
        prefix (str, optional): The prefix for the file name (e.g., 'my_temp_'). Defaults to 'tmp'.
        directory (str, optional): The directory where the temporary file should be created. If None, uses system default temp directory. Defaults to None.
    Returns:
        Tuple[str, str]: A string summary and the absolute path to the created temporary file.
    """
    normalized_directory = normalize_path(directory) if directory else None
    try:
        # NamedTemporaryFile creates a file that is automatically deleted when closed
        # We need to keep it open to get its name, then close it, and return the name.
        # The user/agent is responsible for writing to it and deleting it later.
        # Using mkstemp for more control over deletion.
        fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=normalized_directory)
        os.close(fd) # Close the file descriptor immediately
        console.print(f"[green]Temporary file created:[/] {path}[/]")
        return f"Temporary file created: {path}", path
    except Exception as e:
        return f"[red]Error creating temporary file:[/] {str(e)}", None

@tool
def create_temp_directory(prefix: str = 'tmp', directory: str = None):
    """Create a temporary directory. The directory is created in a secure manner.
    Args:
        prefix (str, optional): The prefix for the directory name (e.g., 'my_temp_dir_'). Defaults to 'tmp'.
        directory (str, optional): The directory where the temporary directory should be created. If None, uses system default temp directory. Defaults to None.
    Returns:
        Tuple[str, str]: A string summary and the absolute path to the created temporary directory.
    """
    normalized_directory = normalize_path(directory) if directory else None
    try:
        path = tempfile.mkdtemp(prefix=prefix, dir=normalized_directory)
        console.print(f"[green]Temporary directory created:[/] {path}[/]")
        return f"Temporary directory created: {path}", path
    except Exception as e:
        return f"[red]Error creating temporary directory:[/] {str(e)}", None

@tool
def empty_cleanup(path: str = '.', delete_empty_dirs: bool = False, delete_empty_files: bool = False):
    """Find and optionally delete empty files and/or empty directories within a specified path (recursively).
    Args:
        path (str, optional): The root directory to start cleanup from. Defaults to ".".
        delete_empty_dirs (bool, optional): If True, empty directories will be deleted after confirmation. Defaults to False.
        delete_empty_files (bool, optional): If True, empty files will be deleted after confirmation. Defaults to False.
    Returns:
        Tuple[str, Tuple[list, list]]: A string summary and a tuple containing lists of deleted files and deleted directories.
    """
    normalized_path = normalize_path(path)
    if not os.path.isdir(normalized_path):
        return f"[red]Directory not found or inaccessible:[/] {normalized_path}", ([], [])

    found_empty_files = []
    found_empty_dirs = []
    deleted_files = []
    deleted_dirs = []

    # First pass: find empty files and directories
    for root, dirs, files in os.walk(normalized_path, topdown=False): # topdown=False for deleting empty dirs correctly
        for file in files:
            file_path = os.path.join(root, file)
            try:
                if os.path.isfile(file_path) and os.path.getsize(file_path) == 0:
                    found_empty_files.append(file_path)
            except OSError:
                continue # Skip inaccessible files

        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            try:
                if os.path.isdir(dir_path) and not os.listdir(dir_path):
                    found_empty_dirs.append(dir_path)
            except OSError:
                continue # Skip inaccessible directories

    summary_messages = []

    # Handle empty files
    if found_empty_files:
        console.print(f"[yellow]Found {len(found_empty_files)} empty file(s) in '{normalized_path}':[/]")
        for f in found_empty_files:
            console.print(f"- {f}")
        if delete_empty_files:
            console.print(f"[yellow]Are you sure you want to delete these {len(found_empty_files)} empty file(s)? (y/n)[/]")
            response = input().strip().lower()
            if response == "y":
                for f in found_empty_files:
                    try:
                        os.remove(f)
                        deleted_files.append(f)
                        console.print(f"[green]Deleted empty file:[/] {f}")
                    except OSError as e:
                        console.print(f"[red]Error deleting empty file {f}:[/] {str(e)}")
                summary_messages.append(f"Deleted {len(deleted_files)} empty file(s).")
            else:
                summary_messages.append(f"Deletion of {len(found_empty_files)} empty file(s) cancelled.")
        else:
            summary_messages.append(f"Found {len(found_empty_files)} empty file(s). Deletion not requested.")
    else:
        summary_messages.append("No empty files found.")

    # Handle empty directories
    if found_empty_dirs:
        console.print(f"[yellow]Found {len(found_empty_dirs)} empty director(y/ies) in '{normalized_path}':[/]")
        for d in found_empty_dirs:
            console.print(f"- {d}")
        if delete_empty_dirs:
            console.print(f"[yellow]Are you sure you want to delete these {len(found_empty_dirs)} empty director(y/ies)? (y/n)[/]")
            response = input().strip().lower()
            if response == "y":
                for d in found_empty_dirs:
                    try:
                        os.rmdir(d) # rmdir only works if directory is truly empty
                        deleted_dirs.append(d)
                        console.print(f"[green]Deleted empty directory:[/] {d}")
                    except OSError as e:
                        console.print(f"[red]Error deleting empty directory {d}:[/] {str(e)}")
                summary_messages.append(f"Deleted {len(deleted_dirs)} empty director(y/ies).")
            else:
                summary_messages.append(f"Deletion of {len(found_empty_dirs)} empty director(y/ies) cancelled.")
        else:
            summary_messages.append(f"Found {len(found_empty_dirs)} empty director(y/ies). Deletion not requested.")
    else:
        summary_messages.append("No empty directories found.")

    final_summary = "[green]Cleanup complete:[/]\n" + "\n".join(summary_messages)
    console.print(final_summary)
    return final_summary, (deleted_files, deleted_dirs)

@tool
def read_file_segment(path=".", filename=None, start_line: int = 1, end_line: int = None, num_lines: int = None):
    """Read a specific segment (lines) from a file.
    Args:
        path (str, optional): The directory containing the file. Defaults to ".".
        filename (str): The name of the file to read.
        start_line (int, optional): The 1-based starting line number. Defaults to 1.
        end_line (int, optional): The 1-based ending line number (inclusive). If None, reads to end. Defaults to None.
        num_lines (int, optional): If provided, reads this many lines from start_line, or the last N lines if start_line is not specified (i.e., reads from end). Overrides end_line if both are present. Defaults to None.
    Returns:
        Tuple[str, list]: A string summary and a list of the read lines.
    """
    if not filename:
        return "[red]No filename provided.[/]", []
    full_path = os.path.join(normalize_path(path), filename)
    if not os.path.isfile(full_path):
        return f"[red]File not found:[/] {full_path}", []

    try:
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
        
        total_lines = len(all_lines)
        
        if num_lines is not None:
            if start_line == 1: # Read first N lines
                lines_to_read = all_lines[:num_lines]
                summary_msg = f"Read first {len(lines_to_read)} lines from {full_path}."
            else: # Read last N lines
                lines_to_read = all_lines[-num_lines:]
                summary_msg = f"Read last {len(lines_to_read)} lines from {full_path}."
        else:
            # Adjust to 0-based indexing
            start_idx = max(0, start_line - 1)
            end_idx = total_lines if end_line is None else min(total_lines, end_line)
            
            if start_idx >= total_lines:
                return f"[yellow]Start line {start_line} is beyond file end. No content read.[/]", []
            
            lines_to_read = all_lines[start_idx:end_idx]
            summary_msg = f"Read lines {start_line} to {end_line if end_line is not None else 'end'} from {full_path}."

        if not lines_to_read:
            return f"[yellow]No content found in the specified segment of {full_path}.[/]", []

        console.rule(f"[bold green]Content from {full_path} (Lines {start_line}-{end_line if end_line else 'end'})[/]")
        for line in lines_to_read:
            console.print(line.strip())
        
        return summary_msg, [line.strip() for line in lines_to_read]
    except Exception as e:
        return f"[red]Error reading file segment:[/] {str(e)}", []

@tool
def insert_content_at_line(path=".", filename=None, content: str = "", line_number: int = 1):
    """Insert content at a specific line number in a file.
    Args:
        path (str, optional): The directory containing the file. Defaults to ".".
        filename (str): The name of the file to modify.
        content (str): The content to insert.
        line_number (int, optional): The 1-based line number where content should be inserted. If 1, inserts at beginning. If greater than total lines, appends. Defaults to 1.
    Returns:
        Tuple[str, None]: A string summary and None.
    """
    if not filename:
        return "[red]No filename provided.[/]", None
    full_path = os.path.join(normalize_path(path), filename)
    if not os.path.isfile(full_path):
        return f"[red]File not found:[/] {full_path}", None

    try:
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # Adjust to 0-based index
        insert_idx = max(0, line_number - 1)
        
        # Ensure content ends with a newline if it's not empty and doesn't already
        if content and not content.endswith('\n'):
            content += '\n'

        if insert_idx >= len(lines):
            # If line_number is beyond current end, append
            lines.append(content)
            action = "appended to"
        else:
            lines.insert(insert_idx, content)
            action = f"inserted at line {line_number} in"
        
        with open(full_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        return f"[green]Content {action} {full_path}.[/]", None
    except Exception as e:
        return f"[red]Error inserting content into file:[/] {str(e)}", None

@tool
def delete_lines_from_file(path=".", filename=None, start_line: int = None, end_line: int = None, pattern: str = None):
    """Delete lines from a file based on a line range or a regex pattern.
    Args:
        path (str, optional): The directory containing the file. Defaults to ".".
        filename (str): The name of the file to modify.
        start_line (int, optional): The 1-based starting line number for deletion (inclusive). Defaults to None.
        end_line (int, optional): The 1-based ending line number for deletion (inclusive). If None, deletes to end. Defaults to None.
        pattern (str, optional): A regex pattern. If provided, deletes all lines matching this pattern. Overrides line range if both are present. Defaults to None.
    Returns:
        Tuple[str, None]: A string summary and None.
    """
    if not filename:
        return "[red]No filename provided.[/]", None
    if start_line is None and end_line is None and pattern is None:
        return "[red]No line range or pattern provided for deletion.[/]", None

    full_path = os.path.join(normalize_path(path), filename)
    if not os.path.isfile(full_path):
        return f"[red]File not found:[/] {full_path}", None

    try:
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        new_lines = []
        deleted_count = 0

        if pattern:
            compiled_pattern = re.compile(pattern)
            for line in lines:
                if compiled_pattern.search(line):
                    deleted_count += 1
                else:
                    new_lines.append(line)
            summary_msg = f"Deleted {deleted_count} line(s) matching pattern '{pattern}' from {full_path}."
        else:
            # Adjust to 0-based indexing for line range
            start_idx = max(0, (start_line or 1) - 1)
            end_idx = len(lines) if end_line is None else min(len(lines), end_line)
            
            if start_idx >= len(lines):
                return f"[yellow]Start line {start_line} is beyond file end. No lines deleted.[/]", None

            for i, line in enumerate(lines):
                if not (start_idx <= i < end_idx):
                    new_lines.append(line)
                else:
                    deleted_count += 1
            
            summary_msg = f"Deleted {deleted_count} line(s) from line {start_line or 1} to {end_line if end_line is not None else 'end'} in {full_path}."
        
        with open(full_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        
        return f"[green]{summary_msg}[/]", None
    except re.error as e:
        return f"[red]Invalid regex pattern:[/] {str(e)}", None
    except Exception as e:
        return f"[red]Error deleting lines from file:[/] {str(e)}", None

@tool
def diff_files(file1_path: str, file2_path: str):
    """Show the line-by-line differences between two text files.
    Args:
        file1_path (str): The path to the first file.
        file2_path (str): The path to the second file.
    Returns:
        Tuple[str, list]: A string summary and a list of diff lines.
    """
    normalized_file1 = normalize_path(file1_path)
    normalized_file2 = normalize_path(file2_path)

    if not os.path.isfile(normalized_file1):
        return f"[red]File not found:[/] {normalized_file1}", []
    if not os.path.isfile(normalized_file2):
        return f"[red]File not found:[/] {normalized_file2}", []

    try:
        with open(normalized_file1, 'r', encoding='utf-8', errors='ignore') as f1:
            lines1 = f1.readlines()
        with open(normalized_file2, 'r', encoding='utf-8', errors='ignore') as f2:
            lines2 = f2.readlines()

        d = difflib.Differ()
        diff = list(d.compare(lines1, lines2))

        if not diff:
            return f"[yellow]No differences found between '{normalized_file1}' and '{normalized_file2}'.[/]", []
        
        console.rule(f"[bold green]Differences between {normalized_file1} and {normalized_file2}[/]")
        for line in diff:
            if line.startswith('+'):
                console.print(f"[green]{line.strip()}[/]")
            elif line.startswith('-'):
                console.print(f"[red]{line.strip()}[/]")
            elif line.startswith('?'):
                console.print(f"[blue]{line.strip()}[/]")
            else:
                console.print(line.strip())
        
        return f"Differences between '{normalized_file1}' and '{normalized_file2}' displayed.", diff
    except Exception as e:
        return f"[red]Error generating diff:[/] {str(e)}", []

@tool
def encode_file_content(path=".", filename=None, encoding_format: str = 'base64'):
    """Encode the content of a file using a specified encoding format.
    Args:
        path (str, optional): The directory containing the file. Defaults to ".".
        filename (str): The name of the file to encode.
        encoding_format (str, optional): The encoding format ('base64'). Defaults to 'base64'.
    Returns:
        Tuple[str, str]: A string summary and the encoded content.
    """
    if not filename:
        return "[red]No filename provided.[/]", None
    full_path = os.path.join(normalize_path(path), filename)
    if not os.path.isfile(full_path):
        return f"[red]File not found:[/] {full_path}", None

    if encoding_format.lower() != 'base64':
        return f"[red]Unsupported encoding format: '{encoding_format}'. Only 'base64' is supported.[/]", None

    try:
        with open(full_path, 'rb') as f:
            raw_content = f.read()
        
        if encoding_format.lower() == 'base64':
            encoded_content = base64.b64encode(raw_content).decode('utf-8')
            summary_msg = f"Content of '{full_path}' encoded to Base64."
        else:
            return f"[red]Internal error: Unhandled encoding format '{encoding_format}'.[/]", None
        
        console.print(f"[green]{summary_msg}[/]")
        console.print(f"[cyan]Encoded content (first 100 chars):[/] {encoded_content[:100]}...")
        return summary_msg, encoded_content
    except Exception as e:
        return f"[red]Error encoding file content:[/] {str(e)}", None

@tool
def decode_file_content(path=".", filename=None, encoding_format: str = 'base64', output_filename: str = None):
    """Decode the content of an encoded file and optionally save it to a new file.
    Args:
        path (str, optional): The directory containing the encoded file. Defaults to ".".
        filename (str): The name of the file containing the encoded content.
        encoding_format (str, optional): The encoding format ('base64'). Defaults to 'base64'.
        output_filename (str, optional): The name of the file to save the decoded content to. If None, returns content as string. Defaults to None.
    Returns:
        Tuple[str, str]: A string summary and the decoded content (or path to output file).
    """
    if not filename:
        return "[red]No filename provided.[/]", None
    full_path = os.path.join(normalize_path(path), filename)
    if not os.path.isfile(full_path):
        return f"[red]File not found:[/] {full_path}", None

    if encoding_format.lower() != 'base64':
        return f"[red]Unsupported decoding format: '{encoding_format}'. Only 'base64' is supported.[/]", None

    try:
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            encoded_content = f.read()
        
        if encoding_format.lower() == 'base64':
            decoded_bytes = base64.b64decode(encoded_content)
            summary_msg = f"Content of '{full_path}' decoded from Base64."
        else:
            return f"[red]Internal error: Unhandled decoding format '{encoding_format}'.[/]", None
        
        if output_filename:
            output_full_path = os.path.join(normalize_path(path), output_filename)
            with open(output_full_path, 'wb') as f_out:
                f_out.write(decoded_bytes)
            console.print(f"[green]{summary_msg} Saved to '{output_full_path}'.[/]")
            return f"{summary_msg} Saved to '{output_full_path}'.", output_full_path
        else:
            decoded_content_str = decoded_bytes.decode('utf-8', errors='ignore')
            console.print(f"[green]{summary_msg}[/]")
            console.print(f"[cyan]Decoded content (first 100 chars):[/] {decoded_content_str[:100]}...")
            return summary_msg, decoded_content_str
    except base64.binascii.Error:
        return f"[red]Error: Content in '{full_path}' is not valid Base64 encoded data.[/]", None
    except Exception as e:
        return f"[red]Error decoding file content:[/] {str(e)}", None


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
    
    # Expand user home directory (e.g., ~ or ~user)
    path = os.path.expanduser(path)

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
For example when creating a new file with given filename we can call file_exist tool to see if file is already created with that name and so on.
If validation is not required for the given operation then don't do the validation.
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
        f"Also, interpret '~' or '~/Downloads' as the user's home directory or a path relative to it.\n"
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

            # Normalize paths for arguments that are paths
            # This is handled within each tool function for robustness, but keeping this for general args
            # for key in ["path", "source_path", "dest_path", "destination_directory", "archive_path"]:
            #     if key in args:
            #         args[key] = normalize_path(args[key])
        
            try:
                func = tool_entry["function"]
                result, _ = func(**args)
                console.print(result)
                conversation_history = history + [{"role": "assistant", "content": result}]

                # Heuristics for marking completion or validation
                # ONLY mark done if user_input does NOT contain "and then"
                if tool in [
                    "view_file", "find_frequent_word", "search_file_content",
                    "search_files_by_name", "count_lines_in_file", "get_file_metadata",
                    "get_directory_size", "list_directory_tree", "get_file_hash",
                    "compare_files", "create_temp_file", "create_temp_directory",
                    "read_file_segment", "diff_files", "encode_file_content", "decode_file_content" # Added new tools
                ]:
                    done = done or (" and then " not in user_input.lower())

                if tool in ["delete_file", "delete_directory", "file_exists", "create_directory", 
                            "set_file_permissions", "copy_directory", "move_directory", 
                            "create_archive", "extract_archive", "empty_cleanup",
                            "insert_content_at_line", "delete_lines_from_file"]: # Added new tools
                    if "cancelled" not in result.lower():
                        validation_count += 1

                if tool in ["delete_directory", "set_file_permissions", "copy_directory", "move_directory", "empty_cleanup"] and "cancelled" in result.lower(): # Added new tools
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
