# /desktop-commander

This slash command instructs Claude to use the desktop-commander MCP server for file operations and command execution.

## Instructions for Claude

When this command is used:
1. **Always start by checking the current working directory** using `$PWD` or equivalent command
2. **Use desktop-commander MCP server tools** for all file operations:
   - `mcp__desktop-commander__execute_command` for terminal commands
   - `mcp__desktop-commander__read_file` for reading files
   - `mcp__desktop-commander__write_file` for writing files
   - `mcp__desktop-commander__edit_block` for editing files
   - `mcp__desktop-commander__search_code` for searching code
   - `mcp__desktop-commander__search_files` for finding files
   - `mcp__desktop-commander__list_directory` for listing directories
3. **Always use absolute paths** when working with desktop-commander tools
4. **Project root directory**: `C:\Users\gk3t-\OneDrive - 又村 友幸\working\PresidioPDF`

## Usage

Type `/desktop-commander` to activate this mode for desktop-commander MCP server usage.