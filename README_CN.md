# AI Commit

基于 OpenAI API 的 AI 驱动 Git 提交信息生成器。

[English](README.md) | **简体中文**

## 功能特性

- 自动生成清晰、描述性的提交信息
- 遵循传统提交格式 (Conventional Commits)
- 支持多种 OpenAI 模型
- 灵活的配置选项
- 丰富的命令行选项
- 详细的日志系统
- 自动提交支持
- 自动推送支持
- 分支上下文感知
- **交互式文件选择** - 选择特定文件进行分析和提交
- **自动暂存模式** - 一键暂存所有变更文件
- **智能文件发现** - 检测已暂存、未暂存和未跟踪的文件

## 安装

```bash
pip install --force-reinstall git+https://github.com/zo0043/py-ai-commit.git
```

## 使用方法

在任何 git 仓库中的基本用法：

```bash
ai-commit
```

### 增强的文件选择功能

**交互模式** - 选择特定文件进行暂存和提交：
```bash
ai-commit -i
```
这将显示所有未暂存的文件，让你选择要分析和提交的文件。

**自动暂存模式** - 自动暂存所有变更文件：
```bash
ai-commit -a
```
这将自动暂存所有未暂存的文件，然后生成提交信息。

**组合使用示例**：
```bash
# 交互选择 + 自动提交 + 详细输出
ai-commit -i -y -v

# 自动暂存所有文件并确认提交
ai-commit -a

# 交互选择 + 预览模式（不实际提交）
ai-commit -i --dry-run
```

命令行选项：

```bash
ai-commit [-h] [-y] [-c CONFIG] [-m MODEL] [--dry-run] [-v] [-i] [-a]

选项:
  -h, --help            显示帮助信息
  -y, --yes            跳过确认直接提交
  -c CONFIG, --config CONFIG
                      指定配置文件路径
  -m MODEL, --model MODEL
                      覆盖配置中的 AI 模型
  --dry-run           生成信息但不提交
  -v, --verbose       显示详细输出
  -i, --interactive   交互式选择要分析和提交的文件
  -a, --all          自动暂存所有变更文件
```

## ⚙️ 配置

你可以通过多种方式配置工具（按优先级排序）：

### 1. 环境变量（始终可用）

在你的 shell 中设置这些环境变量：

```bash
export OPENAI_API_KEY='your-api-key'
export OPENAI_BASE_URL='your-api-base-url'  
export OPENAI_MODEL='gpt-3.5-turbo'
export LOG_PATH='.commitLogs'              # 可选
export AUTO_COMMIT='false'                 # 可选
export AUTO_PUSH='false'                   # 可选
```

### 2. 配置文件

在项目根目录或任何父目录中创建 `.aicommit` 或 `.env` 文件。

#### 创建配置文件

1. 创建 `.aicommit` 或 `.env` 文件：
   - 复制 `.aicommit_template` 为 `.aicommit`
   - 编辑文件填入你的设置

#### 配置选项

```ini
OPENAI_API_KEY=your_api_key          # 必需：你的 OpenAI API 密钥
OPENAI_BASE_URL=your_api_base_url    # 必需：OpenAI API 基础 URL
OPENAI_MODEL=your_model_name         # 必需：要使用的 OpenAI 模型（如 gpt-3.5-turbo）
LOG_PATH=.commitLogs                 # 可选：日志文件目录（默认：.commitLogs）
AUTO_COMMIT=true                     # 可选：跳过确认（默认：false）
AUTO_PUSH=true                       # 可选：提交后自动推送（默认：false）
```

工具将按以下顺序搜索配置：
1. 环境变量（始终作为后备检查）
2. 命令行指定的配置文件（`-c` 选项）
3. 当前或父目录中的 `.aicommit`
4. 当前或父目录中的 `.env`

### 配置优先级

配置值按以下顺序应用（从高到低优先级）：
1. 命令行参数（最高优先级）
2. 配置文件设置（.aicommit 或 .env）
3. 环境变量（最低优先级）

## 功能详细说明

### 自动提交模式

通过以下三种方式之一启用自动提交：
1. 使用 `-y` 或 `--yes` 标志：`ai-commit -y`
2. 在配置文件中设置 `AUTO_COMMIT=true`
3. 交互式确认（默认）

### 自动推送模式

当使用 `AUTO_PUSH=true` 启用时，工具将：
1. 在提交成功后自动推送变更到远程仓库
2. 使用当前分支名进行推送
3. 只有在提交成功时才推送
4. 记录推送操作和任何错误

### 预览模式

使用 `--dry-run` 生成提交信息但不实际提交：
```bash
ai-commit --dry-run
```

### 模型选择

从命令行覆盖模型：
```bash
ai-commit -m gpt-4
```

### 详细日志

启用详细日志记录：
```bash
ai-commit -v
```

### 分支上下文

工具会自动在提交信息生成上下文中包含当前分支名，以生成更相关的信息。

### 交互式文件选择界面

```
============================================================
📁 当前 Git 状态
============================================================

✅ 已暂存文件 (2):
   1. ai_commit/cli.py
   2. README.md

📝 未暂存文件 (3):
   1. tests/test_new.py
   2. docs/api.md
   3. config/settings.json

============================================================

🎯 选择要暂存和分析的文件:
   输入文件编号，用空格分隔（如：1 3 5）
   输入 'all' 选择所有文件
   输入 'none' 跳过文件选择
   按回车完成选择

选择文件: 1 3
✅ 已选择 2 个文件:
   - tests/test_new.py
   - config/settings.json
✅ 已成功暂存 2 个文件
```

## 日志记录

日志存储在配置的 `LOG_PATH` 目录中（默认：`.commitLogs`）：
- 每日日志文件：`commit_YYYYMMDD.log`
- 包含详细信息：
  - 程序启动
  - 配置加载
  - Git 操作
  - API 调用
  - 提交过程
  - 推送操作
  - 错误和警告

## 错误处理

工具包含对以下情况的健壮错误处理：
- 缺失配置
- 无效的 API 密钥
- 网络问题（自动重试）
- Git 仓库错误
- 无效的暂存变更
- 推送失败

## 许可证

MIT