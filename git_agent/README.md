# AI Git Agent

**AI Git Agent** is a command-line tool that allows users to manage Git repositories using natural language commands. Powered by the Groq API, it interprets user inputs and executes Git operations like checking status, committing, branching, merging, and more, with support for both single-step and multi-step tasks. The agent includes safety features like confirmation prompts for destructive Git commands.

## Features

-   **Natural Language Interface**: Execute Git operations using intuitive commands (e.g., "show git status", "add all files then commit with message 'Initial commit'").
-   **Multi-Step Commands**: Chain operations (e.g., "create branch 'feature/new-feature' then checkout to it").
-   **Safety Features**: Prompts for confirmation before executing destructive Git commands like `git reset --hard`, `git clean`, `git revert`, `git rebase`, and `git branch -D`.
-   **Rich Console Output**: Uses the rich library for formatted tables and colored output for Git command results.
-   **Extensible Tools**: Modular toolset with a decorator-based registry for easy addition of new functionalities.

## Tools

The agent provides the following tools for Git repository management:

-   `git_status()`: Show the working tree status, including staged, unstaged, and untracked files, and branch information.
-   `git_add(files: str = '.')`: Add file contents to the index (stage files).
-   `git_commit(message: str = None)`: Record changes to the repository. If no message is provided, an AI will draft one based on staged changes.
-   `git_revert_last_commit()`: Undo the changes introduced by the last commit, creating a new commit that reverts them.
-   `git_create_branch(branch_name: str, base_branch: str = None)`: Create a new branch.
-   `git_fetch()`: Download objects and refs from another repository.
-   `git_pull(branch: str = 'main', remote: str = 'origin')`: Fetch from and integrate with another repository or a local branch.
-   `git_push(branch: str = 'main', remote: str = 'origin')`: Update remote refs along with associated objects.
-   `git_init()`: Create an empty Git repository or reinitialize an existing one.
-   `git_log(num_commits: int = 5)`: Show recent commit logs in a readable table format.
-   `git_checkout(branch_name: str)`: Switch branches or restore working tree files.
-   `git_diff(file_path: str = None)`: Show changes between commits, working tree and index, or between two branches, with formatted output.
-   `git_merge(branch_name: str, no_ff: bool = False)`: Integrate changes from one branch into the current branch.
-   `git_reset(mode: str = 'soft', target: str = 'HEAD')`: Undo changes by moving the HEAD pointer and optionally modifying the index and working directory.
-   `git_stash(action: str = 'save', message: str = None, stash_id: str = None)`: Temporarily save changes that are not ready to be committed.
-   `git_branch_delete(branch_name: str, force: bool = False)`: Delete a local branch.
-   `git_remote_add(name: str, url: str)`: Add a new remote repository.
-   `git_remote_remove(name: str)`: Remove a remote repository.
-   `git_clone(repo_url: str, directory: str = None)`: Clone a repository into a new directory.
-   `git_tag(tag_name: str, message: str = None, lightweight: bool = False)`: Create a tag to mark a specific point in history.
-   `git_show(commit_hash: str = 'HEAD')`: Show information about a Git object (commit, tree, blob, tag).
-   `git_list_branches(all_branches: bool = False, remote_only: bool = False)`: List all local and remote branches.
-   `git_rebase(base_branch: str)`: Reapply commits on top of another base tip, creating a linear history.
-   `git_blame(filename: str)`: Show what revision and author last modified each line of a file.
-   `git_reflog()`: Manage and show the reflog, which records updates to the tip of branches and other references.
-   `git_restore(file_path: str = '.', staged: bool = False, source_commit: str = None)`: Restore working tree files.
-   `git_cherry_pick(commit_hash: str)`: Apply the changes introduced by some existing commits.
-   `git_clean(force: bool, directories: bool = False)`: Remove untracked files from the working directory.
-   `git_list_remotes(verbose: bool = False)`: List the remote repositories you have configured.
-   `git_config_get(key: str, scope: str = 'local')`: Get a Git configuration value.
-   `git_list_tags(pattern: str = None)`: List existing tags in the repository.

## Installation

### Prerequisites

-   Python 3.8+: Ensure Python is installed.
-   `uv`: A Python package manager for managing dependencies and virtual environments.
-   Git: Ensure Git is installed and available in your system's PATH.
-   Groq API Key: Obtain an API key from Groq.

### Steps

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/your-repo/ai-single-file-agents.git
    cd ai-single-file-agents
    cd git_agent
    ```

2.  **Install Dependencies**: Use `uv` to set up a virtual environment and install dependencies:
    ```bash
    uv sync
    ```

    This installs required packages listed in `pyproject.toml`, including `rich`, `groq`, and others.

3.  **Set Up the Groq API Key**: Add the `GROQ_API_KEY` to a `.env` file in the project root (e.g., `ai-single-file-agents/.env`):
    ```
    GROQ_API_KEY="your_grok_api_key_here"
    ```
    Alternatively, set it as an environment variable:
    ```bash
    export GROQ_API_KEY="your_grok_api_key_here"
    ```

4.  **Add to PATH (Optional)**: To run `git_agent.py` from anywhere, add the `git_agent` directory to your `PATH`:

    -   **Linux/macOS**:
        ```bash
        export PATH="$PATH:/path/to/ai-single-file-agents/git_agent"
        echo 'export PATH="$PATH:/path/to/ai-single-file-agents/git_agent"' >> ~/.bashrc
        source ~/.bashrc
        ```

    -   **Windows**:
        ```cmd
        setx PATH "%PATH%;C:\path\to\ai-single-file-agents\git_agent"
        ```

## Usage

Run the agent using `uv` with a natural language command:

