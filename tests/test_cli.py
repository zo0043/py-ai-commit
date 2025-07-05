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
    parse_args
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
            self.assertIsNone(args.config)
            self.assertIsNone(args.model)

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


if __name__ == '__main__':
    unittest.main()