import os
import time
from datetime import datetime, timedelta
from pathlib import Path

def get_crawled_links_dir(base_dir: Path) -> Path:
    """Returns the path to the links_crawled directory, ensuring it exists."""
    links_dir = base_dir / "links_crawled"
    links_dir.mkdir(parents=True, exist_ok=True)
    return links_dir

def load_recent_crawled_links(base_dir: Path, hours: int = 24) -> set[str]:
    """
    Reads all link files in links_crawled that are less than X hours old
    and returns a set of all unique URLs found in them.
    """
    links_dir = get_crawled_links_dir(base_dir)
    recently_crawled = set()
    time_threshold = datetime.now() - timedelta(hours=hours)

    for file_path in links_dir.iterdir():
        if file_path.is_file() and file_path.suffix == ".txt":
            # Get creation time (ctime) for Windows/Unix compatibility
            # On Windows, st_ctime is creation time. On Unix, it's last metadata change.
            # For cross-platform, st_mtime (last modification time) is often more reliable
            # for "freshness" if files are written once and then not touched.
            # Given the user's request for "ctime" and Windows OS, we'll use st_ctime.
            file_ctime = datetime.fromtimestamp(file_path.stat().st_ctime)
            
            if file_ctime > time_threshold:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            link = line.strip()
                            if link:
                                recently_crawled.add(link)
                except Exception as e:
                    print(f"WARNING: Could not read link file {file_path}: {e}")
    return recently_crawled

def save_current_crawled_links(base_dir: Path, links_set: set[str]):
    """
    Creates a new timestamped file in links_crawled and writes the links_set to it.
    """
    links_dir = get_crawled_links_dir(base_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"links_{timestamp}.txt"
    file_path = links_dir / file_name

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            for link in sorted(list(links_set)): # Sort for consistent file content
                f.write(link + '\n')
        print(f"INFO: Saved {len(links_set)} crawled links to {file_path.name}")
    except Exception as e:
        print(f"ERROR: Could not save crawled links to {file_path.name}: {e}")
