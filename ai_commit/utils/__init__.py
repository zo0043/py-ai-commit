"""
Utility modules for AI Commit.

This module contains utility functions for file selection, logging, and other common operations.
"""

import os
import logging
from datetime import datetime
from typing import List, Optional
from pathlib import Path

from ..exceptions import FileOperationError
from ..security import SecureLogger
from ..ui import (
    AnimatedSpinner, InteractivePrompt, StatusDisplay, 
    ProgressBar, MotivationalMessages, Colors, NotificationSound
)


class FileSelector:
    """Handles interactive file selection for staging."""
    
    def __init__(self):
        """Initialize file selector."""
        self.logger = logging.getLogger(__name__)
    
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
            print(Colors.colorize("📝 没有可选择的未暂存文件", Colors.YELLOW))
            return []
        
        selected_indices = InteractivePrompt.select_multiple(
            unstaged_files, 
            "选择要暂存和分析的文件"
        )
        
        selected_files = [unstaged_files[i] for i in selected_indices]
        
        if selected_files:
            print(Colors.colorize(f"\n✅ 已选择 {len(selected_files)} 个文件:", Colors.GREEN))
            for file in selected_files:
                print(f"   📄 {file}")
        else:
            print(Colors.colorize("\n📝 未选择任何文件", Colors.YELLOW))
        
        return selected_files


class LoggingManager:
    """Manages logging configuration and secure logging."""
    
    def __init__(self, log_path: str = ".commitLogs"):
        """
        Initialize logging manager.
        
        Args:
            log_path: Directory for log files
        """
        self.log_path = Path(log_path)
        self.secure_logger = None
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """Setup logging configuration with enhanced formatting."""
        # Create log directory if it doesn't exist
        try:
            self.log_path.mkdir(exist_ok=True)
        except PermissionError:
            raise FileOperationError(f"Cannot create log directory: {self.log_path}")
        
        # Create log file path
        log_file = self.log_path / f'commit_{datetime.now().strftime("%Y%m%d")}.log'
        
        # Configure logger
        logger = logging.getLogger('ai_commit')
        logger.setLevel(logging.INFO)
        
        # Clear existing handlers
        if logger.handlers:
            logger.handlers.clear()
        
        # File handler - logs all levels
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
        self.logger.info(f"Logging initialized - log file: {log_file}", extra={'details': 'System initialization'})
    
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