import os
import re
import shutil
from datetime import datetime

def organize_md_files(md_dir):
    """
    Organizes markdown files in the specified directory into subfolders based on
    the domain at the beginning of the filename and the file's creation date.
    """
    if not os.path.exists(md_dir):
        print(f"Error: Directory '{md_dir}' does not exist.")
        return

    for filename in os.listdir(md_dir):
        file_path = os.path.join(md_dir, filename)

        if os.path.isfile(file_path) and filename.endswith(".md"):
            # Extract domain from filename using multiple strategies
            domain = None

            # Strategy 1: Original regex for domain.tld.com patterns
            match_string_1 = r"([^.]+)\.([^.]+)\.(com|org|gov|edu)"
            match_1 = re.match(match_string_1, filename)
            if match_1:
                domain = f"{match_1.group(1)}.{match_1.group(2)}"

            # Strategy 2: Everything before the first '--' and replace subsequent '--' with '.'
            if domain is None:
                domain_end_index = filename.find("--")
                if domain_end_index != -1:
                    raw_domain = filename[:domain_end_index]
                    domain = raw_domain.replace("--", ".")

            # Strategy 3: Everything before the timestamp pattern (e.g., -<10_digits>-<8_hex_chars>.md)
            if domain is None:
                match_3 = re.match(r"(.+?)(-\d{10}-[0-9a-f]{8}\.md)", filename)
                if match_3:
                    raw_domain = match_3.group(1)
                    domain = raw_domain.replace("--", ".") # Replace double hyphens with dots for domains like github.com--openai

            if domain is None:
                print(f"Could not extract domain from filename: {filename}. Skipping.")
                continue

            # Get file creation date
            # On Windows, os.path.getctime returns creation time.
            # On Unix-like systems, it returns the last metadata change time.
            # For cross-platform consistency, we'll use ctime and assume it's creation time for this task.
            creation_timestamp = os.path.getctime(file_path)
            creation_date = datetime.fromtimestamp(creation_timestamp).strftime("%Y-%m-%d")

            # Create target directory path
            target_dir = os.path.join(md_dir, creation_date + ' - ' + domain)
            os.makedirs(target_dir, exist_ok=True)

            # Move the file
            shutil.move(file_path, os.path.join(target_dir, filename))
            print(f"Moved '{filename}' to '{target_dir}'")

if __name__ == "__main__":
    # Assuming the script is in 'surfs_up/' and 'md/' is a subdirectory
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    md_directory_to_organize = os.path.join(current_script_dir, "md")
    organize_md_files(md_directory_to_organize)
