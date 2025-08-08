# AI Commit

🤖 AI-powered git commit message generator using OpenAI API with advanced file splitting and large commit handling.

**English** | [简体中文](README_CN.md)

[![Version](https://img.shields.io/badge/version-0.3.0-blue.svg)](https://github.com/zero0043/py-ai-commit/releases)
[![Python](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)

## ✨ Features

### 🎯 Core Functionality
- **AI-Powered**: Automatically generates clear, descriptive commit messages using OpenAI API
- **Conventional Commits**: Follows conventional commit format for consistent git history
- **Multi-Model Support**: Compatible with various OpenAI models (GPT-3.5, GPT-4, etc.)
- **Branch Context**: Automatically includes current branch context for more relevant messages

### 🔧 Advanced Features
- **Interactive File Selection** (`-i`): Choose specific files to analyze and commit
- **Auto-staging Mode** (`-a`): Automatically stage all changed files
- **Smart File Discovery**: Detects staged, unstaged, and untracked files
- **Rich Terminal UI**: Beautiful progress indicators, animations, and colored output
- **Comprehensive Logging**: Daily log files with detailed operation tracking
- **Security-First**: Built-in API key management and input validation
- **Modular Architecture**: Clean, maintainable codebase with specialized modules

### 🚀 **NEW: Large Commit Handling**
- **Automatic File Splitting**: Intelligently splits large commits into manageable chunks
- **Smart Diff Processing**: Handles git diffs up to 10MB in size
- **Context Preservation**: Maintains commit context even when splitting large files
- **Chunk Summarization**: Creates comprehensive summaries from split diffs
- **Configurable Chunk Sizes**: Adjustable chunk sizes (default: 500KB per chunk)

### ⚡ Automation & Control
- **Auto-commit**: Skip confirmation prompts (`-y` flag)
- **Auto-push**: Automatically push after successful commits
- **Dry-run Mode**: Preview commit messages without actual commits
- **Flexible Configuration**: Environment variables, config files, and CLI overrides
- **Global Configuration**: `~/.aicommit` for system-wide settings (v0.3.0)
- **Sensitive Content Detection**: Automatic detection and user confirmation for sensitive data (v0.3.0)
- **Plugin Architecture**: Extensible plugin system for commit message enhancement (v0.3.0)

## 🚀 Installation

### Quick Install
```bash
pip install git+https://github.com/zero0043/py-ai-commit.git
```

### Development Install
```bash
git clone https://github.com/zero0043/py-ai-commit.git
cd py-ai-commit
pip install -e .
```

### Alternative Command
After installation, you can use either:
- `ai-commit` (main command)
- `acc` (short alias)

## 💡 Usage

### Basic Usage
In any git repository with staged changes:

```bash
ai-commit
```

### Quick Start
```bash
# First time setup - copy template and edit with your API key
cp .aicommit_template .aicommit

# Stage some changes
git add .

# Generate and commit with AI
ai-commit
```

### Enhanced File Selection

**Interactive Mode** - Choose specific files to stage and commit:
```bash
ai-commit -i
```
This will show you all unstaged files and let you select which ones to analyze and commit.

**Auto-stage Mode** - Automatically stage all changed files:
```bash
ai-commit -a
```
This will automatically stage all unstaged files and then generate a commit message.

**Combined Usage Examples**:
```bash
# Interactive selection with auto-commit and verbose output
ai-commit -i -y -v

# Auto-stage all files and commit with confirmation
ai-commit -a

# Interactive selection with dry-run (no actual commit)
ai-commit -i --dry-run
```

### Configuration Management Commands

The tool includes built-in configuration management:

```bash
# Show current configuration
ai-commit config show

# Test AI service connection
ai-commit config test

# Store API key securely
ai-commit config set-key openai your-api-key
```

Command line options:

```bash
ai-commit [-h] [-y] [-c CONFIG] [-m MODEL] [--dry-run] [-v] [-i] [-a]

options:
  -h, --help            Show this help message
  -y, --yes            Skip confirmation and commit directly
  -c CONFIG, --config CONFIG
                      Path to specific config file
  -m MODEL, --model MODEL
                      Override AI model from config
  --dry-run           Generate message without committing
  -v, --verbose       Show verbose output
  -i, --interactive   Interactively select files to analyze and commit
  -a, --all          Analyze and stage all changed files automatically
```

## 🔧 Large Commit Handling

### Automatic File Splitting

The tool now automatically handles large commits by splitting them into manageable chunks:

- **Detection**: Automatically detects commits larger than 500KB
- **Splitting**: Splits diffs by individual file boundaries
- **Truncation**: For extremely large files, intelligently truncates while preserving context
- **Summarization**: Creates structured summaries with file information
- **Processing**: Processes chunks and generates comprehensive commit messages

### Example Large Commit Output

When processing large commits, the tool generates summaries like:

```
# Large commit diff summary
# Original diff size: 2714806 characters
# Split into 6 manageable chunks
#
# Files changed: 15
#   - src/main.py
#   - src/utils.py
#   - tests/test_main.py
#   - ... (12 more files)
#
# Detailed changes (first chunk only):
#
diff --git a/src/main.py b/src/main.py
index abc123..def456 100644
--- a/src/main.py
+++ b/src/main.py
@@ -1,5 +1,7 @@
 def main():
+    # New feature implementation
+    print("Hello, World!")
     return 0

#
# ... 5 additional chunks omitted for brevity
# Use individual file commits or review the complete diff separately
```

### Configuration Options

The large commit handling is configurable:

- **`split_large_files`**: Enable/disable automatic splitting (default: `true`)
- **`max_chunk_size`**: Maximum size per chunk in characters (default: `500000`)
- **`MAX_DIFF_SIZE`**: Maximum allowed diff size (default: `10MB`)

## ⚙️ Configuration

You can configure the tool in multiple ways (in order of priority):

### 1. Global Configuration (NEW in v0.3.0)

Create a `~/.aicommit` file in your home directory for system-wide settings:

```bash
# ~/.aicommit
OPENAI_API_KEY=your_global_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-3.5-turbo
LOG_PATH=.commitLogs
```

### 2. Environment Variables (Always available)

Set these environment variables in your shell:

```bash
export OPENAI_API_KEY='your-api-key'
export OPENAI_BASE_URL='your-api-base-url'  
export OPENAI_MODEL='gpt-3.5-turbo'
export LOG_PATH='.commitLogs'              # Optional
export AUTO_COMMIT='false'                 # Optional
export AUTO_PUSH='false'                   # Optional
```

### 3. Configuration Files

Create a `.aicommit` or `.env` file in your project root or any parent directory.

#### Creating Configuration Files

1. Create a `.aicommit` or `.env` file:
   - Copy `.aicommit_template` to `.aicommit`
   - Edit the file with your settings

#### Configuration Options

```ini
OPENAI_API_KEY=your_api_key          # Required: Your OpenAI API key
OPENAI_BASE_URL=your_api_base_url    # Required: OpenAI API base URL
OPENAI_MODEL=your_model_name         # Required: OpenAI model to use (e.g., gpt-3.5-turbo)
LOG_PATH=.commitLogs                 # Optional: Directory for log files (default: .commitLogs)
AUTO_COMMIT=true                     # Optional: Skip confirmation (default: false)
AUTO_PUSH=true                       # Optional: Auto push after commit (default: false)
```

The tool will search for configuration files in the following order:
1. Command-line specified config file (`-c` option)
2. **Global config file** (`~/.aicommit`) - NEW in v0.3.0
3. `.aicommit` in current or parent directories
4. `.env` in current or parent directories
5. Environment variables (always checked as fallback)

### Configuration Priority (v0.3.0)

Configuration values are applied in this order (highest to lowest priority):
1. Command-line arguments (highest priority)
2. Global Configuration (`~/.aicommit`)
3. Local Configuration files (`.aicommit` or `.env`)
4. Environment variables (lowest priority)

### Advanced Configuration Options

Additional configuration options available:

```ini
# Large file handling
split_large_files=true          # Enable/disable large file splitting (default: true)
max_chunk_size=500000           # Maximum chunk size in characters (default: 500000)
MAX_DIFF_SIZE=10485760          # Maximum diff size in bytes (default: 10MB)

# Plugin configuration
plugin_enabled=true             # Enable plugin system (default: true)
plugin_path=./plugins           # Plugin directory path

# Security settings
sensitive_content_detection=true  # Enable sensitive content detection (default: true)
strict_validation=true           # Enable strict input validation (default: true)
```

## 🔍 Features in Detail

### Auto-Commit Mode

Enable auto-commit in one of three ways:
1. Use `-y` or `--yes` flag: `ai-commit -y`
2. Set `AUTO_COMMIT=true` in config file
3. Interactive confirmation (default)

### Auto-Push Mode

When enabled with `AUTO_PUSH=true`, the tool will:
1. Automatically push changes to remote after successful commit
2. Use current branch name for pushing
3. Only push if commit is successful
4. Log push operations and any errors

### Dry Run Mode

Use `--dry-run` to generate a commit message without actually committing:
```bash
ai-commit --dry-run
```

### Model Selection

Override the model from command line:
```bash
ai-commit -m gpt-4
```

### Verbose Logging

Enable detailed logging:
```bash
ai-commit -v
```

### Sensitive Content Detection

The tool automatically detects sensitive content in your code and prompts for confirmation:

- **API Keys**: Detects potential API keys and tokens
- **Passwords**: Identifies possible password strings
- **Personal Information**: Detects email addresses, phone numbers
- **Secret Files**: Identifies configuration files with sensitive data
- **User Confirmation**: Interactive prompts to review and confirm sensitive content

When sensitive content is detected, you can:
1. **Continue Commit**: Confirm the content is not sensitive
2. **Cancel Commit**: Review and remove sensitive information
3. **View Details**: See detailed information about detected content

### Plugin System

The v0.3.0 release introduces an extensible plugin architecture:

- **Commit Message Enhancers**: Modify and improve generated commit messages
- **Pre-commit Hooks**: Validate changes before committing
- **Post-commit Actions**: Execute actions after successful commits
- **Custom Validators**: Add project-specific validation rules

Plugins can be developed using the provided plugin API and stored in the configured plugin directory.

## 📝 Logging

Logs are stored in the configured `LOG_PATH` directory (default: `.commitLogs`):
- Daily log files: `commit_YYYYMMDD.log`
- Includes detailed information about:
  - Program startup
  - Configuration loading
  - Git operations
  - API calls
  - Commit process
  - Push operations
  - Large commit splitting operations
  - Errors and warnings

## 🛡️ Error Handling

The tool includes robust error handling for:
- Missing configuration
- Invalid API keys
- Network issues (with automatic retries)
- Git repository errors
- Invalid staged changes
- Large commit processing errors
- Push failures

### Advanced Usage Examples

```bash
# Global configuration setup
echo 'OPENAI_API_KEY=your-key' > ~/.aicommit
echo 'OPENAI_MODEL=gpt-4' >> ~/.aicommit

# Test configuration
ai-commit config show
ai-commit config test

# Large project with auto-commit and verbose logging
ai-commit -a -y -v

# Interactive selection with sensitive content detection
ai-commit -i

# Dry run with custom model
ai-commit --dry-run -m gpt-4

# Auto-stage and commit with branch-specific configuration
ai-commit -a -c ./project-specific-config
```

### Workflow Integration

```bash
# Git hook integration (pre-commit)
#!/bin/bash
# .git/hooks/pre-commit
ai-commit -y --dry-run
if [ $? -eq 0 ]; then
    echo "AI commit message validation passed"
else
    echo "AI commit message validation failed"
    exit 1
fi

# CI/CD pipeline integration
ai-commit --dry-run -c ./ci-config
COMMIT_MSG=$(ai-commit --dry-run | tail -1)
echo "Generated commit message: $COMMIT_MSG"
```

This project features a modern modular architecture with the following components:

- **`ai_commit.config`** - Configuration management with security integration
- **`ai_commit.git`** - Git operations, repository management, and large commit handling
- **`ai_commit.ai`** - AI client with retry logic and error handling
- **`ai_commit.utils`** - File selection, logging, and progress management
- **`ai_commit.ui`** - Rich terminal interface with animations and colors
- **`ai_commit.security`** - API key management and input validation
- **`ai_commit.exceptions`** - Comprehensive error handling system

### Large Commit Processing Architecture

The large commit handling is implemented in the `GitOperations` class with:

- **`get_git_diff()`**: Enhanced with splitting parameters
- **`_split_and_process_diff()`**: Main splitting algorithm
- **`_split_diff_by_files()`**: Splits diffs by file boundaries
- **`_truncate_large_file_diff()`**: Handles extremely large files
- **`_create_diff_summary()`**: Creates structured summaries
- **`_extract_files_from_diff()`**: Extracts file information

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'feat: add some amazing feature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [OpenAI API](https://openai.com/api/)
- Inspired by conventional commit standards
- Thanks to all contributors and users!