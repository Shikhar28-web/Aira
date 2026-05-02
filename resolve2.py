import os

def resolve_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return

    new_lines = []
    state = 'normal'
    conflict_count = 0
    
    for line in lines:
        if line.startswith('<<<<<<< HEAD'):
            state = 'in_head'
            conflict_count += 1
        elif line.startswith('======='):
            state = 'in_master'
        elif line.startswith('>>>>>>>'):
            state = 'normal'
        else:
            if state == 'normal':
                new_lines.append(line)
            elif state == 'in_head':
                pass # Discard HEAD
            elif state == 'in_master':
                new_lines.append(line) # Keep master
                
    if conflict_count > 0:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print(f"Resolved {conflict_count} conflicts in {filepath}")

for root, _, files in os.walk('c:/Users/Shikhar/OneDrive/Desktop/sem4_projects/Aira/backend'):
    for file in files:
        if file.endswith('.py'):
            resolve_file(os.path.join(root, file))
