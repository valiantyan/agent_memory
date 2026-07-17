# Codex Hooks（agent-memory v2）

## 产品原则

1. **不改业务仓 AGENTS.md 也能用**（规则进 `~/.codex` + SessionStart 注入）  
2. **持久数据只在 `AGENT_MEMORY_ROOT`**（换电脑 = 同步该目录）  
3. 回合精华：`agent-memory turn` → `meta/pending-turn/` → Stop → `checkpoint`

## 一键安装

```bash
export AGENT_MEMORY_ROOT="${AGENT_MEMORY_ROOT:-$HOME/.agent-memory}"
bash scripts/install_codex_hooks.sh

# 可选：在业务仓写 hooks 指针（仍不改 AGENTS.md）
bash scripts/install_codex_hooks.sh --project /path/to/app
```

安装内容：

- `~/.codex/hooks/agent-memory/*.sh`
- 合并 `~/.codex/hooks.json`（保留 Muxy 等）
- `codex_hooks = true`
- `~/.codex/agent-memory-v2.rules.md` + 合并进 `~/.codex/AGENTS.md`

## 行为

| 事件 | 行为 |
|------|------|
| SessionStart | `context` + v2 协议 → stdout 注入 |
| Stop | 读 `$ROOT/meta/pending-turn/<project>.json`；完整则 checkpoint；否则 **no-op** |

```bash
agent-memory turn --goal "..." --next-steps "- ..." --cwd .
# Stop hook 自动 checkpoint
```

## 卸载

```bash
bash scripts/uninstall_codex_hooks.sh
bash scripts/uninstall_codex_hooks.sh --purge-cache
```
