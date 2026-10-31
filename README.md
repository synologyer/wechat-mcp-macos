# 微信聊天记录 · Claude 桌面版只读连接

让 Claude 桌面版直接查询本机微信聊天记录，无需逐次手动转发。支持明确选择默认微信或独立分身的数据目录。

本项目只提供 **Claude Desktop + 本机微信数据库读取**：不发消息、不自动回复、不重新签名、不定时监听。数据库在本机解密；通过工具返回给 Claude 的正文会进入 Claude 的模型服务。

## 可以做什么

| 功能 | Claude 工具 |
| --- | --- |
| 检查配置和可用密钥数量 | `connection_status` |
| 查看最近会话 | `list_chats` |
| 列出群聊 | `list_groups` |
| 读取指定会话消息 | `read_messages` |
| 搜索消息 | `search` |
| 检查指定会话的新消息数量 | `check_new` |

读取范围是**所选微信账户**，目前没有群白名单；提示词不是权限隔离。自动归档、定时日报、语音转写和长图生成不属于当前功能。

## 环境和验证范围

- macOS、Claude 桌面 App、Python 3.12；捕获密钥需要 Xcode Command Line Tools 和 Apple 自带 Python/LLDB。
- 密钥捕获只支持原生 Apple Silicon ARM64。
- 微信 4.2.0（270348）分身已验证启动捕获路线，21 个数据库密钥通过认证，并完成 MCP 实际读取。
- 通用捕获脚本另经自建程序验证；没有为发布再次重启真实微信。其他微信版本、Intel/Rosetta 和不同签名状态不保证可用。

## 从安装到使用

所有命令在项目根目录执行。路径示例必须替换为本人的实际路径。

### 1. 下载并安装

```bash
git clone https://github.com/synologyer/wechat-mcp-macos.git
cd wechat-mcp-macos
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r requirements.txt
```

### 2. 选择要读取的微信账户

数据库通常位于：

```text
~/Library/Containers/<实际 Bundle ID>/Data/Documents/xwechat_files/<账户目录>/db_storage
```

分身不一定使用默认微信的 Bundle ID。确认目录下有 `contact/contact.db`，先预览，再保存：

```bash
backend/.venv/bin/python scripts/configure_claude.py --db-dir '/你的账户目录/db_storage'
backend/.venv/bin/python scripts/configure_claude.py --db-dir '/你的账户目录/db_storage' --apply
```

此步骤配置 Claude，保留已有其他 MCP 连接并备份配置；不会提取密钥或重启微信。

### 3. 获取并验证密钥

已有本账户有效密钥可跳过捕获，直接验证导入。首次获取时，先保存草稿，**正常退出指定微信，暂时不要手动打开**；下面的工具会启动它。

```bash
PYTHONPATH="$(/usr/bin/lldb -P)" /usr/bin/python3 scripts/capture_launch_keys.py \
  --app '/Applications/工作.app' \
  --db-dir '/你的账户目录/db_storage' \
  --out "$HOME/.wechat-mcp/captured-keys.json" \
  --acknowledge-debug-launch
```

`--app` 改成你实际使用的微信 App。输出文件必须不存在。期间可能暂停、退出或要求手机确认登录；不执行管理员授权或修改签名。失败就停止排查，不要关闭系统保护。正常捕获结束后会尝试解除调试、保留微信运行；异常可能导致微信退出。

工具只保存通过目标数据库认证的密钥，不打印密钥。随后先验证数量，再安装：

```bash
backend/.venv/bin/python scripts/import_claude_keys.py \
  --source "$HOME/.wechat-mcp/captured-keys.json"
backend/.venv/bin/python scripts/import_claude_keys.py \
  --source "$HOME/.wechat-mcp/captured-keys.json" --apply
```

### 4. 在 Claude 里使用

完全退出并重新打开 Claude 桌面 App，确认本地连接 `work-wechat-readonly` 可用。可以依次说：

> 使用微信只读连接，检查连接状态。
>
> 读取文件传输助手最近一条消息。
>
> 列出微信群，找到日报群，读取最近 24 小时的消息，按群名和时间整理。

不需要再手动转发消息。Claude 是否可以持续追加到某个文件，取决于另行配置的文件访问能力，不是本读取连接自动完成的功能。

## 数据保存在哪里

| 位置 | 内容 |
| --- | --- |
| 项目目录 | 程序、依赖环境、文档和测试 |
| `~/.wechat-mcp/config.json` | 明确选择的微信数据库目录 |
| `~/.wechat-mcp/all_keys.json` | 已验证密钥，文件权限 0600 |
| `~/.wechat-mcp/decrypted/` | 私有、按账户区分的解密缓存 |
| `~/Library/Application Support/Claude/claude_desktop_config.json` | Claude MCP 连接配置 |

密钥、数据库、联系人及聊天导出不应提交到 GitHub。运行时数据保存在项目目录之外。

## 更新、故障排查与开发

完整步骤、换账户、项目迁移和常见问题见 [Claude 使用指南](docs/CLAUDE.md)。

```bash
git pull --ff-only
backend/.venv/bin/python -m pip install -r requirements.txt
# 更新后完全退出并重新打开 Claude。

# 开发测试，不需要读取真实聊天或重启微信。
backend/.venv/bin/python -m unittest discover -s tests -v
```

当前锁定 `wechat-mcp-macos==0.1.1` 和 `fastmcp==4.1.4`，升级依赖后需重新验证。

## 来源

本项目基于 [yancongya/wechat-mcp-macos](https://github.com/yancongya/wechat-mcp-macos) fork，现聚焦 Claude 桌面版。数据库读取使用同名 Python backend；密钥捕获参考 [公开的启动捕获与逐库认证方案](https://gist.github.com/acmerfight/0a01249ef72970d07a2603dbb629e80f)，本仓库独立实现捕获脚本，不引入其自动改签名流程。保留 Git 历史中的来源与贡献记录。
