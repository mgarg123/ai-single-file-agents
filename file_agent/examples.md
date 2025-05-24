# AI File Agent Examples

This document provides examples of how to use the AI File Agent via the command line using `uv run`.

To run a command, use the following format:

```bash
uv run file_agent.py 'your natural language command here'
```

Replace `'your natural language command here'` with the specific task you want the agent to perform.

## Listing Files and Directories

- List all files in the current directory:
```bash
uv run file_agent.py 'list all files'
```

- List all directories in the current directory:
```bash
uv run file_agent.py 'list all directories'
```

- List files in a specific directory (e.g., 'data'):
```bash
uv run file_agent.py 'list files in data directory'
```

- List directories in a specific directory (e.g., '../'):
```bash
uv run file_agent.py 'list directories in previous directory'
```

- List directory tree up to a certain depth (e.g., depth 2):
```bash
uv run file_agent.py 'list directory tree with max depth 2'
```

## File Operations

- View the content of a file (e.g., 'my_document.txt'):
```bash
uv run file_agent.py 'view content of my_document.txt'
```

- Create a new file (e.g., 'new_file.txt'):
```bash
uv run file_agent.py 'create a file named new_file.txt'
```

- Create a new file with content:
```bash
uv run file_agent.py 'create file report.txt with content "This is the report data."'
```

- Add content to an existing file (appends by default):
```bash
uv run file_agent.py 'add "More content here." to new_file.txt'
```

- Overwrite content in an existing file:
```bash
uv run file_agent.py 'add "This overwrites everything." to new_file.txt and do not append'
```

- Rename a file (e.g., 'old_name.txt' to 'new_name.txt'):
```bash
uv run file_agent.py 'rename old_name.txt to new_name.txt'
```

- Copy a file (e.g., 'source.txt' to 'destination/source_copy.txt'):
```bash
uv run file_agent.py 'copy source.txt to destination/source_copy.txt'
```

- Move a file (e.g., 'file_to_move.txt' to 'archive/'):
```bash
uv run file_agent.py 'move file_to_move.txt to archive directory'
```

- Delete a file (e.g., 'temp.log'):
```bash
uv run file_agent.py 'delete temp.log'
```

- Check if a file exists:
```bash
uv run file_agent.py 'check if config.yaml exists'
```

- Get metadata for a file (e.g., size, dates, permissions):
```bash
uv run file_agent.py 'get metadata for important_doc.pdf'
```

- Get a specific metadata attribute (e.g., size):
```bash
uv run file_agent.py 'get size of large_file.zip'
```

- Set file permissions (e.g., 'script.sh' to '755'):
```bash
uv run file_agent.py 'set permissions of script.sh to 755'
```

- Get the hash of a file (e.g., using SHA256):
```bash
uv run file_agent.py 'get sha256 hash of installer.exe'
```

- Compare two files:
```bash
uv run file_agent.py 'compare file1.txt and file2.txt'
```

## Directory Operations

- Create a new directory (e.g., 'backup'):
```bash
uv run file_agent.py 'create a directory called backup'
```

- Delete a directory (e.g., 'old_data'):
```bash
uv run file_agent.py 'delete directory old_data'
```

- Change the current working directory:
```bash
uv run file_agent.py 'change directory to /home/user/documents'
```

- Get the size of a directory:
```bash
uv run file_agent.py 'get size of the current directory'
```

- Copy a directory:
```bash
uv run file_agent.py 'copy directory source_folder to destination_folder'
```

- Move a directory:
```bash
uv run file_agent.py 'move directory temp_folder to archive/temp_folder'
```

## Searching and Finding

- Find the most frequent word in a file:
```bash
uv run file_agent.py 'find the most frequent word in article.txt'
```

- Search for files by name pattern (e.g., all `.log` files):
```bash
uv run file_agent.py 'search for files matching *.log'
```

- Search for files by name pattern in a specific directory:
```bash
uv run file_agent.py 'search for files matching report*.txt in the reports directory'
```

- Search for text content within a file:
```bash
uv run file_agent.py 'search for "error" in application.log'
```

- Search for a regex pattern across multiple files in a directory:
```bash
uv run file_agent.py 'search for pattern "def \w+\(" in the src directory'
```

- Find files larger than a certain size (e.g., 10 MB):
```bash
uv run file_agent.py 'find files larger than 10 MB'
```

- Find duplicate files in a directory:
```bash
uv run file_agent.py 'find duplicate files in the downloads folder'
```

## Cleanup and Temporary Items

- Remove duplicate files (keeps one copy):
```bash
uv run file_agent.py 'remove duplicate files in the current directory'
```

- Find empty files and directories:
```bash
uv run file_agent.py 'find empty files and directories'
```

- Delete empty files:
```bash
uv run file_agent.py 'delete empty files'
```

- Delete empty directories:
```bash
uv run file_agent.py 'delete empty directories'
```

- Delete both empty files and directories:
```bash
uv run file_agent.py 'delete empty files and directories'
```

- Create a temporary file:
```bash
uv run file_agent.py 'create a temporary file'
```

- Create a temporary directory:
```bash
uv run file_agent.py 'create a temporary directory'
```

## Archiving

- Create a zip archive of a file:
```bash
uv run file_agent.py 'create a zip archive of my_file.txt'
```

- Create a tar.gz archive of a directory:
```bash
uv run file_agent.py 'create a gztar archive of the project_folder'
```

- Extract an archive:
```bash
uv run file_agent.py 'extract archive backup.zip to the restore directory'
```

## System Information

- Check the current operating system:
```bash
uv run file_agent.py 'check my operating system'
```

- Check system resources (RAM and Disk):
```bash
uv run file_agent.py 'check system resources'
```

- Get the root directory:
```bash
uv run file_agent.py 'get the root directory'
```

- Get the command line directory:
```bash
uv run file_agent.py 'get the command line directory'
```

## Multi-step Commands

- Create a file, add content, then view it:
```bash
uv run file_agent.py 'create test.txt then add "Hello, world!" to test.txt then view test.txt'
```

- Create a directory, move a file into it, then list files in the new directory:
```bash
uv run file_agent.py 'create directory temp_dir and then move document.pdf to temp_dir and then list files in temp_dir'
```

- Find large files, then search for a term in one of them:
```bash
uv run file_agent.py 'find files larger than 50 MB then search for "configuration" in the largest file found'
```

- Delete a file, then create a new one with the same name and content:
```bash
uv run file_agent.py 'delete old_config.ini then create old_config.ini with content "[settings]\nkey=value"'
```

## Listing Available Tools

- See the list of all available tools and their descriptions:
```bash
uv run file_agent.py list-tools
```
