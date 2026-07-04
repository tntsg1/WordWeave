# WordWeave — 单词故事生成器

上传任意单词表（一行一单词），AI 自动生成英文小故事。目标单词高亮加粗，附带中文释义。

## 功能

- 📂 **上传任意词库** — 拖放 .txt 文件，一行一个单词
- 🔀 **多词库管理** — 下拉切换、上传、删除
- 📖 **AI 编故事** — DeepSeek / OpenAI，每次刷新换新故事
- 🟠 目标单词**橙色加粗**
- 🟢 中文释义紧随单词后
- 🌙 深色主题
- 🐍 纯 Python 标准库，零 pip 依赖

## 快速开始

```bash
# 1. 配置 API Key
cp .env.example .env
# 编辑 .env，填入 DeepSeek 或 OpenAI key

# 2. 启动
python story_server.py

# 3. 浏览器打开 http://localhost:8888
```

上传你的 .txt 单词表，刷新即生成新故事。

## 词库格式

```
apple
banana
cherry
...
```

每行一个单词，UTF-8 编码。上传后自动出现在下拉菜单中。
