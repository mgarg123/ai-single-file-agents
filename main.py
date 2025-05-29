import sys
from rich.console import Console

# Import main functions from your agents
from file_agent import file_agent
from git_agent import git_agent # Assuming git_agent.py has a main() function
from browser_agent import browser_agent # New import

console = Console()

def print_usage():
    console.print("[bold yellow]Usage:[/]")
    console.print("  uv run main.py [agent_name] 'your command here'")
    console.print("\n[bold cyan]Available Agents:[/]")
    console.print("  - [bold green]file_agent[/]: For file system operations.")
    console.print("  - [bold green]git_agent[/]: For Git repository operations.")
    console.print("  - [bold green]browser_agent[/]: For web browser automation.")
    console.print("\n[bold magenta]Examples:[/]")
    console.print("  uv run main.py file_agent 'list all files in current directory'")
    console.print("  uv run main.py git_agent 'git status'")
    console.print("  uv run main.py browser_agent 'open google.com and search for Playwright'")

def main():
    if len(sys.argv) < 3:
        print_usage()
        sys.exit(1)

    agent_name = sys.argv[1].lower()
    command_args = sys.argv[2:]
    
    # Temporarily modify sys.argv for the chosen agent's main function
    original_argv = sys.argv
    sys.argv = [f"main.py {agent_name}"] + command_args # Simulate agent's own CLI call

    try:
        if agent_name == "file_agent":
            console.rule("[bold blue]🚀 Running File Agent[/]")
            file_agent.main()
        elif agent_name == "git_agent":
            console.rule("[bold blue]🚀 Running Git Agent[/]")
            git_agent.main()
        elif agent_name == "browser_agent":
            console.rule("[bold blue]🚀 Running Browser Agent[/]")
            browser_agent.main()
        else:
            console.print(f"[red]Error: Unknown agent '{agent_name}'.[/]")
            print_usage()
            sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred:[/bold red] {e}")
    finally:
        sys.argv = original_argv # Restore original sys.argv

if __name__ == "__main__":
    main()
