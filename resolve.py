import os
import re

def resolve_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return

    # Pattern to match:
    # <<<<<<< HEAD
    # (HEAD content)
    # =======
    # (master content)
    # >>>>>>> master (or similar)
    pattern = re.compile(r'<<<<<<< HEAD.*?\n(.*?)=======\n(.*?)\n>>>>>>>.*?\n', re.DOTALL)
    
    def repl(match):
        return match.group(2) + '\n'

    new_content, count = pattern.subn(repl, content)
    
    if count > 0:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Resolved {count} conflicts in {filepath}")

for root, _, files in os.walk('c:/Users/Shikhar/OneDrive/Desktop/sem4_projects/Aira/backend'):
    for file in files:
        if file.endswith('.py'):
            resolve_file(os.path.join(root, file))
