"""
示例插件：Slack集成

将提交信息发送到Slack频道进行团队协作。
"""

import json
import logging
import requests
from typing import Dict, Any, Optional
from datetime import datetime

from ..plugins import PluginInterface, PluginMetadata, PluginType

logger = logging.getLogger(__name__)


class SlackIntegration(PluginInterface):
    """Slack集成插件"""
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="slack_integration",
            version="1.0.0",
            description="Sends commit notifications to Slack channels",
            author="AI Commit Team",
            plugin_type=PluginType.INTEGRATION,
            dependencies=[],
            config_schema={
                "webhook_url": {"type": "string", "description": "Slack webhook URL"},
                "channel": {"type": "string", "description": "Slack channel name"},
                "username": {"type": "string", "default": "AI Commit"},
                "icon_emoji": {"type": "string", "default": ":git:"},
                "notify_on_commit": {"type": "boolean", "default": True},
                "notify_on_push": {"type": "boolean", "default": True},
                "include_diff_stats": {"type": "boolean", "default": True},
                "include_file_list": {"type": "boolean", "default": False}
            },
            permissions=["send_notifications", "access_webhooks"],
            tags=["slack", "notification", "integration"]
        )
    
    def initialize(self) -> bool:
        """初始化插件"""
        try:
            logger.info("Initializing Slack integration plugin")
            
            # 验证配置
            webhook_url = self.get_config('webhook_url')
            if not webhook_url:
                logger.warning("Slack webhook URL not configured")
                return False
            
            self._initialized = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Slack integration: {e}")
            return False
    
    def cleanup(self) -> None:
        """清理插件资源"""
        logger.info("Cleaning up Slack integration plugin")
    
    def send_commit_notification(self, commit_data: Dict[str, Any]) -> bool:
        """
        发送提交通知到Slack
        
        Args:
            commit_data: 提交数据
            
        Returns:
            发送是否成功
        """
        if not self.get_config('notify_on_commit', True):
            return True
        
        webhook_url = self.get_config('webhook_url')
        if not webhook_url:
            logger.error("Slack webhook URL not configured")
            return False
        
        try:
            # 构建消息
            message = self._build_commit_message(commit_data)
            
            # 发送消息
            response = requests.post(
                webhook_url,
                json=message,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("Commit notification sent to Slack successfully")
                return True
            else:
                logger.error(f"Failed to send Slack notification: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")
            return False
    
    def send_push_notification(self, push_data: Dict[str, Any]) -> bool:
        """
        发送推送通知到Slack
        
        Args:
            push_data: 推送数据
            
        Returns:
            发送是否成功
        """
        if not self.get_config('notify_on_push', True):
            return True
        
        webhook_url = self.get_config('webhook_url')
        if not webhook_url:
            logger.error("Slack webhook URL not configured")
            return False
        
        try:
            # 构建消息
            message = self._build_push_message(push_data)
            
            # 发送消息
            response = requests.post(
                webhook_url,
                json=message,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("Push notification sent to Slack successfully")
                return True
            else:
                logger.error(f"Failed to send Slack notification: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")
            return False
    
    def _build_commit_message(self, commit_data: Dict[str, Any]) -> Dict[str, Any]:
        """构建提交消息"""
        message = {
            "username": self.get_config('username', 'AI Commit'),
            "icon_emoji": self.get_config('icon_emoji', ':git:'),
            "channel": self.get_config('channel'),
            "attachments": []
        }
        
        # 主要信息
        attachment = {
            "color": "good",
            "title": f"New Commit: {commit_data.get('commit_hash', 'unknown')[:7]}",
            "title_link": commit_data.get('commit_url', ''),
            "text": commit_data.get('commit_message', ''),
            "fields": [],
            "footer": f"{commit_data.get('author', 'Unknown')} • {commit_data.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}"
        }
        
        # 添加字段
        fields = []
        
        # 分支信息
        if 'branch' in commit_data:
            fields.append({
                "title": "Branch",
                "value": commit_data['branch'],
                "short": True
            })
        
        # 文件统计
        if self.get_config('include_diff_stats', True) and 'diff_stats' in commit_data:
            stats = commit_data['diff_stats']
            fields.append({
                "title": "Changes",
                "value": f"+{stats.get('additions', 0)} -{stats.get('deletions', 0)}",
                "short": True
            })
        
        # 文件列表
        if self.get_config('include_file_list', False) and 'files' in commit_data:
            files = commit_data['files']
            if files:
                files_text = '\n'.join([f"• {file}" for file in files[:10]])
                if len(files) > 10:
                    files_text += f"\n... and {len(files) - 10} more"
                
                fields.append({
                    "title": "Files Changed",
                    "value": files_text,
                    "short": False
                })
        
        attachment['fields'] = fields
        message['attachments'].append(attachment)
        
        return message
    
    def _build_push_message(self, push_data: Dict[str, Any]) -> Dict[str, Any]:
        """构建推送消息"""
        message = {
            "username": self.get_config('username', 'AI Commit'),
            "icon_emoji": self.get_config('icon_emoji', ':git:'),
            "channel": self.get_config('channel'),
            "attachments": []
        }
        
        # 主要信息
        attachment = {
            "color": "#36a64f",
            "title": f"Push to {push_data.get('branch', 'unknown')}",
            "title_link": push_data.get('compare_url', ''),
            "text": f"{push_data.get('commit_count', 0)} commits pushed by {push_data.get('pusher', 'Unknown')}",
            "fields": [],
            "footer": push_data.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        }
        
        # 添加字段
        fields = []
        
        # 推送信息
        fields.append({
            "title": "Repository",
            "value": push_data.get('repository', 'Unknown'),
            "short": True
        })
        
        fields.append({
            "title": "Commits",
            "value": str(push_data.get('commit_count', 0)),
            "short": True
        })
        
        # 提交列表
        if 'commits' in push_data:
            commits = push_data['commits']
            if commits:
                commits_text = '\n'.join([
                    f"• `{commit.get('hash', 'unknown')[:7]}` {commit.get('message', 'No message')}"
                    for commit in commits[:5]
                ])
                if len(commits) > 5:
                    commits_text += f"\n... and {len(commits) - 5} more"
                
                fields.append({
                    "title": "Recent Commits",
                    "value": commits_text,
                    "short": False
                })
        
        attachment['fields'] = fields
        message['attachments'].append(attachment)
        
        return message
    
    def test_connection(self) -> bool:
        """测试Slack连接"""
        webhook_url = self.get_config('webhook_url')
        if not webhook_url:
            return False
        
        try:
            test_message = {
                "text": "Test message from AI Commit",
                "username": self.get_config('username', 'AI Commit'),
                "icon_emoji": self.get_config('icon_emoji', ':git:')
            }
            
            response = requests.post(
                webhook_url,
                json=test_message,
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Slack connection test failed: {e}")
            return False