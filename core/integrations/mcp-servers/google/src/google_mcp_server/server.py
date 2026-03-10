"""FastMCP server for Gmail and Google Calendar."""

from mcp.server.fastmcp import FastMCP
from google_mcp_server.auth.oauth import GoogleAuthManager
from google_mcp_server.tools import gmail, calendar

# Initialize the MCP server
mcp = FastMCP("Google MCP Server")

# Initialize auth manager (singleton)
auth_manager = GoogleAuthManager()

# Register all tools
gmail.register_tools(mcp, auth_manager)
calendar.register_tools(mcp, auth_manager)


def main():
    """Run the MCP server with stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
