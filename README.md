# PixelQuest — 像素闯关刷题网站

## 项目概述
基于 doocs/leetcode 数据集（3,971道题）构建的闯关制刷题网站，采用游戏化设计将 LeetCode 刷题包装为 RPG 冒险体验。

## 技术栈
- 纯前端：HTML/CSS/JavaScript（单文件）
- 字体：Playfair Display + Space Grotesk + Space Mono
- 主题：6套内置主题系统
- 数据持久化：localStorage

## 三种游戏模式

### 🗺️ 自由探索
12个算法王国（数组、字符串、数学、DP、树、图论、搜索、贪心、数据结构、数据库、杂项、混沌），每个王国独立关卡，随意挑战。

### ⚔️ 主线征程
25关线性任务链，跨王国混合编排，逐步解锁。

### 🏆 秘境试炼
6个精选题单：Hot 100、剑指Offer、面试精选、动态规划专题、二叉树合集、SQL必刷。

## 核心功能
- 王国选择 → 关卡路径 → 战斗刷题 完整游戏流程
- 敌人系统：每道题是一个怪物，难度对应不同怪物和HP
- 代码编辑器：5种语言（Python/Java/C++/Go/JS），LeetCode风格模板
- 题解系统：多语言完整参考代码，默认隐藏
- 酒馆系统：回顾所有已AC题目（被招安的敌人）
- 主题切换：暗夜/晨曦/深海/翠林/紫晶/余晖 6套主题
- 进度持久化：localStorage保存已完成题目和冒险进度

## 数据集
- 来源：doocs/leetcode
- 解析73个标签，归类为11个算法王国
- 每道题含中文题面、多语言题解、难度标签

## 文件说明
- `quest-mode.html` — 主程序（杂志排版风格，全部功能）
- `creative-3d-galaxy.html` — 3D星系探索风格（Three.js）
- `creative-zen.html` — 禅意枯山水风格
- `creative-matrix.html` — 数据矩阵雨风格
- 其余 `creative-*.html` / `style-*.html` — 早期风格实验
- `index.html` — 风格对比入口页
- `Map.png` — 算法大陆地图（AI生成）
- `solution/` — doocs/leetcode 数据集副本
