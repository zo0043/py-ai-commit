#!/usr/bin/env python3
import os
import subprocess
import openai
from datetime import datetime
import logging
import re
import sys
from pathlib import Path

def setup_logging(log_path):
    """Setup logging configuration"""
    if not os.path.exists(log_path):
        os.makedirs(log_path, exist_ok=True)
    
    log_file = os.path.join(log_path, f'commit_{datetime.now().strftime("%Y%m%d")}.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def find_config_file():
    """Find .aicommit file in current or parent directories"""
    current = Path.cwd()
    while current != current.parent:
        config_file = current / '.aicommit'
        if config_file.exists():
            return config_file
        current = current.parent
    return None

def load_config():
    """Load configuration from .aicommit file"""
    config = {}
    config_file = find_config_file()
    
    if config_file is None:
        print("Error: .aicommit file not found in current or parent directories")
        sys.exit(1)
        
    try:
        with open(config_file, 'r') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    config[key] = value
    except FileNotFoundError:
        print("Error: .aicommit file not found")
        sys.exit(1)
    
    # Validate required configuration
    required_keys = ['OPENAI_API_KEY', 'OPENAI_BASE_URL', 'OPENAI_MODEL']
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        print(f"Error: Missing required configuration keys: {', '.join(missing_keys)}")
        sys.exit(1)
        
    return config

def get_git_diff():
    """Get the git diff of staged and unstaged changes"""
    try:
        # Check if we're in a git repository
        subprocess.run(['git', 'rev-parse', '--git-dir'], 
                     check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("Error: Not a git repository")
        sys.exit(1)
        
    # Get unstaged changes
    unstaged = subprocess.run(['git', 'diff'], capture_output=True, text=True).stdout
    # Get staged changes
    staged = subprocess.run(['git', 'diff', '--cached'], capture_output=True, text=True).stdout
    return unstaged + staged

def extract_commit_message(text):
    """Extract commit message from between ``` marks"""
    pattern = r'```(?:\w*\n)?(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        # 返回第一个匹配项并去除首尾空白
        return matches[0].strip()
    # 如果没有找到```包裹的内容，返回原文本
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
        logger.info("Generating commit message using OpenAI API...")
        response = client.chat.completions.create(
            model=config['OPENAI_MODEL'],
            messages=[
                {"role": "system", "content": "You are a helpful assistant that generates clear and concise git commit messages. Wrap your commit message in ```"},
                {"role": "user", "content": prompt}
            ]
        )
        raw_message = response.choices[0].message.content.strip()
        commit_message = extract_commit_message(raw_message)
        logger.info(f"Generated commit message: {commit_message}")
        return commit_message
    except Exception as e:
        logger.error(f"Error generating commit message: {str(e)}")
        return None

def main():
    try:
        # Load configuration
        config = load_config()
        log_path = config.get('LOG_PATH', '.commitLogs')
        
        # Setup logging
        logger = setup_logging(log_path)
        logger.info("Starting commit message generation process...")
        
        # Get git diff
        diff = get_git_diff()
        if not diff:
            logger.info("No changes detected.")
            return
        
        logger.info("Found git changes, analyzing...")
        logger.debug(f"Git diff:\n{diff}")
        
        # Generate commit message
        commit_message = generate_commit_message(diff, config, logger)
        if not commit_message:
            logger.error("Failed to generate commit message.")
            return
        
        # Print the generated commit message
        print("\nGenerated commit message:")
        print("-" * 50)
        print(commit_message)
        print("-" * 50)
        
        # Ask user if they want to commit with this message
        response = input("\nWould you like to commit with this message? (y/N): ")
        if response.lower() == 'y':
            try:
                subprocess.run(['git', 'commit', '-m', commit_message])
                logger.info("Changes committed successfully!")
            except Exception as e:
                logger.error(f"Error during commit: {str(e)}")
        else:
            logger.info("Commit cancelled by user.")
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
