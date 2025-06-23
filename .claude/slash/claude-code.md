# /claude-code

This slash command instructs Claude to use standard Claude Code tools instead of the desktop-commander MCP server.

## Instructions for Claude

When this command is used:
1. **Do NOT use desktop-commander MCP server tools**
2. **Use standard Claude Code tools** for file operations:
   - `Bash` for terminal commands
   - `Read` for reading files
   - `Write` for writing files
   - `Edit` or `MultiEdit` for editing files
   - `Grep` for searching code content
   - `Glob` for finding files by pattern
   - `LS` for listing directories
3. **Use relative paths** as appropriate for standard tools
4. **Follow standard Claude Code conventions** for file operations

## Usage

Type `/claude-code` to activate this mode for standard Claude Code tool usage without desktop-commander MCP server.