"""
AI client module for AI Commit.

This module handles communication with AI providers to generate commit messages.
"""

import time
import logging
import asyncio
from typing import Optional, Dict, Any
import openai

from ..exceptions import APIError, ConfigurationError
from ..config import AICommitConfig
from ..security import InputValidator

logger = logging.getLogger(__name__)


class AIClient:
    """Client for AI-powered commit message generation."""

    def __init__(self, config: AICommitConfig):
        """
        Initialize AI client with configuration.

        Args:
            config: AI Commit configuration
        """
        self.config = config
        self.validator = InputValidator()
        self._client = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize OpenAI client."""
        try:
            self._client = openai.OpenAI(
                api_key=self.config.openai_api_key,
                base_url=self.config.openai_base_url,
                timeout=self.config.timeout
            )
            logger.debug("OpenAI client initialized successfully")
        except Exception as e:
            raise ConfigurationError(f"Failed to initialize OpenAI client: {e}")

    def generate_commit_message(
            self, diff_text: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate commit message from git diff.

        Args:
            diff_text: Git diff content
            context: Additional context (branch name, etc.)

        Returns:
            Generated commit message

        Raises:
            APIError: If API call fails
            ValidationError: If inputs are invalid
        """
        if not self._client:
            raise APIError("AI client not initialized")

        # Validate input
        validated_diff = self.validator.validate_git_diff(diff_text)

        # Prepare context
        context = context or {}
        branch_name = context.get('branch_name', '')

        # Create prompt
        prompt = self._create_commit_prompt(validated_diff, branch_name)

        # Generate message with retries
        message = self._generate_with_retries(prompt)

        # Validate and return result
        return self.validator.validate_commit_message(message)

    def _create_commit_prompt(self, diff_text: str, branch_name: str) -> str:
        """
        Create prompt for commit message generation.

        Args:
            diff_text: Git diff content
            branch_name: Current branch name

        Returns:
            Formatted prompt for AI
        """
        branch_context = f"Current branch: {branch_name}\n" if branch_name else ""

        prompt = f"""Please analyze the following git diff and generate a concise and descriptive commit message.
The commit message should follow conventional commit format and be in English.
Focus on WHAT changed and WHY, not HOW.
Your response should only contain the commit message wrapped in triple backticks.

{branch_context}
Git diff:
{diff_text}

Generate a commit message in the format:
type(scope): description

Where:
- type: feat, fix, docs, style, refactor, test, chore, etc.
- scope: optional, affected component/module
- description: brief description of the change (50 chars or less for the title)

Examples:
- feat(auth): add OAuth2 authentication
- fix(api): resolve connection timeout issue
- docs(readme): update installation instructions
- refactor(config): simplify configuration loading

Generate only the commit message, wrapped in triple backticks."""

        return prompt

    def _generate_with_retries(self, prompt: str) -> str:
        """
        Generate commit message with retry logic.

        Args:
            prompt: The prompt to send to AI

        Returns:
            Generated commit message

        Raises:
            APIError: If all retries fail
        """
        last_error = None

        for attempt in range(self.config.max_retries):
            try:
                logger.info(f"Calling OpenAI API (attempt {attempt + 1}/{self.config.max_retries})")

                response = self._client.chat.completions.create(
                    model=self.config.openai_model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful assistant that generates clear and concise git "
                            "commit messages following conventional commit format. "
                            "Always wrap your response in triple backticks."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    max_tokens=150,
                    temperature=0.7,
                    timeout=self.config.timeout
                )

                raw_message = response.choices[0].message.content.strip()
                commit_message = self._extract_commit_message(raw_message)

                logger.info("Successfully generated commit message")
                logger.debug(f"Raw response: {raw_message}")
                logger.debug(f"Extracted message: {commit_message}")

                return commit_message

            except openai.RateLimitError as e:
                last_error = e
                if attempt < self.config.max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(
                        f"Rate limit hit (attempt {attempt + 1}), waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error("Rate limit exceeded after all retries")

            except openai.AuthenticationError as e:
                # Don't retry authentication errors
                logger.error("Authentication failed - check your API key")
                raise APIError(f"Authentication failed: {e}")

            except openai.BadRequestError as e:
                # Don't retry bad request errors
                logger.error(f"Bad request: {e}")
                raise APIError(f"Bad request: {e}")

            except openai.APITimeoutError as e:
                last_error = e
                if attempt < self.config.max_retries - 1:
                    logger.warning(f"API timeout (attempt {attempt + 1}), retrying...")
                    time.sleep(1)
                else:
                    logger.error("API timeout after all retries")

            except openai.APIConnectionError as e:
                last_error = e
                if attempt < self.config.max_retries - 1:
                    logger.warning(f"Connection error (attempt {attempt + 1}), retrying...")
                    time.sleep(2)
                else:
                    logger.error("Connection error after all retries")

            except Exception as e:
                last_error = e
                if attempt < self.config.max_retries - 1:
                    logger.warning(f"Unexpected error (attempt {attempt + 1}): {e}")
                    time.sleep(1)
                else:
                    logger.error(f"Unexpected error after all retries: {e}")

        # All retries failed
        error_msg = f"Failed to generate commit message after {self.config.max_retries} attempts"
        if last_error:
            error_msg += f": {last_error}"

        raise APIError(error_msg)

    def _extract_commit_message(self, text: str) -> str:
        """
        Extract commit message from AI response.

        Args:
            text: Raw AI response

        Returns:
            Extracted commit message
        """
        import re

        # Try to find content between triple backticks
        pattern = r'```(?:\w*\n)?(.*?)```'
        matches = re.findall(pattern, text, re.DOTALL)

        if matches:
            message = matches[0].strip()
            logger.debug(f"Extracted message from backticks: {message}")
            return message

        # If no backticks found, use the whole text (cleaned up)
        cleaned_text = text.strip()

        # Remove common prefixes
        prefixes_to_remove = [
            "Here's a commit message:",
            "Commit message:",
            "The commit message is:",
            "Here is the commit message:",
        ]

        for prefix in prefixes_to_remove:
            if cleaned_text.lower().startswith(prefix.lower()):
                cleaned_text = cleaned_text[len(prefix):].strip()
                break

        # Remove quotes if present
        if cleaned_text.startswith('"') and cleaned_text.endswith('"'):
            cleaned_text = cleaned_text[1:-1]
        elif cleaned_text.startswith("'") and cleaned_text.endswith("'"):
            cleaned_text = cleaned_text[1:-1]

        logger.debug(f"Cleaned message: {cleaned_text}")
        return cleaned_text

    def test_connection(self) -> bool:
        """
        Test connection to AI service.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info("Testing AI service connection...")

            response = self._client.chat.completions.create(
                model=self.config.openai_model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Say 'test' and nothing else."}
                ],
                max_tokens=10,
                timeout=10
            )

            result = response.choices[0].message.content.strip().lower()
            success = "test" in result

            if success:
                logger.info("AI service connection test successful")
            else:
                logger.warning(f"AI service connection test failed: unexpected response '{result}'")

            return success

        except Exception as e:
            logger.error(f"AI service connection test failed: {e}")
            return False

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the configured model.

        Returns:
            Dictionary with model information
        """
        return {
            'model': self.config.openai_model,
            'base_url': self.config.openai_base_url,
            'max_retries': self.config.max_retries,
            'timeout': self.config.timeout,
        }

    async def generate_commit_message_async(self, diff_text: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Asynchronously generate commit message from git diff.

        Args:
            diff_text: Git diff content
            context: Additional context (branch name, etc.)

        Returns:
            Generated commit message

        Raises:
            APIError: If API call fails
            ValidationError: If inputs are invalid
        """
        if not self._client:
            raise APIError("AI client not initialized")

        # Validate input
        validated_diff = self.validator.validate_git_diff(diff_text)

        # Prepare context
        context = context or {}
        branch_name = context.get('branch_name', '')

        # Create prompt
        prompt = self._create_commit_prompt(validated_diff, branch_name)

        # Generate message with retries asynchronously
        message = await self._generate_with_retries_async(prompt)

        # Validate and return result
        return self.validator.validate_commit_message(message)

    async def _generate_with_retries_async(self, prompt: str) -> str:
        """
        Generate commit message with retries asynchronously.

        Args:
            prompt: Formatted prompt for AI

        Returns:
            Generated commit message

        Raises:
            APIError: If all retries fail
        """
        last_error = None

        for attempt in range(self.config.max_retries):
            try:
                logger.info(f"Calling OpenAI API asynchronously (attempt {attempt + 1}/{self.config.max_retries})")

                # Run the blocking OpenAI call in a thread pool
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self._client.chat.completions.create(
                        model=self.config.openai_model,
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a helpful assistant that generates clear and concise "
                                "commit messages following conventional commit format. "
                                "Always wrap your response in triple backticks."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        max_tokens=500,
                        timeout=self.config.timeout
                    )
                )

                # Extract and validate message
                raw_message = response.choices[0].message.content
                commit_message = self._extract_commit_message(raw_message)

                logger.info("Successfully generated commit message asynchronously")
                return commit_message

            except openai.RateLimitError as e:
                last_error = str(e)
                if attempt < self.config.max_retries - 1:
                    wait_time = min(2 ** attempt, 30)  # Exponential backoff
                    logger.warning(
                        f"Rate limit hit (attempt {attempt + 1}), waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                break
            except Exception as e:
                last_error = str(e)
                if attempt < self.config.max_retries - 1:
                    wait_time = min(2 ** attempt, 30)
                    logger.warning(
                        f"API call failed (attempt {attempt + 1}), waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                break

        # All retries failed
        error_msg = f"Failed to generate commit message after {self.config.max_retries} attempts"
        if last_error:
            error_msg += f": {last_error}"

        raise APIError(error_msg)

    async def test_connection_async(self) -> bool:
        """
        Test connection to AI service asynchronously.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info("Testing AI service connection asynchronously...")

            # Run the blocking OpenAI call in a thread pool
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._client.chat.completions.create(
                    model=self.config.openai_model,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "Say 'test' and nothing else."}
                    ],
                    max_tokens=10,
                    timeout=10
                )
            )

            result = response.choices[0].message.content.strip().lower()
            success = "test" in result

            if success:
                logger.info("AI service connection test successful")
            else:
                logger.warning(f"AI service connection test failed: unexpected response '{result}'")

            return success

        except Exception as e:
            logger.error(f"AI service connection test failed: {e}")
            return False
