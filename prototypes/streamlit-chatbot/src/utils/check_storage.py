# check_storage.py
import os
from pathlib import Path

def get_size_format(bytes):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024

def analyze_directory(path='.', indent=''):
    total_size = 0
    
    try:
        # List all items in directory
        items = os.listdir(path)
        
        # Sort items (directories first, then files)
        dirs = []
        files = []
        for item in items:
            full_path = os.path.join(path, item)
            if os.path.isdir(full_path):
                dirs.append(item)
            else:
                files.append(item)
                
        dirs.sort()
        files.sort()
        
        # Process directories
        for dir_name in dirs:
            full_path = os.path.join(path, dir_name)
            try:
                dir_size = sum(
                    os.path.getsize(os.path.join(dirpath, filename))
                    for dirpath, dirnames, filenames in os.walk(full_path)
                    for filename in filenames
                )
                print(f"{indent}📁 {dir_name}/ ({get_size_format(dir_size)})")
                # Recursively analyze subdirectories
                analyze_directory(full_path, indent + '  ')
                total_size += dir_size
            except Exception as e:
                print(f"{indent}Error accessing {dir_name}: {e}")
        
        # Process files
        for file_name in files:
            full_path = os.path.join(path, file_name)
            try:
                file_size = os.path.getsize(full_path)
                total_size += file_size
                print(f"{indent}📄 {file_name} ({get_size_format(file_size)})")
            except Exception as e:
                print(f"{indent}Error accessing {file_name}: {e}")
                
    except Exception as e:
        print(f"Error accessing directory {path}: {e}")
        
    return total_size

def analyze_project():
    print("\nProject Structure and Size Analysis")
    print("=" * 50)
    
    # Get project root directory
    project_root = str(Path(__file__).resolve().parent.parent.parent)
    print(f"\nProject Root: {project_root}")
    print("-" * 50)
    
    # Analyze entire project structure
    total_size = analyze_directory(project_root)
    
    print("\nSummary")
    print("-" * 50)
    print(f"Total Project Size: {get_size_format(total_size)}")
    
    # Count files by type
    file_types = {}
    for root, _, files in os.walk('.'):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext:
                file_types[ext] = file_types.get(ext, 0) + 1
    
    print("\nFile Types:")
    for ext, count in sorted(file_types.items()):
        print(f"{ext}: {count} files")

def check_cache_directories():
    print("\nChecking Cache Directories")
    print("=" * 50)
    
    home = str(Path.home())
    cache_dirs = {
        "HuggingFace": os.path.join(home, ".cache", "huggingface"),
        "Torch": os.path.join(home, ".cache", "torch"),
        "Transformers": os.path.join(home, ".cache", "transformers")
    }
    
    found_cache = False
    for name, path in cache_dirs.items():
        if os.path.exists(path):
            found_cache = True
            print(f"\n{name} Cache:")
            print(f"Location: {path}")
            try:
                size = sum(
                    os.path.getsize(os.path.join(dirpath, filename))
                    for dirpath, dirnames, filenames in os.walk(path)
                    for filename in filenames
                )
                print(f"Size: {get_size_format(size)}")
            except Exception as e:
                print(f"Error calculating size: {e}")
    
    if not found_cache:
        print("\nNo cache directories found!")
    
    return found_cache

if __name__ == "__main__":
    # Analyze project structure
    analyze_project()
    
    # Check cache directories
    found_cache = check_cache_directories()
    
    if found_cache:
        print("\nWould you like to delete the cache directories?")
        choice = input("Enter 'yes' to delete: ")
        if choice.lower() == 'yes':
            home = str(Path.home())
            cache_dirs = [
                os.path.join(home, ".cache", "huggingface"),
                os.path.join(home, ".cache", "torch"),
                os.path.join(home, ".cache", "transformers")
            ]
            
            for dir_path in cache_dirs:
                if os.path.exists(dir_path):
                    try:
                        import shutil
                        shutil.rmtree(dir_path)
                        print(f"Deleted: {dir_path}")
                    except Exception as e:
                        print(f"Error deleting {dir_path}: {e}")