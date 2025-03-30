'''Script to load a JSONL file as input and export the content as a CSV file.'''

import json
import csv
import click
import re 


def jsonl_to_csv(jsonl_file, csv_file):
    """Convert a JSONL file to a CSV file."""
    try:
        with open(jsonl_file, 'r', encoding='utf-8') as infile, open(csv_file, 'w', newline='', encoding='utf-8') as outfile:
            writer = None
            for line in infile:
                record = json.loads(line.strip())
                # Prettify the 'reportPlain' field for proper rendering in spreadsheet cells
                if 'reportPlain' in record and isinstance(record['reportPlain'], str):
                    # Remove any character before the first occurrence of '* '
                    record['reportPlain'] = re.sub(r'^.*?\* ', '* ', record['reportPlain'], count=1)
                    # Replace Markdown-style bold (**text**) with HTML-style bold (<b>text</b>)
                    # record['reportPlain'] = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', record['reportPlain'])
                    # Add line breaks for better rendering
                    record['reportPlain'] = record['reportPlain'].replace('<br>', '\n')  # Add line breaks after each sentence

                if writer is None:
                    # Initialize CSV writer with headers from the first record
                    writer = csv.DictWriter(outfile, fieldnames=record.keys())
                    writer.writeheader()
                writer.writerow(record)
        click.echo(f"Successfully converted {jsonl_file} to {csv_file}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@click.command()
@click.option('--input', '-i', 'jsonl_file', required=True, type=click.Path(exists=True), help='Path to the input JSONL file.')
@click.option('--output', '-o', 'csv_file', required=True, type=click.Path(), help='Path to the output CSV file.')
def main(jsonl_file, csv_file):
    """Convert a JSONL file to a CSV file."""
    jsonl_to_csv(jsonl_file, csv_file)


if __name__ == "__main__":
    main()