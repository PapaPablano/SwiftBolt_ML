# Coding Agent Skill

This skill provides programmatic control over various coding agents including Codex, Claude Code, OpenCode, and Pi Coding Agent.

## When to Apply

Use this skill when:
- Managing background coding agent processes
- Working with PTY mode for interactive terminals
- Setting up proper working directory contexts
- Executing coding agents with specific flags
- Monitoring and controlling agent sessions
- Performing batch operations with multiple agents

## Core Competencies

### PTY Mode
- All coding agents require pseudo-terminal (PTY) for proper operation
- Always use `pty:true` when running coding agents
- Without PTY, agents may hang or produce broken output

### Background Process Management
- Run coding agents in background for longer tasks
- Use `background:true` parameter to start processes
- Monitor sessions with `process action:log`
- Control sessions with `process action:poll`, `process action:kill`, etc.

### Working Directory Context
- Use `workdir` parameter to set agent context
- Agents operate only within specified directory
- Prevents wandering off and reading unrelated files

### Agent-Specific Usage
- **Codex CLI**: Supports `exec`, `--full-auto`, `--yolo` flags
- **Claude Code**: Use `claude` command with proper PTY
- **OpenCode**: Use `opencode run` command
- **Pi Coding Agent**: Use `pi` command with various options

## Output Format

Provide clear, structured guidance with:
- Proper bash command syntax
- PTY requirements
- Working directory considerations
- Process monitoring instructions
- Error handling advice

## Usage

This skill can be invoked in Claude Code when:
1. User mentions coding agents (Codex, Claude Code, OpenCode, Pi)
2. User asks about background process management
3. User requests help with PTY mode
4. User needs guidance on working directory contexts
5. User wants to understand agent interaction patterns

*Created for managing coding agents programmatically*