import unittest
import sys
import os
from unittest.mock import patch, MagicMock

# Add the parent directory to the path to import ai_commit
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ai_commit.cli import (
    extract_commit_message,
    get_branch_name,
    validate_git_staged_changes,
    parse_args,
    get_changed_files,
    stage_selected_files,
    load_config,
    validate_config
)


class TestAICommit(unittest.TestCase):
    """Test cases for AI Commit functionality"""

    def test_extract_commit_message(self):
        """Test commit message extraction from markdown"""
        # Test with code block
        text_with_code = "```\nfeat(auth): add user authentication\n```"
        result = extract_commit_message(text_with_code)
        self.assertEqual(result, "feat(auth): add user authentication")
        
        # Test with language specified
        text_with_lang = "```bash\nfix(api): resolve connection timeout\n```"
        result = extract_commit_message(text_with_lang)
        self.assertEqual(result, "fix(api): resolve connection timeout")
        
        # Test without code block
        text_plain = "docs(readme): update installation instructions"
        result = extract_commit_message(text_plain)
        self.assertEqual(result, "docs(readme): update installation instructions")

    def test_parse_args(self):
        """Test argument parsing"""
        # Test default args
        with patch('sys.argv', ['ai-commit']):
            args = parse_args()
            self.assertFalse(args.yes)
            self.assertFalse(args.dry_run)
            self.assertFalse(args.verbose)
            self.assertFalse(args.interactive)
            self.assertFalse(args.all)
            self.assertIsNone(args.config)
            self.assertIsNone(args.model)
        
        # Test interactive mode
        with patch('sys.argv', ['ai-commit', '-i']):
            args = parse_args()
            self.assertTrue(args.interactive)
        
        # Test all mode
        with patch('sys.argv', ['ai-commit', '-a']):
            args = parse_args()
            self.assertTrue(args.all)

    @patch('subprocess.run')
    def test_get_branch_name(self, mock_run):
        """Test branch name extraction"""
        # Test successful branch name retrieval
        mock_run.return_value = MagicMock(stdout="main\n", returncode=0)
        result = get_branch_name()
        self.assertEqual(result, "main")
        
        # Test error handling
        mock_run.side_effect = Exception("Git error")
        result = get_branch_name()
        self.assertIsNone(result)

    @patch('subprocess.run')
    def test_validate_git_staged_changes(self, mock_run):
        """Test staged changes validation"""
        # Create a mock logger
        mock_logger = MagicMock()
        
        # Test with staged changes
        mock_run.return_value = MagicMock(returncode=1)  # Non-zero means changes exist
        result = validate_git_staged_changes(mock_logger)
        self.assertTrue(result)
        
        # Test without staged changes
        mock_run.return_value = MagicMock(returncode=0)  # Zero means no changes
        result = validate_git_staged_changes(mock_logger)
        self.assertFalse(result)

    @patch('subprocess.run')
    def test_get_changed_files(self, mock_run):
        """Test getting changed files"""
        mock_logger = MagicMock()
        
        # Mock the three subprocess calls
        mock_run.side_effect = [
            MagicMock(stdout="file1.py\nfile2.py\n", returncode=0),  # staged files
            MagicMock(stdout="file3.py\n", returncode=0),           # unstaged files
            MagicMock(stdout="file4.py\n", returncode=0)            # untracked files
        ]
        
        staged, unstaged = get_changed_files(mock_logger)
        
        self.assertEqual(staged, ['file1.py', 'file2.py'])
        self.assertEqual(set(unstaged), {'file3.py', 'file4.py'})

    @patch('subprocess.run')
    def test_stage_selected_files(self, mock_run):
        """Test staging selected files"""
        mock_logger = MagicMock()
        
        # Test successful staging
        mock_run.return_value = MagicMock(returncode=0)
        result = stage_selected_files(['file1.py', 'file2.py'], mock_logger)
        self.assertTrue(result)
        
        # Test with empty list
        result = stage_selected_files([], mock_logger)
        self.assertTrue(result)

    def test_validate_config(self):
        """Test configuration validation"""
        # Test valid configuration
        valid_config = {
            'OPENAI_API_KEY': 'sk-test-key',
            'OPENAI_BASE_URL': 'https://api.openai.com/v1',
            'OPENAI_MODEL': 'gpt-3.5-turbo'
        }
        result = validate_config(valid_config)
        self.assertTrue(result)
        
        # Test invalid API key format
        invalid_config = {
            'OPENAI_API_KEY': 'invalid-key',
            'OPENAI_BASE_URL': 'https://api.openai.com/v1',
            'OPENAI_MODEL': 'gpt-3.5-turbo'
        }
        result = validate_config(invalid_config)
        self.assertFalse(result)
        
        # Test missing required key
        incomplete_config = {
            'OPENAI_API_KEY': 'sk-test-key',
            'OPENAI_BASE_URL': 'https://api.openai.com/v1'
            # Missing OPENAI_MODEL
        }
        result = validate_config(incomplete_config)
        self.assertFalse(result)

    @patch.dict(os.environ, {
        'OPENAI_API_KEY': 'sk-env-test-key',
        'OPENAI_BASE_URL': 'https://api.openai.com/v1',
        'OPENAI_MODEL': 'gpt-4',
        'LOG_PATH': '.logs',
        'AUTO_COMMIT': 'true'
    })
    @patch('ai_commit.cli.find_config_files')
    def test_load_config_from_env_vars(self, mock_find_config):
        """Test loading configuration from environment variables"""
        mock_logger = MagicMock()
        mock_find_config.return_value = (None, None)  # No config file found
        
        config = load_config(mock_logger)
        
        self.assertEqual(config['OPENAI_API_KEY'], 'sk-env-test-key')
        self.assertEqual(config['OPENAI_BASE_URL'], 'https://api.openai.com/v1')
        self.assertEqual(config['OPENAI_MODEL'], 'gpt-4')
        self.assertEqual(config['LOG_PATH'], '.logs')
        self.assertTrue(config['AUTO_COMMIT'])  # Should be converted to boolean


if __name__ == '__main__':
    unittest.main()