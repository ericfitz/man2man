#!/usr/bin/env python3
# /// script
# dependencies = [
#   "requests>=2.31.0",
#   "beautifulsoup4>=4.12.0",
# ]
# ///

"""
Man page to JSON converter
Reads a man page and converts it to structured JSON format.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from typing import List, Dict, Any, Optional

import requests
from bs4 import BeautifulSoup


def get_man_page_from_web(command: str) -> Optional[str]:
    """Fetch man page from linux.die.net."""
    try:
        url = f"https://linux.die.net/man/1/{command}"
        print(f"Fetching man page from {url}...", file=sys.stderr)

        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            print(f"Error: Could not fetch man page from web (status {response.status_code})", file=sys.stderr)
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the man page content
        content_div = soup.find('div', {'id': 'content'})
        if not content_div:
            print("Error: Could not parse web man page", file=sys.stderr)
            return None

        # Extract text from the content
        text = content_div.get_text()
        return text
    except requests.RequestException as e:
        print(f"Error fetching from web: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error parsing web man page: {e}", file=sys.stderr)
        return None


def get_man_page(command: str) -> Optional[str]:
    """Fetch the man page content for a given command."""
    try:
        # Use col -b to remove formatting characters
        man_proc = subprocess.Popen(
            ['man', command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        col_proc = subprocess.Popen(
            ['col', '-b'],
            stdin=man_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        man_proc.stdout.close()
        stdout, stderr = col_proc.communicate()

        if col_proc.returncode != 0 or not stdout.strip():
            print(f"Local man page not found for '{command}', trying web...", file=sys.stderr)
            return get_man_page_from_web(command)

        return stdout
    except subprocess.CalledProcessError:
        print(f"Local man page not found for '{command}', trying web...", file=sys.stderr)
        return get_man_page_from_web(command)
    except FileNotFoundError:
        print("'man' or 'col' command not found, trying web...", file=sys.stderr)
        return get_man_page_from_web(command)


def extract_description(man_content: str) -> str:
    """Extract the description from the NAME or DESCRIPTION section."""
    # Try NAME section first (usually has one-line description)
    name_match = re.search(r'NAME\s*\n\s*\S+\s*[-–—]\s*(.+?)(?=\n\S|\n\n)', man_content, re.DOTALL)
    if name_match:
        desc = name_match.group(1).strip()
        # Clean up whitespace and newlines
        desc = re.sub(r'\s+', ' ', desc)
        return desc

    # Fall back to DESCRIPTION section
    desc_match = re.search(r'DESCRIPTION\s*\n\s*(.+?)(?=\n\S+\n|\n\n\S)', man_content, re.DOTALL)
    if desc_match:
        desc = desc_match.group(1).strip()
        # Take first sentence or first 200 chars
        sentences = re.split(r'[.!?]\s+', desc)
        if sentences:
            return sentences[0].strip()

    return "No description available"


def classify_parameter_type(param_name: str, description: str, first_line: str = "") -> str:
    """Classify the parameter type based on its format and description."""
    # Flag: no value needed (e.g., -v, --verbose)
    if re.search(r'\b(toggle|enable|disable|flag)\b', description.lower()):
        return "flag"

    # Check for key-value patterns in description or first_line
    combined_text = f"{param_name} {first_line} {description}"

    # Option with key=value pattern: --cookie name=value
    if re.search(r'\b\w+=\w+\b', combined_text) and '=' not in param_name:
        # This is option-kv-equals: option takes "key=value" format
        if re.search(r'\bname=value\b', combined_text, re.IGNORECASE):
            return "option-kv-equals"

    # Option with key:value pattern: -A username:password
    if re.search(r'\b\w+:\w+\b', combined_text) and ':' not in param_name:
        # This is option-kv-colon: option takes "key:value" format
        if re.search(r'\busername:password\b', combined_text, re.IGNORECASE) or \
           re.search(r'\bname:value\b', combined_text, re.IGNORECASE):
            return "option-kv-colon"

    # Option with equals in the param itself: --option=value
    if '=' in param_name or re.search(r'--\w+=', description):
        return "option-equals"

    # Check if it takes a value
    if re.search(r'\s+\w+(?:\s+|\]|$)', param_name):
        return "option"

    # Default to flag if it's a short option without clear value
    if param_name.startswith('-') and len(param_name) == 2:
        # Check context - if description mentions a value, it's an option
        if re.search(r'\b(specify|set|use|take|accept|require)\b', description.lower()):
            return "option"
        return "flag"

    return "option"


def extract_value_type(param_text: str, description: str) -> Optional[str]:
    """Extract the value type from parameter documentation."""
    # Common patterns in man pages
    value_patterns = [
        r'[-<](\w+(?:[_-]\w+)*)[>\]]',  # <file> or -file or [file]
        r'\s+(\w+(?:[_-]\w+)*)\s*\.\.\.',  # file...
        r'=(\w+(?:[_-]\w+)*)',  # =value
        r'\s+([A-Z][A-Z_]+)\b',  # VALUE (all caps)
    ]

    for pattern in value_patterns:
        match = re.search(pattern, param_text)
        if match:
            value_type = match.group(1).lower()
            # Normalize common types
            if value_type in ['file', 'path', 'filename', 'filepath']:
                return "file-path"
            elif value_type in ['num', 'number', 'n', 'count']:
                return "number"
            elif value_type in ['string', 'str', 'text']:
                return "string"
            elif value_type in ['pid', 'process']:
                return "pid"
            elif value_type in ['dir', 'directory']:
                return "directory"
            return value_type

    # Check description for hints
    desc_lower = description.lower()
    if 'file' in desc_lower or 'path' in desc_lower:
        return "file-path"
    elif 'number' in desc_lower or 'numeric' in desc_lower:
        return "number"
    elif 'directory' in desc_lower:
        return "directory"
    elif 'pid' in desc_lower or 'process id' in desc_lower:
        return "pid"

    return None


def parse_options(man_content: str) -> List[Dict[str, Any]]:
    """Parse the OPTIONS section of the man page."""
    parameters = []

    # Find OPTIONS section or section with options described
    # Some man pages have "The following options are available:"
    options_match = re.search(
        r'(?:OPTIONS|The following options are available:?)\s*\n(.*?)(?=\n[A-Z][A-Z\s]+\n|\Z)',
        man_content,
        re.DOTALL | re.MULTILINE | re.IGNORECASE
    )

    if not options_match:
        return parameters

    options_text = options_match.group(1)

    # Split into individual option entries
    # Pattern: lines starting with whitespace followed by - or --
    option_entries = re.split(r'\n(?=\s+-)', options_text)

    for entry in option_entries:
        if not entry.strip():
            continue

        lines = entry.strip().split('\n')
        if not lines:
            continue

        first_line = lines[0].strip()

        # Skip if it doesn't start with a dash
        if not first_line.startswith('-'):
            continue

        # Extract option names and any inline value specifier
        # Patterns: -a, --long, -D format, --color=when, --file=FILE
        option_pattern = r'(-{1,2}[a-zA-Z0-9_-]+(?:=\S+)?|\-[a-zA-Z](?:\s+\S+)?)'
        option_matches = re.findall(option_pattern, first_line)

        if not option_matches:
            continue

        # Get the primary option (first one)
        primary_option = option_matches[0]

        # Get description from remaining lines
        description_lines = []

        # Check if there's description on the first line after the option
        desc_on_first = re.sub(option_pattern, '', first_line, count=len(option_matches))
        desc_on_first = desc_on_first.strip()
        if desc_on_first:
            description_lines.append(desc_on_first)

        # Add subsequent lines
        for line in lines[1:]:
            cleaned = line.strip()
            if cleaned:
                description_lines.append(cleaned)

        description = ' '.join(description_lines)
        description = re.sub(r'\s+', ' ', description).strip()

        # Parse the option
        param_type = classify_parameter_type(primary_option, description, first_line)
        value_type = extract_value_type(first_line, description) if param_type not in ["flag"] else None

        param = {
            "name": primary_option.strip(),
            "param-type": param_type,
        }

        if value_type:
            param["value-type"] = value_type

        if description:
            param["description"] = description[:200]  # Truncate long descriptions

        parameters.append(param)

    return parameters


def parse_positional_args(man_content: str, command: str) -> List[Dict[str, Any]]:
    """Parse positional arguments from SYNOPSIS section."""
    parameters = []

    # Find SYNOPSIS section
    synopsis_match = re.search(
        r'SYNOPSIS\s*\n\s*(.+?)(?=\n\n|\n[A-Z])',
        man_content,
        re.DOTALL
    )

    if not synopsis_match:
        return parameters

    synopsis = synopsis_match.group(1).strip()

    # Look for positional arguments (non-option arguments in synopsis)
    # Remove the command name and options
    synopsis = re.sub(rf'\b{command}\b', '', synopsis)
    synopsis = re.sub(r'\[?-{1,2}\w+(?:\s+\w+)?\]?', '', synopsis)

    # Find remaining words (likely positional args)
    positional_pattern = r'\[?([A-Z_]+|\w+\.\.\.)(?:\s+[A-Z_]+|\s+\w+\.\.\.)?\]?'
    positional_matches = re.findall(positional_pattern, synopsis)

    for idx, pos_arg in enumerate(positional_matches, 1):
        if pos_arg.strip():
            param = {
                "name": pos_arg.strip(),
                "param-type": "positional",
                "position": idx
            }

            # Infer value type
            arg_lower = pos_arg.lower()
            if 'file' in arg_lower or 'path' in arg_lower:
                param["value-type"] = "file-path"
            elif 'dir' in arg_lower:
                param["value-type"] = "directory"
            elif 'pid' in arg_lower:
                param["value-type"] = "pid"
            else:
                param["value-type"] = arg_lower.rstrip('.')

            parameters.append(param)

    return parameters


def man_to_json(command: str) -> Dict[str, Any]:
    """Convert a man page to JSON format."""
    man_content = get_man_page(command)

    if not man_content:
        return None

    # Extract description
    description = extract_description(man_content)

    # Parse options
    options = parse_options(man_content)

    # Parse positional arguments
    positional = parse_positional_args(man_content, command)

    # Combine all parameters
    all_parameters = positional + options

    return {
        "tool": {
            "name": command,
            "description": description,
            "parameters": all_parameters
        }
    }


def main():
    parser = argparse.ArgumentParser(
        description='Convert man pages to structured JSON format'
    )
    parser.add_argument(
        'command',
        help='Name of the command-line tool to process'
    )
    parser.add_argument(
        '-o', '--output',
        dest='output_file',
        help='Output JSON file (if exists, appends to tools array)'
    )
    parser.add_argument(
        '--pretty',
        action='store_true',
        help='Pretty-print JSON output'
    )

    args = parser.parse_args()

    result = man_to_json(args.command)

    if not result:
        return 1

    indent = 2 if args.pretty else None

    # Handle output
    if args.output_file:
        # Check if file exists
        if os.path.exists(args.output_file):
            try:
                # Read existing file
                with open(args.output_file, 'r') as f:
                    existing_data = json.load(f)

                # Ensure it has a "tools" array
                if "tools" not in existing_data:
                    existing_data = {"tools": []}
                elif not isinstance(existing_data["tools"], list):
                    print("Error: Existing file's 'tools' is not an array", file=sys.stderr)
                    return 1

                # Append the new tool
                existing_data["tools"].append(result["tool"])

                # Write back to file
                with open(args.output_file, 'w') as f:
                    json.dump(existing_data, f, indent=indent)

                print(f"Appended {args.command} to {args.output_file}", file=sys.stderr)
            except json.JSONDecodeError:
                print(f"Error: Could not parse existing JSON file {args.output_file}", file=sys.stderr)
                return 1
            except Exception as e:
                print(f"Error writing to file: {e}", file=sys.stderr)
                return 1
        else:
            # Create new file with tools array
            try:
                output_data = {"tools": [result["tool"]]}
                with open(args.output_file, 'w') as f:
                    json.dump(output_data, f, indent=indent)

                print(f"Created {args.output_file} with {args.command}", file=sys.stderr)
            except Exception as e:
                print(f"Error writing to file: {e}", file=sys.stderr)
                return 1
    else:
        # Output to stdout
        print(json.dumps(result, indent=indent))

    return 0


if __name__ == '__main__':
    sys.exit(main())
