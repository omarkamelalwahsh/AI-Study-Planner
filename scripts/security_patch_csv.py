import re
import os

file_path = os.path.join(os.getcwd(), 'data', 'courses.csv')

def clean_csv():
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Regex to match ?token=... (non-greedy until formatted end or strict chars)
        # Tokens in the file look like ?token=... ending at line end or close quote
        # Safe regex: \?token=[a-zA-Z0-9._-]+
        
        new_content = re.sub(r'\?token=[a-zA-Z0-9._-]+', '', content)
        
        if len(new_content) < len(content):
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print("Successfully cleaned tokens from courses.csv")
        else:
            print("No tokens found or no changes made.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    clean_csv()
