from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

import os
import argparse

load_dotenv(".env")

# Get configuration from environment variables
env_transport = os.getenv("MCP_TRANSPORT", "stdio")
host = os.getenv("MCP_HOST", "0.0.0.0")
port = int(os.getenv("MCP_PORT", "8050"))
server_name = os.getenv("MCP_SERVER_NAME", "Calculator")

# Create an MCP server
mcp = FastMCP(
    name="Calculator",
    host="0.0.0.0",  # only used for SSE transport (localhost)
    port=8050,  # only used for SSE transport (set this to any port)
    stateless_http=True,
)


# Add a simple calculator tool
@mcp.tool()
def add(numbers:list[int]) -> int:
    """Add multiple numbers together"""
    return sum(numbers)


# Run the server
if __name__ == "__main__":
    # set up command line argument parsing

    """
        # Use environment variable (from .env file)
        uv run python server.py

        # Override with command line argument
        uv run python server.py --transport sse

        # Override with command line argument
        uv run python server.py --transport streamable-http

        # Get help
        uv run python server.py --help
    """
    parser = argparse.ArgumentParser(description="MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default=env_transport, # Use env variable as default
        help="Transport Protocol to use"
    )

    args = parser.parse_args()

    # Command line argument takes precedence over env variables 
    transport = args.transport

    if transport == "stdio":
        print("Running server with stdio transport")
        mcp.run(transport="stdio")
    elif transport == "sse":
        print("Running server with SSE transport")
        mcp.run(transport="sse")
    elif transport == "streamable-http":
        print("Running server with Streamable HTTP transport")
        mcp.run(transport="streamable-http")
    else:
        raise ValueError(f"Unknown transport: {transport}")