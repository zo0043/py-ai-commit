import unittest
import sys
import os
from unittest.mock import patch, MagicMock
import tempfile

# Add the parent directory to the path to import ai_commit
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import from the new modular architecture
from ai_commit.cli import parse_args, AICommitWorkflow
from ai_commit.config import AICommitConfig
from ai_commit.git import GitOperations
from ai_commit.ai import AIClient
from ai_commit.utils import FileSelector
from ai_commit.exceptions import GitOperationError, ValidationError


class TestAICommit(unittest.TestCase):
    """Test cases for AI Commit functionality"""

    def setUp(self):
        """Set up test fixtures."""
        self.test_config = AICommitConfig(
            openai_api_key="sk-test-key-1234567890abcdef",
            openai_base_url="https://api.openai.com/v1",
            openai_model="gpt-3.5-turbo"
        )

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

    @patch('ai_commit.git.subprocess.run')
    def test_git_operations_get_branch_name(self, mock_run):
        """Test branch name extraction with GitOperations"""
        git_ops = GitOperations()
        
        # Test successful branch name retrieval
        mock_run.return_value = MagicMock(stdout="main\n", returncode=0)
        result = git_ops.get_current_branch()
        self.assertEqual(result, "main")
        
        # Test error handling - should return None on subprocess error
        import subprocess
        mock_run.side_effect = subprocess.CalledProcessError(1, 'git')
        result = git_ops.get_current_branch()
        self.assertIsNone(result)

    @patch('ai_commit.git.subprocess.run')
    def test_git_operations_validate_staged_changes(self, mock_run):
        """Test staged changes validation with GitOperations"""
        git_ops = GitOperations()
        
        # Test with staged changes
        mock_run.return_value = MagicMock(returncode=1)  # Non-zero means changes exist
        result = git_ops.validate_staged_changes()
        self.assertTrue(result)
        
        # Test without staged changes
        mock_run.return_value = MagicMock(returncode=0)  # Zero means no changes
        result = git_ops.validate_staged_changes()
        self.assertFalse(result)

    @patch('ai_commit.git.subprocess.run')
    def test_git_operations_get_changed_files(self, mock_run):
        """Test getting changed files with GitOperations"""
        git_ops = GitOperations()
        
        # Mock the three subprocess calls
        mock_run.side_effect = [
            MagicMock(stdout="file1.py\nfile2.py\n", returncode=0),  # staged files
            MagicMock(stdout="file3.py\n", returncode=0),           # unstaged files
            MagicMock(stdout="file4.py\n", returncode=0)            # untracked files
        ]
        
        staged, unstaged = git_ops.get_changed_files()
        
        self.assertEqual(staged, ['file1.py', 'file2.py'])
        self.assertEqual(set(unstaged), {'file3.py', 'file4.py'})

    @patch('ai_commit.git.subprocess.run')
    def test_git_operations_stage_files(self, mock_run):
        """Test staging files with GitOperations"""
        git_ops = GitOperations()
        
        # Test successful staging
        mock_run.return_value = MagicMock(returncode=0)
        
        # Mock Path.exists to return True
        with patch('pathlib.Path.exists', return_value=True):
            result = git_ops.stage_files(['file1.py', 'file2.py'])
            self.assertTrue(result)
        
        # Test with empty list
        result = git_ops.stage_files([])
        self.assertTrue(result)

    def test_config_validation(self):
        """Test configuration validation"""
        # Test valid configuration
        valid_config = AICommitConfig(
            openai_api_key="sk-test-key-1234567890abcdef",
            openai_base_url="https://api.openai.com/v1",
            openai_model="gpt-3.5-turbo"
        )
        # Should not raise an exception
        valid_config.validate()
        
        # Test invalid API key format - should raise ConfigurationError due to validation in __post_init__
        from ai_commit.exceptions import ConfigurationError
        with self.assertRaises(ConfigurationError):
            AICommitConfig(
                openai_api_key="invalid-key",
                openai_base_url="https://api.openai.com/v1",
                openai_model="gpt-3.5-turbo"
            )

    @patch.dict(os.environ, {
        'OPENAI_API_KEY': 'sk-env-test-key-1234567890abcdef',
        'OPENAI_BASE_URL': 'https://api.openai.com/v1',
        'OPENAI_MODEL': 'gpt-4',
        'LOG_PATH': '.logs',
        'AUTO_COMMIT': 'true'
    })
    def test_load_config_from_env_vars(self):
        """Test loading configuration from environment variables"""
        from ai_commit.config import ConfigurationLoader
        
        config_loader = ConfigurationLoader()
        
        # Mock file finding to return no config files
        with patch.object(config_loader, '_find_config_files', return_value=(None, None)):
            config = config_loader.load_config()
            
            self.assertEqual(config.openai_api_key, 'sk-env-test-key-1234567890abcdef')
            self.assertEqual(config.openai_base_url, 'https://api.openai.com/v1')
            self.assertEqual(config.openai_model, 'gpt-4')
            self.assertEqual(config.log_path, '.logs')
            self.assertTrue(config.auto_commit)

    def test_ai_client_initialization(self):
        """Test AI client initialization"""
        ai_client = AIClient(self.test_config)
        self.assertIsInstance(ai_client, AIClient)
        
        # Test that methods exist
        self.assertTrue(hasattr(ai_client, 'generate_commit_message'))
        self.assertTrue(hasattr(ai_client, 'test_connection'))

    def test_file_selector_initialization(self):
        """Test file selector initialization"""
        file_selector = FileSelector()
        
        # Test that methods exist
        self.assertTrue(hasattr(file_selector, 'display_file_changes'))
        self.assertTrue(hasattr(file_selector, 'select_files_interactive'))

    def test_workflow_initialization(self):
        """Test workflow initialization"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = AICommitConfig(
                openai_api_key="sk-test-key-1234567890abcdef",
                openai_base_url="https://api.openai.com/v1",
                openai_model="gpt-3.5-turbo",
                log_path=temp_dir
            )
            
            workflow = AICommitWorkflow(config)
            self.assertIsInstance(workflow, AICommitWorkflow)
            self.assertEqual(workflow.config, config)
            self.assertIsNotNone(workflow.git_ops)
            self.assertIsNotNone(workflow.ai_client)
            self.assertIsNotNone(workflow.file_selector)


if __name__ == '__main__':
    unittest.main()