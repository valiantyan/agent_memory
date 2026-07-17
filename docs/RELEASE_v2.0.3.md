# agent-memory v2.0.3

| 项 | 内容 |
|----|------|
| 版本 | **2.0.3** |
| 相对 | 2.0.2 |

## 修复（同项目多 Codex session）

1. **intent-draft 按 session 分文件**（`project__sess_<id>.json`），互不覆盖  
2. **event / work item / pending-turn 记录 session_id**  
3. **context** 列出全部 open intents + 全部 active work items  
4. **UserPrompt 任务类** 自动 `work upsert`（`set_focus=false`）  
5. turn/checkpoint **只清同 session 的 intent**  

## 升级

```bash
pip install -e ".[dev]"
bash scripts/install_codex_hooks.sh --project /path/to/kmp-music
agent-memory --version  # 2.0.3
```
