
import os
from google import genai

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("No API Key found")
    exit()

try:
    client = genai.Client(api_key=api_key)
    # List models to see what's available
    # The SDK might not have a direct list_models in the Client, usually it is client.models.list()
    # Let's try to interpret the error or just try a generation with gemini-2.0-flash-exp
    print("Attempting to generate with gemini-2.0-flash-exp...")
    response = client.models.generate_content(model='gemini-2.0-flash-exp', contents='Hello')
    print("gemini-2.0-flash-exp is WORKING")
except Exception as e:
    print(f"gemini-2.0-flash-exp failed: {e}")

try:
    print("Attempting to generate with gemini-1.5-pro...")
    response = client.models.generate_content(model='gemini-1.5-pro', contents='Hello')
    print("gemini-1.5-pro is WORKING")
except Exception as e:
    print(f"gemini-1.5-pro failed: {e}")
