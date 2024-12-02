# AI Commit

AI-powered git commit message generator using OpenAI API.

## Installation

```bash
pip install git+https://github.com/zero0043/py-ai-commit.git
```

## Configuration

You can configure the tool using either a `.aicommit` file or a `.env` file in your project root or any parent directory.

### Using .aicommit file:

```
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=your_api_base_url
OPENAI_MODEL=your_model_name
LOG_PATH=.commitLogs
AUTO_COMMIT=true  # Optional: set to true to commit automatically without confirmation
```

### Using .env file:

```
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=your_api_base_url
OPENAI_MODEL=your_model_name
LOG_PATH=.commitLogs
AUTO_COMMIT=true  # Optional: set to true to commit automatically without confirmation
```

The tool will first look for a `.aicommit` file, and if not found, it will look for a `.env` file. The search will continue in parent directories until a configuration file is found.

### Configuration Options

- `OPENAI_API_KEY`: Your OpenAI API key (required)
- `OPENAI_BASE_URL`: The base URL for the OpenAI API (required)
- `OPENAI_MODEL`: The model to use for generating commit messages (required)
- `LOG_PATH`: Directory to store log files (optional, defaults to `.commitLogs`)
- `AUTO_COMMIT`: Set to `true` to automatically commit without confirmation (optional, defaults to `false`)

## Usage

In any git repository:

```bash
ai-commit
```

This will:
1. Analyze your uncommitted changes
2. Generate a commit message using AI
3. If `AUTO_COMMIT` is true, automatically commit the changes
4. Otherwise, ask for confirmation before committing
5. Log the process in the specified log directory

## License

MIT