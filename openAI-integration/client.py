import asyncio
import json
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional
import os
import signal
import sys
import subprocess
import atexit
import re

import tiktoken #for counting tokens used
import nest_asyncio

from decouple import config
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from google import genai


# Apply nest_asyncio to allow nested event loops (needed for Jupyter/IPython)
nest_asyncio.apply()

# Global variable to track server process
server_process = None

# Function to extract question using regex
def get_question(kb_text, q_num=1):
    """Extract a specific question from the knowledge base text.
    
    Args:
        kb_text: The knowledge base text
        q_num: The question number to extract (default: 1)
    
    Returns:
        The question text or None if not found
    """
    pattern = rf'Q{q_num}:\s*(.*?)(?=\n[A-Z]\d+:|$)'
    match = re.search(pattern, kb_text, re.DOTALL)
    return match.group(1).strip() if match else None

def find_matching_question(kb_text, user_query):
    """ Find the most relevant question in the knowledge base for the user query """
    # Extract all questions
    all_questions = {}
    for i in range(1, 10): # Assuming max 9 questions
        q_text = get_question(kb_text, i)
        if q_text:
            all_questions[i] = q_text
        else:
            break 

    # Simple matching based on word overlap
    user_words = set(user_query.lower().split())
    best_match = 1 # Default to Q1
    highest_score = 0

    for q_num, q_text in all_questions.items():
        q_words = set(q_text.lower().split())
        score = len(user_words.intersection(q_words))
        if score > highest_score:
            highest_score = score
            best_match = q_num

    return best_match, all_questions[best_match]

# Function to kill server on exit
def kill_server_on_exit():
    global server_process
    if server_process:
        try:
            print("🧹 Terminating server process...")
            server_process.terminate()
        except:
            try:
                print("⚠️ Force killing server process...")
                server_process.kill()
            except:
                pass

# Register cleanup function to run on exit
atexit.register(kill_server_on_exit)

# Signal handler for Ctrl+C
def signal_handler(sig, frame):
    print("\n🛑 Interrupted by Ctrl+C. Exiting...")
    kill_server_on_exit()
    os._exit(0)  # Force exit

# Register signal handler
signal.signal(signal.SIGINT, signal_handler)




class MCPGenAIClient:
    """Client for interacting with GenAI models using MCP tools."""

    def __init__(self, model: str = "gemini-2.0-flash"):
        """Initialize the GenAI MCP client.

        Args:
            model: The GenAI model to use.
            api_key: Google API key.
        """
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.model = model
        self.stdio: Optional[Any] = None
        self.write: Optional[Any] = None
        self.total_tokens_used = 0
        
        # Store the API key for validation
        self.api_key = config('GOOGLE_API_KEY', default=None)

        # Configure GenAI client 
        self.client = genai.Client(api_key=self.api_key)

        # Initialize token encoding
        try:
            self.encoding = tiktoken.encoding_for_model("gpt-4")
        except:
            self.encoding = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoding.encode(text))

    async def connect_to_server(self, server_script_path: str = "../server.py"):
        """Connect to an MCP server with proper process management."""
        global server_process
        
        # Get absolute path to server script
        absolute_server_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__),
            server_script_path
        ))

        print(f"Connecting to server at: {absolute_server_path}")

        # FIXED: Better process management with signal handling
        server_params = StdioServerParameters(
            command="python",
            args=[absolute_server_path],
            # Add process creation flags for Windows
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )

        try:
            # Connect to the server
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            
            # Store reference to server process for cleanup
            if hasattr(stdio_transport, '_process'):
                server_process = stdio_transport._process
            
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
                
        except Exception as e:
            print(f"Failed to connect to server: {e}")
            if server_process:
                try:
                    server_process.terminate()
                except:
                    pass
            raise

    async def get_mcp_tools(self) -> List[Dict[str, Any]]:
        """Get available tools from the MCP server in GenAI format."""
        tools_result = await self.session.list_tools()
        
        tools = []
        for tool in tools_result.tools:
            tool_def = {
                "function_declarations": [{
                    "name": tool.name,
                    "description": f"{tool.description}. Use this tool to retrieve company information and policies.",
                    "parameters": tool.inputSchema or {
                        "type": "object", 
                        "properties": {},
                        "required": []
                    }
                }]
            }
            tools.append(tool_def)
        
        return tools

    async def process_query(self, query: str) -> str:
        """Process a query using GenAI and available MCP tools."""
        tools = await self.get_mcp_tools()
        input_tokens = self.count_tokens(query)
        tools_tokens = self.count_tokens(json.dumps(tools))

        print(f"Input tokens: {input_tokens}")
        print(f"Tools tokens: {tools_tokens}")

        if not self.api_key:
            return "Error: No Google API key provided. Please set the GOOGLE_API_KEY environment variable."
            
        try:
            system_instruction = """You are a helpful assistant with access to company knowledge base tools. 
            When asked about company policies, procedures, or information, you MUST use the available tools to retrieve the most current information.
            Always use the get_knowledge_base tool when answering questions about company policies."""
            
            contents = [
                {"role": "user", "parts": [{"text": f"{system_instruction}\n\nUser question: {query}"}]}
            ]
            
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=contents,
                config=genai.types.GenerateContentConfig(
                    tools=tools,
                    temperature=0.1,
                )
            )

            estimated_tokens = self.count_tokens(query + str(response.text))
            self.total_tokens_used += estimated_tokens
            print(f"Estimated tokens used: {estimated_tokens}")
            print(f"Total tokens used so far: {self.total_tokens_used}")

            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                
                if hasattr(candidate, 'content') and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, 'function_call') and part.function_call:
                            function_name = part.function_call.name
                            function_args = dict(part.function_call.args) if part.function_call.args else {}
                            
                            print(f"✓ Executing function: {function_name} with args: {function_args}")
                            
                            result = await self.session.call_tool(
                                function_name,
                                arguments=function_args
                            )
                            
                            # get question
                            kb_text = result.content[0].text
                            best_q_num, question_text = find_matching_question(kb_text, query)
                            print(f"✓ Most relevant question (Q{best_q_num}): {question_text}")
                            
                            final_query = f"""Original question: {query}

Knowledge base information retrieved:
{result.content[0].text}

Based on this information from our company knowledge base, please provide a comprehensive answer to the original question.

FORMAT YOUR RESPONSE WITH EACH STATEMENT ON A NEW LINE AND USE CLEAR LANGUAGE."""

                            final_response = await self.client.aio.models.generate_content(
                                model=self.model,
                                contents=final_query
                            )
                            
                            return final_response.text

            print("⚠️  WARNING: No function calls detected. Gemini should have used the knowledge base tool.")
            return f"Direct response (no tools used): {response.text}"

        except Exception as e:
            return f"Error calling GenAI API: {str(e)}"
            
    async def cleanup(self):
        """Clean up resources properly."""
        print("🧹 Cleaning up resources...")
        
        try:
            # Cancel pending tasks
            for task in asyncio.all_tasks():
                if task != asyncio.current_task():
                    task.cancel()
                    
            # Close the exit stack to release resources
            await self.exit_stack.aclose()
        except Exception as e:
            print(f"Error during cleanup: {e}")


async def main():
    """Main entry point for the client."""
    client = None
    try:
        client = MCPGenAIClient()
        print("🚀 Starting MCP GenAI Client...")
        await client.connect_to_server("../server.py")
        
        # Clear, single query
        query = "How can I submit a report on expenses?"
        print(f"\nQuery: {query}")

        # Single call to process_query
        response = await client.process_query(query)
        print(f"\nResponse: {response}")
        
    except Exception as e:
        print(f"❌ Main error: {e}")
    finally:
        if client:
            await client.cleanup()
            # Short pause to allow cleanup to complete
            await asyncio.sleep(0.2)
        # Only call once
        kill_server_on_exit()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Program interrupted by Ctrl+C")
    except Exception as e:
        print(f"💥 Error: {e}")
    finally:
        # Double-ensure cleanup runs
        kill_server_on_exit()
        # Force exit to terminate any hanging resources
        print("🏁 Force exiting...")
        os._exit(0)  # More reliable than sys.exit()