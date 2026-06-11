import json
import sys

# Force UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

transcript_path = r"C:\Users\User\.gemini\antigravity\brain\f19f4b02-022d-47b0-83e2-303bbd5b5150\.system_generated\logs\transcript.jsonl"

try:
    with open(transcript_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    # Let's search from the end for the USER_INPUT step
    user_input = None
    for line in reversed(lines):
        try:
            data = json.loads(line)
            if data.get("type") == "USER_INPUT":
                user_input = data
                break
        except Exception:
            continue
            
    if user_input:
        content = user_input.get("content", "")
        print(f"FOUND USER INPUT (length={len(content)}):")
        print(content)
    else:
        print("USER_INPUT not found in transcript.jsonl")
except Exception as e:
    print(f"Error reading transcript: {e}")
