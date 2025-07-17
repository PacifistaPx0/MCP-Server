import asyncio
import json
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional
import os

import tiktoken #for counting tokens used
import nest_asyncio
import openai
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI

# Apply nest_asyncio to allow nested event loops (needed for Jupyter/IPython)
nest_asyncio.apply()

# Load environment variables
load_dotenv("../.env")


class MCPOpenAIClient:
    """Client for interacting with OpenAI models using MCP tools."""

    def __init__(self, model: str = "gpt-4o", api_key: str = None):
        """Initialize the OpenAI MCP client.

        Args:
            model: The OpenAI model to use.
        """
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.openai_client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.stdio: Optional[Any] = None
        self.write: Optional[Any] = None

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoding.encode(text))

    async def connect_to_server(self, server_script_path: str = "../server.py"):
        """Connect to an MCP server.

        Args:
            server_script_path: Path to the server script.
        """
        # Get absolute path to server script
        absolute_server_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__),
            server_script_path
        ))

        print(f"Connecting to server at: {absolute_server_path}")

        # Use Python directly instead of uv
        server_params = StdioServerParameters(
            command="python",  # Just use Python directly
            args=[absolute_server_path],  # Use absolute path
        )

        # Connect to the server
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )

        # Initialize the connection
        await self.session.initialize()

        # List available tools
        tools_result = await self.session.list_tools()
        print("\nConnected to server with tools:")
        for tool in tools_result.tools:
            print(f"  - {tool.name}: {tool.description}")

    async def get_mcp_tools(self) -> List[Dict[str, Any]]:
        """Get available tools from the MCP server in OpenAI format.

        Returns:
            A list of tools in OpenAI format.
        """
        tools_result = await self.session.list_tools()
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema,
                },
            }
            for tool in tools_result.tools
        ]

    async def process_query(self, query: str) -> str:
        """Process a query using OpenAI and available MCP tools.

        Args:
            query: The user query.

        Returns:
            The response from OpenAI.
        """
        # Get available tools
        tools = await self.get_mcp_tools()

        # Count input tokens
        input_tokens = self.count_tokens(query)
        tools_tokens = self.count_tokens(json.dumps(tools))

        print(f"Input tokens: {input_tokens}")
        print(f"Tools tokens: {tools_tokens}")

        # Validate API key before making call
        if not self.openai_client.api_key:
            return "Error: No OpenAI API key provided. Please set the OPENAI_API_KEY environment variable or provide it when initializing the client."
            
        try:
            # Initial OpenAI API call
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": query}],
                tools=tools,
                tool_choice="auto",
            )
            
            if hasattr(response, 'usage'):
                total_tokens = response.usage.total_tokens
                self.total_tokens_used += total_tokens
                print(f"API call used: {total_tokens} tokens")
                print(f"Total tokens used so far: {self.total_tokens_used}")

        except openai.RateLimitError:
            raise  # Re-raise to be handled by the main function
        except Exception as e:
            return f"Error calling OpenAI API: {str(e)}"

        # Get assistant's response
        assistant_message = response.choices[0].message

        # Initialize conversation with user query and assistant response
        messages = [
            {"role": "user", "content": query},
            assistant_message,
        ]

        # Handle tool calls if present
        if assistant_message.tool_calls:
            # Process each tool call
            for tool_call in assistant_message.tool_calls:
                # Execute tool call
                result = await self.session.call_tool(
                    tool_call.function.name,
                    arguments=json.loads(tool_call.function.arguments),
                )

                # Add tool response to conversation
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result.content[0].text,
                    }
                )

            # Get final response from OpenAI with tool results
            final_response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="none",  # Don't allow more tool calls
            )

            return final_response.choices[0].message.content

        # No tool calls, just return the direct response
        return assistant_message.content

    async def cleanup(self):
        """Clean up resources."""
        await self.exit_stack.aclose()


async def main():
    """Main entry point for the client."""
    client = MCPOpenAIClient(api_key=os.getenv("OPENAI_API_KEY"))
    await client.connect_to_server("../server.py")
    try:
        # Example: Ask about company vacation policy
        query = "What is our company's vacation policy?"
        print(f"\nQuery: {query}")

        response = await client.process_query(query)
        print(f"\nResponse: {response}")
    except openai.RateLimitError as e:
        print(f"\nERROR: OpenAI API rate limit exceeded.")
        print("This usually means your API key has insufficient quota or billing issues.")
        print("Visit https://platform.openai.com/account/billing to check your billing status.")
        print(f"\nError details: {e}")
    except Exception as e:
        print(f"\nERROR: An error occurred: {e}")
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())