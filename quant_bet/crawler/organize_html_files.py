import os
import re
import shutil
from datetime import datetime

def organize_html_files(html_dir):
    """
    Organizes html files in the specified directory into subfolders based on
    the domain at the beginning of the filename and the file's creation date.
    """
    if not os.path.exists(html_dir):
        print(f"Error: Directory '{html_dir}' does not exist.")
        return

    for filename in os.listdir(html_dir):
        file_path = os.path.join(html_dir, filename)

        if os.path.isfile(file_path) and filename.endswith(".html"):
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

            # Strategy 3: Everything before the timestamp pattern (e.g., -<10_digits>-<8_hex_chars>.html)
            if domain is None:
                match_3 = re.match(r"(.+?)(-\d{10}-[0-9a-f]{8}\.html)", filename)
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
            target_dir = os.path.join(html_dir, creation_date + ' - ' + domain)
            os.makedirs(target_dir, exist_ok=True)

            # Move the file
            shutil.move(file_path, os.path.join(target_dir, filename))
            print(f"Moved '{filename}' to '{target_dir}'")

if __name__ == "__main__":
    # Assuming the script is in 'crawler/' and 'pages/' is a subdirectory
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    html_directory_to_organize = os.path.join(current_script_dir, "pages")
    organize_html_files(html_directory_to_organize)
