# Codex Hooks（agent-memory v2.0.4）

## 产品原则

1. **不改业务仓 AGENTS.md 也能用**（规则进 `~/.codex` + SessionStart 注入）  
2. **持久数据只在 `AGENT_MEMORY_ROOT`**（换电脑 = 同步该目录）  
3. 回合精华：`agent-memory turn` → `meta/pending-turn/` → Stop → `checkpoint`  
4. **多项目**：hooks 传 `context --cwd`，只注入**当前工作区项目**（2.0.4）  
5. **触发与实现分离**：脚本在 `~/.codex/hooks/agent-memory/`；触发推荐只挂**项目** `.codex/hooks.json`

## 一键安装

```bash
export AGENT_MEMORY_ROOT="${AGENT_MEMORY_ROOT:-$HOME/.agent-memory}"

# 推荐：项目触发（默认剥离全局 agent-memory 触发，防双写）
bash scripts/install_codex_hooks.sh --project /path/to/app

# 仅全局触发（无业务仓指针）
bash scripts/install_codex_hooks.sh

# 与 --project 同用且仍要全局触发（不推荐）
bash scripts/install_codex_hooks.sh --project /path/to/app --global-hooks
```

安装内容：

- `~/.codex/hooks/agent-memory/*.sh` + `agent-memory.path` / `memory-root.path`
- 有 `--project`：合并 `app/.codex/hooks.json`，**strip** 全局里的 agent-memory 触发
- `codex_hooks = true`（若可写 config.toml）
- `~/.codex/agent-memory-v2.rules.md`（可合并进 `~/.codex/AGENTS.md`）

可选：仓库根一行 `.agent-memory-project`（项目 id）。

## 行为

| 事件 | 行为 |
|------|------|
| SessionStart | `context --query … --cwd <workdir>` + v2.0.4 协议 → 注入 |
| UserPromptSubmit | `event`（session_id）+ 任务句 intent/item；启发式再 `context --cwd` |
| Stop | 读 `$ROOT/meta/pending-turn/<project>.json` → claim → checkpoint；否则 no-op + interrupt intent |

```bash
agent-memory turn --goal "..." --next-steps "- ..." --cwd .
# Stop hook 自动 checkpoint（带 project / session 若可得）
```

**不要删除** `~/.codex/hooks/agent-memory/` 目录（除非整包卸载记忆）；那是脚本实现，不是「多余全局触发」。

## 卸载

```bash
bash scripts/uninstall_codex_hooks.sh
bash scripts/uninstall_codex_hooks.sh --purge-cache
```

## 相关文档

- [`docs/RELEASE_v2.0.4.md`](../../docs/RELEASE_v2.0.4.md)
- [`docs/接入指南.md`](../../docs/接入指南.md)
- [`docs/使用手册.md`](../../docs/使用手册.md)
