"""
Utility modules for AI Commit.

This module contains utility functions for file selection, logging, and other common operations.
"""

import os
import logging
from datetime import datetime
from typing import List, Optional, Set, Dict, Any
from pathlib import Path
from dataclasses import dataclass, field
from collections import defaultdict
import time

from ..exceptions import FileOperationError
from ..security import SecureLogger
from ..ui import (
    AnimatedSpinner, InteractivePrompt, StatusDisplay,
    ProgressBar, MotivationalMessages, Colors, NotificationSound
)


@dataclass
class FileStatus:
    """Cached file status information."""
    exists: bool
    size: int
    modified_time: float
    is_binary: bool = False


@dataclass
class FileCacheStats:
    """File cache statistics for monitoring and optimization."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    large_files_filtered: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def record_hit(self) -> None:
        """Record a cache hit."""
        self.hits += 1
    
    def record_miss(self) -> None:
        """Record a cache miss."""
        self.misses += 1
    
    def record_eviction(self) -> None:
        """Record a cache eviction."""
        self.evictions += 1
    
    def record_large_file_filtered(self) -> None:
        """Record a large file being filtered."""
        self.large_files_filtered += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics as dictionary."""
        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': self.hit_rate,
            'evictions': self.evictions,
            'large_files_filtered': self.large_files_filtered,
            'total_requests': self.hits + self.misses
        }


class FileStatusCache:
    """Cache for file status information."""
    
    def __init__(self, ttl: float = 60.0):  # 1 minute
        self._cache: Dict[str, FileStatus] = {}
        self._timestamps: Dict[str, float] = {}
        self._ttl = ttl
        self._stats = FileCacheStats()
        self._access_counts: Dict[str, int] = defaultdict(int)
    
    def get_status(self, file_path: str) -> Optional[FileStatus]:
        """Get cached file status if not expired."""
        if file_path in self._cache:
            timestamp = self._timestamps.get(file_path, 0)
            if time.time() - timestamp < self._ttl:
                self._access_counts[file_path] += 1
                self._stats.record_hit()
                return self._cache[file_path]
            else:
                del self._cache[file_path]
                del self._timestamps[file_path]
                self._stats.record_eviction()
        
        self._stats.record_miss()
        return None
    
    def set_status(self, file_path: str, status: FileStatus) -> None:
        """Set cached file status."""
        # Check if we need to evict an entry (LRU strategy)
        if len(self._cache) >= 200:  # Max cache size
            self._evict_lru_entry()
        
        self._cache[file_path] = status
        self._timestamps[file_path] = time.time()
        self._access_counts[file_path] = 0
    
    def _evict_lru_entry(self) -> None:
        """Evict least recently used cache entry."""
        if not self._timestamps:
            return
        
        # Find entry with oldest timestamp
        lru_key = min(self._timestamps.keys(), 
                     key=lambda k: self._timestamps[k])
        del self._cache[lru_key]
        del self._timestamps[lru_key]
        self._access_counts.pop(lru_key, None)
        self._stats.record_eviction()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            'cache_stats': self._stats.get_stats(),
            'cache_size': len(self._cache),
            'ttl': self._ttl,
            'most_accessed_files': self._get_most_accessed_files()
        }
    
    def _get_most_accessed_files(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get most accessed files."""
        files = [
            {
                'file_path': file_path,
                'access_count': count,
                'size': self._cache[file_path].size,
                'age': time.time() - self._timestamps.get(file_path, 0)
            }
            for file_path, count in self._access_counts.items()
            if file_path in self._cache
        ]
        return sorted(files, key=lambda x: x['access_count'], reverse=True)[:limit]
    
    def clear(self) -> None:
        """Clear all cached file statuses."""
        self._cache.clear()
        self._timestamps.clear()
        self._access_counts.clear()
        self._stats = FileCacheStats()


class FileSelector:
    """Handles interactive file selection for staging."""

    def __init__(self):
        """Initialize file selector."""
        self.logger = logging.getLogger(__name__)
        self._status_cache = FileStatusCache()

    def _get_file_status(self, file_path: str) -> FileStatus:
        """Get file status with caching."""
        # Check cache first
        cached_status = self._status_cache.get_status(file_path)
        if cached_status is not None:
            return cached_status
        
        # Get fresh status
        path = Path(file_path)
        exists = path.exists()
        
        if exists:
            size = path.stat().st_size
            modified_time = path.stat().st_mtime
            # Simple binary detection
            is_binary = False
            try:
                with open(path, 'rb') as f:
                    chunk = f.read(1024)
                    is_binary = b'\x00' in chunk
            except (OSError, IOError):
                is_binary = True
        else:
            size = 0
            modified_time = 0
            is_binary = False
        
        status = FileStatus(exists=exists, size=size, modified_time=modified_time, is_binary=is_binary)
        self._status_cache.set_status(file_path, status)
        return status

    def _filter_large_files(self, files: List[str], max_size: int = 10 * 1024 * 1024) -> List[str]:
        """Filter out files that are too large for processing."""
        filtered_files = []
        
        for file_path in files:
            status = self._get_file_status(file_path)
            if status.exists and status.size > max_size:
                self.logger.warning(f"Skipping large file: {file_path} ({status.size} bytes)")
                self._stats.record_large_file_filtered()
                continue
            filtered_files.append(file_path)
        
        return filtered_files

    def display_file_changes(self, staged_files: List[str], unstaged_files: List[str]) -> None:
        """
        Display current file changes in a formatted way.

        Args:
            staged_files: List of staged files
            unstaged_files: List of unstaged files
        """
        StatusDisplay.show_files_status(staged_files, unstaged_files)

    def select_files_interactive(self, unstaged_files: List[str]) -> List[str]:
        """
        Interactive file selection for staging and analysis.

        Args:
            unstaged_files: List of unstaged files to choose from

        Returns:
            List of selected file paths
        """
        if not unstaged_files:
            print("没有可选择的未暂存文件")
            return []

        selected_indices = InteractivePrompt.select_multiple(
            unstaged_files,
            "选择要暂存和分析的文件"
        )

        selected_files = [unstaged_files[i] for i in selected_indices]

        if selected_files:
            print(f"\n已选择 {len(selected_files)} 个文件:")
            for file in selected_files:
                print(f"  - {file}")
        else:
            print("\n未选择任何文件")

        return selected_files


class LoggingManager:
    """Manages logging configuration and secure logging with singleton pattern."""

    _instance = None
    _initialized = False

    def __new__(cls, log_path: str = ".commitLogs"):
        """Singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, log_path: str = ".commitLogs"):
        """
        Initialize logging manager.

        Args:
            log_path: Directory for log files
        """
        if self._initialized:
            return

        self.log_path = Path(log_path)
        self.secure_logger = None
        self._logger_instance = None
        self._setup_logging()
        self._initialized = True

    def _setup_logging(self) -> None:
        """Setup logging configuration with enhanced formatting and log rotation."""
        # Create log directory if it doesn't exist
        try:
            self.log_path.mkdir(exist_ok=True)
        except PermissionError:
            raise FileOperationError(f"Cannot create log directory: {self.log_path}")

        # Create log file path with rotation
        log_file = self._get_log_file_path()

        # Configure logger
        logger = logging.getLogger('ai_commit')
        logger.setLevel(logging.INFO)

        # Clear existing handlers only if not already configured
        if logger.handlers and not hasattr(self, '_logger_configured'):
            logger.handlers.clear()

        # File handler with rotation
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(SafeFormatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s\nDetails: %(details)s\n',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))

        # Console handler - only shows INFO and above
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(ColoredFormatter('%(message)s'))

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        # Create secure logger wrapper
        self.secure_logger = SecureLogger(logger)

        self.logger = logger
        self._logger_instance = logger
        self._logger_configured = True

        # Clean up old log files
        self._cleanup_old_logs()

        self.logger.info(
            f"Logging initialized - log file: {log_file}",
            extra={
                'details': 'System initialization'})

    def _get_log_file_path(self) -> Path:
        """Get current log file path with rotation."""
        current_date = datetime.now().strftime("%Y%m%d")

        # Check if today's log file exists and is too large
        log_file = self.log_path / f'commit_{current_date}.log'

        if log_file.exists():
            file_size = log_file.stat().st_size
            max_size = 10 * 1024 * 1024  # 10MB max per file

            if file_size > max_size:
                # Create rotated log file
                timestamp = datetime.now().strftime("%H%M%S")
                rotated_file = self.log_path / f'commit_{current_date}_{timestamp}.log'
                log_file.rename(rotated_file)

        return log_file

    def _cleanup_old_logs(self) -> None:
        """Clean up old log files to prevent disk space issues."""
        try:
            # Keep logs for 30 days
            cutoff_date = datetime.now().timestamp() - (30 * 24 * 60 * 60)

            for log_file in self.log_path.glob('commit_*.log'):
                if log_file.stat().st_mtime < cutoff_date:
                    log_file.unlink()
                    self.logger.debug(f"Cleaned up old log file: {log_file}")
        except Exception as e:
            # Don't fail if cleanup fails
            self.logger.debug(f"Log cleanup failed: {e}")

    @classmethod
    def get_instance(cls, log_path: str = ".commitLogs") -> 'LoggingManager':
        """Get the singleton instance of LoggingManager."""
        if cls._instance is None:
            cls._instance = cls(log_path)
        return cls._instance

    def get_logger(self) -> logging.Logger:
        """Get the configured logger."""
        return self.logger

    def get_secure_logger(self) -> SecureLogger:
        """Get the secure logger wrapper."""
        return self.secure_logger

    def log_with_details(self, level: int, message: str, details: Optional[str] = None) -> None:
        """
        Log message with details using secure logger.

        Args:
            level: Log level
            message: Log message
            details: Additional details
        """
        if self.secure_logger:
            self.secure_logger.log_safe(level, message, details)
        else:
            # Fallback to regular logging
            extra = {'details': details if details else 'No additional details'}
            self.logger.log(level, message, extra=extra)


class SafeFormatter(logging.Formatter):
    """A logging formatter that safely handles missing 'details' field."""

    def format(self, record):
        # Ensure 'details' field exists
        if not hasattr(record, 'details'):
            record.details = 'No additional details'
        return super().format(record)


class ColoredFormatter(logging.Formatter):
    """Custom log formatter with color support for console output."""

    # Color codes
    GREY = "\x1b[38;21m"
    BLUE = "\x1b[38;5;39m"
    YELLOW = "\x1b[38;5;226m"
    RED = "\x1b[38;5;196m"
    BOLD_RED = "\x1b[31;1m"
    RESET = "\x1b[0m"

    def __init__(self, fmt):
        super().__init__()
        self.fmt = fmt
        self.FORMATS = {
            logging.DEBUG: self.GREY + self.fmt + self.RESET,
            logging.INFO: self.BLUE + self.fmt + self.RESET,
            logging.WARNING: self.YELLOW + self.fmt + self.RESET,
            logging.ERROR: self.RED + self.fmt + self.RESET,
            logging.CRITICAL: self.BOLD_RED + self.fmt + self.RESET
        }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


class ProgressManager:
    """Manages progress display and user feedback with enhanced animations."""

    def __init__(self):
        """Initialize progress manager."""
        self.current_operation = None
        self.spinner = AnimatedSpinner()
        self._active_operations = []

    def show_operation(self, operation: str) -> None:
        """
        Show current operation to user with spinner.

        Args:
            operation: Description of current operation
        """
        self.current_operation = operation
        self.spinner.start(operation)

    def complete_operation(self, success_message: str = None) -> None:
        """
        Complete current operation with success message.

        Args:
            success_message: Custom success message
        """
        if success_message:
            final_msg = Colors.colorize(f"✅ {success_message}", Colors.GREEN)
        else:
            final_msg = Colors.colorize(f"✅ {self.current_operation} 完成", Colors.GREEN)

        self.spinner.stop(final_msg)
        NotificationSound.success()

    def show_success(self, message: str) -> None:
        """
        Show success message.

        Args:
            message: Success message
        """
        print(Colors.colorize(f"✅ {message}", Colors.GREEN))

    def show_warning(self, message: str) -> None:
        """
        Show warning message.

        Args:
            message: Warning message
        """
        print(Colors.colorize(f"⚠️  {message}", Colors.YELLOW))

    def show_error(self, message: str) -> None:
        """
        Show error message.

        Args:
            message: Error message
        """
        self.spinner.stop()
        print(Colors.colorize(f"❌ {message}", Colors.RED))
        NotificationSound.error()

    def show_info(self, message: str) -> None:
        """
        Show info message.

        Args:
            message: Info message
        """
        print(Colors.colorize(f"ℹ️  {message}", Colors.BLUE))

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures proper cleanup."""
        self.cleanup()

    def cleanup(self) -> None:
        """Clean up resources and ensure all operations are properly stopped."""
        # Stop any active spinner
        if hasattr(self, 'spinner') and self.spinner:
            self.spinner.stop()

        # Clear active operations list
        self._active_operations.clear()

        # Reset current operation
        self.current_operation = None


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string
    """
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to specified length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add when truncating

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix
