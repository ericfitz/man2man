# man2man

man-page-to-manifest

A Python script that parses man pages and converts them to a structured JSON manifest format. This tool extracts command information including description, parameters, parameter types, and value types from Unix/Linux man pages. If a man page is not available locally, it automatically fetches it from linux.die.net.

## Installation

This script uses UV for dependency management. UV will automatically install required dependencies when you run the script.

### Requirements

- Python 3.8+
- UV (Python package manager)
- `man` command (standard on Unix/Linux/macOS)
- `col` command (standard on Unix/Linux/macOS)

### Dependencies

The project dependencies are defined in both the inline script metadata and `pyproject.toml`:

- `requests>=2.31.0` - For fetching man pages from the web
- `beautifulsoup4>=4.12.0` - For parsing HTML man pages

UV will automatically install these when running the script.

## Usage

Basic usage (output to console):

```bash
uv run man2man.py <command-name>
```

With pretty-printed output:

```bash
uv run man2man.py <command-name> --pretty
```

Output to a file:

```bash
uv run man2man.py <command-name> -o output.json --pretty
```

Append to an existing file:

```bash
# First command creates the file
uv run man2man.py grep -o tools.json --pretty

# Subsequent commands append to the tools array
uv run man2man.py ls -o tools.json --pretty
uv run man2man.py curl -o tools.json --pretty
```

Examples:

```bash
# Get grep parameters in compact JSON to console
uv run man2man.py grep

# Get ls parameters with pretty formatting
uv run man2man.py ls --pretty

# Build a collection of tools in one file
uv run man2man.py ps -o mytools.json --pretty
uv run man2man.py tar -o mytools.json --pretty
uv run man2man.py find -o mytools.json --pretty
```

You can also make the script executable:

```bash
chmod +x man2man.py
./man2man.py grep --pretty
```

## Output Format

### Single Tool (Console Output)

When outputting to console, the script outputs JSON with this structure:

```json
{
  "tool": {
    "name": "<command-name>",
    "description": "<description from man page>",
    "parameters": [
      {
        "name": "<parameter name, e.g., '-a', '--all'>",
        "param-type": "<type>",
        "value-type": "<optional value type>",
        "position": "<optional position for positional args>",
        "description": "<optional description>"
      }
    ]
  }
}
```

### Multiple Tools (File Output)

When using the `-o` flag, tools are stored in an array:

```json
{
  "tools": [
    {
      "name": "grep",
      "description": "...",
      "parameters": [...]
    },
    {
      "name": "ls",
      "description": "...",
      "parameters": [...]
    }
  ]
}
```

### Parameter Types

The script categorizes parameters into six types:

1. **`positional`** - Positional arguments that must appear in a specific order

   - Example: `FILE` in `cat FILE`
   - Includes a `position` field (1-based)

2. **`flag`** - Boolean flags that don't take values

   - Example: `-v`, `--verbose`
   - No `value-type` field

3. **`option`** - Options that take a space-separated value

   - Example: `-o file`, `--output file`
   - Includes `value-type` field

4. **`option-equals`** - Options using equals syntax for the option itself

   - Example: `--output=file`, `--color=auto`
   - Includes `value-type` field

5. **`option-kv-equals`** - Options that take key=value pairs

   - Example: `--cookie name=value` in curl
   - Includes `value-type` field

6. **`option-kv-colon`** - Options that take key:value pairs
   - Example: `-A username:password` in ab
   - Includes `value-type` field

### Value Types

When a parameter takes a value, the script attempts to identify the type:

- `file-path` - File or path arguments
- `directory` - Directory arguments
- `number` - Numeric values
- `pid` - Process IDs
- `string` - String values
- Custom types extracted from man page syntax (e.g., `pattern`, `action`)

## Features

- **Local man pages first**: Attempts to read man pages from the local system
- **Web fallback**: Automatically fetches from https://linux.die.net if local man page not found
- **Smart parameter classification**: Identifies 6 different parameter types including key-value options
- **File output with append**: Build a collection of tools in a single JSON file
- **Pretty printing**: Optional formatted output for readability

## Examples

### grep command:

```bash
uv run man2man.py grep --pretty
```

Output excerpt:

```json
{
  "tool": {
    "name": "grep",
    "description": "The grep utility searches any given input files...",
    "parameters": [
      {
        "name": "-i",
        "param-type": "flag",
        "description": "Perform case insensitive matching..."
      },
      {
        "name": "-e",
        "param-type": "option",
        "value-type": "pattern",
        "description": "Specify a pattern used during the search..."
      },
      {
        "name": "--color=when",
        "param-type": "option-equals",
        "description": "Mark up the matching text..."
      }
    ]
  }
}
```

## How It Works

1. **Fetches man page** - Uses the `man` command and pipes through `col -b` to remove formatting, falls back to web if not found
2. **Extracts description** - Parses the NAME and DESCRIPTION sections
3. **Parses parameters** - Analyzes the OPTIONS section to extract parameter information
4. **Classifies parameters** - Determines parameter type based on syntax and description (including key-value patterns)
5. **Infers value types** - Examines parameter syntax and descriptions to identify value types
6. **Outputs JSON** - Formats all information as structured JSON, either to console or file with append support

## Limitations

- Man page formats vary across systems and commands
- Some complex parameter syntaxes may not be perfectly parsed
- Descriptions are truncated to 200 characters
- Works best with standard GNU/BSD style man pages

## License

MIT License - feel free to use and modify as needed.
