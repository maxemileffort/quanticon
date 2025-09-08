import os
import argparse
import logging
from html2text import html2text

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def convert_html_to_md(input_dir, output_dir):
    """
    Walks through the input_dir, converts HTML files to Markdown,
    and saves them to the output_dir, replicating the directory structure.
    It also avoids overwriting existing Markdown files.
    """
    if not os.path.exists(input_dir):
        logging.error(f"Input directory '{input_dir}' does not exist.")
        return
    if not os.path.isdir(input_dir):
        logging.error(f"Input path '{input_dir}' is not a directory.")
        return

    for root, _, files in os.walk(input_dir):
        # Construct the corresponding output directory path
        relative_path = os.path.relpath(root, input_dir)
        current_output_dir = os.path.join(output_dir, relative_path)

        try:
            os.makedirs(current_output_dir, exist_ok=True)
        except OSError as e:
            logging.error(f"Could not create output directory '{current_output_dir}': {e}")
            continue

        for filename in files:
            if not filename.endswith(".html"):
                logging.info(f"Skipping non-HTML file: '{os.path.join(root, filename)}'")
                continue

            input_filepath = os.path.join(root, filename)
            output_filename = os.path.splitext(filename)[0] + ".md"
            output_filepath = os.path.join(current_output_dir, output_filename)

            if os.path.exists(output_filepath):
                logging.info(f"Skipping '{output_filename}' as it already exists in '{current_output_dir}'.")
                continue

            html_content = ""
            try:
                with open(input_filepath, 'r', encoding='utf-8') as f:
                    html_content = f.read()
            except FileNotFoundError:
                logging.warning(f"File not found, skipping: '{input_filepath}'")
                continue
            except IOError as e:
                logging.error(f"Error reading file '{input_filepath}': {e}")
                continue

            if not html_content.strip():
                logging.warning(f"HTML content is empty or whitespace only for '{filename}', skipping conversion.")
                continue

            try:
                markdown_content = html2text(html_content)
            except Exception as e:
                logging.error(f"Error converting HTML to Markdown for '{filename}': {e}")
                continue

            try:
                with open(output_filepath, 'w', encoding='utf-8') as f:
                    f.write(markdown_content)
                logging.info(f"Converted '{os.path.join(relative_path, filename)}' to '{os.path.join(os.path.relpath(current_output_dir, output_dir), output_filename)}'")
            except IOError as e:
                logging.error(f"Error writing Markdown file '{output_filepath}': {e}")
                continue

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert HTML files to Markdown.")
    parser.add_argument("input_directory", help="Path to the directory containing HTML files.")
    parser.add_argument("output_directory", help="Path to the directory where Markdown files will be saved.")
    args = parser.parse_args()

    convert_html_to_md(args.input_directory, args.output_directory)

# example usage:
# python html_to_md.py ./pages ./md
