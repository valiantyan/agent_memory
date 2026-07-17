# Codex Hooks（随 agent-memory 交付）

使用者安装记忆系统后，**一键安装 hooks**，即可在 Codex 中：

| 时机 | 行为 |
|------|------|
| 会话开始 / 恢复 | 自动 `context`（读 T0 + Working + 语义） |
| 回合结束 | 自动 `checkpoint`（写任务态；优先 `turn.json`） |
| 可选：用户发消息 | 含「上次/之前/怎么做」等词时再 `context` |

**不会**把对话全文写入 semantic（不当垃圾桶）。

---

## 一键安装

在**本仓库根目录**（已 `pip install -e .` 或 venv 可用）：

```bash
# 记忆根（按你的路径）
export AGENT_MEMORY_ROOT="${AGENT_MEMORY_ROOT:-$HOME/.agent-memory}"

# 标准安装（SessionStart + Stop）
bash scripts/install_codex_hooks.sh

# 同时启用「用户消息条件检索」
bash scripts/install_codex_hooks.sh --with-prompt-search
```

安装器会：

1. 复制脚本到 `~/.codex/hooks/agent-memory/`
2. 记录 `agent-memory` 路径与 `AGENT_MEMORY_ROOT`
3. **合并** `~/.codex/hooks.json`（**保留**已有 hook，例如 Muxy）
4. 先备份原 `hooks.json`

卸载（只去 agent-memory，保留其它）：

```bash
bash scripts/uninstall_codex_hooks.sh
```

---

## 安装后文件

```text
~/.codex/hooks/agent-memory/
  _common.sh
  session_start.sh
  stop_turn.sh
  user_prompt_maybe_search.sh
  agent-memory.path      # CLI 绝对路径
  memory-root.path       # 记忆根

~/.codex/hooks.json      # 已合并
~/.codex/memory-cache/   # context 输出缓存
```

---

## 与项目约定（可选，建议版本更新时写入业务仓）

Agent 每轮结束前写入（质量更好）：

```text
.agent-memory/turn.json
```

```json
{
  "project_id": "my-app",
  "goal": "…",
  "next_steps": "- …",
  "decisions": "- …"
}
```

无此文件时 Stop 仍会 **保底 checkpoint**（goal 为提示文案），保证「至少更新了任务态」。

仓库根可放 `.agent-memory-project`（一行项目 id），Stop 会自动带上 `--project-id`。

---

## 启用 Codex hooks

若 hooks 完全不跑，检查 Codex 是否开启 hooks 特性（版本不同配置名可能不同），例如 `~/.codex/config.toml`：

```toml
[features]
codex_hooks = true
```

你本机若已有 Muxy 的 `Stop` hook，通常 hooks 已可用。

---

## 手动试跑

```bash
bash ~/.codex/hooks/agent-memory/session_start.sh
head -40 ~/.codex/memory-cache/last-context.md

mkdir -p .agent-memory
echo '{"goal":"试钩子","next_steps":"- 验收","project_id":"demo"}' > .agent-memory/turn.json
bash ~/.codex/hooks/agent-memory/stop_turn.sh
agent-memory recent --n 3
```

---

## 安全

- hook **exit 0**，避免打断 Codex
- 不写 semantic 全文
- 不在日志中打印密钥
