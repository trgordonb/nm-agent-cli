import os
import subprocess
import glob as glob_module
from urllib.parse import quote
from typing import Literal, List

import httpx
from langchain_core.tools import tool
from langchain_openviking import create_openviking_tools
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def _jina_api_key() -> str:
    return os.getenv("JINA_API_KEY", "")


def _jina_auth_headers(accept: str) -> dict:
    headers = {"Accept": accept}
    api_key = _jina_api_key()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers

# Define harness tools
@tool
def ls(directory: str = ".") -> str:
    """List files and directories in the specified path."""
    try:
        result = subprocess.run(["ls", "-la", directory], capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else result.stderr
    except Exception as e:
        return f"Error: {str(e)}"

@tool
def read_file(file_path: str) -> str:
    """Read the contents of a file."""
    try:
        with open(file_path, 'r') as f:
            return f.read()
    except Exception as e:
        return f"Error: {str(e)}"

@tool
def write_file(file_path: str, content: str) -> str:
    """Write content to a file (overwrites if exists)."""
    try:
        with open(file_path, 'w') as f:
            f.write(content)
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Error: {str(e)}"

@tool
def edit_file(file_path: str, old_string: str, new_string: str) -> str:
    """Replace a specific string in a file with new content."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        if old_string not in content:
            return f"Error: '{old_string}' not found in file"
        new_content = content.replace(old_string, new_string)
        with open(file_path, 'w') as f:
            f.write(new_content)
        return f"Successfully edited {file_path}"
    except Exception as e:
        return f"Error: {str(e)}"

@tool
def glob(pattern: str, path: str = ".") -> str:
    """Find files matching a glob pattern."""
    try:
        search_path = os.path.join(path, pattern)
        matches = glob_module.glob(search_path, recursive=True)
        return "\n".join(matches) if matches else "No matches found"
    except Exception as e:
        return f"Error: {str(e)}"

@tool
def grep(pattern: str, path: str = ".", file_pattern: str = "*") -> str:
    """Search for a pattern in files using grep."""
    try:
        result = subprocess.run(
            ["grep", "-r", pattern, path, "--include", file_pattern],
            capture_output=True,
            text=True
        )
        return result.stdout if result.returncode == 0 else result.stderr
    except Exception as e:
        return f"Error: {str(e)}"

@tool
def execute(command: str) -> str:
    """Execute a shell command."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        output = result.stdout if result.stdout else ""
        error = result.stderr if result.stderr else ""
        return f"Output:\n{output}\nError:\n{error}" if error else f"Output:\n{output}"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 30 seconds"
    except Exception as e:
        return f"Error: {str(e)}"

@tool
def web_to_markdown_tool(urls: List[str]) -> str:
    """
    Fetches content from a list of URLs (web pages, PDFs, JS-heavy sites) using the
    Jina Reader API (r.jina.ai) and returns clean, LLM-friendly Markdown.

    Args:
        urls (List[str]): A list of string URLs to fetch and convert.

    Returns:
        str: The combined Markdown content of all successfully fetched URLs.
    """
    if not urls:
        return "Error: no URLs provided"
    headers = _jina_auth_headers("text/plain")
    headers["X-Remove-Selector"] = "nav, header, footer, aside, .ads, .sidebar, .related-posts, .comments"
    headers["X-Retain-Images"] = "none"
    headers["X-Retain-Links"] = "text"
    headers["X-With-Links-Summary"] = "true"
    headers["X-Max-Tokens"] = "8000"
    parts = []
    failures = []
    for url in urls:
        try:
            response = httpx.get(f"https://r.jina.ai/{url}", headers=headers, timeout=180.0)
            if response.status_code != 200:
                failures.append(f"{url}: HTTP {response.status_code}")
                continue
            content = response.text.strip() or "(empty content)"
            parts.append(f"--- Source: {url} ---\n\n{content}")
        except Exception as e:
            failures.append(f"{url}: {str(e)[:200]}")
    if not parts:
        return f"Error: all fetches failed: {'; '.join(failures)}"
    output = "\n\n".join(parts)
    if failures:
        output += "\n\n(Note: some requests failed: " + "; ".join(failures) + ")"
    return output


@tool
def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
) -> str:
    """
    Run a web search using the Jina Search API (s.jina.ai), returning LLM-friendly
    results with title, URL, description and page content.

    Args:
        query (str): The search query.
        max_results (int): Number of results to return (1-20, default 5).
        topic (str): "general" for web search, "news" for news search. "finance"
            is treated as a general web search.

    Returns:
        str: Formatted search results.
    """
    if not _jina_api_key():
        return "Error: JINA_API_KEY is not set. Add it to the environment or .env file (get a key at https://jina.ai/)."
    try:
        params = {
            "type": "news" if topic == "news" else "web",
            "num": max(1, min(max_results, 20)),
        }
        response = httpx.get(
            f"https://s.jina.ai/{quote(query)}",
            headers=_jina_auth_headers("application/json") | {"X-Respond-With": "no-content"},
            params=params,
            timeout=60.0,
        )
        data = response.json()
        if data.get("code") != 200:
            message = str(data.get("message") or data.get("readableMessage") or data)[:300]
            return f"Error: Jina search failed (code {data.get('code')}): {message}"
        results = data.get("data") or []
        if isinstance(results, dict):
            results = results.get("results") or []
        if not results:
            return "Error: Jina search returned no results"
        blocks = []
        for i, result in enumerate(results, 1):
            content = str(result.get("content") or "")
            if len(content) > 4000:
                content = content[:4000] + "\n[... content truncated ...]"
            blocks.append(
                f"--- Result {i}: {result.get('title')} ---\n"
                f"URL: {result.get('url')}\n"
                f"{str(result.get('description') or '').strip()}\n\n"
                f"{content.strip()}"
            )
        return "\n\n".join(blocks)
    except Exception as e:
        return f"Error: Jina search failed: {str(e)}"


viking_tools = create_openviking_tools(
    url=os.getenv("OPENVIKING_URL"),
    api_key=os.getenv("OPENVIKING_API_KEY"),
    profile="agent",   # includes find/search/browse/read/grep/store
)


# Tool list
tools = [ls, read_file, write_file, edit_file, glob, grep, execute, web_to_markdown_tool, internet_search, *viking_tools]
