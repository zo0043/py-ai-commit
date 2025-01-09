# AI Commit

AI-powered git commit message generator using OpenAI API.

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

## Installation

```bash
pip install git+https://github.com/zo0043/py-ai-commit.git
```

## Usage

Basic usage in any git repository:

```bash
ai-commit
```

Command line options:

```bash
ai-commit [-h] [-y] [-c CONFIG] [-m MODEL] [--dry-run] [-v]

options:
  -h, --help            Show this help message
  -y, --yes            Skip confirmation and commit directly
  -c CONFIG, --config CONFIG
                      Path to specific config file
  -m MODEL, --model MODEL
                      Override AI model from config
  --dry-run           Generate message without committing
  -v, --verbose       Show verbose output
```

## Configuration

You can configure the tool using either a `.aicommit` file or a `.env` file in your project root or any parent directory.

### Configuration Files

1. Create a `.aicommit` or `.env` file:
   - Copy `.aicommit_template` to `.aicommit`
   - Edit the file with your settings

### Configuration Options

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
2. `.aicommit` in current or parent directories
3. `.env` in current or parent directories

### Configuration Priority

1. Command-line arguments (highest priority)
2. Configuration file settings
3. Default values (lowest priority)

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
