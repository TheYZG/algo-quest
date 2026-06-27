# PixelQuest — 算法大陆闯关刷题网站

> 基于 doocs/leetcode 3,971 题数据集构建的游戏化刷题平台

## 当前状态

**风格：** 杂志排版（Playfair Display + Space Grotesk），6套内置主题
**进度：** 前端 Demo 完成，待后端判题系统对接
**Git 提交：** `80e4930` — 初始提交

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
| 三游戏模式 | ✅ | 自由探索 / 主线征程 / 秘境试炼 |
| 12 算法王国 | ✅ | 数组 字符串 数学 DP 树 图论 搜索 贪心 数据结构 数据库 杂项 混沌 |
| 关卡顺序解锁 | ✅ | 主线+自由模式均支持 |
| 战斗系统 | ✅ | 敌人HP / ATTACK / 招安 / 动画 |
| 代码编辑器 | ✅ | 5语言模板（Python/Java/C++/Go/JS） |
| 多语言题解 | ✅ | PY/JS/JAVA/CPP/GO 切换，默认隐藏 |
| 酒馆系统 | ✅ | 已AC题目回顾切磋 |
| 6套主题 | ✅ | 暗夜/晨曦/深海/翠林/紫晶/余晖，localStorage持久化 |
| 进度持久化 | ✅ | localStorage 保存 AC 记录和冒险进度 |
| 判题系统 | ❌ | 需搭建 Docker 沙箱后端 |
| 用户系统 | ❌ | 需后端 |

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

- [ ] 后端判题服务（Docker 沙箱运行代码）
- [ ] 用户注册/登录
- [ ] 批量导入完整 3,971 题数据
- [ ] 题目讨论区
- [ ] 竞赛模式
