"""
示例插件：Git提交前钩子

在提交前验证代码质量和提交信息。
"""

from typing import Dict, Any, List
import re
import logging
from pathlib import Path

from ..plugins import HookPlugin, PluginMetadata, PluginType

logger = logging.getLogger(__name__)


class PreCommitHook(HookPlugin):
    """提交前钩子插件"""
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="pre_commit_hook",
            version="1.0.0",
            description="Pre-commit validation hook for code quality and commit message",
            author="AI Commit Team",
            plugin_type=PluginType.HOOK,
            dependencies=[],
            config_schema={
                "check_code_quality": {"type": "boolean", "default": True},
                "check_commit_message": {"type": "boolean", "default": True},
                "max_file_size": {"type": "integer", "default": 1024 * 1024},
                "forbidden_patterns": {"type": "array", "default": ["TODO", "FIXME", "HACK"]}
            },
            permissions=["read_files", "validate_commit"],
            tags=["git", "validation", "quality"]
        )
    
    def initialize(self) -> bool:
        """初始化插件"""
        try:
            logger.info("Initializing pre-commit hook plugin")
            self._initialized = True
            return True
        except Exception as e:
            logger.error(f"Failed to initialize pre-commit hook: {e}")
            return False
    
    def cleanup(self) -> None:
        """清理插件资源"""
        logger.info("Cleaning up pre-commit hook plugin")
    
    def execute_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行提交前钩子
        
        Args:
            context: 钩子上下文
            
        Returns:
            执行结果
        """
        logger.info("Executing pre-commit hook")
        
        result = context.copy()
        result['pre_commit_results'] = {
            'passed': True,
            'warnings': [],
            'errors': [],
            'checks': {}
        }
        
        # 获取配置
        check_code_quality = self.get_config('check_code_quality', True)
        check_commit_message = self.get_config('check_commit_message', True)
        max_file_size = self.get_config('max_file_size', 1024 * 1024)
        forbidden_patterns = self.get_config('forbidden_patterns', ['TODO', 'FIXME', 'HACK'])
        
        # 检查代码质量
        if check_code_quality:
            quality_result = self._check_code_quality(context.get('staged_files', []), max_file_size, forbidden_patterns)
            result['pre_commit_results']['checks']['code_quality'] = quality_result
            if not quality_result['passed']:
                result['pre_commit_results']['passed'] = False
                result['pre_commit_results']['errors'].extend(quality_result['errors'])
            result['pre_commit_results']['warnings'].extend(quality_result['warnings'])
        
        # 检查提交信息
        if check_commit_message and 'commit_message' in context:
            message_result = self._check_commit_message(context['commit_message'])
            result['pre_commit_results']['checks']['commit_message'] = message_result
            if not message_result['passed']:
                result['pre_commit_results']['passed'] = False
                result['pre_commit_results']['errors'].extend(message_result['errors'])
            result['pre_commit_results']['warnings'].extend(message_result['warnings'])
        
        logger.info(f"Pre-commit hook completed: {'PASSED' if result['pre_commit_results']['passed'] else 'FAILED'}")
        return result
    
    def _check_code_quality(self, staged_files: List[str], max_file_size: int, forbidden_patterns: List[str]) -> Dict[str, Any]:
        """检查代码质量"""
        result = {
            'passed': True,
            'errors': [],
            'warnings': []
        }
        
        for file_path in staged_files:
            path = Path(file_path)
            if not path.exists():
                continue
            
            # 检查文件大小
            if path.stat().st_size > max_file_size:
                result['passed'] = False
                result['errors'].append(f"File too large: {file_path} ({path.stat().st_size} bytes)")
            
            # 检查文件内容
            if path.suffix in ['.py', '.js', '.ts', '.java', '.cpp', '.c']:
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                        # 检查禁止的模式
                        for pattern in forbidden_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                result['warnings'].append(f"Forbidden pattern '{pattern}' found in {file_path}")
                        
                        # 检查语法错误（Python）
                        if path.suffix == '.py':
                            self._check_python_syntax(content, file_path, result)
                
                except Exception as e:
                    result['warnings'].append(f"Could not read file {file_path}: {e}")
        
        return result
    
    def _check_python_syntax(self, content: str, file_path: str, result: Dict[str, Any]) -> None:
        """检查Python语法"""
        try:
            compile(content, file_path, 'exec')
        except SyntaxError as e:
            result['passed'] = False
            result['errors'].append(f"Syntax error in {file_path}: {e}")
    
    def _check_commit_message(self, message: str) -> Dict[str, Any]:
        """检查提交信息"""
        result = {
            'passed': True,
            'errors': [],
            'warnings': []
        }
        
        # 检查提交信息长度
        if len(message) > 200:
            result['warnings'].append("Commit message is too long (should be < 200 characters)")
        
        # 检查是否符合常规提交格式
        if not re.match(r'^(feat|fix|docs|style|refactor|test|chore)(\(.+\))?: .+', message):
            result['warnings'].append("Commit message should follow conventional commit format")
        
        # 检查是否有空提交信息
        if not message.strip():
            result['passed'] = False
            result['errors'].append("Commit message cannot be empty")
        
        return result