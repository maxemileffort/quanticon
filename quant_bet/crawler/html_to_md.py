import os
import argparse
from html2text import html2text

def convert_html_to_md(input_dir, output_dir):
    """
    Loops through HTML files in the input_dir, converts them to Markdown,
    and saves them to the output_dir.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for filename in os.listdir(input_dir):
        if filename.endswith(".html"):
            input_filepath = os.path.join(input_dir, filename)
            output_filename = os.path.splitext(filename)[0] + ".md"
            output_filepath = os.path.join(output_dir, output_filename)

            with open(input_filepath, 'r', encoding='utf-8') as f:
                html_content = f.read()

            markdown_content = html2text(html_content)

            with open(output_filepath, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            print(f"Converted '{filename}' to '{output_filename}'")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert HTML files to Markdown.")
    parser.add_argument("input_directory", help="Path to the directory containing HTML files.")
    parser.add_argument("output_directory", help="Path to the directory where Markdown files will be saved.")
    args = parser.parse_args()

    convert_html_to_md(args.input_directory, args.output_directory)


# python html_to_md.py pages md