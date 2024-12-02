#!/usr/bin/env python3
import os
import subprocess
import openai
from datetime import datetime
import logging
import re
import sys
from pathlib import Path
from dotenv import load_dotenv

class CustomFormatter(logging.Formatter):
    """自定义日志格式化器，添加颜色支持"""
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

def setup_logging(log_path):
    """Setup logging configuration with enhanced formatting"""
    if not os.path.exists(log_path):
        os.makedirs(log_path, exist_ok=True)
    
    log_file = os.path.join(log_path, f'commit_{datetime.now().strftime("%Y%m%d")}.log')
    
    # 创建logger
    logger = logging.getLogger('ai_commit')
    logger.setLevel(logging.DEBUG)
    
    # 清除现有的handlers
    if logger.handlers:
        logger.handlers.clear()
    
    # 文件处理器 - 记录所有级别的日志
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s\nDetails: %(details)s\n'
    ))
    
    # 控制台处理器 - 只显示INFO及以上级别
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(CustomFormatter(
        '%(message)s'
    ))
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def log_with_details(logger, level, message, details=None):
    """Helper function to log messages with details"""
    extra = {'details': details if details else 'No additional details'}
    logger.log(level, message, extra=extra)

def find_config_files():
    """Find .aicommit or .env file in current or parent directories"""
    current = Path.cwd()
    while current != current.parent:
        aicommit_file = current / '.aicommit'
        env_file = current / '.env'
        
        if aicommit_file.exists():
            return ('aicommit', aicommit_file)
        elif env_file.exists():
            return ('env', env_file)
            
        current = current.parent
    return (None, None)

def load_aicommit_config(config_file):
    """Load configuration from .aicommit file"""
    config = {}
    with open(config_file, 'r') as f:
        for line in f:
            if '=' in line:
                key, value = line.strip().split('=', 1)
                config[key] = value
    return config

def load_config(logger):
    """Load configuration from .aicommit or .env file"""
    config_type, config_file = find_config_files()
    
    if config_type is None:
        log_with_details(logger, logging.ERROR,
            "Configuration file not found",
            "Neither .aicommit nor .env file found in current or parent directories"
        )
        sys.exit(1)
    
    log_with_details(logger, logging.INFO,
        f"Found configuration file: {config_type}",
        f"Using config file: {config_file}"
    )
    
    config = {}
    try:
        if config_type == 'aicommit':
            config = load_aicommit_config(config_file)
        else:  # env
            load_dotenv(config_file)
            # 从环境变量中获取配置
            for key in ['OPENAI_API_KEY', 'OPENAI_BASE_URL', 'OPENAI_MODEL', 'LOG_PATH', 'AUTO_COMMIT']:
                if value := os.getenv(key):
                    config[key] = value
        
        # Convert AUTO_COMMIT string to boolean
        if 'AUTO_COMMIT' in config:
            config['AUTO_COMMIT'] = config['AUTO_COMMIT'].lower() == 'true'
        
        log_with_details(logger, logging.DEBUG,
            "Configuration loaded successfully",
            f"Loaded keys: {', '.join(config.keys())}"
        )
    except Exception as e:
        log_with_details(logger, logging.ERROR,
            "Failed to load configuration",
            f"Error: {str(e)}"
        )
        sys.exit(1)
    
    # Validate required configuration
    required_keys = ['OPENAI_API_KEY', 'OPENAI_BASE_URL', 'OPENAI_MODEL']
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        log_with_details(logger, logging.ERROR,
            "Missing required configuration",
            f"Missing keys: {', '.join(missing_keys)}"
        )
        sys.exit(1)
        
    return config

def get_git_diff(logger):
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

def extract_commit_message(text):
    """Extract commit message from between ``` marks"""
    pattern = r'```(?:\w*\n)?(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        return matches[0].strip()
    return text.strip()

def generate_commit_message(diff_text, config, logger):
    """Generate commit message using OpenAI API"""
    client = openai.OpenAI(
        api_key=config['OPENAI_API_KEY'],
        base_url=config['OPENAI_BASE_URL']
    )

    prompt = f"""Please analyze the following git diff and generate a concise and descriptive commit message.
The commit message should follow conventional commit format and be in English.
Focus on WHAT changed and WHY, not HOW.
Your response should only contain the commit message wrapped in ```.

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
        
        response = client.chat.completions.create(
            model=config['OPENAI_MODEL'],
            messages=[
                {"role": "system", "content": "You are a helpful assistant that generates clear and concise git commit messages. Wrap your commit message in ```"},
                {"role": "user", "content": prompt}
            ]
        )
        
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

def commit_changes(commit_message, logger):
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

def main():
    try:
        # Setup initial logging with default path
        logger = setup_logging('.commitLogs')
        log_with_details(logger, logging.INFO,
            "Starting AI Commit",
            f"Process ID: {os.getpid()}\n"
            f"Working directory: {os.getcwd()}"
        )
        
        # Load configuration
        config = load_config(logger)
        
        # Update logging path if specified in config
        log_path = config.get('LOG_PATH', '.commitLogs')
        if log_path != '.commitLogs':
            logger = setup_logging(log_path)
            log_with_details(logger, logging.INFO,
                "Updated logging path",
                f"New log path: {log_path}"
            )
        
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
        
        # Check if auto commit is enabled
        auto_commit = config.get('AUTO_COMMIT', False)
        if auto_commit:
            log_with_details(logger, logging.INFO,
                "Auto commit enabled",
                "Proceeding with automatic commit"
            )
            commit_changes(commit_message, logger)
        else:
            # Ask user if they want to commit with this message
            response = input("\nWould you like to commit with this message? (y/N): ")
            if response.lower() == 'y':
                commit_changes(commit_message, logger)
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