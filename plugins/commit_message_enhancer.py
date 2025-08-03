"""
示例插件：提交信息增强器

增强和优化提交信息，使其更加规范和详细。
"""

from typing import Dict, Any, List
import re
import logging
from pathlib import Path

from ..plugins import ProcessorPlugin, PluginMetadata, PluginType

logger = logging.getLogger(__name__)


class CommitMessageEnhancer(ProcessorPlugin):
    """提交信息增强器插件"""
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="commit_message_enhancer",
            version="1.0.0",
            description="Enhances commit messages with additional context and formatting",
            author="AI Commit Team",
            plugin_type=PluginType.PROCESSOR,
            dependencies=[],
            config_schema={
                "add_file_count": {"type": "boolean", "default": True},
                "add_branch_info": {"type": "boolean", "default": True},
                "add_issue_numbers": {"type": "boolean", "default": True},
                "max_message_length": {"type": "integer", "default": 200},
                "format_template": {"type": "string", "default": "{type}{scope}: {description}"}
            },
            permissions=["modify_commit_message"],
            tags=["git", "enhancement", "formatting"]
        )
    
    def initialize(self) -> bool:
        """初始化插件"""
        try:
            logger.info("Initializing commit message enhancer plugin")
            self._initialized = True
            return True
        except Exception as e:
            logger.error(f"Failed to initialize commit message enhancer: {e}")
            return False
    
    def cleanup(self) -> None:
        """清理插件资源"""
        logger.info("Cleaning up commit message enhancer plugin")
    
    def process(self, data: Any) -> Any:
        """
        处理提交信息
        
        Args:
            data: 输入数据（提交信息字符串或包含上下文的字典）
            
        Returns:
            处理后的提交信息
        """
        logger.info("Processing commit message enhancement")
        
        # 处理不同类型的输入
        if isinstance(data, str):
            commit_message = data
            context = {}
        elif isinstance(data, dict):
            commit_message = data.get('commit_message', '')
            context = data
        else:
            logger.error("Invalid input data type for commit message enhancer")
            return data
        
        # 获取配置
        add_file_count = self.get_config('add_file_count', True)
        add_branch_info = self.get_config('add_branch_info', True)
        add_issue_numbers = self.get_config('add_issue_numbers', True)
        max_message_length = self.get_config('max_message_length', 200)
        format_template = self.get_config('format_template', '{type}{scope}: {description}')
        
        # 增强提交信息
        enhanced_message = self._enhance_commit_message(
            commit_message, 
            context,
            add_file_count,
            add_branch_info,
            add_issue_numbers,
            max_message_length,
            format_template
        )
        
        # 返回适当格式的结果
        if isinstance(data, dict):
            result = data.copy()
            result['commit_message'] = enhanced_message
            result['enhanced'] = True
            return result
        else:
            return enhanced_message
    
    def _enhance_commit_message(self, 
                              message: str, 
                              context: Dict[str, Any],
                              add_file_count: bool,
                              add_branch_info: bool,
                              add_issue_numbers: bool,
                              max_message_length: int,
                              format_template: str) -> str:
        """增强提交信息"""
        
        # 解析现有的提交信息
        parsed = self._parse_commit_message(message)
        
        # 添加文件计数
        if add_file_count and 'staged_files' in context:
            file_count = len(context['staged_files'])
            if file_count > 0:
                parsed['body'] = f"Files changed: {file_count}\n{parsed['body']}"
        
        # 添加分支信息
        if add_branch_info and 'branch' in context:
            branch = context['branch']
            if branch and branch != 'main' and branch != 'master':
                parsed['body'] = f"Branch: {branch}\n{parsed['body']}"
        
        # 添加问题编号
        if add_issue_numbers:
            issue_numbers = self._extract_issue_numbers(context)
            if issue_numbers:
                if parsed['footer']:
                    parsed['footer'] += f"\nCloses: {', '.join(issue_numbers)}"
                else:
                    parsed['footer'] = f"Closes: {', '.join(issue_numbers)}"
        
        # 重新构建提交信息
        enhanced_message = self._build_commit_message(parsed, format_template)
        
        # 确保不超过最大长度
        if len(enhanced_message) > max_message_length:
            enhanced_message = self._truncate_message(enhanced_message, max_message_length)
        
        return enhanced_message
    
    def _parse_commit_message(self, message: str) -> Dict[str, str]:
        """解析提交信息"""
        lines = message.strip().split('\n')
        
        parsed = {
            'type': '',
            'scope': '',
            'description': '',
            'body': '',
            'footer': ''
        }
        
        if not lines:
            return parsed
        
        # 解析标题行
        title_line = lines[0]
        
        # 尝试匹配常规提交格式
        match = re.match(r'^(\w+)(?:\(([^)]+)\))?: (.+)$', title_line)
        if match:
            parsed['type'] = match.group(1)
            parsed['scope'] = match.group(2) or ''
            parsed['description'] = match.group(3)
        else:
            parsed['description'] = title_line
        
        # 解析正文和页脚
        if len(lines) > 1:
            # 找到空行分隔正文和页脚
            blank_line_index = -1
            for i, line in enumerate(lines[1:], 1):
                if not line.strip():
                    blank_line_index = i
                    break
            
            if blank_line_index > 0:
                # 有页脚
                parsed['body'] = '\n'.join(lines[1:blank_line_index])
                parsed['footer'] = '\n'.join(lines[blank_line_index+1:])
            else:
                # 只有正文
                parsed['body'] = '\n'.join(lines[1:])
        
        return parsed
    
    def _extract_issue_numbers(self, context: Dict[str, Any]) -> List[str]:
        """提取问题编号"""
        issue_numbers = []
        
        # 从分支名提取
        if 'branch' in context:
            branch = context['branch']
            branch_matches = re.findall(r'(\d+)', branch)
            issue_numbers.extend([f"#{num}" for num in branch_matches])
        
        # 从文件名提取
        if 'staged_files' in context:
            for file_path in context['staged_files']:
                file_matches = re.findall(r'(\d+)', Path(file_path).stem)
                issue_numbers.extend([f"#{num}" for num in file_matches])
        
        # 去重
        return list(set(issue_numbers))
    
    def _build_commit_message(self, parsed: Dict[str, str], format_template: str) -> str:
        """构建提交信息"""
        # 构建标题
        title = format_template.format(**parsed)
        
        # 构建完整信息
        parts = [title]
        
        if parsed['body'].strip():
            parts.append(parsed['body'].strip())
        
        if parsed['footer'].strip():
            parts.append(parsed['footer'].strip())
        
        return '\n\n'.join(parts)
    
    def _truncate_message(self, message: str, max_length: int) -> str:
        """截断提交信息"""
        if len(message) <= max_length:
            return message
        
        # 尝试保留标题
        lines = message.split('\n')
        if lines:
            title = lines[0]
            if len(title) <= max_length:
                return title
        
        # 如果标题也太长，截断标题
        return message[:max_length-3] + "..."