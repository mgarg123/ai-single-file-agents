# AI File Agent

**AI File Agent** is a command-line tool that allows users to manage files and directories using natural language commands. Powered by the Grok API from xAI, it interprets user inputs and executes file operations like listing, creating, deleting, and searching files, with support for both single-step and multi-step tasks. The agent is cross-platform, handling Windows, Linux, and macOS paths, and includes safety features like confirmation prompts for deletions.

## Features

- **Natural Language Interface**: Execute file operations using intuitive commands (e.g., "list files in my_folder", "create test.txt with content 'Hello'").
- **Cross-Platform Support**: Works on Windows, Linux, and macOS, with proper handling of paths (e.g., C:\ on Windows, / on Linux).
- **Multi-Step Commands**: Chain operations (e.g., "create my_folder then create file.txt in my_folder").
- **Safety Features**: Prompts for confirmation before deleting files or directories to prevent accidental data loss.
- **Rich Console Output**: Uses the rich library for formatted tables and colored output.
- **Extensible Tools**: Modular toolset with a decorator-based registry for easy addition of new functionalities.

## Tools

The agent provides the following tools for file and directory management:

- `list_files(path=".")`: Lists all files in the specified directory.
- `view_file(path=".", filename=None)`: Displays the contents of a file.
- `rename_file(path=".", filename=None, new_filename=None)`: Renames a file.
- `find_frequent_word(path=".", filename=None)`: Finds the most frequent word in a file.
- `create_file(path=".", filename=None, content=None)`: Creates a new file with optional content.
- `search_file_content(path=".", filename=None, keyword=None)`: Searches for a keyword in a file’s content.
- `delete_file(path=".", filename=None)`: Deletes a file after user confirmation.
- `file_exists(path=".", filename=None)`: Checks if a file exists.
- `add_content_to_file(path=".", filename=None, content=None, append=True)`: Adds content to a file (append or overwrite).
- `copy_file(source_path=".", filename=None, dest_path=".")`: Copies a file to a destination.
- `move_file(source_path=".", filename=None, dest_path=".")`: Moves a file to a destination.
- `create_directory(path=".")`: Creates a new directory.
- `delete_directory(path=".")`: Deletes an empty directory after user confirmation.
- `search_files_by_name(path=".", pattern=None)`: Searches for files by name using a pattern.
- `replace_text_in_file(path=".", filename=None, old_text=None, new_text=None)`: Replaces text in a file.
- `count_lines_in_file(path=".", filename=None)`: Counts the number of lines in a file.
- `list_directories(path=".")`: Lists all directories in the specified path.
- `get_file_metadata(path=".", filename=None, attribute="all")`: Displays file metadata (size, creation time, modification time, permissions).
- `check_os()`: Returns the current operating system details.
- `get_root_directory()`: Returns the topmost root directory (e.g., C:\ on Windows, / on Linux).
- `get_command_line_directory()`: Returns the absolute path of the script’s directory.
- `get_current_directory()`: Returns the absolute path of the current working directory.

## Installation

### Prerequisites

- Python 3.8+: Ensure Python is installed.
- `uv`: A Python package manager for managing dependencies and virtual environments.
- Groq API Key: Obtain an API key from xAI.

### Steps

1. **Clone the Repository**:
    ```bash
    git clone https://github.com/your-repo/ai-single-file-agents.git
    cd ai-single-file-agents
    cd file_agent.py
    ```

2. **Install Dependencies**: Use `uv` to set up a virtual environment and install dependencies:
    ```bash
    uv sync
    ```

    This installs required packages listed in `pyproject.toml`, including `rich`, `groq`, and others.

3. **Set Up the Groq API Key**: Replace the placeholder API key in `file_agent.py` with your actual key or add the GROQ_API_KEY in .env file in project root and move to next step:
    ```python
    groq_api_key = "your_grok_api_key_here"
    ```

    Alternatively, set it as an environment variable:
    ```bash
    export GROQ_API_KEY="your_grok_api_key_here"
    ```

4. **Add to PATH (Optional)**: To run `file_agent.py` from anywhere, add the project directory to your `PATH`:

    - **Linux/macOS**:
        ```bash
        export PATH="$PATH:/path/to/ai-single-file-agents"
        echo 'export PATH="$PATH:/path/to/ai-single-file-agents"' >> ~/.bashrc
        source ~/.bashrc
        ```

    - **Windows**:
        ```cmd
        setx PATH "%PATH%;C:\path\to\ai-single-file-agents"
        ```

## Usage

Run the agent using `uv` with a natural language command:

```bash
uv run file_agent.py "your command here"
```

### Examples

- **List Files**:
    ```bash
    uv run file_agent.py "list files in my_folder"
    ```
    Lists files in `my_folder`.

- **Create and Modify a File**:
    ```bash
    uv run file_agent.py "create test.txt with 'Hello World' then append '!' to test.txt"
    ```

- **Delete a File (with Confirmation)**:
    ```bash
    uv run file_agent.py "delete test.txt"
    ```

- **Multi-Step Command**:
    ```bash
    uv run file_agent.py "create directory data then move file.txt to data then list files in data"
    ```

- **Check System Info**:
    ```bash
    uv run file_agent.py "check os"
    ```

- **List Tools**:
    ```bash
    uv run file_agent.py "list-tools"
    ```

## Notes

- **Path Handling**: Supports Windows (C:\, D:) and Unix (/home/user) paths. Bare directory names (e.g., `my_folder`) are searched in the current and parent directories.
- **Error Handling**: Provides clear error messages and proceeds with multi-step tasks on non-critical failures.
- **Safety**: Deletion operations require user confirmation to prevent accidental data loss.

## Project Structure

```
sf-agents/
├── file_agent 
       ├── file_agent.py     # Main script with tools and CLI logic
       ├── README.md 
├── pyproject.toml    # Project metadata and dependencies
├── uv.lock           # Dependency lock file
├── README.md         # This file
└── .gitignore        # Git ignore file
```

## Contributing

Contributions are welcome! To add new tools or features:

1. Fork the repository.
2. Create a new branch:
    ```bash
    git checkout -b feature/new-tool
    ```
3. Add your tool to `file_agent.py` using the `@tool` decorator.
4. Update `TOOLS_DOC` in `file_agent.py` with new mappings and examples.
5. Submit a pull request.

## License

This project is licensed under the MIT License. See the LICENSE file for details.
