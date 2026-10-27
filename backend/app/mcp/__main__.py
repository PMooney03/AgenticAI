"""Run the allowlisted MCP server over stdio.

uv run python -m app.mcp
"""

from app.config import get_settings
from app.mcp.server import get_mcp_server

if __name__ == "__main__":
    get_mcp_server(str(get_settings().notes_path)).run(transport="stdio")
