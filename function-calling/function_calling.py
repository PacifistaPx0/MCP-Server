""" Utilizing Function calling for AI integration """

import json
from google import generativeai as genai
from decouple import config
from tools import add


# Load API key from .env file
api_key = config('GOOGLE_API_KEY', default=None)
if not api_key:
    raise ValueError("No Google API key found! Please check your .env file.")

# Configure the client - UPDATED METHOD
genai.configure(api_key=api_key)  # This is the correct method

# Define tool for the model - UPDATED TOOLS FORMAT
add_tool = {
    "function_declarations": [
        {
            "name": "add",
            "description": "Add two numbers together",
            "parameters": {
                "type": "object",  # Use lowercase "object"
                "properties": {
                    "a": {"type": "integer", "description": "First number"},  # Use lowercase "integer"
                    "b": {"type": "integer", "description": "Second number"}
                },
                "required": ["a", "b"]
            }
        }
    ]
}

# Initialize the model
model = genai.GenerativeModel('gemini-2.0-flash')

# Call LLM - UPDATED API CALL
response = model.generate_content(
    "Calculate 25 + 17",
    generation_config=genai.GenerationConfig(
        temperature=0.1,
    ),
    tools=[add_tool]  # Pass the function declaration
)

# Handle tool calls
if response.candidates[0].content.parts and any(
    hasattr(part, 'function_call') for part in response.candidates[0].content.parts
):
    # Extract function call
    for part in response.candidates[0].content.parts:
        if hasattr(part, 'function_call') and part.function_call:
            function_call = part.function_call
            function_name = function_call.name
            function_args = dict(function_call.args)
            
            print(f"Function called: {function_name}")
            print(f"Arguments: {function_args}")
            
            # Execute the function
            result = add(**function_args)
            print(f"Result: {result}")
            
            # Send result back to model
            final_response = model.generate_content(
                contents=[
                    {"role": "user", "parts": [{"text": "Calculate 25 + 17"}]},
                    {"role": "model", "parts": [{"function_call": {
                        "name": function_name,
                        "args": function_args
                    }}]},
                    
                    {"role": "user", "parts": [{"text": f"The result of adding {function_args['a']} and {function_args['b']} is {result}"}]}
                ]
            )
            print(f"Final response: {final_response.text}")
else:
    print(f"Direct response (no function call): {response.text}")