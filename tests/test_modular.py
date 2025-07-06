"""
Tests for the new modular architecture.

This module contains tests for the refactored AI Commit components.
"""

import unittest
import os
import tempfile
from unittest.mock import patch, MagicMock, Mock
from pathlib import Path

# Import the new modular components
from ai_commit.config import AICommitConfig, ConfigurationLoader
from ai_commit.security import APIKeyManager, InputValidator
from ai_commit.git import GitOperations
from ai_commit.ai import AIClient
from ai_commit.utils import FileSelector, LoggingManager
from ai_commit.exceptions import (
    ConfigurationError, GitOperationError, APIError, 
    SecurityError, ValidationError
)


class TestModularArchitecture(unittest.TestCase):
    """Test cases for the new modular architecture."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_config = AICommitConfig(
            openai_api_key="sk-test-key-1234567890abcdef",
            openai_base_url="https://api.openai.com/v1",
            openai_model="gpt-3.5-turbo"
        )
    
    def test_config_validation(self):
        """Test configuration validation."""
        # Test valid configuration
        self.assertIsInstance(self.test_config, AICommitConfig)
        
        # Test invalid API key
        with self.assertRaises(ConfigurationError):
            AICommitConfig(
                openai_api_key="invalid-key",
                openai_base_url="https://api.openai.com/v1",
                openai_model="gpt-3.5-turbo"
            )
    
    def test_input_validator(self):
        """Test input validation functionality."""
        validator = InputValidator()
        
        # Test valid git diff
        valid_diff = "diff --git a/test.py b/test.py\n+print('hello')"
        result = validator.validate_git_diff(valid_diff)
        self.assertEqual(result, valid_diff)
        
        # Test empty diff
        with self.assertRaises(ValidationError):
            validator.validate_git_diff("")
        
        # Test valid commit message
        valid_message = "feat(auth): add user authentication"
        result = validator.validate_commit_message(valid_message)
        self.assertEqual(result, valid_message)
        
        # Test empty commit message
        with self.assertRaises(ValidationError):
            validator.validate_commit_message("")
    
    def test_api_key_manager(self):
        """Test API key management (mocked)."""
        with patch('keyring.get_keyring'):
            api_key_manager = APIKeyManager()
            
            # Test that methods exist and can be called
            self.assertTrue(hasattr(api_key_manager, 'store_api_key'))
            self.assertTrue(hasattr(api_key_manager, 'get_api_key'))
            self.assertTrue(hasattr(api_key_manager, 'delete_api_key'))
    
    def test_file_selector(self):
        """Test file selector functionality."""
        file_selector = FileSelector()
        
        # Test that methods exist
        self.assertTrue(hasattr(file_selector, 'display_file_changes'))
        self.assertTrue(hasattr(file_selector, 'select_files_interactive'))
    
    @patch('ai_commit.git.subprocess.run')
    def test_git_operations(self, mock_run):
        """Test git operations."""
        git_ops = GitOperations()
        
        # Mock successful git rev-parse
        mock_run.return_value = MagicMock(returncode=0, stdout=".git\n")
        
        # Test git repository validation
        try:
            git_ops.validate_git_repository()
        except GitOperationError:
            self.fail("validate_git_repository raised GitOperationError unexpectedly")
        
        # Test get current branch
        mock_run.return_value = MagicMock(returncode=0, stdout="main\n")
        branch = git_ops.get_current_branch()
        self.assertEqual(branch, "main")
    
    def test_ai_client_initialization(self):
        """Test AI client initialization."""
        # Test successful initialization
        ai_client = AIClient(self.test_config)
        self.assertIsInstance(ai_client, AIClient)
        
        # Test methods exist
        self.assertTrue(hasattr(ai_client, 'generate_commit_message'))
        self.assertTrue(hasattr(ai_client, 'test_connection'))
    
    def test_logging_manager(self):
        """Test logging manager."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logging_manager = LoggingManager(temp_dir)
            
            # Test that logger is created
            logger = logging_manager.get_logger()
            self.assertIsNotNone(logger)
            
            # Test secure logger
            secure_logger = logging_manager.get_secure_logger()
            self.assertIsNotNone(secure_logger)


class TestConfigurationLoader(unittest.TestCase):
    """Test configuration loading from various sources."""
    
    def test_environment_variable_loading(self):
        """Test loading configuration from environment variables."""
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'sk-env-test-key-1234567890abcdef',
            'OPENAI_BASE_URL': 'https://api.openai.com/v1',
            'OPENAI_MODEL': 'gpt-4',
        }):
            config_loader = ConfigurationLoader()
            
            # Mock file finding to return no config files
            with patch.object(config_loader, '_find_config_files', return_value=(None, None)):
                config = config_loader.load_config()
                
                self.assertEqual(config.openai_api_key, 'sk-env-test-key-1234567890abcdef')
                self.assertEqual(config.openai_model, 'gpt-4')


if __name__ == '__main__':
    unittest.main()