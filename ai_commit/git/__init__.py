"""
Git operations module for AI Commit.

This module handles all git-related operations including diff analysis,
file staging, committing, and repository validation.
"""

import subprocess
import logging
import time
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path
from dataclasses import dataclass, field
from collections import defaultdict

from ..exceptions import GitOperationError, ValidationError
from ..security import InputValidator

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry for git command results."""
    data: Any
    timestamp: float
    ttl: float = 30.0  # 30 seconds cache
    access_count: int = 0
    
    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl
    
    def record_access(self) -> None:
        """Record an access to this cache entry."""
        self.access_count += 1


@dataclass
class CacheStats:
    """Cache statistics for monitoring and optimization."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_access_time: float = 0.0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    @property
    def avg_access_time(self) -> float:
        """Calculate average access time."""
        return self.total_access_time / self.hits if self.hits > 0 else 0.0
    
    def record_hit(self, access_time: float = 0.0) -> None:
        """Record a cache hit."""
        self.hits += 1
        self.total_access_time += access_time
    
    def record_miss(self) -> None:
        """Record a cache miss."""
        self.misses += 1
    
    def record_eviction(self) -> None:
        """Record a cache eviction."""
        self.evictions += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics as dictionary."""
        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': self.hit_rate,
            'evictions': self.evictions,
            'avg_access_time': self.avg_access_time,
            'total_requests': self.hits + self.misses
        }


class GitOperations:
    """Handles git operations for AI Commit."""

    def __init__(self):
        """Initialize Git operations handler."""
        self.validator = InputValidator()
        self._cache: Dict[str, CacheEntry] = {}
        self._cache_stats = CacheStats()
        self._repo_root: Optional[str] = None
        self._command_stats: Dict[str, Dict[str, float]] = defaultdict(lambda: {
            'count': 0, 'total_time': 0.0, 'avg_time': 0.0
        })
        self._prewarmed = False
        self._prewarm_lock = None
        self._cache_enabled = True

    def _get_cache_key(self, command: str, args: List[str] = None) -> str:
        """Generate cache key for git commands."""
        if not args:
            return command
        
        # Use a more efficient key generation strategy
        # Hash the arguments for better performance and shorter keys
        import hashlib
        
        # Sort args for consistency
        sorted_args = sorted(args)
        args_str = '_'.join(sorted_args)
        
        # Create hash of arguments for shorter cache keys
        args_hash = hashlib.md5(args_str.encode()).hexdigest()[:8]
        
        return f"{command}_{args_hash}"

    def _get_cached_result(self, key: str) -> Optional[Any]:
        """Get cached result if not expired."""
        if not self._cache_enabled:
            return None
            
        start_time = time.time()
        if key in self._cache:
            entry = self._cache[key]
            if not entry.is_expired():
                entry.record_access()
                access_time = time.time() - start_time
                self._cache_stats.record_hit(access_time)
                logger.debug(f"Cache hit for {key} (access count: {entry.access_count})")
                return entry.data
            else:
                del self._cache[key]
                self._cache_stats.record_eviction()
                logger.debug(f"Cache expired for {key}")
        
        self._cache_stats.record_miss()
        return None

    def _cache_result(self, key: str, data: Any, ttl: float = 30.0) -> None:
        """Cache result with TTL."""
        if not self._cache_enabled:
            return
            
        # Check if we need to evict an entry (LRU strategy)
        if len(self._cache) >= 100:  # Max cache size
            self._evict_lru_entry()
        
        self._cache[key] = CacheEntry(
            data=data, 
            timestamp=time.time(), 
            ttl=ttl
        )
        logger.debug(f"Cached result for {key}")
    
    def _evict_lru_entry(self) -> None:
        """Evict least recently used cache entry."""
        if not self._cache:
            return
        
        # Find entry with oldest access time
        lru_key = min(self._cache.keys(), 
                     key=lambda k: self._cache[k].timestamp)
        del self._cache[lru_key]
        self._cache_stats.record_eviction()
        logger.debug(f"Evicted LRU cache entry: {lru_key}")

    def _run_git_command(self, command: List[str], cache_key: str = None, ttl: float = 30.0) -> str:
        """Run git command with caching support."""
        start_time = time.time()
        command_str = ' '.join(command)
        
        if cache_key:
            cached_result = self._get_cached_result(cache_key)
            if cached_result is not None:
                return cached_result
        
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )
            
            execution_time = time.time() - start_time
            self._record_command_stats(command[0], execution_time)
            
            if cache_key:
                self._cache_result(cache_key, result.stdout, ttl)
            
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise GitOperationError(f"Git command failed: {command_str} - {e}")
        except subprocess.TimeoutExpired:
            raise GitOperationError(f"Git command timed out: {command_str}")
    
    def _record_command_stats(self, command: str, execution_time: float) -> None:
        """Record command execution statistics."""
        stats = self._command_stats[command]
        stats['count'] += 1
        stats['total_time'] += execution_time
        stats['avg_time'] = stats['total_time'] / stats['count']

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
            self._repo_root = result.stdout.strip()
            logger.debug(f"Git repository found: {self._repo_root}")
            
            # Pre-warm cache on first validation
            if not self._prewarmed:
                self._prewarm_cache_async()
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
        # Use a fixed cache key for branch name as it changes infrequently
        cache_key = "current_branch"
        cached_result = self._get_cached_result(cache_key)
        if cached_result is not None:
            return cached_result
        
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
            
            # Cache with longer TTL as branch names don't change frequently
            self._cache_result(cache_key, branch_name, ttl=120.0)  # 2 minutes
            
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
        # Use a cache key based on the repository state
        # This helps avoid repeated calls when no files have changed
        import hashlib
        
        try:
            # Get repository state hash for caching
            state_result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                check=True,
                timeout=10
            )
            
            # Create cache key based on HEAD commit
            head_hash = state_result.stdout.strip()[:8]
            cache_key = f"changed_files_{head_hash}"
            
            cached_result = self._get_cached_result(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Use single git command to get all file status information
            # This reduces subprocess calls from 3 to 1
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                capture_output=True,
                text=True,
                check=True,
                timeout=10
            )

            staged_files = []
            unstaged_files = []
            untracked_files = []

            # Parse git status output
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue

                # Git status format: XY FILENAME
                # X = staged status, Y = unstaged status
                staged_status = line[0]
                unstaged_status = line[1]
                filename = line[3:]

                if staged_status != ' ' and staged_status != '?':
                    # File is staged (but not untracked)
                    staged_files.append(filename)

                if unstaged_status != ' ':
                    # File has unstaged changes
                    unstaged_files.append(filename)
                elif staged_status == '?' and unstaged_status == '?':
                    # Untracked file
                    untracked_files.append(filename)

            # Combine unstaged and untracked files
            all_unstaged = list(set(unstaged_files + untracked_files))
            
            # Cache with short TTL as file status changes frequently
            result_tuple = (staged_files, all_unstaged)
            self._cache_result(cache_key, result_tuple, ttl=15.0)  # 15 seconds

            logger.info(f"Found {len(staged_files)} staged, {len(all_unstaged)} unstaged files")
            return staged_files, all_unstaged

        except subprocess.CalledProcessError as e:
            raise GitOperationError(f"Failed to get changed files: {e}")
        except subprocess.TimeoutExpired:
            raise GitOperationError("Git command timed out while getting changed files")

    def get_git_diff(self, split_large_files: bool = True, max_chunk_size: int = 500000) -> str:
        """
        Get git diff of staged and unstaged changes.

        Args:
            split_large_files: Whether to split large diffs into chunks
            max_chunk_size: Maximum size of each diff chunk in characters

        Returns:
            Git diff content

        Raises:
            GitOperationError: If git diff fails
            ValidationError: If diff content is invalid
        """
        try:
            # Get staged and unstaged changes
            staged_result = subprocess.run(
                ['git', 'diff', '--stat', '--cached', '--unified=3'],
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )

            unstaged_result = subprocess.run(
                ['git', 'diff', '--stat', '--unified=3'],
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )

            # Combine results
            total_diff = staged_result.stdout + unstaged_result.stdout

            if not total_diff.strip():
                logger.warning("No changes detected in git diff")
                return ""

            # Handle large diff splitting
            if split_large_files and len(total_diff) > max_chunk_size:
                logger.info(f"Large diff detected ({len(total_diff)} characters), splitting into chunks")
                return self._split_and_process_diff(total_diff, max_chunk_size)

            # Validate diff content
            validated_diff = self.validator.validate_git_diff(total_diff)

            logger.info(f"Retrieved git diff: {len(validated_diff)} characters")
            return validated_diff

        except subprocess.CalledProcessError as e:
            raise GitOperationError(f"Failed to get git diff: {e}")
        except subprocess.TimeoutExpired:
            raise GitOperationError("Git diff command timed out")

    def _split_and_process_diff(self, diff: str, max_chunk_size: int) -> str:
        """
        Split large diff into manageable chunks and process them.
        
        Args:
            diff: The complete git diff
            max_chunk_size: Maximum size for each chunk
            
        Returns:
            Processed diff summary
        """
        # Split diff into individual file diffs
        file_diffs = self._split_diff_by_files(diff)
        
        # Group files into chunks
        chunks = []
        current_chunk = ""
        current_size = 0
        
        for file_diff in file_diffs:
            file_size = len(file_diff)
            
            # If single file is too large, truncate it
            if file_size > max_chunk_size:
                truncated_diff = self._truncate_large_file_diff(file_diff, max_chunk_size)
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                    current_size = 0
                chunks.append(truncated_diff)
                continue
            
            # If adding this file would exceed chunk size, start new chunk
            if current_size + file_size > max_chunk_size and current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
                current_size = 0
            
            current_chunk += file_diff + "\n"
            current_size += file_size
        
        # Add the last chunk if it has content
        if current_chunk:
            chunks.append(current_chunk)
        
        logger.info(f"Split diff into {len(chunks)} chunks")
        
        # Process chunks and create summary
        return self._create_diff_summary(chunks, diff)
    
    def _split_diff_by_files(self, diff: str) -> List[str]:
        """
        Split git diff into individual file diffs.
        
        Args:
            diff: Complete git diff
            
        Returns:
            List of individual file diffs
        """
        # Git diff format: diff --git a/path/to/file b/path/to/file
        file_diffs = []
        lines = diff.split('\n')
        current_diff = []
        
        for line in lines:
            if line.startswith('diff --git '):
                # Start of new file diff
                if current_diff:
                    file_diffs.append('\n'.join(current_diff))
                    current_diff = []
                current_diff.append(line)
            else:
                current_diff.append(line)
        
        # Add the last file diff
        if current_diff:
            file_diffs.append('\n'.join(current_diff))
        
        return file_diffs
    
    def _truncate_large_file_diff(self, file_diff: str, max_size: int) -> str:
        """
        Truncate a large file diff to fit within size limits.
        
        Args:
            file_diff: Single file diff
            max_size: Maximum size for the truncated diff
            
        Returns:
            Truncated diff
        """
        if len(file_diff) <= max_size:
            return file_diff
        
        lines = file_diff.split('\n')
        
        # Keep the header (diff --git line and index line)
        header_lines = []
        content_lines = []
        
        for line in lines:
            if line.startswith('diff --git ') or line.startswith('index '):
                header_lines.append(line)
            else:
                content_lines.append(line)
        
        # If no content lines, just return header
        if not content_lines:
            return '\n'.join(header_lines)
        
        # Calculate how many lines we can keep (approximate)
        header_size = len('\n'.join(header_lines)) + len('\n')
        truncation_msg_size = 50  # Approximate size of truncation message
        available_size = max_size - header_size - truncation_msg_size
        
        if available_size <= 0:
            # If header is too large, just return basic info
            return f"{header_lines[0]}\n# Large file diff truncated ({len(file_diff)} characters)"
        
        # Estimate average line length
        avg_line_length = sum(len(line) for line in content_lines) / len(content_lines)
        lines_to_keep = max(1, int(available_size / avg_line_length / 2))  # Half from beginning, half from end
        
        if lines_to_keep >= len(content_lines) // 2:
            # No need to truncate
            return file_diff
        
        beginning = content_lines[:lines_to_keep]
        end = content_lines[-lines_to_keep:]
        
        truncated_diff = '\n'.join(header_lines) + '\n'
        truncated_diff += '\n'.join(beginning) + '\n'
        truncated_diff += f"# ... {len(content_lines) - (lines_to_keep * 2)} lines omitted ...\n"
        truncated_diff += '\n'.join(end)
        
        return truncated_diff
    
    def _create_diff_summary(self, chunks: List[str], original_diff: str) -> str:
        """
        Create a summary from processed diff chunks.
        
        Args:
            chunks: List of diff chunks
            original_diff: Original complete diff
            
        Returns:
            Summary diff
        """
        # Create a summary that includes information about all files
        summary_lines = []
        summary_lines.append("# Large commit diff summary")
        summary_lines.append(f"# Original diff size: {len(original_diff)} characters")
        summary_lines.append(f"# Split into {len(chunks)} manageable chunks")
        summary_lines.append("#")
        
        # Extract file information from each chunk
        all_files = []
        for chunk in chunks:
            files_in_chunk = self._extract_files_from_diff(chunk)
            all_files.extend(files_in_chunk)
        
        summary_lines.append(f"# Files changed: {len(all_files)}")
        for file in all_files:
            summary_lines.append(f"#   - {file}")
        
        summary_lines.append("#")
        summary_lines.append("# Detailed changes (first chunk only):")
        summary_lines.append("#")
        
        # Add the first chunk as representative
        if chunks:
            first_chunk = chunks[0]
            summary_lines.append(first_chunk)
        
        if len(chunks) > 1:
            summary_lines.append("#")
            summary_lines.append(f"# ... {len(chunks) - 1} additional chunks omitted for brevity")
            summary_lines.append("# Use individual file commits or review the complete diff separately")
        
        result = '\n'.join(summary_lines)
        logger.info(f"Created diff summary: {len(result)} characters (reduced from {len(original_diff)})")
        
        return result
    
    def _extract_files_from_diff(self, diff: str) -> List[str]:
        """
        Extract file paths from a git diff.
        
        Args:
            diff: Git diff chunk
            
        Returns:
            List of file paths
        """
        files = []
        lines = diff.split('\n')
        
        for line in lines:
            if line.startswith('diff --git '):
                # Extract file path from diff --git a/path b/path
                parts = line.split(' ')
                if len(parts) >= 4:
                    # Remove a/ and b/ prefixes
                    file_path = parts[3][2:]  # Remove b/ prefix
                    files.append(file_path)
        
        return files

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

        # Filter out files that should be ignored
        filtered_files = self._filter_stageable_files(files)

        if not filtered_files:
            logger.debug("No stageable files after filtering")
            return True

        try:
            for file in filtered_files:
                # Check if file exists or was deleted
                file_path = Path(file)
                if not file_path.exists():
                    logger.debug(f"File does not exist: {file} - likely deleted, using git rm")
                    # Use git rm for deleted files
                    result = subprocess.run(
                        ['git', 'rm', file],
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=10
                    )
                else:
                    # Use git add for existing files
                    result = subprocess.run(
                        ['git', 'add', file],
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=10
                    )

            logger.info(f"Successfully staged {len(filtered_files)} files")
            return True

        except subprocess.CalledProcessError as e:
            raise GitOperationError(f"Failed to stage files: {e}")
        except subprocess.TimeoutExpired:
            raise GitOperationError("Git add/rm command timed out")

    def _filter_stageable_files(self, files: List[str]) -> List[str]:
        """
        Filter out files that should not be staged (e.g., ignored files).

        Args:
            files: List of file paths to filter

        Returns:
            Filtered list of stageable files
        """
        stageable_files = []

        for file in files:
            try:
                # Check if file is ignored by git
                result = subprocess.run(
                    ['git', 'check-ignore', file],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                # If git check-ignore returns 0, the file is ignored
                if result.returncode == 0:
                    logger.debug(f"Skipping ignored file: {file}")
                    continue

            except subprocess.TimeoutExpired:
                logger.warning(f"Timeout checking ignore status for: {file}")
                continue
            except subprocess.CalledProcessError:
                # If git check-ignore fails (return code != 0), file is not ignored
                pass

            # Additional filter for known log patterns
            if self._is_log_file(file):
                logger.debug(f"Skipping log file: {file}")
                continue

            stageable_files.append(file)

        return stageable_files

    def _is_log_file(self, file_path: str) -> bool:
        """
        Check if a file is a log file that should not be staged.

        Args:
            file_path: Path to check

        Returns:
            True if file is a log file, False otherwise
        """
        file_path = file_path.lower()
        log_patterns = [
            '.commitlogs/',
            '.log',
            'logs/',
            '/logs/',
            'commit_',
        ]

        return any(pattern in file_path for pattern in log_patterns)

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

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        return {
            'cache_stats': self._cache_stats.get_stats(),
            'cache_size': len(self._cache),
            'command_stats': dict(self._command_stats),
            'most_accessed_entries': self._get_most_accessed_entries()
        }
    
    def _get_most_accessed_entries(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get most accessed cache entries."""
        entries = [
            {
                'key': key,
                'access_count': entry.access_count,
                'age': time.time() - entry.timestamp,
                'is_expired': entry.is_expired()
            }
            for key, entry in self._cache.items()
        ]
        return sorted(entries, key=lambda x: x['access_count'], reverse=True)[:limit]
    
    def _prewarm_cache_async(self) -> None:
        """Asynchronously pre-warm cache with common operations."""
        if self._prewarmed:
            return
        
        import threading
        
        def prewarm_worker():
            try:
                logger.debug("Starting cache pre-warming...")
                
                # Pre-warm current branch
                self.get_current_branch()
                
                # Pre-warm changed files
                self.get_changed_files()
                
                # Pre-warm repository validation
                self.validate_git_repository()
                
                self._prewarmed = True
                logger.debug("Cache pre-warming completed")
                
            except Exception as e:
                logger.debug(f"Cache pre-warming failed: {e}")
        
        # Start pre-warming in background thread
        thread = threading.Thread(target=prewarm_worker, daemon=True)
        thread.start()
    
    def disable_cache_for_testing(self) -> None:
        """Disable cache for testing purposes."""
        self._cache.clear()
        self._cache_enabled = False
        logger.debug("Cache disabled for testing")
    
    def enable_cache_for_testing(self) -> None:
        """Enable cache for testing purposes."""
        self._cache_enabled = True
        logger.debug("Cache enabled for testing")
    
    def prewarm_cache(self) -> None:
        """Synchronously pre-warm cache with common operations."""
        if self._prewarmed:
            return
        
        logger.debug("Starting synchronous cache pre-warming...")
        
        # Pre-warm current branch
        self.get_current_branch()
        
        # Pre-warm changed files
        self.get_changed_files()
        
        self._prewarmed = True
        logger.debug("Cache pre-warming completed")
    
    def cleanup_expired_entries(self) -> int:
        """Clean up expired cache entries.
        
        Returns:
            Number of expired entries removed
        """
        expired_keys = []
        current_time = time.time()
        
        for key, entry in self._cache.items():
            if entry.is_expired():
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
            self._cache_stats.record_eviction()
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)
    
    def optimize_cache_size(self, max_size: int = 50) -> int:
        """Optimize cache size by removing least recently used entries.
        
        Args:
            max_size: Maximum number of entries to keep
            
        Returns:
            Number of entries removed
        """
        if len(self._cache) <= max_size:
            return 0
        
        # Sort by access count and timestamp
        entries = [
            (key, entry.access_count, entry.timestamp)
            for key, entry in self._cache.items()
        ]
        
        # Sort by access count (ascending) then by timestamp (ascending)
        entries.sort(key=lambda x: (x[1], x[2]))
        
        # Remove least accessed/oldest entries
        keys_to_remove = [entry[0] for entry in entries[:len(self._cache) - max_size]]
        
        for key in keys_to_remove:
            del self._cache[key]
            self._cache_stats.record_eviction()
        
        logger.debug(f"Optimized cache size: removed {len(keys_to_remove)} entries")
        return len(keys_to_remove)
    
    def clear_cache(self) -> None:
        """Clear all cached data and reset statistics."""
        self._cache.clear()
        self._cache_stats = CacheStats()
        self._command_stats.clear()
        self._prewarmed = False
        logger.info("Cache cleared and statistics reset")
    
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
                'cache_stats': self.get_cache_stats()
            }

        except subprocess.CalledProcessError as e:
            raise GitOperationError(f"Failed to get repository status: {e}")
        except subprocess.TimeoutExpired:
            raise GitOperationError("Git status command timed out")
