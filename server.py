from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

import os
import argparse
import json

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

@mcp.tool()
def get_knowledge_base() -> str:
    """ Retrieve entire knowledge base as string 
    
    Returns: 
        A formatted string containing all Q&A from the knowledge base
    """
    try:
        kb_path = os.path.join(os.path.dirname(__file__), "data", "kb.json")
        with open(kb_path, "r") as f:
            kb_data = json.load(f)

        # Format the knowledge base as a string
        kb_text = "Here is the retrieved knowledge base:\n\n"

        if isinstance(kb_data, list):
            for i, item in enumerate(kb_data, 1): # index starting at 1
                if isinstance(item, dict):
                    question = item.get("question", "Unknown question")
                    answer = item.get("answer", "Unknown answer")
                else:
                    question = f"Item {i}"
                    answer = str(item)

                kb_text += f"Q{i}: {question}\n"
                kb_text += f"A{i}: {answer}\n\n"
        else:
            kb_text += f"Knowledge base content: {json.dumps(kb_data, indent=2)}\n\n"

        return kb_text
    except FileNotFoundError:
        return "Error: Knowledge base file not found"
    except json.JSONDecodeError:
        return "Error: Invalid JSON in knowledge base file"
    except Exception as e:
        return f"Error: {str(e)}"

# Add a simple calculator tool
# @mcp.tool()
# def add(numbers:list[int]) -> int:
#     """Add multiple numbers together"""
#     return sum(numbers)


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