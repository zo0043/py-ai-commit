"""
Git operations module for AI Commit.

This module handles all git-related operations including diff analysis,
file staging, committing, and repository validation.
"""

import subprocess
import logging
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path

from ..exceptions import GitOperationError, ValidationError
from ..security import InputValidator

logger = logging.getLogger(__name__)


class GitOperations:
    """Handles git operations for AI Commit."""
    
    def __init__(self):
        """Initialize Git operations handler."""
        self.validator = InputValidator()
    
    def validate_git_repository(self) -> None:
        """
        Validate that current directory is a git repository.
        
        Raises:
            GitOperationError: If not in a git repository
        """
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--git-dir'],
                capture_output=True,
                text=True,
                check=True,
                timeout=10
            )
            logger.debug(f"Git repository found: {result.stdout.strip()}")
        except subprocess.CalledProcessError:
            raise GitOperationError(
                "Not a git repository. Please run this command from within a git repository."
            )
        except subprocess.TimeoutExpired:
            raise GitOperationError("Git command timed out")
    
    def get_current_branch(self) -> Optional[str]:
        """
        Get current git branch name.
        
        Returns:
            Current branch name or None if cannot be determined
        """
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                capture_output=True,
                text=True,
                check=True,
                timeout=10
            )
            branch_name = result.stdout.strip()
            logger.debug(f"Current branch: {branch_name}")
            return branch_name
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.warning(f"Could not determine current branch: {e}")
            return None
    
    def get_changed_files(self) -> Tuple[List[str], List[str]]:
        """
        Get lists of staged and unstaged files.
        
        Returns:
            Tuple of (staged_files, unstaged_files)
            
        Raises:
            GitOperationError: If git operations fail
        """
        try:
            staged_files = self._get_staged_files()
            unstaged_files = self._get_unstaged_files()
            untracked_files = self._get_untracked_files()
            
            # Combine unstaged and untracked files
            all_unstaged = list(set(unstaged_files + untracked_files))
            
            logger.info(f"Found {len(staged_files)} staged, {len(all_unstaged)} unstaged files")
            return staged_files, all_unstaged
            
        except subprocess.CalledProcessError as e:
            raise GitOperationError(f"Failed to get changed files: {e}")
        except subprocess.TimeoutExpired:
            raise GitOperationError("Git command timed out while getting changed files")
    
    def _get_staged_files(self) -> List[str]:
        """Get list of staged files."""
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only'],
            capture_output=True,
            text=True,
            check=True,
            timeout=10
        )
        return [f.strip() for f in result.stdout.splitlines() if f.strip()]
    
    def _get_unstaged_files(self) -> List[str]:
        """Get list of modified but unstaged files."""
        result = subprocess.run(
            ['git', 'diff', '--name-only'],
            capture_output=True,
            text=True,
            check=True,
            timeout=10
        )
        return [f.strip() for f in result.stdout.splitlines() if f.strip()]
    
    def _get_untracked_files(self) -> List[str]:
        """Get list of untracked files."""
        result = subprocess.run(
            ['git', 'ls-files', '--others', '--exclude-standard'],
            capture_output=True,
            text=True,
            check=True,
            timeout=10
        )
        return [f.strip() for f in result.stdout.splitlines() if f.strip()]
    
    def get_git_diff(self) -> str:
        """
        Get git diff of staged and unstaged changes.
        
        Returns:
            Git diff content
            
        Raises:
            GitOperationError: If git diff fails
            ValidationError: If diff content is invalid
        """
        try:
            # Get unstaged changes
            unstaged_result = subprocess.run(
                ['git', 'diff'],
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )
            
            # Get staged changes
            staged_result = subprocess.run(
                ['git', 'diff', '--cached'],
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )
            
            total_diff = unstaged_result.stdout + staged_result.stdout
            
            if not total_diff.strip():
                logger.warning("No changes detected in git diff")
                return ""
            
            # Validate diff content
            validated_diff = self.validator.validate_git_diff(total_diff)
            
            logger.info(f"Retrieved git diff: {len(validated_diff)} characters")
            return validated_diff
            
        except subprocess.CalledProcessError as e:
            raise GitOperationError(f"Failed to get git diff: {e}")
        except subprocess.TimeoutExpired:
            raise GitOperationError("Git diff command timed out")
    
    def validate_staged_changes(self) -> bool:
        """
        Validate that there are staged changes for commit.
        
        Returns:
            True if staged changes exist, False otherwise
        """
        try:
            result = subprocess.run(
                ['git', 'diff', '--cached', '--quiet'],
                capture_output=True,
                timeout=10
            )
            # Return code 0 means no differences (no staged changes)
            # Return code 1 means differences exist (staged changes present)
            has_changes = result.returncode != 0
            logger.debug(f"Staged changes present: {has_changes}")
            return has_changes
        except subprocess.TimeoutExpired:
            raise GitOperationError("Git command timed out while checking staged changes")
        except subprocess.CalledProcessError:
            return False
    
    def stage_files(self, files: List[str]) -> bool:
        """
        Stage specified files.
        
        Args:
            files: List of file paths to stage
            
        Returns:
            True if staging succeeded, False otherwise
            
        Raises:
            GitOperationError: If staging fails
        """
        if not files:
            logger.debug("No files to stage")
            return True
        
        try:
            for file in files:
                # Validate file path
                file_path = Path(file)
                if not file_path.exists():
                    logger.warning(f"File does not exist: {file}")
                    continue
                
                result = subprocess.run(
                    ['git', 'add', file],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=10
                )
            
            logger.info(f"Successfully staged {len(files)} files")
            return True
            
        except subprocess.CalledProcessError as e:
            raise GitOperationError(f"Failed to stage files: {e}")
        except subprocess.TimeoutExpired:
            raise GitOperationError("Git add command timed out")
    
    def commit_changes(self, commit_message: str) -> bool:
        """
        Commit staged changes with the provided message.
        
        Args:
            commit_message: The commit message to use
            
        Returns:
            True if commit succeeded, False otherwise
            
        Raises:
            GitOperationError: If commit fails
            ValidationError: If commit message is invalid
        """
        # Validate commit message
        validated_message = self.validator.validate_commit_message(commit_message)
        
        try:
            result = subprocess.run(
                ['git', 'commit', '-m', validated_message],
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )
            
            logger.info("Changes committed successfully")
            logger.debug(f"Commit output: {result.stdout}")
            return True
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            raise GitOperationError(f"Failed to commit changes: {error_msg}")
        except subprocess.TimeoutExpired:
            raise GitOperationError("Git commit command timed out")
    
    def push_changes(self) -> bool:
        """
        Push committed changes to remote repository.
        
        Returns:
            True if push succeeded, False otherwise
            
        Raises:
            GitOperationError: If push fails
        """
        # Get current branch name
        branch_name = self.get_current_branch()
        if not branch_name:
            raise GitOperationError("Could not determine current branch for push")
        
        try:
            result = subprocess.run(
                ['git', 'push', 'origin', branch_name],
                capture_output=True,
                text=True,
                check=True,
                timeout=60
            )
            
            logger.info(f"Changes pushed successfully to origin/{branch_name}")
            logger.debug(f"Push output: {result.stdout}")
            return True
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            raise GitOperationError(f"Failed to push changes: {error_msg}")
        except subprocess.TimeoutExpired:
            raise GitOperationError("Git push command timed out")
    
    def get_repository_status(self) -> Dict[str, Any]:
        """
        Get comprehensive repository status.
        
        Returns:
            Dictionary containing repository status information
        """
        try:
            # Get git status
            status_result = subprocess.run(
                ['git', 'status', '--porcelain'],
                capture_output=True,
                text=True,
                check=True,
                timeout=10
            )
            
            # Parse status output
            staged_files = []
            unstaged_files = []
            untracked_files = []
            
            for line in status_result.stdout.splitlines():
                if len(line) >= 3:
                    status_code = line[:2]
                    file_path = line[3:]
                    
                    if status_code[0] != ' ' and status_code[0] != '?':
                        staged_files.append(file_path)
                    if status_code[1] != ' ':
                        if status_code[1] == '?':
                            untracked_files.append(file_path)
                        else:
                            unstaged_files.append(file_path)
            
            return {
                'branch': self.get_current_branch(),
                'staged_files': staged_files,
                'unstaged_files': unstaged_files,
                'untracked_files': untracked_files,
                'has_staged_changes': len(staged_files) > 0,
                'has_unstaged_changes': len(unstaged_files) > 0,
                'has_untracked_files': len(untracked_files) > 0,
            }
            
        except subprocess.CalledProcessError as e:
            raise GitOperationError(f"Failed to get repository status: {e}")
        except subprocess.TimeoutExpired:
            raise GitOperationError("Git status command timed out")