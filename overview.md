# 沙箱禁用 & 代码编辑器横向滚动 — 完成总结

## 日期
2026-07-01

## 完成事项

### 1. 沙箱执行系统已禁用
**文件**: `backend/app/api/progress.py`

- 注释掉 `_execute_python_code()` 函数（约 40 行），替换为简短注释说明
- 移除 `submit_solution()` 中沙箱并行验证块（约 25 行）
- 更新模块 docstring：标注"沙箱执行系统已禁用，全部使用 AI 大模型判题"
- 判题流程现在全部走 `_ai_evaluate()` → DeepSeek LLM 对比判题路径

### 2. 代码编辑器横向滚动
**文件**: `quest-mode.html`

- `.code-editor-wrapper`: `overflow: hidden` → `overflow-x: auto; overflow-y: hidden`，添加精美横向滚动条样式（暗色/亮色主题适配）
- `.code-textarea`: 新增 `white-space: pre; overflow-wrap: normal; word-break: normal;` 禁止长代码行自动折行
- `.code-textarea`: 新增 `overflow-x: hidden; overflow-y: auto;` 确保横向溢出交给 wrapper 统一处理，避免双重滚动条
- HTML textarea: 添加 `wrap="off"` 属性
- Light 主题：为 `.code-editor-wrapper` 横向滚动条添加浅色样式

## 技术要点

### 横向滚动设计
- **Wrapper 级横向滚动**：整个编辑器区域（行号 + 代码）作为整体横向滚动
- **Textarea 纵向滚动**：textarea 自身处理垂直滚动，行号通过 `syncScroll()` 保持同步
- **行号固定宽度**：`.line-numbers` 保持 `flex-shrink: 0` + `min-width: 52px`，不随横向滚动挤压
- 滚动条美化：暗色主题 `#30363d`，亮色主题 `#d0d0d0`

### AI 判题流程（当前唯一路径）
```
submit_solution → _ai_evaluate → _get_reference_solution (DB) → ai_judge (DeepSeek LLM)
```
