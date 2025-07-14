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
    name=server_name,
    host=host,  # only used for SSE transport (localhost)
    port=port,  # only used for SSE transport (set this to any port)
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
    parser.add_argument("--port", type=int, default=port, help="Port for HTTP transports")

    args = parser.parse_args()

    # Get final values (command line overrides environment)
    final_transport = args.transport
    final_port = args.port

    # Update the server configuration
    mcp.port = final_port

    if final_transport == "stdio":
        mcp.run(transport="stdio")
    elif final_transport == "sse":
        mcp.run(transport="sse")
    elif final_transport == "streamable-http":
        mcp.run(transport="streamable-http")
    else:
        raise ValueError(f"Unknown transport: {final_transport}")