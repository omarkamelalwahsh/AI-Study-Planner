
import sys
import os

sys.path.append(os.getcwd())

try:
    print("Importing app.skills...")
    from app.skills import analyze_career_request
    print("Successfully imported analyze_career_request")
    
    # Try running it with a dummy input if possible (mocking Groq?)
    # analyze_career_request uses Groq client.
    
except Exception as e:
    print(f"Import Error: {e}")
    import traceback
    traceback.print_exc()
