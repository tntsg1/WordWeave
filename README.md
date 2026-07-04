# WordWeave — SAT Vocabulary Story Generator

AI 驱动的 SAT 单词故事生成器。每次刷新自动随机选取单词，生成一篇纯英文小故事，目标单词高亮加粗，下方附带中文释义版本。

## 效果

- 🎲 1765 个 SAT 核心词汇（TD SAT 黄金单词 5.0）
- 📖 点击刷新 → 全新故事（DeepSeek / OpenAI）
- 🟠 目标单词橙色加粗
- 🟢 中文释义紧随单词后
- 🌙 深色主题 Web UI
- 🐍 纯 Python 标准库，零 pip 依赖

## 快速开始

```bash
# 1. 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 DeepSeek 或 OpenAI key

# 2. 启动
python story_server.py

# 3. 浏览器打开
# http://localhost:8888
```

按 `F5` 或点 🔄 按钮刷新，生成新故事。

## 文件结构

```
├── story_server.py          # 主程序
├── TD_SAT_Golden_Words.txt  # 单词库（1765词）
├── .env.example             # API Key 模板
├── .gitignore
└── README.md
```
