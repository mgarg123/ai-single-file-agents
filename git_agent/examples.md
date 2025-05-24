# AI Git Agent Examples

This document provides examples of how to use the AI Git Agent via the command line using `uv run`.

To run a command, use the following format:

```bash
uv run git_agent/git_agent.py 'your natural language command here'
```

Replace `'your natural language command here'` with the specific task you want the agent to perform.

## Git Status and Basic Operations

-   Show the current Git status:
    ```bash
    uv run git_agent/git_agent.py 'show git status'
    ```

-   Add all changes to the staging area:
    ```bash
    uv run git_agent/git_agent.py 'add all files'
    ```

-   Add a specific file to the staging area:
    ```bash
    uv run git_agent/git_agent.py 'add my_file.txt'
    ```

-   Commit staged changes with a message:
    ```bash
    uv run git_agent/git_agent.py 'commit with message "feat: Add new feature"'
    ```

-   Commit staged changes and let AI draft the message:
    ```bash
    uv run git_agent/git_agent.py 'commit my changes'
    ```

-   Show differences in the working directory:
    ```bash
    uv run git_agent/git_agent.py 'show git diff'
    ```

-   Show differences for a specific file:
    ```bash
    uv run git_agent/git_agent.py 'show diff for README.md'
    ```

## Branch Management

-   List all local branches:
    ```bash
    uv run git_agent/git_agent.py 'list branches'
    ```

-   List all branches, including remote-tracking branches:
    ```bash
    uv run git_agent/git_agent.py 'list all branches'
    ```

-   List only remote branches:
    ```bash
    uv run git_agent/git_agent.py 'list remote branches'
    ```

-   Create a new branch:
    ```bash
    uv run git_agent/git_agent.py 'create a new branch named "feature/login"'
    ```

-   Create a new branch based on another branch:
    ```bash
    uv run git_agent/git_agent.py 'create branch "hotfix/bug-123" based on "main"'
    ```

-   Switch to an existing branch:
    ```bash
    uv run git_agent/git_agent.py 'checkout to develop branch'
    ```

-   Delete a local branch (safe delete):
    ```bash
    uv run git_agent/git_agent.py 'delete branch "old-feature"'
    ```

-   Force delete a local branch (even if unmerged):
    ```bash
    uv run git_agent/git_agent.py 'force delete branch "temp-branch"'
    ```

## Remote Operations

-   Fetch latest changes from all remotes:
    ```bash
    uv run git_agent/git_agent.py 'fetch latest changes'
    ```

-   Pull changes from a specific remote and branch:
    ```bash
    uv run git_agent/git_agent.py 'pull from origin main'
    ```

-   Push current branch to remote:
    ```bash
    uv run git_agent/git_agent.py 'push my changes to origin main'
    ```

-   Add a new remote repository:
    ```bash
    uv run git_agent/git_agent.py 'add a new remote named "upstream" with url "https://github.com/fork/repo.git"'
    ```

-   Remove an existing remote:
    ```bash
    uv run git_agent/git_agent.py 'remove remote "old-remote"'
    ```

-   List all configured remotes:
    ```bash
    uv run git_agent/git_agent.py 'list remotes'
    ```

-   List remotes with their URLs:
    ```bash
    uv run git_agent/git_agent.py 'list remotes verbosely'
    ```

-   Clone a repository:
    ```bash
    uv run git_agent/git_agent.py 'clone repository "https://github.com/user/project.git"'
    ```

-   Clone a repository into a specific directory:
    ```bash
    uv run git_agent/git_agent.py 'clone "https://github.com/user/project.git" into "my-project-folder"'
    ```

## History and Revisions

-   Show the last 5 commits:
    ```bash
    uv run git_agent/git_agent.py 'show last 5 commits'
    ```

-   Show the last 10 commits:
    ```bash
    uv run git_agent/git_agent.py 'show last 10 commits'
    ```

-   Show details of a specific commit:
    ```bash
    uv run git_agent/git_agent.py 'show details of commit abcdef1'
    ```

-   Revert the last commit (creates a new commit to undo changes):
    ```bash
    uv run git_agent/git_agent.py 'revert the last commit'
    ```

-   Reset to a previous commit, keeping changes staged:
    ```bash
    uv run git_agent/git_agent.py 'undo last commit but keep changes staged'
    ```

-   Reset to a previous commit, unstaging changes:
    ```bash
    uv run git_agent/git_agent.py 'reset to HEAD~1 and unstage changes'
    ```

-   Reset to a previous commit, discarding all changes (use with extreme caution):
    ```bash
    uv run git_agent/git_agent.py 'hard reset to commit 1234567'
    ```

-   Show the reflog (history of HEAD and branch updates):
    ```bash
    uv run git_agent/git_agent.py 'show reflog'
    ```

-   Show who last modified each line of a file:
    ```bash
    uv run git_agent/git_agent.py 'blame main.py'
    ```

## Merging and Rebasing

-   Merge a branch into the current branch:
    ```bash
    uv run git_agent/git_agent.py 'merge feature/new-feature into current branch'
    ```

-   Merge a branch and always create a merge commit (no fast-forward):
    ```bash
    uv run git_agent/git_agent.py 'merge develop branch with no fast-forward'
    ```

-   Rebase the current branch onto another branch:
    ```bash
    uv run git_agent/git_agent.py 'rebase current branch onto main'
    ```

-   Cherry-pick a specific commit:
    ```bash
    uv run git_agent/git_agent.py 'cherry-pick commit 789abc0'
    ```

## Stashing Changes

-   Stash current changes with a message:
    ```bash
    uv run git_agent/git_agent.py 'stash my current changes with message "WIP: Half-done feature"'
    ```

-   List all stashes:
    ```bash
    uv run git_agent/git_agent.py 'list all stashes'
    ```

-   Apply the latest stash (keeps it in the stash list):
    ```bash
    uv run git_agent/git_agent.py 'apply the latest stash'
    ```

-   Pop the latest stash (applies and removes it from the stash list):
    ```bash
    uv run git_agent/git_agent.py 'pop the latest stash'
    ```

-   Apply a specific stash by ID:
    ```bash
    uv run git_agent/git_agent.py 'apply stash number 1'
    ```

-   Drop a specific stash by ID:
    ```bash
    uv run git_agent/git_agent.py 'drop stash 2'
    ```

## Tagging

-   Create a lightweight tag:
    ```bash
    uv run git_agent/git_agent.py 'create lightweight tag "v1.0.0"'
    ```

-   Create an annotated tag with a message:
    ```bash
    uv run git_agent/git_agent.py 'create tag "v1.1.0" with message "Release 1.1.0"'
    ```

-   List all tags:
    ```bash
    uv run git_agent/git_agent.py 'list all tags'
    ```

-   List tags matching a pattern:
    ```bash
    uv run git_agent/git_agent.py 'list tags starting with "release-"'
    ```

## Cleaning the Working Directory

-   Discard unstaged changes in a specific file:
    ```bash
    uv run git_agent/git_agent.py 'discard unstaged changes in config.py'
    ```

-   Discard all unstaged changes in the current directory:
    ```bash
    uv run git_agent/git_agent.py 'discard all unstaged changes'
    ```

-   Unstage changes for a specific file:
    ```bash
    uv run git_agent/git_agent.py 'unstage changes for temp_file.txt'
    ```

-   Remove untracked files (requires force=True):
    ```bash
    uv run git_agent/git_agent.py 'clean untracked files'
    ```

-   Remove untracked files and directories (requires force=True):
    ```bash
    uv run git_agent/git_agent.py 'clean untracked files and directories'
    ```

## Configuration

-   Get a global Git configuration value (e.g., user email):
    ```bash
    uv run git_agent/git_agent.py 'get my global user email'
    ```

-   Get a local Git configuration value (e.g., remote origin URL):
    ```bash
    uv run git_agent/git_agent.py 'get local config for remote.origin.url'
    ```

## Multi-step Commands

-   Add all files, then commit them with a message, then push to origin main:
    ```bash
    uv run git_agent/git_agent.py 'add all files then commit with message "feat: Initial setup" then push to origin main'
    ```

-   Create a new branch, then checkout to it, then show git status:
    ```bash
    uv run git_agent/git_agent.py 'create branch "dev/feature-x" then checkout to "dev/feature-x" then show git status'
    ```

-   Fetch latest changes, then pull from origin develop, then show last 3 commits:
    ```bash
    uv run git_agent/git_agent.py 'fetch latest changes and then pull from origin develop and then show last 3 commits'
    ```

-   Stash current changes, then checkout to main, then pop the stash:
    ```bash
    uv run git_agent/git_agent.py 'stash my changes then checkout to main then pop the latest stash'
    ```

## Listing Available Tools

-   See the list of all available tools and their descriptions:
    ```bash
    uv run git_agent/git_agent.py list-tools
    ```
