# agent-memory v2.0.2 发布说明

| 项 | 内容 |
|----|------|
| 版本 | **2.0.2**（schema 仍为 **1.0.0**） |
| 相对 | 2.0.1 |

## 修复

1. **Hooks 双写**：`--project` 安装时默认 **剥离全局** agent-memory 的 SessionStart/Stop/UserPrompt；触发只在项目。  
   - `--global-hooks` 可强制保留全局触发（不推荐与项目同时用）。  
2. **「当前任务」优先级**：context / rules 明确 Open intent > focused Working > other items。  
3. **多任务不互抹**：`checkpoint` 写入 `working/items/wi_*.md` + `focus.json`；`working/current.md` 仅为焦点镜像。  
   - `agent-memory work list|focus|upsert`

## 升级

```bash
pip install -e ".[dev]"
bash scripts/install_codex_hooks.sh --project /path/to/kmp-music
# 确认 ~/.codex/hooks.json 中无 agent-memory-hook 触发（可有 Muxy 等）
agent-memory --version   # 2.0.2
```

## 验收

- 同 project 两次不同 goal checkpoint → `work list` 两条都在  
- `work focus` 切换 → current.md 变，旧 item 文件仍在  
- 项目+全局不再双写 events  
