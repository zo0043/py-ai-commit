# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based AI-powered git commit message generator that uses OpenAI's API to create conventional commit messages. The tool analyzes git diffs and generates appropriate commit messages following conventional commit format.

## Common Development Commands

### Installation & Setup
```bash
# Install in development mode
pip install -e .

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt

# Build package (modern way)
python -m build

# Install from local build
pip install dist/ai_commit-0.2.0-py3-none-any.whl

# Configure the tool (copy and edit the template)
cp .aicommit_template .aicommit
```

### Testing the Tool
```bash
# Basic usage (requires staged changes)
ai-commit

# Interactive file selection mode
ai-commit -i

# Auto-stage all changed files
ai-commit -a

# Dry run mode to test without committing
ai-commit --dry-run

# Auto-commit mode
ai-commit -y

# With verbose logging
ai-commit -v

# Override model
ai-commit -m gpt-4

# Combine options (interactive + auto-commit + verbose)
ai-commit -i -y -v
```

### Development & Debugging
```bash
# Run with Python directly for debugging
python -m ai_commit.cli

# Run tests
python -m pytest tests/

# Run a specific test
python -m pytest tests/test_cli.py::TestAICommit::test_extract_commit_message

# Check logs (daily files)
ls .commitLogs/
cat .commitLogs/commit_$(date +%Y%m%d).log
```

## Architecture

### Core Components

- **`ai_commit/cli.py`** - Main CLI module containing all functionality
- **`ai_commit/__init__.py`** - Package initialization (version 0.2.0)
- **`pyproject.toml`** - Modern Python package configuration (replaces setup.py)
- **`requirements.txt`** - Runtime dependencies
- **`requirements-dev.txt`** - Development dependencies

### Key Functions in cli.py

- `parse_args()` - Command line argument parsing with type hints (now includes -i/--interactive and -a/--all)
- `validate_config()` - Configuration validation with API key format checking
- `load_config()` - Configuration loading from .aicommit or .env files
- `get_changed_files()` - Discover staged and unstaged files with comprehensive file status
- `display_file_changes()` - Pretty-print current git status with file categorization
- `select_files_interactive()` - Interactive file selection with numbered options
- `stage_selected_files()` - Batch staging of user-selected files
- `get_git_diff()` - Git diff extraction for both staged and unstaged changes
- `generate_commit_message()` - OpenAI API integration with retry logic and error handling
- `commit_changes()` - Git commit execution
- `push_changes()` - Auto-push functionality
- `setup_logging()` - Comprehensive logging with file and console output

### Configuration System

The tool uses a hierarchical configuration system:
1. Command-line arguments (highest priority)
2. `.aicommit` file (key=value format)
3. `.env` file (dotenv format)
4. Default values (lowest priority)

Required config keys: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`
Optional config keys: `LOG_PATH`, `AUTO_COMMIT`, `AUTO_PUSH`

### Logging System

- Daily log files in configurable directory (default: `.commitLogs/`)
- Colored console output using CustomFormatter
- Detailed logging with context via `log_with_details()` function
- Different log levels for file (DEBUG+) and console (INFO+)

## Development Notes

### Error Handling
- Enhanced error handling with specific exception types (RateLimitError, AuthenticationError)
- Exponential backoff for rate limits with configurable retry logic
- Git repository validation before operations
- Staged changes validation with user-friendly messages
- Configuration validation with API key format checking
- Comprehensive logging for debugging and monitoring

### Testing
- Unit tests in `tests/test_cli.py` covering core functionality
- Mock-based testing for external dependencies (git, OpenAI API)
- Test coverage for argument parsing, message extraction, and validation functions

### Key Features
- **Interactive File Selection** - Choose specific files to analyze and commit with -i flag
- **Auto-staging Mode** - Automatically stage all changed files with -a flag  
- **Smart File Discovery** - Detects staged, unstaged, and untracked files automatically
- **Visual Status Display** - Pretty-formatted git status with file categorization
- Branch context awareness (includes current branch in commit message generation)
- Conventional commit format enforcement
- Auto-commit and auto-push capabilities
- Dry-run mode for testing
- Verbose logging for debugging

### Dependencies
- `openai>=1.0.0` - OpenAI API client
- `python-dotenv>=0.19.0` - Environment variable loading
- Standard library modules: subprocess, logging, argparse, pathlib, typing, etc.

### Entry Point
The tool is installed as `ai-commit` command via setuptools entry point: `ai_commit.cli:main`