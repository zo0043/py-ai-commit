"""
Enhanced UI components for AI Commit.

This module provides immersive user interface components with animations,
dynamic feedback, and improved user experience.
"""

import sys
import time
import random
import threading
from typing import List, Optional, Callable, Any
from datetime import datetime
import os


class AnimatedSpinner:
    """Animated spinner for operations with dynamic messages."""

    def __init__(self):
        self.frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self.is_spinning = False
        self.thread = None
        self.message = ""

    def start(self, message: str = "Processing") -> None:
        """Start the spinner with a message."""
        self.message = message
        self.is_spinning = True
        self.thread = threading.Thread(target=self._spin)
        self.thread.daemon = True
        self.thread.start()

    def stop(self, final_message: str = "") -> None:
        """Stop the spinner and show final message."""
        self.is_spinning = False
        if self.thread:
            self.thread.join()
        # Clear the spinner line
        sys.stdout.write('\r' + ' ' * (len(self.message) + 10) + '\r')
        if final_message:
            print(final_message)
        sys.stdout.flush()

    def _spin(self) -> None:
        """Internal spinning animation."""
        idx = 0
        while self.is_spinning:
            frame = self.frames[idx % len(self.frames)]
            sys.stdout.write(f'\r{frame} {self.message}')
            sys.stdout.flush()
            time.sleep(0.1)
            idx += 1


class TypewriterEffect:
    """Typewriter effect for displaying text."""

    @staticmethod
    def print_slowly(text: str, delay: float = 0.03, color: str = "") -> None:
        """Print text with typewriter effect."""
        reset = "\033[0m" if color else ""
        for char in text:
            sys.stdout.write(f"{color}{char}{reset}")
            sys.stdout.flush()
            time.sleep(delay)
        print()


class ProgressBar:
    """Animated progress bar for file operations."""

    def __init__(self, total: int, width: int = 40):
        self.total = total
        self.width = width
        self.current = 0

    def update(self, value: int, description: str = "") -> None:
        """Update progress bar."""
        self.current = value
        percent = (self.current / self.total) * 100
        filled = int(self.width * self.current // self.total)
        bar = '█' * filled + '░' * (self.width - filled)

        sys.stdout.write(f'\r🔄 [{bar}] {percent:.1f}% {description}')
        sys.stdout.flush()

    def finish(self, message: str = "Complete") -> None:
        """Finish progress bar."""
        sys.stdout.write(f'\r✅ [{"█" * self.width}] 100% {message}\n')
        sys.stdout.flush()


class InteractivePrompt:
    """Enhanced interactive prompts with better UX."""

    @staticmethod
    def confirm(message: str, default: bool = False) -> bool:
        """简化的确认提示."""
        default_text = "Y/n" if default else "y/N"

        print(f"\n{message} ({default_text}): ")

        try:
            response = input().strip().lower()
            if not response:
                return default
            return response in ('y', 'yes', '是', '好')
        except (KeyboardInterrupt, EOFError):
            print("\n操作已取消")
            return False

    @staticmethod
    def select_multiple(options: List[str], prompt: str = "选择选项") -> List[int]:
        """简化的多选提示界面."""
        print(f"\n{prompt}:")

        for i, option in enumerate(options, 1):
            print(f"  {i}. {option}")

        print("\n选择 (数字空格分隔, all=全选, 回车=跳过): ")

        try:
            response = input().strip().lower()

            if response == 'all':
                return list(range(len(options)))
            elif not response:
                return []
            else:
                numbers = []
                for part in response.split():
                    try:
                        num = int(part)
                        if 1 <= num <= len(options):
                            numbers.append(num - 1)
                    except ValueError:
                        continue
                return numbers

        except (KeyboardInterrupt, EOFError):
            print("\n操作已取消")
            return []


class StatusDisplay:
    """Enhanced status display with visual improvements."""

    @staticmethod
    def show_header(title: str, subtitle: str = "") -> None:
        """Show styled header."""
        width = max(len(title), len(subtitle)) + 4

        print(f"\n╭{'─' * width}╮")
        print(f"│ {title.center(width - 2)} │")
        if subtitle:
            print(f"│ {subtitle.center(width - 2)} │")
        print(f"╰{'─' * width}╯")

    @staticmethod
    def show_files_status(staged: List[str], unstaged: List[str]) -> None:
        """简化的文件状态显示."""
        print("\nGit 文件状态:")

        if staged:
            print(f"\n已暂存 ({len(staged)}):")
            for i, file in enumerate(staged, 1):
                print(f"  {i}. {file}")

        if unstaged:
            print(f"\n未暂存 ({len(unstaged)}):")
            for i, file in enumerate(unstaged, 1):
                clean_file = file[3:] if file.startswith(("A  ", "M  ", "?? ")) else file
                print(f"  {i}. {clean_file}")

        if not staged and not unstaged:
            print("  暂无变更")

        print("━" * 50)

    @staticmethod
    def show_commit_message(message: str, is_preview: bool = False) -> None:
        """Show commit message with enhanced styling."""
        title = "📝 生成的提交信息" if not is_preview else "👀 提交信息预览"

        print(f"\n┌─ {title}")
        print("├─" + "─" * 48)

        lines = message.split('\n')
        for line in lines:
            print(f"│ {line}")

        print("└─" + "─" * 48)


class MotivationalMessages:
    """Motivational and contextual messages for better UX."""

    LOADING_MESSAGES = [
        "🧠 AI正在思考最佳提交信息...",
        "✨ 分析代码变更中...",
        "🎯 生成符合规范的提交信息...",
        "🚀 即将完成，请稍候...",
        "💡 正在优化提交描述..."
    ]

    SUCCESS_MESSAGES = [
        "🎉 完美！提交信息已生成",
        "✨ 太棒了！准备就绪",
        "🚀 搞定！看起来很不错",
        "💎 优秀！质量很高",
        "🌟 完成！专业水准"
    ]

    @classmethod
    def get_loading_message(cls) -> str:
        """Get random loading message."""
        return random.choice(cls.LOADING_MESSAGES)

    @classmethod
    def get_success_message(cls) -> str:
        """Get random success message."""
        return random.choice(cls.SUCCESS_MESSAGES)


class Colors:
    """ANSI color codes for terminal styling."""

    # Basic colors
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

    # Styles
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    # Reset
    RESET = "\033[0m"

    @classmethod
    def colorize(cls, text: str, color: str) -> str:
        """Colorize text."""
        return f"{color}{text}{cls.RESET}"


class NotificationSound:
    """Simple system notification sounds."""

    @staticmethod
    def success() -> None:
        """Play success sound (if available)."""
        try:
            if sys.platform == "darwin":  # macOS
                os.system("afplay /System/Library/Sounds/Glass.aiff 2>/dev/null &")
            elif sys.platform.startswith("linux"):
                os.system("paplay /usr/share/sounds/alsa/Front_Left.wav 2>/dev/null &")
        except BaseException:
            pass  # Silently fail if sound not available

    @staticmethod
    def error() -> None:
        """Play error sound (if available)."""
        try:
            if sys.platform == "darwin":  # macOS
                os.system("afplay /System/Library/Sounds/Sosumi.aiff 2>/dev/null &")
            elif sys.platform.startswith("linux"):
                os.system("paplay /usr/share/sounds/alsa/Front_Right.wav 2>/dev/null &")
        except BaseException:
            pass  # Silently fail if sound not available
