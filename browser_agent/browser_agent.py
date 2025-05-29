import os
import sys
import json
import re
import inspect
import typing # Added for type hinting, especially Optional
from rich.console import Console
from rich.table import Table
from rich import box
from rich.text import Text
from groq import Groq
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Page, Browser, Playwright

load_dotenv()

console = Console()
groq_api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=groq_api_key)

TOOL_REGISTRY = {}

# Global Playwright instances
_playwright_instance: Playwright = None
_browser: Browser = None
_page: Page = None
_current_page_elements = {} # Stores elements identified by get_page_state for later use

def tool(func):
    """Decorator to register a function as a tool with its docstring and signature."""
    TOOL_REGISTRY[func.__name__] = {
        "function": func,
        "doc": inspect.getdoc(func),
        "signature": str(inspect.signature(func))
    }
    return func

# ==== HELPER FUNCTIONS FOR BROWSER AGENT ====

def _get_interactive_elements_info(page: Page):
    """
    Extracts information about interactive elements on the page, assigning them unique IDs.
    Prioritizes visible and enabled elements.
    """
    elements_info = []
    interactive_tags = ['a', 'button', 'input', 'textarea', 'select']
    
    # Use a counter for unique IDs
    element_id_counter = 1
    
    for tag in interactive_tags:
        # Find all elements of the current tag
        locators = page.locator(tag).all()
        for locator in locators:
            try:
                # Check if element is visible and enabled
                if not locator.is_visible() or not locator.is_enabled():
                    continue

                element_id = f"E{element_id_counter}"
                element_id_counter += 1
                
                text_content = locator.text_content().strip()
                if not text_content and tag == 'input':
                    # For inputs, try placeholder or value if no text content
                    text_content = locator.get_attribute('placeholder') or locator.get_attribute('value') or ''
                
                element_type_display = tag
                if tag == 'input':
                    input_type = locator.get_attribute('type')
                    element_type_display = f"input type='{input_type or 'text'}'"
                elif tag == 'a':
                    element_type_display = f"link"
                elif tag == 'button':
                    element_type_display = f"button"
                elif tag == 'textarea':
                    element_type_display = f"textarea"
                elif tag == 'select':
                    element_type_display = f"select"

                # Determine a robust selector for the element
                selector = None
                if locator.get_attribute('id'):
                    selector = f"#{locator.get_attribute('id')}"
                elif locator.get_attribute('name'):
                    selector = f"[name='{locator.get_attribute('name')}']"
                elif text_content:
                    # Use text content for a more human-readable selector, but can be brittle
                    # Escape single quotes within text_content for CSS selector
                    escaped_text_content = text_content.replace("'", "\\'")
                    selector = f"{tag}:has-text('{escaped_text_content}')"
                else:
                    # Fallback to a more generic selector if no good attributes
                    # This is a last resort and might not be unique
                    selector = f"{tag} >> nth={locators.index(locator)}" 

                if selector:
                    _current_page_elements[element_id] = selector # Store for later use by click/type tools
                    elements_info.append(
                        f"[{element_id}] <{element_type_display}> {text_content!r} (selector: {selector})"
                    )
            except Exception:
                # Skip elements that cause issues during inspection
                continue
    return elements_info

# ==== BROWSER TOOL FUNCTIONS ====

@tool
def launch_browser(browser_type: str = 'chromium', headless: bool = False):
    """
    Launches a new browser instance.
    Args:
        browser_type (str, optional): The type of browser to launch ('chromium', 'firefox', 'webkit'). Defaults to 'chromium'.
        headless (bool, optional): Whether to run the browser in headless mode (without a visible UI). Defaults to False.
    Returns:
        Tuple[str, None]: A string summary and None.
    """
    global _playwright_instance, _browser, _page
    if _browser:
        return "[yellow]Browser already launched. Close it first if you want to launch a new one.[/]", None
    try:
        _playwright_instance = sync_playwright().start()
        if browser_type.lower() == 'chromium':
            _browser = _playwright_instance.chromium.launch(headless=headless)
        elif browser_type.lower() == 'firefox':
            _browser = _playwright_instance.firefox.launch(headless=headless)
        elif browser_type.lower() == 'webkit':
            _browser = _playwright_instance.webkit.launch(headless=headless)
        else:
            return f"[red]Invalid browser type: {browser_type}. Choose 'chromium', 'firefox', or 'webkit'.[/]", None
        
        _page = _browser.new_page()
        return f"[green]Browser launched: {browser_type} (headless={headless})[/]", None
    except Exception as e:
        return f"[red]Error launching browser:[/] {str(e)}", None

@tool
def close_browser():
    """
    Closes the current browser instance.
    Returns:
        Tuple[str, None]: A string summary and None.
    """
    global _playwright_instance, _browser, _page
    if _browser:
        try:
            _browser.close()
            _playwright_instance.stop()
            _browser = None
            _page = None
            return "[green]Browser closed.[/]", None
        except Exception as e:
            return f"[red]Error closing browser:[/] {str(e)}", None
    return "[yellow]No browser is currently launched.[/]", None

@tool
def navigate_to_url(url: str):
    """
    Navigates the browser to the specified URL.
    Args:
        url (str): The URL to navigate to.
    Returns:
        Tuple[str, None]: A string summary and None.
    """
    global _page
    if not _page:
        return "[red]Browser not launched. Use launch_browser first.[/]", None
    try:
        _page.goto(url)
        return f"[green]Navigated to: {url}[/]", None
    except Exception as e:
        return f"[red]Error navigating to {url}:[/] {str(e)}", None

@tool
def get_page_state():
    """
    Captures the current URL, title, and a list of interactive elements with unique IDs and selectors.
    This tool is crucial for the LLM to understand the current state of the web page and identify elements to interact with.
    Returns:
        Tuple[str, dict]: A string summary and a dictionary containing URL, title, and elements.
    """
    global _page, _current_page_elements
    if not _page:
        return "[red]Browser not launched. Use launch_browser first.[/]", None
    
    try:
        # Wait for network to be idle, which is often more reliable for complex pages
        _page.wait_for_load_state("networkidle") 
        # Add a small timeout as a fallback for pages with dynamic content that might not trigger networkidle immediately
        _page.wait_for_timeout(1000) # Wait for 1 second

        url = _page.url
        title = _page.title()
        _current_page_elements = {} # Clear previous elements before populating new ones
        interactive_elements_list = _get_interactive_elements_info(_page)
        
        state_summary = f"Current URL: {url}\nPage Title: {title}\n\nInteractive Elements:\n"
        if interactive_elements_list:
            state_summary += "\n".join(interactive_elements_list)
        else:
            state_summary += "No interactive elements found on this page."
            
        console.print(f"[bold blue]--- Current Page State ---[/]\n{state_summary}\n[bold blue]--------------------------[/]")
        return state_summary, {"url": url, "title": title, "elements": _current_page_elements}
    except Exception as e:
        return f"[red]Error getting page state:[/] {str(e)}", None

@tool
def type_text(identifier: str, text: str):
    """
    Types text into an element identified by a CSS selector or a unique element ID from get_page_state.
    Args:
        identifier (str): The CSS selector of the input field, or an element ID (e.g., 'E1', 'E2') obtained from get_page_state.
        text (str): The text to type into the element.
    Returns:
        Tuple[str, None]: A string summary and None.
    """
    global _page, _current_page_elements
    if not _page:
        return "[red]Browser not launched. Use launch_browser first.[/]", None
    
    selector = _current_page_elements.get(identifier, identifier) # Resolve ID to selector, or use identifier as selector directly
    
    try:
        _page.fill(selector, text)
        return f"[green]Typed '{text}' into element '{identifier}' (selector: {selector})[/]", None
    except Exception as e:
        return f"[red]Error typing into '{identifier}' (selector: {selector}):[/] {str(e)}", None

@tool
def click_element(identifier: str):
    """
    Clicks an element identified by a CSS selector or a unique element ID from get_page_state.
    Args:
        identifier (str): The CSS selector of the element to click, or an element ID (e.g., 'E1', 'E2') obtained from get_page_state.
    Returns:
        Tuple[str, None]: A string summary and None.
    """
    global _page, _current_page_elements
    if not _page:
        return "[red]Browser not launched. Use launch_browser first.[/]", None
    
    selector = _current_page_elements.get(identifier, identifier) # Resolve ID to selector, or use identifier as selector directly
    
    try:
        _page.click(selector)
        return f"[green]Clicked element '{identifier}' (selector: {selector})[/]", None
    except Exception as e:
        return f"[red]Error clicking '{identifier}' (selector: {selector}):[/] {str(e)}", None

@tool
def get_element_text(identifier: str):
    """
    Retrieves the text content of an element identified by a CSS selector or a unique element ID.
    Args:
        identifier (str): The CSS selector of the element, or an element ID (e.g., 'E1', 'E2') obtained from get_page_state.
    Returns:
        Tuple[str, str]: A string summary and the text content of the element.
    """
    global _page, _current_page_elements
    if not _page:
        return "[red]Browser not launched. Use launch_browser first.[/]", None
    
    selector = _current_page_elements.get(identifier, identifier)
    
    try:
        text_content = _page.locator(selector).text_content()
        if text_content is None:
            return f"[yellow]No text content found for element '{identifier}' (selector: {selector}).[/]", ""
        console.print(f"[green]Text content of '{identifier}':[/] {text_content.strip()}")
        return f"Text content of '{identifier}': {text_content.strip()}", text_content.strip()
    except Exception as e:
        return f"[red]Error getting text content for '{identifier}' (selector: {selector}):[/] {str(e)}", None

@tool
def take_screenshot(filename: str = "screenshot.png"):
    """
    Takes a screenshot of the current page and saves it to the specified filename.
    Args:
        filename (str, optional): The name of the file to save the screenshot. Defaults to "screenshot.png".
    Returns:
        Tuple[str, str]: A string summary and the path to the saved screenshot.
    """
    global _page
    if not _page:
        return "[red]Browser not launched. Use launch_browser first.[/]", None
    try:
        _page.screenshot(path=filename)
        return f"[green]Screenshot saved to: {filename}[/]", filename
    except Exception as e:
        return f"[red]Error taking screenshot:[/] {str(e)}", None

@tool
def wait_for_selector(selector: str, timeout: int = 10000):
    """
    Waits for an element matching the given selector to appear in the DOM.
    Args:
        selector (str): The CSS selector to wait for.
        timeout (int, optional): Maximum time in milliseconds to wait for the selector. Defaults to 10000 (10 seconds).
    Returns:
        Tuple[str, bool]: A string summary and a boolean indicating if the selector was found.
    """
    global _page
    if not _page:
        return "[red]Browser not launched. Use launch_browser first.[/]", False
    try:
        _page.wait_for_selector(selector, timeout=timeout)
        return f"[green]Element with selector '{selector}' appeared.[/]", True
    except Exception as e:
        return f"[yellow]Element with selector '{selector}' did not appear within {timeout/1000} seconds: {str(e)}[/]", False

def generate_tools_doc():
    tool_docs = []
    for name, info in TOOL_REGISTRY.items():
        doc = info["doc"] or "No description."
        sig = inspect.signature(info["function"])
        # Format signature to be more readable for the LLM, e.g., (url: str, headless: bool = False)
        params = []
        for param_name, param in sig.parameters.items():
            if param_name == 'self': continue
            param_str = param_name
            if param.annotation is not inspect.Parameter.empty:
                # Get the name of the type, handling Optional
                type_name = str(param.annotation)
                if 'typing.Optional[' in type_name:
                    type_name = type_name.replace('typing.Optional[', '').replace(']', '')
                param_str += f": {type_name.split('.')[-1]}" # Just the type name, e.g., 'str'
            if param.default is not inspect.Parameter.empty:
                param_str += f" = {repr(param.default)}"
            params.append(param_str)
        formatted_sig = f"({', '.join(params)})"
        
        tool_docs.append(f"- {name}{formatted_sig}: {doc}")
    return "Available tools:\n" + "\n".join(tool_docs)

def print_available_tools():
    console.rule("[bold green]🛠️ Available Browser Tools")
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

# Function to generate Groq-compatible tool schemas - This function is no longer needed if tools are not passed as schema
# However, keeping it for now as it's part of the original structure, but it won't be used for API calls.
def _get_json_schema_type(py_type):
    if py_type is str: return "string"
    if py_type is int: return "integer"
    if py_type is float: return "number"
    if py_type is bool: return "boolean"
    if py_type is list: return "array"
    if py_type is dict: return "object"
    # Handle Optional types (e.g., typing.Optional[str])
    if hasattr(py_type, '__origin__') and py_type.__origin__ is typing.Union:
        # Check if NoneType is in the union, indicating Optional
        if type(None) in py_type.__args__:
            # Get the actual type, excluding NoneType
            actual_type = next(arg for arg in py_type.__args__ if arg is not type(None))
            return _get_json_schema_type(actual_type)
    return "string" # Default to string if type is unknown or complex

def generate_groq_tools_schema():
    # This function will still generate the schema, but it won't be used in the API call.
    # It's kept for consistency if other parts of the system might expect it,
    # but the core change is to remove its usage in client.chat.completions.create.
    groq_tools = []
    for name, info in TOOL_REGISTRY.items():
        func = info["function"]
        sig = inspect.signature(func)
        parameters = {"type": "object", "properties": {}, "required": []}

        for param_name, param in sig.parameters.items():
            # Skip 'self' if this were a class method, or any other non-argument parameters
            if param_name == 'self':
                continue

            param_type = param.annotation
            param_default = param.default

            is_optional = False
            if hasattr(param_type, '__origin__') and param_type.__origin__ is typing.Union:
                if type(None) in param_type.__args__:
                    is_optional = True
                    param_type = next(arg for arg in param_type.__args__ if arg is not type(None))

            json_type = _get_json_schema_type(param_type)
            
            param_schema = {"type": json_type}
            if param_type is bool: # Add enum for boolean to guide LLM
                param_schema["enum"] = [True, False]
            
            # Add description if available from docstring (simple parsing)
            if info["doc"]:
                param_doc_match = re.search(rf"Args:\s*.*{param_name}\s+\(.*\):\s*(.*)", info["doc"])
                if param_doc_match:
                    param_schema["description"] = param_doc_match.group(1).strip()

            parameters["properties"][param_name] = param_schema
            
            if param_default is inspect.Parameter.empty and not is_optional:
                parameters["required"].append(param_name)

        groq_tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": info["doc"],
                "parameters": parameters
            }
        })
    return groq_tools

AVAILABLE_TOOLS_DOC = generate_tools_doc() # For printing to console and LLM prompt
# GROQ_TOOLS_SCHEMA = generate_groq_tools_schema() # This will no longer be used as a direct parameter

# === LLM Decision ===
TOOLS_DOC = f"""
You are an AI agent that controls a web browser to perform tasks based on natural language commands.
You operate by choosing and executing specific browser automation tools.

**CRITICAL RULE: You MUST generate ONLY ONE tool call per response.**
**Do NOT provide multiple tool calls in a single response.**
**IMPORTANT: Your tool call MUST be embedded as a string within the 'content' field of your response, using the exact format: `<function=tool_name={{arguments_json_string}}></function>`.**
**For example: `<function=navigate_to_url={{"url": "https://www.example.com"}}></function>`**
**The agent will parse ONLY this specific format from the 'content' field. Any other text or format will be ignored for tool execution.**

Each tool call represents a single atomic action. After each action, you will receive the tool's output and an updated "page state" (current URL, title, interactive elements with IDs). You will then make your next decision based on this new information.

Your primary goal is to break down complex user commands into a sequence of atomic browser actions.

You MUST use the provided element IDs (e.g., 'E1', 'E2') or CSS selectors when interacting with elements (e.g., for `type_text` or `click_element`).

Below is the list of Available tools you can use:
{AVAILABLE_TOOLS_DOC}

Crucial Workflow for Browser Interaction:
1.  **Launch Browser:** Always start by launching the browser using `launch_browser`. This tool should generally be called only once at the very beginning of a task, or after `close_browser`.
2.  **Navigate:** Use `navigate_to_url` to go to the target website.
3.  **Observe Page State:** Immediately after navigation or any interaction that changes the page (like clicking a button or typing text), you MUST use `get_page_state` to get the latest interactive elements and their IDs. This is how you "see" the page and understand its current content and interactive elements. Pay close attention to the elements returned, especially if they indicate unexpected states (e.g., CAPTCHAs, error pages, login prompts).
4.  **Interact:** Use `type_text` or `click_element` referring to the element IDs (e.g., 'E1', 'E2') or selectors obtained from `get_page_state`.
5.  **Validate/Observe Again:** After an interaction, use `get_page_state` again to confirm the action was successful and to get the new page state for the next step.
6.  **Close Browser:** When all tasks are complete, use `close_browser`. This tool should be called at the very end of the task.

Handle errors gracefully:
- If a tool fails (e.g., element not found, navigation error, "Browser already launched"), analyze the error message provided in the tool output.
- Adapt your plan based on the error. For example, if `launch_browser` fails because it's already launched, do not call it again; proceed with navigation or `get_page_state`.
- Never repeat successful operations or operations that consistently fail without a change in strategy.
- If the command is unclear or cannot be executed with the available tools (e.g., stuck on an unsolvable CAPTCHA), or if you believe the task is fully complete, do not call any more tools. Instead, provide a concise summary of the situation or the completed task.

**REMINDER: You MUST generate ONLY ONE tool call per response, and it MUST be in the 'content' field using the `<function=tool_name={{arguments_json_string}}></function>` format.**
"""

def choose_tool(natural_language_input, conversation_history=None):
    if conversation_history is None:
        conversation_history = []
    
    system_content = (
        f"You are a tool-choosing assistant for browser automation.\n"
        f"{TOOLS_DOC}\n" # TOOLS_DOC already contains the strict instructions
        f"Based on the user's request and the conversation history, you should decide which single tool to call next. "
        f"If the task is complete or cannot be fulfilled by the available tools, do not call any tool."
        f"Always review the previous tool's output and the current page state before deciding the next action."
        f"Remember: Your response MUST contain ONLY ONE tool call, and it MUST be in the 'content' field using the `<function=tool_name={{arguments_json_string}}></function>` format."
    )
    
    messages = [
        {"role": "system", "content": system_content},
        *conversation_history,
        {"role": "user", "content": f"User's request: {natural_language_input}"}
    ]
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            # tools=GROQ_TOOLS_SCHEMA, # REMOVED: Tools are now described in the prompt and parsed from content
            tool_choice="auto" # This parameter might still be useful for models that support it, even without explicit tool schema.
                               # However, for models that rely purely on prompt for tool calling, it might be ignored.
        )
        
        response_message = response.choices[0].message
        
        console.print(f"[yellow]LLM response message (raw):[/] {response_message.model_dump_json(indent=2)}")

        # Append the LLM's response (which might contain tool_calls or content) to history
        # Note: response_message.tool_calls will always be None if tools parameter is not used.
        conversation_history.append(response_message.model_dump(exclude_unset=True))

        tool_name = None
        args = {}
        tool_call_id = None

        # Attempt to parse tool call from content
        if response_message.content:
            # Regex to find <function=tool_name={"arg":"value"}></function>
            # The regex is adjusted to be non-greedy for the tool_name part `([^=]+?)`
            # and to correctly capture the JSON string `({.*?})`
            match = re.search(r'<function=([^=]+?)=({.*?})></function>', response_message.content)
            if match:
                tool_name = match.group(1)
                args_str = match.group(2)
                try:
                    args = json.loads(args_str)
                    tool_call_id = f"call_{tool_name}_{os.urandom(4).hex()}" # Generate a dummy ID
                    console.print(f"[green]Parsed tool call from content: {tool_name} with args {args}[/]")
                except json.JSONDecodeError as e:
                    console.print(f"[red]Error parsing JSON arguments from LLM content: {e}. Content: {args_str}[/]")
                    tool_name = None # Invalidate tool call if args are malformed
            else:
                # If content exists but doesn't match tool call format
                console.print("[yellow]LLM provided content but it does not match the expected tool call format.[/]")
        
        if tool_name: # If a tool call was successfully parsed
            return (
                tool_name,
                args,
                False, # Not done if a tool is called
                conversation_history, # Updated history with LLM's tool call
                tool_call_id # Pass the generated tool_call_id back
            )
        else:
            # If LLM didn't provide a parsable tool call in content
            console.print("[yellow]LLM did not suggest a tool call in the expected format. Assuming task is complete or unclear.[/]")
            return (
                "done", # Signal that no tool was chosen
                {},
                True, # Mark as done
                conversation_history, # Updated history with LLM's final content
                None # No tool_call_id
            )
    
    except Exception as e:
        console.print(f"[red]Error communicating with LLM:[/] {str(e)}")
        conversation_history.append({"role": "assistant", "content": f"Error processing command: {str(e)}"})
        return (
            "done",
            {},
            True,
            conversation_history,
            None
        )

# ==== CLI ====

def main():
    console.rule("[bold blue]🌐 AI Browser Agent (Natural Language CLI)")

    if len(sys.argv) < 2:
        console.print("[yellow]Usage:[/] uv run browser_agent.py 'your command here'")
        return

    user_input = " ".join(sys.argv[1:])

    if user_input.lower() == "list-tools":
        print_available_tools()
        return
    
    conversation_history = []
    max_iterations = 20 # Increased iterations for multi-step browser tasks
    
    # Add initial user message to history
    conversation_history.append({"role": "user", "content": user_input})

    try:
        for i in range(max_iterations):
            # choose_tool now returns tool_call_id
            tool_name, args, done, history, tool_call_id = choose_tool(user_input, conversation_history)
            conversation_history = history # Update history with LLM's tool call message

            if tool_name == "done":
                console.print("[green]Task completed by LLM decision or no tool suggested.[/]")
                break
            
            if tool_name in TOOL_REGISTRY:
                tool_entry = TOOL_REGISTRY[tool_name]
                
                try:
                    func = tool_entry["function"]
                    result_message, result_data = func(**args)
                    console.print(result_message)
                    
                    # Append tool output to conversation history using tool_call_id
                    tool_output_message = {
                        "role": "tool",
                        "tool_call_id": tool_call_id, # USE THE ID HERE
                        "content": result_message
                    }
                    # If get_page_state, include structured data in content
                    if tool_name == "get_page_state" and result_data:
                        tool_output_message["content"] += f"\nStructured page data: {json.dumps(result_data)}"

                    conversation_history.append(tool_output_message)

                except Exception as e:
                    console.print(f"[red]Error executing tool '{tool_name}': {e}[/]")
                    # If tool execution fails, send an error message back to the LLM
                    error_message = {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": f"Error executing tool '{tool_name}': {str(e)}"
                    }
                    conversation_history.append(error_message)
                    # If a critical tool like launch/navigate fails, might need to stop
                    if tool_name in ["launch_browser", "navigate_to_url"]:
                        console.print("[red]Critical browser operation failed. Aborting task.[/]")
                        break
                    # Otherwise, let LLM try to recover
                    continue

            else:
                # This branch is hit if choose_tool returns "done" because no tool_calls were made
                # The 'done' status is already handled above.
                # This 'else' block might indicate an unexpected state if tool_name is not "done"
                # but also not in TOOL_REGISTRY.
                console.print(f"[red]Unexpected state: Tool '{tool_name}' not found in registry after LLM decision.[/]")
                break
            
            if done: # This 'done' comes from the LLM not suggesting a tool
                console.print("[green]Task completed as per LLM's 'done' signal (no further tools suggested).[/]")
                break
        else:
            console.print("[red]Max iterations reached. Task might be incomplete.[/]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation interrupted by user.[/]")
    finally:
        # Ensure browser is closed even if an error occurs or task is interrupted
        if _browser:
            console.print("[yellow]Ensuring browser is closed...[/]")
            close_browser()
            console.print("[yellow]Browser cleanup complete.[/]")

if __name__ == "__main__":
    main()
