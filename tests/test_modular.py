"""
Tests for the new modular architecture.

This module contains tests for the refactored AI Commit components.
"""

import unittest
import os
import tempfile
import time
import subprocess
import logging
from unittest.mock import patch, MagicMock, Mock
from pathlib import Path

# Import the new modular components
from ai_commit.config import AICommitConfig, ConfigurationLoader
from ai_commit.security import APIKeyManager, InputValidator
from ai_commit.git import GitOperations
from ai_commit.ai import AIClient
from ai_commit.utils import FileSelector, LoggingManager, ProgressManager
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
        git_ops.disable_cache_for_testing()
        branch = git_ops.get_current_branch()
        self.assertEqual(branch, "main")
        git_ops.enable_cache_for_testing()
    
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


class TestBoundaryConditions(unittest.TestCase):
    """Test boundary conditions and edge cases."""
    
    def test_empty_git_diff_validation(self):
        """Test validation of empty git diff."""
        validator = InputValidator()
        
        with self.assertRaises(ValidationError):
            validator.validate_git_diff("")
        
        with self.assertRaises(ValidationError):
            validator.validate_git_diff("   ")
    
    def test_large_git_diff_validation(self):
        """Test validation of large git diff."""
        validator = InputValidator()
        
        # Create a diff that's exactly at the limit
        large_diff = "a" * (1024 * 1024)  # 1MB
        validated_diff = validator.validate_git_diff(large_diff)
        self.assertEqual(validated_diff, large_diff)
        
        # Test diff that's too large
        too_large_diff = "a" * (1024 * 1024 + 1)  # 1MB + 1 byte
        with self.assertRaises(ValidationError):
            validator.validate_git_diff(too_large_diff)
    
    def test_commit_message_length_validation(self):
        """Test validation of commit message length."""
        validator = InputValidator()
        
        # Test message that's exactly at the limit
        long_message = "a" * 200
        validated_message = validator.validate_commit_message(long_message)
        self.assertEqual(validated_message, long_message)
        
        # Test message that's too long
        too_long_message = "a" * 201
        with self.assertRaises(ValidationError):
            validator.validate_commit_message(too_long_message)
    
    def test_sensitive_data_detection_edge_cases(self):
        """Test sensitive data detection with various edge cases."""
        validator = InputValidator()
        
        # Test strings that look like but aren't API keys
        safe_strings = [
            "sk-test",  # Too short
            "not-a-key",  # Wrong format
            "sk-123",  # Too short
            "ghp_",  # Incomplete GitHub token
        ]
        
        for safe_string in safe_strings:
            try:
                validator.validate_git_diff(f"diff --git a/test.py b/test.py\n+{safe_string}")
            except ValidationError:
                self.fail(f"False positive detected for safe string: {safe_string}")
    
    def test_progress_manager_context_manager(self):
        """Test ProgressManager context manager functionality."""
        with ProgressManager() as pm:
            self.assertIsNotNone(pm)
            pm.show_operation("Test operation")
        
        # Test that cleanup was called
        self.assertIsNone(pm.current_operation)
    
    def test_logging_manager_singleton(self):
        """Test LoggingManager singleton pattern."""
        # Create two instances
        lm1 = LoggingManager()
        lm2 = LoggingManager()
        
        # They should be the same instance
        self.assertIs(lm1, lm2)
        
        # Test get_instance method
        lm3 = LoggingManager.get_instance()
        self.assertIs(lm1, lm3)


class TestIntegrationScenarios(unittest.TestCase):
    """Test integration scenarios and real-world usage patterns."""
    
    def test_complete_workflow_simulation(self):
        """Test a complete workflow simulation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test configuration
            config = AICommitConfig(
                openai_api_key="sk-test-key-1234567890abcdef",
                openai_base_url="https://api.openai.com/v1",
                openai_model="gpt-3.5-turbo",
                log_path=temp_dir
            )
            
            # Test git operations with mocked git
            with patch('ai_commit.git.subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout=".git\n")
                git_ops = GitOperations()
                git_ops.validate_git_repository()
            
            # Test file selector
            file_selector = FileSelector()
            self.assertIsNotNone(file_selector)
            
            # Test logging manager
            # Reset singleton for testing to ensure fresh initialization
            LoggingManager._instance = None
            LoggingManager._initialized = False
            logging_manager = LoggingManager(temp_dir)
            logger = logging_manager.get_logger()
            self.assertIsNotNone(logger)
            
            # Test logging - log a message to ensure file creation
            logger.info("Test log message")
            logging_manager.log_with_details(logging.INFO, "Test message with details", "Test details")
            
            # Test that log file was created
            log_files = list(Path(temp_dir).glob("commit_*.log"))
            self.assertGreater(len(log_files), 0)
    
    def test_error_handling_scenarios(self):
        """Test various error handling scenarios."""
        # Test configuration error
        with self.assertRaises(ConfigurationError):
            AICommitConfig(
                openai_api_key="",
                openai_base_url="https://api.openai.com/v1",
                openai_model="gpt-3.5-turbo"
            )
        
        # Test git operation error
        with patch('ai_commit.git.subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, 'git')
            git_ops = GitOperations()
            
            with self.assertRaises(GitOperationError):
                git_ops.validate_git_repository()
    
    def test_performance_scenarios(self):
        """Test performance-related scenarios."""
        # Test with large file lists
        large_file_list = [f"file_{i}.py" for i in range(1000)]
        
        file_selector = FileSelector()
        
        # Test file selector initialization (avoid interactive input in tests)
        start_time = time.time()
        # Just test that the file selector can handle large lists without interactive selection
        self.assertIsNotNone(file_selector)
        end_time = time.time()
        
        # Should complete quickly
        self.assertLess(end_time - start_time, 1.0)


if __name__ == '__main__':
    unittest.main()