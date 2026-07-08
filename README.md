# PixelQuest — 算法大陆闯关刷题网站

> 基于 doocs/leetcode 3,971 题数据集构建的游戏化刷题平台

## 当前状态

**进度：** 前后端集成完成，AI Agent 驱动的智能刷题平台可运行
**后端：** FastAPI + SQLite + ChromaDB + text2vec-base-chinese + DeepSeek LLM
**前端：** 原生 HTML/JS（四模式：自由探索 / 主线征程 / 秘境试炼 / AI搜索）
**Git 提交：** `5bfd4f0` — AI搜索集成到主界面 + 启动脚本修复

## 项目结构

```
quest-mode.html          ← 主程序（三模式 + 6主题 + 闯关 + 酒馆）
index.html               ← 风格对比导航页
creative-3d-galaxy.html  ← 3D 星系探索风格（Three.js）
creative-zen.html        ← 禅意枯山水风格
creative-matrix.html     ← 数据矩阵雨风格
creative-magazine.html   ← 杂志排版原型
creative-terminal.html   ← 黑客终端风格
creative-organic.html    ← 有机玻璃拟态风格
README.md                ← 本文件
.gitignore               ← 排除 solution/ 和图片
solution/                ← doocs/leetcode 数据集（不入 git）
```

## 核心功能矩阵

| 功能 | 状态 | 说明 |
|------|------|------|
| 四游戏模式 | ✅ | 自由探索 / 主线征程 / 秘境试炼 / AI语义搜索 |
| 11 算法王国 + 混沌领域 | ✅ | 每题多王国归属，73标签全量映射 |
| 关卡顺序解锁 | ✅ | 主线+自由模式均支持 |
| 战斗系统 | ✅ | 敌人HP / ATTACK / 招安 / 动画 |
| 代码编辑器 | ✅ | 5语言模板（Python/Java/C++/Go/JS） |
| 多语言题解 | ✅ | PY/JS/JAVA/CPP/GO 切换 |
| 酒馆系统 | ✅ | 已AC题目回顾 |
| 6套主题 | ✅ | 暗夜/晨曦/深海/翠林/紫晶/余晖，localStorage持久化 |
| 进度持久化 | ✅ | localStorage + SQLite 双重保存 |
| AI 判题 | ✅ | DeepSeek LLM 对比判题 + 离线 fallback |
| AI 语义搜索 | ✅ | ChromaDB + text2vec-base-chinese，自然语言搜题 |
| 三级 Agent 帮助 | ✅ | Hint/Guide/Explain，金币消耗（1/3/5） |
| 用户系统 | ✅ | JWT 注册/登录，金币经济 |
| 数据导入 | ✅ | 3971 题已导入 ChromaDB |
| 题目讨论区 | ❌ | 待实现 |
| 竞赛模式 | ❌ | 待实现 |

## 数据集

- 来源：doocs/leetcode 开源项目
- 规模：3,971 题
- 标签：73 个，归类为 11 个算法王国 + 混沌领域
- 语言：每道题含中英文题面 + 10+语言题解

## 设计迭代历程

1. 暗色IDE / 亮色学术 / 赛博朋克 → 基础方向探索
2. 像素塔防闯关 → 游戏化方向确定
3. 算法大陆 SVG 地图 → 交互地图方案（后放弃）
4. AI 生图多轮迭代 → 王国保卫战 / 手绘水彩等多种风格
5. Canvas 代码生成地图 → 纯代码可控方案
6. 5套创意风格 → 杂志排版定型
7. 杂志排版 + 闯关系统融合 → **当前方案**

## 待办

- [ ] 题目讨论区
- [ ] 竞赛模式
- [ ] API 速率限制
- [ ] 移动端适配优化
