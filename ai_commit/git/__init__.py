"""
Git operations module for AI Commit.

This module handles all git-related operations including diff analysis,
file staging, committing, and repository validation.
"""

import subprocess
import logging
import time
import os
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
        Get git diff of staged and unstaged changes with optimized memory usage.

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
            # Use streaming approach for better memory efficiency
            staged_diff = self._get_streaming_git_diff(['--stat', '--cached', '--unified=3'])
            unstaged_diff = self._get_streaming_git_diff(['--stat', '--unified=3'])
            
            # Combine results
            total_diff = staged_diff + unstaged_diff

            if not total_diff.strip():
                logger.warning("No changes detected in git diff")
                return ""

            # Handle large diff splitting with memory optimization
            if split_large_files and len(total_diff) > max_chunk_size:
                logger.info(f"Large diff detected ({len(total_diff)} characters), splitting into chunks")
                return self._split_and_process_diff_optimized(total_diff, max_chunk_size)

            # Validate diff content
            validated_diff = self.validator.validate_git_diff(total_diff)

            logger.info(f"Retrieved git diff: {len(validated_diff)} characters")
            return validated_diff

        except subprocess.CalledProcessError as e:
            raise GitOperationError(f"Failed to get git diff: {e}")
        except subprocess.TimeoutExpired:
            raise GitOperationError("Git diff command timed out")

    def _get_streaming_git_diff(self, args: List[str]) -> str:
        """
        Get git diff with streaming approach for better memory efficiency.
        
        Args:
            args: Git diff arguments
            
        Returns:
            Git diff content
        """
        try:
            result = subprocess.run(
                ['git', 'diff'] + args,
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )
            return result.stdout
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
        # Use optimized version by default
        return self._split_and_process_diff_optimized(diff, max_chunk_size)

    def _split_and_process_diff_optimized(self, diff: str, max_chunk_size: int) -> str:
        """
        Optimized version of diff splitting with better memory efficiency.
        
        Args:
            diff: The complete git diff
            max_chunk_size: Maximum size for each chunk
            
        Returns:
            Processed diff summary
        """
        # Use generator-based approach to reduce memory usage
        file_diffs = list(self._generate_file_diffs_streaming(diff))
        
        # Process files in chunks with optimized memory usage
        chunks = []
        current_chunk = []
        current_size = 0
        
        for file_diff in file_diffs:
            file_size = len(file_diff)
            
            # If single file is too large, use smart truncation
            if file_size > max_chunk_size:
                # Finalize current chunk if exists
                if current_chunk:
                    chunks.append("\n".join(current_chunk))
                    current_chunk = []
                    current_size = 0
                
                # Use optimized truncation
                truncated_diff = self._truncate_large_file_diff_optimized(file_diff, max_chunk_size)
                chunks.append(truncated_diff)
                continue
            
            # Check if adding this file would exceed chunk size
            if current_size + file_size > max_chunk_size and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_size = 0
            
            current_chunk.append(file_diff)
            current_size += file_size
        
        # Add the last chunk if it has content
        if current_chunk:
            chunks.append("\n".join(current_chunk))
        
        logger.info(f"Split diff into {len(chunks)} chunks (optimized)")
        
        # Create optimized summary
        return self._create_diff_summary_optimized(chunks, diff)

    def _generate_file_diffs_streaming(self, diff: str):
        """
        Generate file diffs using streaming approach for better memory efficiency.
        
        Args:
            diff: Complete git diff
            
        Yields:
            Individual file diffs
        """
        # Use memory-efficient string operations
        start_idx = 0
        diff_len = len(diff)
        
        while start_idx < diff_len:
            # Find next diff header
            diff_header_pos = diff.find('diff --git ', start_idx)
            
            if diff_header_pos == -1:
                # No more diffs found
                if start_idx < diff_len:
                    # Yield remaining content
                    yield diff[start_idx:]
                break
            
            if diff_header_pos > start_idx:
                # Yield the diff before this header
                yield diff[start_idx:diff_header_pos]
            
            # Find the end of this file diff
            next_diff_pos = diff.find('\ndiff --git ', diff_header_pos + 1)
            if next_diff_pos == -1:
                # This is the last diff
                yield diff[diff_header_pos:]
                break
            
            # Yield this file diff
            yield diff[diff_header_pos:next_diff_pos]
            start_idx = next_diff_pos + 1

    def _truncate_large_file_diff_optimized(self, file_diff: str, max_size: int) -> str:
        """
        Optimized version of large file diff truncation.
        
        Args:
            file_diff: Single file diff
            max_size: Maximum size for the truncated diff
            
        Returns:
            Truncated diff
        """
        if len(file_diff) <= max_size:
            return file_diff
        
        # Use more efficient parsing
        lines = file_diff.split('\n')
        header_lines = []
        content_lines = []
        in_header = True
        
        for line in lines:
            if in_header and (line.startswith('diff --git ') or line.startswith('index ')):
                header_lines.append(line)
            else:
                in_header = False
                content_lines.append(line)
        
        if not content_lines:
            return '\n'.join(header_lines)
        
        # Calculate optimal truncation
        header_size = len('\n'.join(header_lines)) + 1
        available_size = max_size - header_size - 60  # Reserve space for truncation message
        
        if available_size <= 0:
            return f"{header_lines[0]}\n# Large file diff truncated ({len(file_diff)} characters)"
        
        # Use binary search-like approach to find optimal number of lines
        total_lines = len(content_lines)
        target_lines = max(1, min(available_size // 80, total_lines // 4))  # Approximate 80 chars per line
        
        # Take from beginning and end for better context
        if target_lines * 2 >= total_lines:
            # No need to truncate
            return file_diff
        
        beginning = content_lines[:target_lines]
        end = content_lines[-target_lines:]
        
        # Build truncated diff efficiently
        result = []
        result.extend(header_lines)
        result.extend(beginning)
        result.append(f"# ... {total_lines - (target_lines * 2)} lines omitted ...")
        result.extend(end)
        
        return '\n'.join(result)

    def _create_diff_summary_optimized(self, chunks: List[str], original_diff: str) -> str:
        """
        Create an optimized summary from processed diff chunks.
        
        Args:
            chunks: List of diff chunks
            original_diff: Original complete diff
            
        Returns:
            Optimized summary diff
        """
        # Pre-calculate file information
        all_files = []
        total_original_size = len(original_diff)
        
        # Extract file info more efficiently
        for chunk in chunks:
            chunk_files = self._extract_files_from_diff_optimized(chunk)
            all_files.extend(chunk_files)
        
        # Build summary efficiently
        summary_parts = [
            f"# Large commit diff summary",
            f"# Original diff size: {total_original_size:,} characters",
            f"# Split into {len(chunks)} manageable chunks",
            f"# Files changed: {len(all_files)}",
            f"# Processing time: {self._get_processing_time():.2f}s",
            "#"
        ]
        
        # Add file list (limited to prevent oversized summary)
        max_files_to_show = 20
        if len(all_files) > max_files_to_show:
            summary_parts.extend([f"#   - {file}" for file in all_files[:max_files_to_show]])
            summary_parts.append(f"#   ... and {len(all_files) - max_files_to_show} more files")
        else:
            summary_parts.extend([f"#   - {file}" for file in all_files])
        
        summary_parts.extend([
            "#",
            "# Detailed changes (first chunk only):",
            "#"
        ])
        
        # Add first chunk
        if chunks:
            summary_parts.append(chunks[0])
        
        if len(chunks) > 1:
            summary_parts.extend([
                "#",
                f"# ... {len(chunks) - 1} additional chunks omitted for brevity",
                "# Use individual file commits or review the complete diff separately"
            ])
        
        result = '\n'.join(summary_parts)
        logger.info(f"Created optimized diff summary: {len(result)} characters (reduced from {total_original_size:,})")
        
        return result

    def _extract_files_from_diff_optimized(self, diff: str) -> List[str]:
        """
        Extract file paths from a git diff using optimized parsing.
        
        Args:
            diff: Git diff chunk
            
        Returns:
            List of file paths
        """
        files = []
        # Use finditer for better performance
        import re
        
        # More efficient regex pattern
        pattern = r'diff --git a/(.+?) b/'
        matches = re.finditer(pattern, diff)
        
        for match in matches:
            files.append(match.group(1))
        
        return files

    def _get_processing_time(self) -> float:
        """
        Get processing time for performance monitoring.
        
        Returns:
            Processing time in seconds
        """
        # Simple implementation - can be enhanced with actual timing
        return 0.0

    def get_git_diff_incremental(self, split_large_files: bool = True, max_chunk_size: int = 500000) -> str:
        """
        Get git diff using incremental processing for very large repositories.
        
        Args:
            split_large_files: Whether to split large diffs into chunks
            max_chunk_size: Maximum size of each diff chunk in characters
            
        Returns:
            Git diff content
        """
        try:
            # Get file list first
            changed_files = self._get_changed_files_list()
            
            if not changed_files:
                logger.warning("No changed files found")
                return ""
            
            # Process files incrementally
            total_diff = self._process_files_incremental(changed_files, max_chunk_size)
            
            if not total_diff.strip():
                logger.warning("No changes detected in incremental diff")
                return ""
            
            # Handle large diff splitting if needed
            if split_large_files and len(total_diff) > max_chunk_size:
                logger.info(f"Large incremental diff detected ({len(total_diff)} characters), splitting into chunks")
                return self._split_and_process_diff_optimized(total_diff, max_chunk_size)
            
            # Validate diff content
            validated_diff = self.validator.validate_git_diff(total_diff)
            
            logger.info(f"Retrieved incremental git diff: {len(validated_diff)} characters")
            return validated_diff
            
        except Exception as e:
            logger.error(f"Failed to get incremental git diff: {e}")
            # Fallback to regular method
            return self.get_git_diff(split_large_files, max_chunk_size)

    def _get_changed_files_list(self) -> List[str]:
        """
        Get list of changed files efficiently.
        
        Returns:
            List of changed file paths
        """
        try:
            # Get both staged and unstaged files
            staged_files = self._get_staged_files()
            unstaged_files = self._get_unstaged_files()
            
            # Combine and deduplicate
            all_files = list(set(staged_files + unstaged_files))
            
            logger.debug(f"Found {len(all_files)} changed files")
            return all_files
            
        except Exception as e:
            logger.error(f"Failed to get changed files list: {e}")
            return []

    def _get_staged_files(self) -> List[str]:
        """
        Get list of staged files.
        
        Returns:
            List of staged file paths
        """
        try:
            result = subprocess.run(
                ['git', 'diff', '--cached', '--name-only'],
                capture_output=True,
                text=True,
                check=True,
                timeout=10
            )
            
            files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            return files
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get staged files: {e}")
            return []
        except subprocess.TimeoutExpired:
            logger.error("Git command timed out while getting staged files")
            return []

    def _get_unstaged_files(self) -> List[str]:
        """
        Get list of unstaged files.
        
        Returns:
            List of unstaged file paths
        """
        try:
            result = subprocess.run(
                ['git', 'diff', '--name-only'],
                capture_output=True,
                text=True,
                check=True,
                timeout=10
            )
            
            files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            return files
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get unstaged files: {e}")
            return []
        except subprocess.TimeoutExpired:
            logger.error("Git command timed out while getting unstaged files")
            return []

    def _process_files_incremental(self, files: List[str], max_chunk_size: int) -> str:
        """
        Process files incrementally to handle very large repositories efficiently.
        
        Args:
            files: List of changed files
            max_chunk_size: Maximum size for processing chunks
            
        Returns:
            Combined diff content
        """
        # Process files in batches to manage memory
        batch_size = 50  # Process 50 files at a time
        all_diffs = []
        
        for i in range(0, len(files), batch_size):
            batch_files = files[i:i + batch_size]
            batch_diff = self._process_file_batch(batch_files)
            
            if batch_diff:
                all_diffs.append(batch_diff)
                
                # If we're accumulating too much, process incrementally
                current_size = sum(len(diff) for diff in all_diffs)
                if current_size > max_chunk_size:
                    # Combine what we have and return early
                    combined_diff = '\n'.join(all_diffs)
                    logger.info(f"Early return from incremental processing: {len(combined_diff)} characters")
                    return combined_diff
        
        # Combine all diffs
        combined_diff = '\n'.join(all_diffs)
        logger.info(f"Processed {len(files)} files incrementally: {len(combined_diff)} characters")
        
        return combined_diff

    def _process_file_batch(self, files: List[str]) -> str:
        """
        Process a batch of files efficiently.
        
        Args:
            files: List of files to process
            
        Returns:
            Diff content for the batch
        """
        if not files:
            return ""
        
        try:
            # Use git diff with specific files for better performance
            cmd = ['git', 'diff', '--unified=3'] + files
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )
            
            # Also get staged changes for these files
            cmd_staged = ['git', 'diff', '--cached', '--unified=3'] + files
            result_staged = subprocess.run(
                cmd_staged,
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )
            
            # Combine results
            combined_diff = result_staged.stdout + result.stdout
            
            return combined_diff
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to process file batch: {e}")
            return ""
        except subprocess.TimeoutExpired:
            logger.error("Git command timed out while processing file batch")
            return ""

    def get_git_diff_smart(self, max_size: int = 10000000) -> str:
        """
        Smart git diff processing that chooses the best method based on repository size.
        
        Args:
            max_size: Maximum size threshold for method selection
            
        Returns:
            Git diff content
        """
        try:
            # Estimate repository size
            repo_size = self._estimate_repository_size()
            
            # Choose processing method based on size
            if repo_size > max_size:
                logger.info(f"Large repository detected ({repo_size:,} bytes), using incremental processing")
                return self.get_git_diff_incremental(split_large_files=True, max_chunk_size=500000)
            else:
                logger.info(f"Medium repository detected ({repo_size:,} bytes), using optimized processing")
                return self.get_git_diff(split_large_files=True, max_chunk_size=500000)
                
        except Exception as e:
            logger.error(f"Failed to estimate repository size, falling back to standard method: {e}")
            return self.get_git_diff(split_large_files=True, max_chunk_size=500000)

    def _estimate_repository_size(self) -> int:
        """
        Estimate repository size to choose appropriate processing method.
        
        Returns:
            Estimated repository size in bytes
        """
        try:
            # Get repository directory size
            repo_path = self._repo_root or '.'
            total_size = 0
            
            for root, dirs, files in os.walk(repo_path):
                # Skip .git directory and other non-content directories
                dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
                
                for file in files:
                    # Skip certain file types
                    if not any(file.endswith(ext) for ext in ['.pyc', '.log', '.tmp']):
                        try:
                            file_path = os.path.join(root, file)
                            total_size += os.path.getsize(file_path)
                        except (OSError, IOError):
                            continue
            
            logger.debug(f"Estimated repository size: {total_size:,} bytes")
            return total_size
            
        except Exception as e:
            logger.error(f"Failed to estimate repository size: {e}")
            return 0

    def get_git_diff_with_file_type_detection(self, split_large_files: bool = True, max_chunk_size: int = 500000) -> str:
        """
        Get git diff with intelligent file type detection and processing.
        
        Args:
            split_large_files: Whether to split large diffs into chunks
            max_chunk_size: Maximum size of each diff chunk in characters
            
        Returns:
            Git diff content with file type optimizations
        """
        try:
            # Get changed files with type information
            typed_files = self._get_typed_changed_files()
            
            if not typed_files:
                logger.warning("No changed files found")
                return ""
            
            # Process files by type with type-specific strategies
            processed_diff = self._process_files_by_type(typed_files, max_chunk_size)
            
            if not processed_diff.strip():
                logger.warning("No changes detected in typed diff processing")
                return ""
            
            # Handle large diff splitting if needed
            if split_large_files and len(processed_diff) > max_chunk_size:
                logger.info(f"Large typed diff detected ({len(processed_diff)} characters), splitting into chunks")
                return self._split_and_process_diff_optimized(processed_diff, max_chunk_size)
            
            # Validate diff content
            validated_diff = self.validator.validate_git_diff(processed_diff)
            
            logger.info(f"Retrieved typed git diff: {len(validated_diff)} characters")
            return validated_diff
            
        except Exception as e:
            logger.error(f"Failed to get typed git diff: {e}")
            # Fallback to smart method
            return self.get_git_diff_smart()

    def _get_typed_changed_files(self) -> List[Dict[str, Any]]:
        """
        Get changed files with type classification.
        
        Returns:
            List of dictionaries with file information
        """
        try:
            files = self._get_changed_files_list()
            typed_files = []
            
            for file_path in files:
                file_info = {
                    'path': file_path,
                    'type': self._classify_file_type(file_path),
                    'size': self._get_file_size(file_path),
                    'is_binary': self._is_binary_file(file_path),
                    'is_text': self._is_text_file(file_path),
                    'priority': self._get_file_priority(file_path)
                }
                typed_files.append(file_info)
            
            # Sort by priority (higher priority first)
            typed_files.sort(key=lambda x: x['priority'], reverse=True)
            
            logger.debug(f"Classified {len(typed_files)} files by type")
            return typed_files
            
        except Exception as e:
            logger.error(f"Failed to get typed changed files: {e}")
            return []

    def _classify_file_type(self, file_path: str) -> str:
        """
        Classify file type for intelligent processing.
        
        Args:
            file_path: Path to the file
            
        Returns:
            File type classification
        """
        import mimetypes
        
        # Get file extension
        _, ext = os.path.splitext(file_path.lower())
        
        # Text-based files (high priority for detailed diff)
        text_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h', '.hpp',
            '.go', '.rs', '.swift', '.kt', '.cs', '.php', '.rb', '.sh', '.sql',
            '.html', '.css', '.scss', '.less', '.vue', '.angular', '.xml', '.json',
            '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf', '.md', '.rst', '.txt'
        }
        
        # Configuration files (medium priority)
        config_extensions = {
            '.env', '.config', '.properties', '.settings', '.prefs', '.lock',
            '.gitignore', '.dockerignore', '.npmignore', '.babelrc', '.eslintrc'
        }
        
        # Binary files (low priority, summary only)
        binary_extensions = {
            '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.ico', '.webp',
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar', '.deb', '.rpm',
            '.exe', '.dll', '.so', '.dylib', '.a', '.lib', '.o', '.obj',
            '.mp3', '.mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv', 'webm'
        }
        
        # Check file type
        if ext in text_extensions:
            return 'text'
        elif ext in config_extensions:
            return 'config'
        elif ext in binary_extensions:
            return 'binary'
        else:
            # Use mime type as fallback
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type:
                if mime_type.startswith('text/'):
                    return 'text'
                elif mime_type.startswith('image/'):
                    return 'binary'
                elif mime_type.startswith('application/'):
                    if 'json' in mime_type or 'xml' in mime_type:
                        return 'config'
                    else:
                        return 'binary'
            
            return 'unknown'

    def _get_file_size(self, file_path: str) -> int:
        """
        Get file size safely.
        
        Args:
            file_path: Path to the file
            
        Returns:
            File size in bytes
        """
        try:
            return os.path.getsize(file_path)
        except (OSError, IOError):
            return 0

    def _is_binary_file(self, file_path: str) -> bool:
        """
        Check if file is binary.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if file is binary
        """
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                return b'\x00' in chunk
        except (OSError, IOError):
            return False

    def _is_text_file(self, file_path: str) -> bool:
        """
        Check if file is text.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if file is text
        """
        return not self._is_binary_file(file_path)

    def _get_file_priority(self, file_path: str) -> int:
        """
        Get processing priority for file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Priority score (higher = more important)
        """
        file_type = self._classify_file_type(file_path)
        
        # Priority mapping
        priority_map = {
            'text': 100,      # Source code, documentation
            'config': 80,     # Configuration files
            'unknown': 50,    # Unknown files
            'binary': 20      # Binary files
        }
        
        base_priority = priority_map.get(file_type, 50)
        
        # Adjust based on file location
        if any(keyword in file_path.lower() for keyword in ['readme', 'license', 'changelog']):
            base_priority += 20
        elif any(keyword in file_path.lower() for keyword in ['test', 'spec']):
            base_priority += 10
        
        return base_priority

    def _process_files_by_type(self, typed_files: List[Dict[str, Any]], max_chunk_size: int) -> str:
        """
        Process files grouped by type with type-specific strategies.
        
        Args:
            typed_files: List of typed file information
            max_chunk_size: Maximum size for processing chunks
            
        Returns:
            Combined diff content
        """
        # Group files by type
        files_by_type = {}
        for file_info in typed_files:
            file_type = file_info['type']
            if file_type not in files_by_type:
                files_by_type[file_type] = []
            files_by_type[file_type].append(file_info)
        
        all_diffs = []
        
        # Process each type with appropriate strategy
        for file_type, files in files_by_type.items():
            logger.debug(f"Processing {len(files)} {file_type} files")
            
            if file_type == 'binary':
                # Binary files: show only metadata
                type_diff = self._process_binary_files(files)
            elif file_type == 'config':
                # Config files: show full diff but with limits
                type_diff = self._process_config_files(files, max_chunk_size)
            else:
                # Text files: show full diff
                type_diff = self._process_text_files(files, max_chunk_size)
            
            if type_diff:
                all_diffs.append(type_diff)
        
        # Combine all diffs
        combined_diff = '\n'.join(all_diffs)
        logger.info(f"Processed files by type: {len(combined_diff)} characters")
        
        return combined_diff

    def _process_binary_files(self, files: List[Dict[str, Any]]) -> str:
        """
        Process binary files with metadata-only approach.
        
        Args:
            files: List of binary file information
            
        Returns:
            Summary of binary file changes
        """
        if not files:
            return ""
        
        summary_lines = [
            "# Binary file changes summary",
            f"# Total binary files changed: {len(files)}"
        ]
        
        for file_info in files:
            file_path = file_info['path']
            file_size = file_info['size']
            summary_lines.append(f"#   - {file_path} ({file_size:,} bytes)")
        
        summary_lines.append("# Binary file content not shown in diff")
        
        return '\n'.join(summary_lines)

    def _process_config_files(self, files: List[Dict[str, Any]], max_chunk_size: int) -> str:
        """
        Process configuration files with size limits.
        
        Args:
            files: List of config file information
            max_chunk_size: Maximum size for processing
            
        Returns:
            Config file diffs
        """
        if not files:
            return ""
        
        # Get file paths
        file_paths = [f['path'] for f in files]
        
        # Process in smaller batches for config files
        batch_size = 10  # Smaller batches for config files
        all_diffs = []
        
        for i in range(0, len(file_paths), batch_size):
            batch_files = file_paths[i:i + batch_size]
            batch_diff = self._process_file_batch(batch_files)
            
            if batch_diff:
                # Limit config file diff size
                if len(batch_diff) > max_chunk_size // 2:
                    batch_diff = self._truncate_config_diff(batch_diff, max_chunk_size // 2)
                
                all_diffs.append(batch_diff)
        
        return '\n'.join(all_diffs)

    def _process_text_files(self, files: List[Dict[str, Any]], max_chunk_size: int) -> str:
        """
        Process text files with full diff capability.
        
        Args:
            files: List of text file information
            max_chunk_size: Maximum size for processing
            
        Returns:
            Text file diffs
        """
        if not files:
            return ""
        
        # Get file paths
        file_paths = [f['path'] for f in files]
        
        # Process in batches
        batch_size = 30  # Larger batches for text files
        all_diffs = []
        
        for i in range(0, len(file_paths), batch_size):
            batch_files = file_paths[i:i + batch_size]
            batch_diff = self._process_file_batch(batch_files)
            
            if batch_diff:
                all_diffs.append(batch_diff)
        
        return '\n'.join(all_diffs)

    def _truncate_config_diff(self, diff: str, max_size: int) -> str:
        """
        Truncate configuration file diff intelligently.
        
        Args:
            diff: Config file diff
            max_size: Maximum size
            
        Returns:
            Truncated diff
        """
        if len(diff) <= max_size:
            return diff
        
        lines = diff.split('\n')
        
        # Keep header and some context
        header_lines = []
        content_lines = []
        
        for line in lines:
            if line.startswith('diff --git ') or line.startswith('index '):
                header_lines.append(line)
            else:
                content_lines.append(line)
        
        if not content_lines:
            return '\n'.join(header_lines)
        
        # Calculate how many lines to keep
        header_size = len('\n'.join(header_lines)) + 1
        available_size = max_size - header_size - 60
        
        if available_size <= 0:
            return f"{header_lines[0] if header_lines else '# Config diff truncated'}"
        
        # Keep beginning and end of config
        lines_to_keep = max(5, min(available_size // 100, len(content_lines) // 3))
        
        beginning = content_lines[:lines_to_keep]
        end = content_lines[-lines_to_keep:] if len(content_lines) > lines_to_keep * 2 else []
        
        result = []
        result.extend(header_lines)
        result.extend(beginning)
        
        if end:
            result.append(f"# ... {len(content_lines) - (lines_to_keep * 2)} config lines omitted ...")
            result.extend(end)
        
        return '\n'.join(result)

    def get_git_diff_parallel(self, split_large_files: bool = True, max_chunk_size: int = 500000, max_workers: int = None) -> str:
        """
        Get git diff using parallel processing for large repositories.
        
        Args:
            split_large_files: Whether to split large diffs into chunks
            max_chunk_size: Maximum size of each diff chunk in characters
            max_workers: Maximum number of worker threads
            
        Returns:
            Git diff content
        """
        try:
            import concurrent.futures
            import threading
            
            # Determine optimal number of workers
            if max_workers is None:
                max_workers = min(4, (os.cpu_count() or 1) + 1)
            
            # Get changed files with type information
            typed_files = self._get_typed_changed_files()
            
            if not typed_files:
                logger.warning("No changed files found")
                return ""
            
            # Process files in parallel
            logger.info(f"Processing {len(typed_files)} files with {max_workers} workers")
            
            # Split files into batches for parallel processing
            batch_size = max(1, len(typed_files) // max_workers)
            file_batches = [typed_files[i:i + batch_size] for i in range(0, len(typed_files), batch_size)]
            
            # Process batches in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks
                future_to_batch = {
                    executor.submit(self._process_file_batch_parallel, batch, max_chunk_size): batch 
                    for batch in file_batches
                }
                
                # Collect results
                all_diffs = []
                for future in concurrent.futures.as_completed(future_to_batch):
                    batch = future_to_batch[future]
                    try:
                        batch_diff = future.result()
                        if batch_diff:
                            all_diffs.append(batch_diff)
                    except Exception as e:
                        logger.error(f"Error processing batch {batch}: {e}")
                        # Fallback to sequential processing for this batch
                        try:
                            fallback_diff = self._process_file_batch_sequential(batch, max_chunk_size)
                            if fallback_diff:
                                all_diffs.append(fallback_diff)
                        except Exception as fallback_error:
                            logger.error(f"Fallback processing also failed for batch {batch}: {fallback_error}")
            
            # Combine all diffs
            combined_diff = '\n'.join(all_diffs)
            
            if not combined_diff.strip():
                logger.warning("No changes detected in parallel diff processing")
                return ""
            
            # Handle large diff splitting if needed
            if split_large_files and len(combined_diff) > max_chunk_size:
                logger.info(f"Large parallel diff detected ({len(combined_diff)} characters), splitting into chunks")
                return self._split_and_process_diff_optimized(combined_diff, max_chunk_size)
            
            # Validate diff content
            validated_diff = self.validator.validate_git_diff(combined_diff)
            
            logger.info(f"Retrieved parallel git diff: {len(validated_diff)} characters")
            return validated_diff
            
        except Exception as e:
            logger.error(f"Failed to get parallel git diff: {e}")
            # Fallback to typed method
            return self.get_git_diff_with_file_type_detection(split_large_files, max_chunk_size)

    def _process_file_batch_parallel(self, file_batch: List[Dict[str, Any]], max_chunk_size: int) -> str:
        """
        Process a batch of files in parallel using sub-batching.
        
        Args:
            file_batch: List of file information dictionaries
            max_chunk_size: Maximum size for processing chunks
            
        Returns:
            Combined diff content for the batch
        """
        try:
            # Further split batch into smaller sub-batches for parallel processing
            sub_batch_size = max(1, len(file_batch) // 2)
            sub_batches = [file_batch[i:i + sub_batch_size] for i in range(0, len(file_batch), sub_batch_size)]
            
            if len(sub_batches) <= 1:
                # No need for parallel processing of small batches
                return self._process_file_batch_sequential(file_batch, max_chunk_size)
            
            # Process sub-batches in parallel
            import concurrent.futures
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(2, len(sub_batches))) as executor:
                futures = [executor.submit(self._process_file_batch_sequential, sub_batch, max_chunk_size) for sub_batch in sub_batches]
                
                all_diffs = []
                for future in concurrent.futures.as_completed(futures):
                    try:
                        sub_batch_diff = future.result()
                        if sub_batch_diff:
                            all_diffs.append(sub_batch_diff)
                    except Exception as e:
                        logger.error(f"Error processing sub-batch: {e}")
            
            return '\n'.join(all_diffs)
            
        except Exception as e:
            logger.error(f"Failed to process file batch in parallel: {e}")
            # Fallback to sequential processing
            return self._process_file_batch_sequential(file_batch, max_chunk_size)

    def _process_file_batch_sequential(self, file_batch: List[Dict[str, Any]], max_chunk_size: int) -> str:
        """
        Process a batch of files sequentially.
        
        Args:
            file_batch: List of file information dictionaries
            max_chunk_size: Maximum size for processing chunks
            
        Returns:
            Combined diff content for the batch
        """
        if not file_batch:
            return ""
        
        # Group files by type for efficient processing
        files_by_type = {}
        for file_info in file_batch:
            file_type = file_info['type']
            if file_type not in files_by_type:
                files_by_type[file_type] = []
            files_by_type[file_type].append(file_info)
        
        all_diffs = []
        
        # Process each type
        for file_type, files in files_by_type.items():
            if file_type == 'binary':
                type_diff = self._process_binary_files(files)
            elif file_type == 'config':
                type_diff = self._process_config_files(files, max_chunk_size)
            else:
                type_diff = self._process_text_files(files, max_chunk_size)
            
            if type_diff:
                all_diffs.append(type_diff)
        
        return '\n'.join(all_diffs)

    def get_git_diff_adaptive(self, max_size_threshold: int = 5000000) -> str:
        """
        Adaptive git diff processing that automatically chooses the best method.
        
        This method analyzes the repository and selects the most appropriate
        processing strategy based on repository size, number of files, and system resources.
        
        Args:
            max_size_threshold: Threshold for switching to advanced methods
            
        Returns:
            Git diff content
        """
        try:
            # Analyze repository characteristics
            repo_stats = self._analyze_repository_characteristics()
            
            # Choose processing strategy based on analysis
            if repo_stats['is_very_large']:
                logger.info("Using parallel processing for very large repository")
                return self.get_git_diff_parallel(
                    split_large_files=True, 
                    max_chunk_size=500000,
                    max_workers=min(4, repo_stats['optimal_workers'])
                )
            elif repo_stats['is_large']:
                logger.info("Using incremental processing for large repository")
                return self.get_git_diff_incremental(
                    split_large_files=True, 
                    max_chunk_size=500000
                )
            elif repo_stats['has_many_files']:
                logger.info("Using file type detection for repository with many files")
                return self.get_git_diff_with_file_type_detection(
                    split_large_files=True, 
                    max_chunk_size=500000
                )
            else:
                logger.info("Using standard processing for small repository")
                return self.get_git_diff(
                    split_large_files=True, 
                    max_chunk_size=500000
                )
                
        except Exception as e:
            logger.error(f"Failed to analyze repository, falling back to standard method: {e}")
            return self.get_git_diff(split_large_files=True, max_chunk_size=500000)

    def _analyze_repository_characteristics(self) -> Dict[str, Any]:
        """
        Analyze repository characteristics to determine optimal processing strategy.
        
        Returns:
            Dictionary with repository analysis results
        """
        try:
            # Get basic repository stats
            changed_files = self._get_changed_files_list()
            repo_size = self._estimate_repository_size()
            
            # Count files by type
            file_type_counts = {'text': 0, 'config': 0, 'binary': 0, 'unknown': 0}
            total_file_size = 0
            
            for file_path in changed_files:
                file_type = self._classify_file_type(file_path)
                file_size = self._get_file_size(file_path)
                
                file_type_counts[file_type] += 1
                total_file_size += file_size
            
            # Determine characteristics
            num_files = len(changed_files)
            avg_file_size = total_file_size / num_files if num_files > 0 else 0
            
            # Classification thresholds
            is_very_large = (
                repo_size > 50000000 or  # 50MB+
                num_files > 200 or        # 200+ files
                total_file_size > 20000000  # 20MB+ of changes
            )
            
            is_large = (
                repo_size > 10000000 or   # 10MB+
                num_files > 50 or         # 50+ files
                total_file_size > 5000000   # 5MB+ of changes
            )
            
            has_many_files = num_files > 20
            
            # Calculate optimal workers
            optimal_workers = 1
            if is_very_large:
                optimal_workers = min(4, max(1, (os.cpu_count() or 1) // 2))
            elif is_large:
                optimal_workers = min(2, max(1, (os.cpu_count() or 1) // 4))
            
            analysis = {
                'repo_size': repo_size,
                'num_files': num_files,
                'total_file_size': total_file_size,
                'avg_file_size': avg_file_size,
                'file_type_counts': file_type_counts,
                'is_very_large': is_very_large,
                'is_large': is_large,
                'has_many_files': has_many_files,
                'optimal_workers': optimal_workers,
                'system_cores': os.cpu_count() or 1
            }
            
            logger.debug(f"Repository analysis: {analysis}")
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze repository characteristics: {e}")
            # Return conservative defaults
            return {
                'repo_size': 0,
                'num_files': 0,
                'total_file_size': 0,
                'avg_file_size': 0,
                'file_type_counts': {'text': 0, 'config': 0, 'binary': 0, 'unknown': 0},
                'is_very_large': False,
                'is_large': False,
                'has_many_files': False,
                'optimal_workers': 1,
                'system_cores': 1
            }
    
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

    def optimize_cache_strategy(self) -> None:
        """
        Optimize cache strategy based on usage patterns.
        
        Analyzes cache usage and adjusts TTL values and cache size
        for better performance.
        """
        try:
            stats = self.get_cache_stats()
            cache_stats = stats['cache_stats']
            
            # Analyze hit rate
            hit_rate = cache_stats['hit_rate']
            
            # Adjust TTL based on hit rate
            if hit_rate > 0.8:  # High hit rate
                # Increase TTL for frequently accessed items
                self._adjust_cache_ttl_multiplier(1.5)
                logger.info("Increased cache TTL due to high hit rate")
            elif hit_rate < 0.3:  # Low hit rate
                # Decrease TTL to reduce memory usage
                self._adjust_cache_ttl_multiplier(0.7)
                logger.info("Decreased cache TTL due to low hit rate")
            
            # Adjust cache size based on usage
            cache_size = stats['cache_size']
            if cache_size > 80:  # Cache is getting full
                self.optimize_cache_size(60)  # Reduce to 60 entries
                logger.info("Optimized cache size due to high usage")
            
            # Clean up expired entries
            expired_count = self.cleanup_expired_entries()
            if expired_count > 0:
                logger.info(f"Cleaned up {expired_count} expired cache entries")
                
        except Exception as e:
            logger.error(f"Failed to optimize cache strategy: {e}")

    def _adjust_cache_ttl_multiplier(self, multiplier: float) -> None:
        """
        Adjust TTL values for existing cache entries.
        
        Args:
            multiplier: TTL multiplier to apply
        """
        current_time = time.time()
        
        for key, entry in self._cache.items():
            # Calculate new TTL
            original_ttl = entry.ttl
            new_ttl = original_ttl * multiplier
            
            # Update entry TTL while preserving age
            age = current_time - entry.timestamp
            entry.ttl = new_ttl
            entry.timestamp = current_time - age
            
            logger.debug(f"Adjusted TTL for {key}: {original_ttl:.1f}s -> {new_ttl:.1f}s")

    def get_cache_performance_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive cache performance report.
        
        Returns:
            Dictionary with cache performance metrics
        """
        try:
            stats = self.get_cache_stats()
            cache_stats = stats['cache_stats']
            
            # Calculate additional metrics
            total_requests = cache_stats['total_requests']
            hit_rate = cache_stats['hit_rate']
            avg_access_time = cache_stats['avg_access_time']
            
            # Memory usage estimation
            estimated_memory = self._estimate_cache_memory_usage()
            
            # Performance rating
            performance_rating = self._calculate_cache_performance_rating(cache_stats)
            
            # Recommendations
            recommendations = self._generate_cache_recommendations(cache_stats)
            
            report = {
                'timestamp': time.time(),
                'performance_rating': performance_rating,
                'cache_size': stats['cache_size'],
                'hit_rate': hit_rate,
                'total_requests': total_requests,
                'avg_access_time': avg_access_time,
                'estimated_memory_kb': estimated_memory / 1024,
                'evictions': cache_stats['evictions'],
                'most_accessed_entries': stats['most_accessed_entries'],
                'command_stats': stats['command_stats'],
                'recommendations': recommendations,
                'cache_health': self._assess_cache_health(cache_stats)
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate cache performance report: {e}")
            return {'error': str(e)}

    def _estimate_cache_memory_usage(self) -> int:
        """
        Estimate cache memory usage in bytes.
        
        Returns:
            Estimated memory usage in bytes
        """
        try:
            total_size = 0
            
            for key, entry in self._cache.items():
                # Estimate key size
                key_size = len(str(key).encode('utf-8'))
                
                # Estimate data size
                if isinstance(entry.data, str):
                    data_size = len(entry.data.encode('utf-8'))
                elif isinstance(entry.data, (list, tuple)):
                    data_size = sum(len(str(item).encode('utf-8')) for item in entry.data)
                elif isinstance(entry.data, dict):
                    data_size = sum(len(str(k).encode('utf-8')) + len(str(v).encode('utf-8')) 
                                 for k, v in entry.data.items())
                else:
                    data_size = len(str(entry.data).encode('utf-8'))
                
                # Add overhead for cache entry structure
                entry_overhead = 200  # Approximate overhead per entry
                
                total_size += key_size + data_size + entry_overhead
            
            return total_size
            
        except Exception as e:
            logger.error(f"Failed to estimate cache memory usage: {e}")
            return 0

    def _calculate_cache_performance_rating(self, cache_stats: Dict[str, Any]) -> str:
        """
        Calculate cache performance rating.
        
        Args:
            cache_stats: Cache statistics
            
        Returns:
            Performance rating (Excellent, Good, Fair, Poor)
        """
        hit_rate = cache_stats['hit_rate']
        total_requests = cache_stats['total_requests']
        
        if total_requests < 10:
            return "Insufficient Data"
        
        if hit_rate >= 0.8:
            return "Excellent"
        elif hit_rate >= 0.6:
            return "Good"
        elif hit_rate >= 0.4:
            return "Fair"
        else:
            return "Poor"

    def _generate_cache_recommendations(self, cache_stats: Dict[str, Any]) -> List[str]:
        """
        Generate cache optimization recommendations.
        
        Args:
            cache_stats: Cache statistics
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        hit_rate = cache_stats['hit_rate']
        total_requests = cache_stats['total_requests']
        evictions = cache_stats['evictions']
        
        if total_requests < 10:
            recommendations.append("Insufficient data for recommendations")
            return recommendations
        
        # Hit rate recommendations
        if hit_rate < 0.3:
            recommendations.append("Consider reducing cache TTL - low hit rate suggests cached data expires too quickly")
        elif hit_rate > 0.9:
            recommendations.append("Consider increasing cache TTL - high hit rate suggests data could be cached longer")
        
        # Eviction recommendations
        if evictions > 10:
            recommendations.append("Consider increasing cache size - high eviction rate suggests cache is too small")
        
        # Memory usage recommendations
        estimated_memory = self._estimate_cache_memory_usage()
        if estimated_memory > 10 * 1024 * 1024:  # 10MB
            recommendations.append("Consider reducing cache size - high memory usage detected")
        
        return recommendations

    def _assess_cache_health(self, cache_stats: Dict[str, Any]) -> str:
        """
        Assess overall cache health.
        
        Args:
            cache_stats: Cache statistics
            
        Returns:
            Health assessment (Healthy, Warning, Critical)
        """
        hit_rate = cache_stats['hit_rate']
        total_requests = cache_stats['total_requests']
        evictions = cache_stats['evictions']
        
        if total_requests < 10:
            return "Unknown"
        
        # Health scoring
        score = 0
        
        # Hit rate score (0-40 points)
        score += min(40, hit_rate * 50)
        
        # Eviction score (0-30 points)
        if evictions == 0:
            score += 30
        elif evictions < 5:
            score += 20
        elif evictions < 10:
            score += 10
        
        # Request volume score (0-30 points)
        if total_requests > 100:
            score += 30
        elif total_requests > 50:
            score += 20
        elif total_requests > 20:
            score += 10
        
        # Health assessment
        if score >= 80:
            return "Healthy"
        elif score >= 60:
            return "Warning"
        else:
            return "Critical"

    def enable_adaptive_cache(self) -> None:
        """
        Enable adaptive cache optimization.
        
        This enables automatic cache optimization based on usage patterns.
        """
        self._adaptive_cache_enabled = True
        logger.info("Adaptive cache optimization enabled")

    def disable_adaptive_cache(self) -> None:
        """
        Disable adaptive cache optimization.
        """
        self._adaptive_cache_enabled = False
        logger.info("Adaptive cache optimization disabled")

    def _maybe_optimize_cache(self) -> None:
        """
        Maybe optimize cache based on usage patterns.
        
        This is called periodically to optimize cache performance.
        """
        if not getattr(self, '_adaptive_cache_enabled', False):
            return
        
        try:
            # Optimize every 100 cache operations
            total_operations = self._cache_stats.total_requests
            if total_operations > 0 and total_operations % 100 == 0:
                logger.info("Running adaptive cache optimization")
                self.optimize_cache_strategy()
        except Exception as e:
            logger.error(f"Failed to run adaptive cache optimization: {e}")

    def get_cache_entry_details(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific cache entry.
        
        Args:
            key: Cache key
            
        Returns:
            Dictionary with entry details or None if not found
        """
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        current_time = time.time()
        
        return {
            'key': key,
            'data_type': type(entry.data).__name__,
            'age_seconds': current_time - entry.timestamp,
            'ttl_seconds': entry.ttl,
            'time_to_expiry': max(0, entry.ttl - (current_time - entry.timestamp)),
            'access_count': entry.access_count,
            'is_expired': entry.is_expired(),
            'estimated_size_bytes': self._estimate_entry_size(entry)
        }

    def _estimate_entry_size(self, entry: CacheEntry) -> int:
        """
        Estimate memory usage of a cache entry.
        
        Args:
            entry: Cache entry
            
        Returns:
            Estimated size in bytes
        """
        try:
            # Data size
            if isinstance(entry.data, str):
                data_size = len(entry.data.encode('utf-8'))
            elif isinstance(entry.data, (list, tuple)):
                data_size = sum(len(str(item).encode('utf-8')) for item in entry.data)
            elif isinstance(entry.data, dict):
                data_size = sum(len(str(k).encode('utf-8')) + len(str(v).encode('utf-8')) 
                             for k, v in entry.data.items())
            else:
                data_size = len(str(entry.data).encode('utf-8'))
            
            # Add overhead
            return data_size + 200  # Approximate overhead
            
        except Exception:
            return 200  # Fallback estimate
    
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
