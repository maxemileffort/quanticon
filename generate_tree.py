import os

def generate_tree(startpath):
    print(os.path.basename(startpath) + "/")
    prefix = ""
    
    # Walk the directory
    for root, dirs, files in os.walk(startpath):
        # Modify dirs in-place to skip unwanted directories
        if 'backtests' in dirs:
            dirs.remove('backtests')
            # Manually print backtests as a leaf/collapsed node
            level = root.replace(startpath, '').count(os.sep)
            indent = ' ' * 4 * (level)
            print('{}{}backtests/ (contents hidden)'.format(indent, "|-- "))

        if '__pycache__' in dirs:
            dirs.remove('__pycache__')
        if '.git' in dirs:
            dirs.remove('.git')
            
        level = root.replace(startpath, '').count(os.sep)
        indent = ' ' * 4 * (level)
        subindent = ' ' * 4 * (level + 1)
        
        # files
        for f in files:
            if f.endswith('.pyc'): continue
            print('{}{}{}'.format(indent, "|-- ", f))
            
        # dirs
        for d in dirs:
            print('{}{}{}/'.format(indent, "|-- ", d))

# Actually, os.walk is depth-first but printing it nicely as a tree requires a recursive function usually, 
# or careful handling of os.walk.
# Let's use a recursive function instead for better control over the tree drawing lines.

def print_tree(dir_path, prefix=""):
    # Get list of files and dirs
    try:
        items = os.listdir(dir_path)
    except PermissionError:
        return

    # Filter items
    items = [i for i in items if i not in ['.git', '__pycache__', '.DS_Store'] and not i.endswith('.pyc')]
    items.sort()
    
    # Handle backtests specifically - don't recurse into it
    if 'backtests' in items:
        # We will handle it in the loop, but we need to know not to recurse
        pass

    pointers = [ "|-- " ] * (len(items) - 1) + [ "`-- " ]
    
    for pointer, item in zip(pointers, items):
        path = os.path.join(dir_path, item)
        is_dir = os.path.isdir(path)
        
        print(f"{prefix}{pointer}{item}{'/' if is_dir else ''}")
        
        if is_dir:
            if item == 'backtests':
                # Don't recurse, just indicate it exists
                # Actually we already printed it. We just don't call print_tree.
                print(f"{prefix}{'|   ' if pointer == '|-- ' else '    '}|-- ... (contents hidden)")
            else:
                extension = "|   " if pointer == "|-- " else "    "
                print_tree(path, prefix + extension)

if __name__ == "__main__":
    target_dir = "quanticon"
    print(f"{target_dir}/")
    print_tree(target_dir)
