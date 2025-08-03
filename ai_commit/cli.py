"""
Refactored CLI module for AI Commit.

This module provides the command-line interface using the new modular architecture.
"""

import argparse
import logging
import sys
from typing import Optional

from .config import ConfigurationLoader, AICommitConfig
from .git import GitOperations
from .ai import AIClient
from .utils import FileSelector, LoggingManager, ProgressManager
from .ui import StatusDisplay, InteractivePrompt, MotivationalMessages, Colors
from .exceptions import (
    AICommitError, ConfigurationError, GitOperationError,
    APIError, SecurityError, ValidationError
)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='AI-powered git commit message generator')

    # Main command options
    parser.add_argument('-y', '--yes', action='store_true',
                        help='Skip confirmation and commit directly')
    parser.add_argument('-c', '--config', type=str,
                        help='Path to specific config file')
    parser.add_argument('-m', '--model', type=str,
                        help='Override AI model from config')
    parser.add_argument('--dry-run', action='store_true',
                        help='Generate message without committing')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Show verbose output')
    parser.add_argument('-i', '--interactive', action='store_true',
                        help='Interactively select files to analyze and commit')
    parser.add_argument('-a', '--all', action='store_true',
                        help='Analyze and stage all changed files automatically')

    # Configuration management commands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    config_parser = subparsers.add_parser('config', help='Configuration management')
    config_subparsers = config_parser.add_subparsers(dest='config_action')

    config_subparsers.add_parser('show', help='Show current configuration')
    config_subparsers.add_parser('test', help='Test AI service connection')

    set_key_parser = config_subparsers.add_parser('set-key', help='Store API key securely')
    set_key_parser.add_argument('provider', help='AI provider (e.g., openai)')
    set_key_parser.add_argument('api_key', help='API key to store')

    return parser.parse_args()


class AICommitWorkflow:
    """Main workflow orchestrator for AI Commit operations."""

    def __init__(self, config: AICommitConfig):
        """
        Initialize workflow with configuration.

        Args:
            config: AI Commit configuration
        """
        self.config = config
        self.logging_manager = LoggingManager(config.log_path)
        self.logger = self.logging_manager.get_logger()
        self.secure_logger = self.logging_manager.get_secure_logger()
        self.progress = ProgressManager()
        self.git_ops = GitOperations()
        self.ai_client = AIClient(config)
        self.file_selector = FileSelector()

    def execute_commit_workflow(self, args: argparse.Namespace) -> None:
        """
        Execute the main commit workflow.

        Args:
            args: Parsed command line arguments
        """
        try:
            self.secure_logger.log_safe(
                logging.INFO,
                "Starting AI Commit workflow",
                f"Arguments: {vars(args)}"
            )

            # Set verbose logging if requested
            if args.verbose:
                self.logger.setLevel(logging.DEBUG)

            # Override model if specified
            if args.model:
                self.config.openai_model = args.model
                self.ai_client = AIClient(self.config)  # Reinitialize with new model
                self.progress.show_info(f"Using model: {args.model}")

            # Validate git repository
            self.progress.show_operation("Validating git repository")
            self.git_ops.validate_git_repository()

            # Handle file selection if requested
            if args.interactive or args.all:
                StatusDisplay.show_header("🎯 文件选择模式", "请选择要分析的文件")
                self._handle_file_selection(args)

            # Validate staged changes
            if not self.git_ops.validate_staged_changes():
                if args.interactive or args.all:
                    self.progress.show_error("No staged changes found after file selection")
                else:
                    self.progress.show_error(
                        "No staged changes found. Use 'git add' to stage changes first")
                return

            # Get git diff
            self.progress.show_operation("Analyzing git changes")
            diff = self.git_ops.get_git_diff()
            if not diff:
                self.progress.show_warning("No changes detected")
                return

            # Generate commit message with enhanced feedback
            loading_msg = MotivationalMessages.get_loading_message()
            self.progress.show_operation(loading_msg)

            branch_name = self.git_ops.get_current_branch()
            context = {'branch_name': branch_name} if branch_name else {}

            commit_message = self.ai_client.generate_commit_message(diff, context)

            success_msg = MotivationalMessages.get_success_message()
            self.progress.complete_operation(success_msg)

            # Display generated message
            self._display_commit_message(commit_message)

            # Handle dry run
            if args.dry_run:
                self.progress.show_info("🎙️  模拟模式 - 跳过提交")
                return

            # Determine if we should commit
            should_commit = args.yes or self.config.auto_commit
            if not should_commit:
                should_commit = self._get_user_confirmation()

            if should_commit:
                self._execute_commit(commit_message)

                # Handle auto-push if enabled
                if self.config.auto_push:
                    self._execute_push()
            else:
                self.progress.show_info("💫 用户取消提交")

        except KeyboardInterrupt:
            self.progress.show_warning("⚙️  操作已取消")
            sys.exit(1)
        except Exception as e:
            self._handle_error(e)
            sys.exit(1)

    def _handle_file_selection(self, args: argparse.Namespace) -> None:
        """Handle interactive or automatic file selection."""
        self.progress.show_operation("Discovering file changes")
        staged_files, unstaged_files = self.git_ops.get_changed_files()
        self.progress.complete_operation("File discovery completed")

        # Display current status
        self.file_selector.display_file_changes(staged_files, unstaged_files)

        if args.all:
            # Auto-stage all unstaged files
            if unstaged_files:
                self.progress.show_operation(f"Auto-staging {len(unstaged_files)} files")
                self.git_ops.stage_files(unstaged_files)
                self.progress.show_success(f"Staged {len(unstaged_files)} files")
            else:
                self.progress.show_info("No unstaged files to stage")

        elif args.interactive:
            # Interactive file selection
            if unstaged_files:
                selected_files = self.file_selector.select_files_interactive(unstaged_files)
                if selected_files:
                    self.progress.show_operation(f"Staging {len(selected_files)} selected files")
                    self.git_ops.stage_files(selected_files)
                    self.progress.show_success(f"Staged {len(selected_files)} files")
                elif not staged_files:
                    raise ValidationError("No files selected and no staged files available")
            else:
                self.progress.show_info("No unstaged files available for selection")

    def _display_commit_message(self, message: str) -> None:
        """Display the generated commit message with enhanced styling."""
        StatusDisplay.show_commit_message(message)

    def _get_user_confirmation(self) -> bool:
        """Get user confirmation for commit with enhanced prompt."""
        return InteractivePrompt.confirm("是否使用该提交信息？", False)

    def _execute_commit(self, message: str) -> None:
        """Execute the git commit with enhanced feedback."""
        self.progress.show_operation("正在提交更改")
        self.git_ops.commit_changes(message)
        self.progress.complete_operation("🎉 提交成功！")

    def _execute_push(self) -> None:
        """Execute git push if auto-push is enabled."""
        self.progress.show_operation("正在推送到远程仓库")
        try:
            self.git_ops.push_changes()
            self.progress.complete_operation("🚀 推送成功！")
        except GitOperationError as e:
            self.progress.show_warning(f"推送失败: {e}")

    def _handle_error(self, error: Exception) -> None:
        """Handle different types of errors with appropriate messages."""
        if isinstance(error, ConfigurationError):
            self.progress.show_error(f"Configuration error: {error}")
        elif isinstance(error, GitOperationError):
            self.progress.show_error(f"Git error: {error}")
        elif isinstance(error, APIError):
            self.progress.show_error(f"AI service error: {error}")
        elif isinstance(error, SecurityError):
            self.progress.show_error(f"Security error: {error}")
        elif isinstance(error, ValidationError):
            self.progress.show_error(f"Validation error: {error}")
        else:
            self.progress.show_error(f"Unexpected error: {error}")

        # Log detailed error information
        self.secure_logger.log_safe(
            logging.ERROR,
            f"Error occurred: {type(error).__name__}",
            f"Details: {str(error)}"
        )


def handle_config_commands(args: argparse.Namespace) -> None:
    """Handle configuration-related commands."""
    from .security import APIKeyManager

    progress = ProgressManager()

    if args.config_action == 'show':
        try:
            config_loader = ConfigurationLoader()
            config = config_loader.load_config(args.config)

            print("\n📋 Current Configuration:")
            print("=" * 40)
            for key, value in config.get_masked_config().items():
                print(f"{key}: {value}")
            print("=" * 40)

        except ConfigurationError as e:
            progress.show_error(f"Configuration error: {e}")
            sys.exit(1)

    elif args.config_action == 'test':
        try:
            config_loader = ConfigurationLoader()
            config = config_loader.load_config(args.config)

            progress.show_operation("Testing AI service connection")
            ai_client = AIClient(config)

            if ai_client.test_connection():
                progress.show_success("AI service connection successful")
            else:
                progress.show_error("AI service connection failed")
                sys.exit(1)

        except Exception as e:
            progress.show_error(f"Connection test failed: {e}")
            sys.exit(1)

    elif args.config_action == 'set-key':
        try:
            api_key_manager = APIKeyManager()
            api_key_manager.store_api_key(args.provider, args.api_key)
            progress.show_success(f"API key for {args.provider} stored securely")

        except SecurityError as e:
            progress.show_error(f"Failed to store API key: {e}")
            sys.exit(1)


def main() -> None:
    """Main entry point for AI Commit CLI."""
    try:
        args = parse_args()

        # Handle configuration commands
        if args.command == 'config':
            handle_config_commands(args)
            return

        # Load configuration
        config_loader = ConfigurationLoader()
        config = config_loader.load_config(args.config)

        # Create and execute workflow
        workflow = AICommitWorkflow(config)
        workflow.execute_commit_workflow(args)

    except ConfigurationError as e:
        print(f"❌ Configuration error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
