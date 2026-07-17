# agent-memory v2.0.4

| 项 | 内容 |
|----|------|
| 版本 | **2.0.4** |
| 相对 | 2.0.3 |

## 修复

多项目共享同一 `AGENT_MEMORY_ROOT` 时，在 **Vibe-ANR-Monitoring** 开会话仍注入 **kmp-music** 的 Working/focus。

### 变更

1. **context 项目解析**：`--project` > `--cwd` detect(high) > working effective  
2. **hooks**：SessionStart / UserPrompt 调用 `context --cwd <workdir>`  
3. **per-project focus**：`working/focus/<project>.json`（全局 `focus.json` 仅作 last-active）  
4. **Working 注入**：只用本项目 focus item；无 focus 时不展示外项目 `current.md`  
5. **items / intents / events**：context 内按本项目过滤  

## 升级

```bash
pip install -e ".[dev]"
bash scripts/install_codex_hooks.sh --project /path/to/repo
agent-memory --version  # 2.0.4
```
