#!/usr/bin/env python3
import os
import subprocess
import openai
from datetime import datetime
import logging
import re
import sys
import argparse
import time
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Optional, Tuple, Any, List

class CustomFormatter(logging.Formatter):
    """Custom log formatter with color support"""
    grey = "\x1b[38;21m"
    blue = "\x1b[38;5;39m"
    yellow = "\x1b[38;5;226m"
    red = "\x1b[38;5;196m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    def __init__(self, fmt):
        super().__init__()
        self.fmt = fmt
        self.FORMATS = {
            logging.DEBUG: self.grey + self.fmt + self.reset,
            logging.INFO: self.blue + self.fmt + self.reset,
            logging.WARNING: self.yellow + self.fmt + self.reset,
            logging.ERROR: self.red + self.fmt + self.reset,
            logging.CRITICAL: self.bold_red + self.fmt + self.reset
        }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

def parse_args() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='AI-powered git commit message generator')
    parser.add_argument('-y', '--yes', action='store_true',
                      help='Skip confirmation and commit directly')
    parser.add_argument('-c', '--config', type=str,
                      help='Path to specific config file')
    parser.add_argument('-m', '--model', type=str,
                      help='Override AI model from config')
    parser.add_argument('--dry-run', action='store_true',
                      help='Generate message without committing')
    parser.add_argument('-v', '--verbose', action='store_true',
                      help='Show verbose output')
    parser.add_argument('-i', '--interactive', action='store_true',
                      help='Interactively select files to analyze and commit')
    parser.add_argument('-a', '--all', action='store_true',
                      help='Analyze and stage all changed files automatically')
    return parser.parse_args()

def setup_logging(log_path: str) -> logging.Logger:
    """Setup logging configuration with enhanced formatting"""
    if not os.path.exists(log_path):
        os.makedirs(log_path, exist_ok=True)
    
    log_file = os.path.join(log_path, f'commit_{datetime.now().strftime("%Y%m%d")}.log')
    
    # 创建logger
    logger = logging.getLogger('ai_commit')
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    if logger.handlers:
        logger.handlers.clear()
    
    # File handler - logs all levels
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s\nDetails: %(details)s\n'
    ))
    
    # Console handler - only shows INFO and above
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(CustomFormatter(
        '%(message)s'
    ))
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def log_with_details(logger: logging.Logger, level: int, message: str, details: Optional[str] = None) -> None:
    """Helper function to log messages with details"""
    extra = {'details': details if details else 'No additional details'}
    logger.log(level, message, extra=extra)

def find_config_files(config_path: Optional[str] = None) -> Tuple[Optional[str], Optional[Path]]:
    """Find .aicommit or .env file in current or parent directories"""
    if config_path:
        config_file = Path(config_path)
        if config_file.exists():
            return ('custom', config_file)
        else:
            raise FileNotFoundError(f"Config file not found: {config_path}")
    
    current = Path.cwd()
    while current != current.parent:
        aicommit_file = current / '.aicommit'
        env_file = current / '.env'
        template_file = current / '.aicommit_template'
        
        if aicommit_file.exists():
            return ('aicommit', aicommit_file)
        elif env_file.exists():
            return ('env', env_file)
        elif template_file.exists():
            print("Found .aicommit_template file. Please configure it and rename to .aicommit")
            sys.exit(1)
            
        current = current.parent
    return (None, None)

def load_aicommit_config(config_file: Path) -> Dict[str, str]:
    """Load configuration from .aicommit file"""
    config = {}
    with open(config_file, 'r') as f:
        for line in f:
            if '=' in line:
                key, value = line.strip().split('=', 1)
                config[key] = value
    return config

def validate_config(config: Dict[str, Any]) -> bool:
    """Validate configuration values"""
    # Check for required keys
    required_keys = ['OPENAI_API_KEY', 'OPENAI_BASE_URL', 'OPENAI_MODEL']
    for key in required_keys:
        if key not in config or not config[key]:
            return False
    
    # Validate API key format (basic check for OpenAI and other providers)
    api_key = config['OPENAI_API_KEY']
    # Support OpenAI (sk-), GLM/Zhipu AI, and other formats - just check not empty and reasonable length
    if len(api_key) < 20:
        return False
    
    # Validate model name
    model = config['OPENAI_MODEL']
    valid_models = ['gpt-3.5-turbo', 'gpt-4', 'gpt-4-turbo', 'gpt-4o', 'gpt-4o-mini', 
                   'glm-4', 'glm-4-flash', 'glm-4-plus', 'glm-4v', 'glm-4v-plus']
    if model not in valid_models:
        print(f"Warning: Using potentially unsupported model '{model}'. Supported models: {', '.join(valid_models)}")
    
    return True


def load_config(logger: logging.Logger, config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from .aicommit/.env files or environment variables"""
    config_type, config_file = find_config_files(config_path)
    
    config = {}
    
    # First, always try to load from environment variables (lowest priority)
    env_config = {}
    for key in ['OPENAI_API_KEY', 'OPENAI_BASE_URL', 'OPENAI_MODEL', 'LOG_PATH', 'AUTO_COMMIT', 'AUTO_PUSH']:
        if value := os.getenv(key):
            env_config[key] = value
    
    if env_config:
        config.update(env_config)
        log_with_details(logger, logging.INFO,
            "Loaded configuration from environment variables",
            f"Found env vars: {', '.join(env_config.keys())}"
        )
    
    # Then load from config file if available (higher priority)
    if config_type is not None:
        log_with_details(logger, logging.INFO,
            f"Found configuration file: {config_type}",
            f"Using config file: {config_file}"
        )
        
        try:
            file_config = {}
            if config_type == 'aicommit':
                file_config = load_aicommit_config(config_file)
            else:  # env file
                load_dotenv(config_file)
                # Re-read environment variables after loading .env file
                for key in ['OPENAI_API_KEY', 'OPENAI_BASE_URL', 'OPENAI_MODEL', 'LOG_PATH', 'AUTO_COMMIT', 'AUTO_PUSH']:
                    if value := os.getenv(key):
                        file_config[key] = value
            
            # File config overrides environment variables
            config.update(file_config)
            
            log_with_details(logger, logging.DEBUG,
                "Configuration loaded from file",
                f"File config keys: {', '.join(file_config.keys())}"
            )
        except Exception as e:
            log_with_details(logger, logging.ERROR,
                "Failed to load configuration file",
                f"Error: {str(e)}"
            )
            sys.exit(1)
    
    # If no configuration found at all, show helpful error
    if not config:
        log_with_details(logger, logging.ERROR,
            "No configuration found",
            "Set environment variables or create .aicommit/.env file in current or parent directories"
        )
        print("\n" + "="*60)
        print("❌ Configuration Required")
        print("="*60)
        print("No configuration found. You can configure ai-commit in two ways:")
        print("\n1. Environment Variables:")
        print("   export OPENAI_API_KEY='your-api-key'")
        print("   export OPENAI_BASE_URL='your-api-base-url'")
        print("   export OPENAI_MODEL='gpt-3.5-turbo'")
        print("\n2. Configuration File:")
        print("   Create .aicommit or .env file with your settings")
        print("="*60)
        sys.exit(1)
    
    # Convert AUTO_COMMIT and AUTO_PUSH strings to boolean
    for key in ['AUTO_COMMIT', 'AUTO_PUSH']:
        if key in config:
            config[key] = config[key].lower() == 'true'
    
    log_with_details(logger, logging.DEBUG,
        "Final configuration loaded",
        f"All config keys: {', '.join(config.keys())}"
    )
    
    # Validate configuration
    if not validate_config(config):
        log_with_details(logger, logging.ERROR,
            "Invalid configuration",
            "Please check your API key format and required settings"
        )
        sys.exit(1)
        
    return config

def get_changed_files(logger: logging.Logger) -> Tuple[List[str], List[str]]:
    """Get lists of staged and unstaged files"""
    try:
        # Get staged files
        staged_result = subprocess.run(['git', 'diff', '--cached', '--name-only'], 
                                     capture_output=True, text=True, check=True)
        staged_files = [f.strip() for f in staged_result.stdout.splitlines() if f.strip()]
        
        # Get unstaged files (modified and untracked)
        unstaged_result = subprocess.run(['git', 'diff', '--name-only'], 
                                       capture_output=True, text=True, check=True)
        unstaged_files = [f.strip() for f in unstaged_result.stdout.splitlines() if f.strip()]
        
        # Get untracked files
        untracked_result = subprocess.run(['git', 'ls-files', '--others', '--exclude-standard'], 
                                        capture_output=True, text=True, check=True)
        untracked_files = [f.strip() for f in untracked_result.stdout.splitlines() if f.strip()]
        
        # Combine unstaged and untracked
        all_unstaged = list(set(unstaged_files + untracked_files))
        
        log_with_details(logger, logging.INFO,
            "Retrieved file changes",
            f"Staged: {len(staged_files)}, Unstaged: {len(all_unstaged)}"
        )
        
        return staged_files, all_unstaged
        
    except subprocess.CalledProcessError as e:
        log_with_details(logger, logging.ERROR,
            "Failed to get changed files",
            f"Error: {str(e)}"
        )
        return [], []


def display_file_changes(staged_files: List[str], unstaged_files: List[str]) -> None:
    """Display current file changes in a formatted way"""
    print("\n" + "="*60)
    print("📁 Current Git Status")
    print("="*60)
    
    if staged_files:
        print(f"\n✅ Staged files ({len(staged_files)}):")
        for i, file in enumerate(staged_files, 1):
            print(f"  {i:2d}. {file}")
    else:
        print("\n✅ No staged files")
    
    if unstaged_files:
        print(f"\n📝 Unstaged files ({len(unstaged_files)}):")
        for i, file in enumerate(unstaged_files, 1):
            print(f"  {i:2d}. {file}")
    else:
        print("\n📝 No unstaged files")
    
    print("\n" + "="*60)


def select_files_interactive(staged_files: List[str], unstaged_files: List[str], logger: logging.Logger) -> List[str]:
    """Interactive file selection for staging and analysis"""
    selected_files = []
    
    if not unstaged_files:
        print("No unstaged files to select from.")
        return staged_files
    
    print("\n🎯 Select files to stage and analyze:")
    print("   Enter file numbers separated by spaces (e.g., 1 3 5)")
    print("   Enter 'all' to select all files")
    print("   Enter 'none' to skip file selection")
    print("   Press Enter to finish selection")
    
    while True:
        try:
            response = input("\nSelect files: ").strip().lower()
            
            if response == 'all':
                selected_files = unstaged_files.copy()
                break
            elif response == 'none' or response == '':
                break
            else:
                # Parse numbers
                numbers = []
                for part in response.split():
                    try:
                        num = int(part)
                        if 1 <= num <= len(unstaged_files):
                            numbers.append(num)
                        else:
                            print(f"Invalid number: {num}. Please use numbers 1-{len(unstaged_files)}")
                    except ValueError:
                        print(f"Invalid input: {part}. Please enter numbers only.")
                
                if numbers:
                    selected_files = [unstaged_files[i-1] for i in numbers]
                    break
                    
        except KeyboardInterrupt:
            print("\nSelection cancelled.")
            return []
    
    if selected_files:
        print(f"\n✅ Selected {len(selected_files)} files:")
        for file in selected_files:
            print(f"   - {file}")
    
    return selected_files


def stage_selected_files(files: List[str], logger: logging.Logger) -> bool:
    """Stage the selected files"""
    if not files:
        return True
    
    try:
        for file in files:
            result = subprocess.run(['git', 'add', file], 
                                  capture_output=True, text=True, check=True)
            
        log_with_details(logger, logging.INFO,
            "Files staged successfully",
            f"Staged files: {', '.join(files)}"
        )
        print(f"✅ Staged {len(files)} files successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        log_with_details(logger, logging.ERROR,
            "Failed to stage files",
            f"Error: {str(e)}"
        )
        print(f"❌ Failed to stage files: {str(e)}")
        return False


def get_git_diff(logger: logging.Logger) -> Optional[str]:
    """Get the git diff of staged and unstaged changes"""
    try:
        # Check if we're in a git repository
        subprocess.run(['git', 'rev-parse', '--git-dir'], 
                     check=True, capture_output=True)
    except subprocess.CalledProcessError:
        log_with_details(logger, logging.ERROR,
            "Not a git repository",
            "Current directory is not a git repository"
        )
        sys.exit(1)
    
    try:
        # Get git status
        status = subprocess.run(['git', 'status', '-s'], capture_output=True, text=True).stdout
        log_with_details(logger, logging.INFO,
            "Git status retrieved",
            f"Current status:\n{status}"
        )
        
        # Get unstaged changes
        unstaged = subprocess.run(['git', 'diff'], capture_output=True, text=True).stdout
        # Get staged changes
        staged = subprocess.run(['git', 'diff', '--cached'], capture_output=True, text=True).stdout
        
        total_diff = unstaged + staged
        
        if total_diff:
            log_with_details(logger, logging.INFO,
                "Retrieved git changes",
                f"Total changes size: {len(total_diff)} characters\n"
                f"Unstaged changes: {len(unstaged)} characters\n"
                f"Staged changes: {len(staged)} characters"
            )
        else:
            log_with_details(logger, logging.WARNING,
                "No changes detected",
                "No staged or unstaged changes found"
            )
            
        return total_diff
    except Exception as e:
        log_with_details(logger, logging.ERROR,
            "Failed to get git diff",
            f"Error: {str(e)}"
        )
        return None

def validate_git_staged_changes(logger: logging.Logger) -> bool:
    """Validate that there are staged changes for commit"""
    try:
        staged = subprocess.run(['git', 'diff', '--cached', '--quiet'],
                              capture_output=True)
        if staged.returncode == 0:
            log_with_details(logger, logging.WARNING,
                "No staged changes",
                "Please stage your changes using 'git add' first"
            )
            return False
        return True
    except subprocess.CalledProcessError:
        return False

def get_branch_name() -> Optional[str]:
    """Get current git branch name"""
    try:
        result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                              capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except (subprocess.CalledProcessError, Exception):
        return None

def extract_commit_message(text: str) -> str:
    """Extract commit message from between ``` marks"""
    pattern = r'```(?:\w*\n)?(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        return matches[0].strip()
    return text.strip()

def generate_commit_message(diff_text: str, config: Dict[str, Any], logger: logging.Logger) -> Optional[str]:
    """Generate commit message using OpenAI API"""
    client = openai.OpenAI(
        api_key=config['OPENAI_API_KEY'],
        base_url=config['OPENAI_BASE_URL']
    )

    # Get current branch name for context
    branch_name = get_branch_name()
    branch_context = f"Current branch: {branch_name}\n" if branch_name else ""

    prompt = f"""Please analyze the following git diff and generate a concise and descriptive commit message.
The commit message should follow conventional commit format and be in English.
Focus on WHAT changed and WHY, not HOW.
Your response should only contain the commit message wrapped in ```.

{branch_context}
Git diff:
{diff_text}

Generate a commit message in the format:
type(scope): description"""

    try:
        log_with_details(logger, logging.INFO,
            "Calling OpenAI API",
            f"Using model: {config['OPENAI_MODEL']}\n"
            f"Prompt length: {len(prompt)} characters"
        )
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                response = client.chat.completions.create(
                    model=config['OPENAI_MODEL'],
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that generates clear and concise git commit messages. Wrap your commit message in ```"},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=150,
                    temperature=0.7
                )
                break
            except openai.RateLimitError as e:
                retry_count += 1
                if retry_count == max_retries:
                    log_with_details(logger, logging.ERROR,
                        "Rate limit exceeded",
                        "OpenAI API rate limit reached. Please try again later."
                    )
                    raise e
                wait_time = 2 ** retry_count  # Exponential backoff
                log_with_details(logger, logging.WARNING,
                    f"Rate limit hit (attempt {retry_count}/{max_retries})",
                    f"Waiting {wait_time} seconds before retry..."
                )
                time.sleep(wait_time)
            except openai.AuthenticationError as e:
                log_with_details(logger, logging.ERROR,
                    "Authentication failed",
                    "Invalid OpenAI API key. Please check your configuration."
                )
                raise e
            except Exception as e:
                retry_count += 1
                if retry_count == max_retries:
                    raise e
                log_with_details(logger, logging.WARNING,
                    f"API call failed (attempt {retry_count}/{max_retries})",
                    f"Error: {str(e)}\nRetrying..."
                )
                time.sleep(1)  # Add delay to avoid frequent requests
        
        raw_message = response.choices[0].message.content.strip()
        commit_message = extract_commit_message(raw_message)
        
        log_with_details(logger, logging.INFO,
            "Generated commit message",
            f"Raw response:\n{raw_message}\n\n"
            f"Extracted message:\n{commit_message}"
        )
        
        return commit_message
    except Exception as e:
        log_with_details(logger, logging.ERROR,
            "Failed to generate commit message",
            f"Error: {str(e)}"
        )
        return None

def commit_changes(commit_message: str, logger: logging.Logger) -> bool:
    """Commit changes with the generated message"""
    try:
        result = subprocess.run(['git', 'commit', '-m', commit_message],
                             capture_output=True, text=True)
        if result.returncode == 0:
            log_with_details(logger, logging.INFO,
                "Changes committed successfully",
                f"Commit output:\n{result.stdout}"
            )
            return True
        else:
            log_with_details(logger, logging.ERROR,
                "Failed to commit changes",
                f"Error output:\n{result.stderr}"
            )
            return False
    except Exception as e:
        log_with_details(logger, logging.ERROR,
            "Error during commit",
            f"Exception: {str(e)}"
        )
        return False

def push_changes(logger: logging.Logger) -> bool:
    """Push committed changes to remote repository"""
    try:
        # Get current branch name
        branch_name = get_branch_name()
        if not branch_name:
            log_with_details(logger, logging.ERROR,
                "Failed to get branch name",
                "Could not determine current branch for push"
            )
            return False

        # Execute git push
        result = subprocess.run(['git', 'push', 'origin', branch_name],
                             capture_output=True, text=True)
        if result.returncode == 0:
            log_with_details(logger, logging.INFO,
                "Changes pushed successfully",
                f"Push output:\n{result.stdout}"
            )
            return True
        else:
            log_with_details(logger, logging.ERROR,
                "Failed to push changes",
                f"Error output:\n{result.stderr}"
            )
            return False
    except Exception as e:
        log_with_details(logger, logging.ERROR,
            "Error during push",
            f"Exception: {str(e)}"
        )
        return False

def main() -> None:
    try:
        args = parse_args()
        
        # Setup initial logging with default path
        logger = setup_logging('.commitLogs')
        if args.verbose:
            logger.setLevel(logging.DEBUG)
            
        log_with_details(logger, logging.INFO,
            "Starting AI Commit",
            f"Process ID: {os.getpid()}\n"
            f"Working directory: {os.getcwd()}\n"
            f"Command arguments: {vars(args)}"
        )
        
        # Load configuration
        config = load_config(logger, args.config)
        
        # Override model if specified in command line
        if args.model:
            config['OPENAI_MODEL'] = args.model
            log_with_details(logger, logging.INFO,
                "Model override",
                f"Using model from command line: {args.model}"
            )
        
        # Update logging path if specified in config
        log_path = config.get('LOG_PATH', '.commitLogs')
        if log_path != '.commitLogs':
            logger = setup_logging(log_path)
            if args.verbose:
                logger.setLevel(logging.DEBUG)
            log_with_details(logger, logging.INFO,
                "Updated logging path",
                f"New log path: {log_path}"
            )
        
        # Handle file selection based on arguments
        if args.interactive or args.all:
            # Get current file changes
            staged_files, unstaged_files = get_changed_files(logger)
            
            # Display current status
            display_file_changes(staged_files, unstaged_files)
            
            if args.all:
                # Auto-stage all unstaged files
                if unstaged_files:
                    print(f"\n🔄 Auto-staging all {len(unstaged_files)} unstaged files...")
                    if not stage_selected_files(unstaged_files, logger):
                        return
                else:
                    print("\n✅ No unstaged files to stage")
            
            elif args.interactive:
                # Interactive file selection
                if unstaged_files:
                    selected_files = select_files_interactive(staged_files, unstaged_files, logger)
                    if selected_files:
                        if not stage_selected_files(selected_files, logger):
                            return
                    elif not staged_files:
                        print("No files selected and no staged files available for commit.")
                        return
                else:
                    print("\n✅ No unstaged files available for selection")
        
        # Validate git repository and changes
        if not validate_git_staged_changes(logger):
            if args.interactive or args.all:
                print("No staged changes found after file selection. Please select files to stage first.")
            else:
                print("No staged changes found. Please use 'git add' to stage your changes first.")
            return
        
        # Get git diff
        diff = get_git_diff(logger)
        if not diff:
            return
        
        # Generate commit message
        commit_message = generate_commit_message(diff, config, logger)
        if not commit_message:
            return
        
        # Print the generated commit message
        print("\nGenerated commit message:")
        print("-" * 50)
        print(commit_message)
        print("-" * 50)
        
        # Check if we should commit
        should_commit = (
            args.yes or  # Command line override
            (not args.dry_run and config.get('AUTO_COMMIT', False))  # Config setting and not dry run
        )
        
        if args.dry_run:
            log_with_details(logger, logging.INFO,
                "Dry run mode",
                "Skipping commit as requested"
            )
            return
            
        if should_commit:
            log_with_details(logger, logging.INFO,
                "Auto commit enabled",
                f"Source: {'command line' if args.yes else 'config file'}"
            )
            if commit_changes(commit_message, logger):
                # If commit succeeds and auto-push is enabled, push changes
                if config.get('AUTO_PUSH', False):
                    log_with_details(logger, logging.INFO,
                        "Auto push enabled",
                        "Attempting to push changes to remote"
                    )
                    push_changes(logger)
        else:
            # Ask user if they want to commit with this message
            response = input("\nWould you like to commit with this message? (y/N): ")
            if response.lower() == 'y':
                if commit_changes(commit_message, logger):
                    # If commit succeeds and auto-push is enabled, push changes
                    if config.get('AUTO_PUSH', False):
                        log_with_details(logger, logging.INFO,
                            "Auto push enabled",
                            "Attempting to push changes to remote"
                        )
                        push_changes(logger)
            else:
                log_with_details(logger, logging.INFO,
                    "Commit cancelled by user",
                    "User chose not to proceed with the commit"
                )
            
    except KeyboardInterrupt:
        log_with_details(logger, logging.WARNING,
            "Operation cancelled",
            "User interrupted the process"
        )
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        log_with_details(logger, logging.ERROR,
            "Unexpected error",
            f"Exception: {str(e)}\n"
            f"Type: {type(e).__name__}"
        )
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
