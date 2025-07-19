# AI Commit

AI-powered git commit message generator using OpenAI API.

**English** | [简体中文](README_CN.md)

## Features

- Automatically generates clear and descriptive commit messages
- Follows conventional commit format
- Supports multiple OpenAI models
- Flexible configuration options
- Command-line interface with various options
- Detailed logging system
- Auto-commit support
- Auto-push support
- Branch context awareness
ff
## Installation

```bash
pip install git+https://github.com/zo0043/py-ai-commit.git
```

## Usage

Basic usage in any git repository:

```bash
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

## Configuration

You can configure the tool in multiple ways (in order of priority):

### 1. Environment Variables (Always available)

Set these environment variables in your shell:

```bash
export OPENAI_API_KEY='your-api-key'
export OPENAI_BASE_URL='your-api-base-url'  
export OPENAI_MODEL='gpt-3.5-turbo'
export LOG_PATH='.commitLogs'              # Optional
export AUTO_COMMIT='false'                 # Optional
export AUTO_PUSH='false'                   # Optional
```

### 2. Configuration Files

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
1. Environment variables (always checked as fallback)
2. Command-line specified config file (`-c` option)
3. `.aicommit` in current or parent directories
4. `.env` in current or parent directories

### Configuration Priority

Configuration values are applied in this order (highest to lowest priority):
1. Command-line arguments (highest priority)
2. Configuration file settings (.aicommit or .env)
3. Environment variables (lowest priority)

## Features in Detail

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

### Branch Context

The tool automatically includes the current branch name in the commit message generation context for more relevant messages.

## Logging

Logs are stored in the configured `LOG_PATH` directory (default: `.commitLogs`):
- Daily log files: `commit_YYYYMMDD.log`
- Includes detailed information about:
  - Program startup
  - Configuration loading
  - Git operations
  - API calls
  - Commit process
  - Push operations
  - Errors and warnings

## Error Handling

The tool includes robust error handling for:
- Missing configuration
- Invalid API keys
- Network issues (with automatic retries)
- Git repository errors
- Invalid staged changes
- Push failures

## License

MIT
# Test change
# Test change
