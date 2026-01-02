import os
from dotenv import load_dotenv

load_dotenv()

try:
    from openai import OpenAI
    print("OpenAI version:", OpenAI.__version__ if hasattr(OpenAI, '__version__') else 'unknown')

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("No API key set, using dummy")
        api_key = "dummy"

    print("Trying to initialize OpenAI client...")
    client = OpenAI(api_key=api_key)
    print("Success!")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
