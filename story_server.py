#!/usr/bin/env python3
"""
SAT Vocabulary Story Generator
每次刷新页面自动生成包含SAT单词的英文小故事，目标单词加粗，
下方附带同样故事但单词后标注中文释义。

Usage:
    python story_server.py
    浏览器打开 http://localhost:8888
"""

import http.server
import urllib.request
import json
import random
import os
import sys
from pathlib import Path

# ===== CONFIG =====
PORT = 8888
WORDS_FILE = Path(__file__).parent / "TD_SAT_Golden_Words.txt"
WORDS_PER_STORY = 12

# API Key: 优先环境变量 → 本地 .env 文件
def _load_api_key():
    key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if key:
        return key
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    k, v = line.split('=', 1)
                    if k.strip() in ('DEEPSEEK_API_KEY', 'OPENAI_API_KEY'):
                        return v.strip().strip('"').strip("'")
    return "YOUR_API_KEY_HERE"

API_KEY = _load_api_key()
API_BASE = os.environ.get("API_BASE", "https://api.deepseek.com/v1")
MODEL = os.environ.get("STORY_MODEL", "deepseek-chat")

# ==================

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SAT 单词故事生成器</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Georgia', 'Times New Roman', 'Noto Serif SC', serif; background: #0d1117; color: #c9d1d9; min-height: 100vh; display: flex; flex-direction: column; align-items: center; padding: 2rem; }
  .container { max-width: 800px; width: 100%; }
  h1 { text-align: center; font-size: 1.8rem; margin-bottom: 0.3rem; color: #f0f6fc; }
  .subtitle { text-align: center; color: #8b949e; margin-bottom: 2rem; font-size: 0.9rem; }
  .words-bar { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px 16px; margin-bottom: 1.5rem; display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
  .words-bar span { background: #1f6feb22; color: #58a6ff; border: 1px solid #1f6feb44; padding: 3px 10px; border-radius: 12px; font-size: 0.85rem; }
  .section-title { font-size: 1.1rem; color: #f0f6fc; margin-bottom: 0.8rem; padding-bottom: 6px; border-bottom: 1px solid #30363d; }
  .story { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 24px; margin-bottom: 2rem; line-height: 2; font-size: 1.05rem; text-align: justify; }
  .story b { color: #ffa657; font-weight: 700; }
  .translation { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 24px; margin-bottom: 2rem; line-height: 2; font-size: 1.05rem; text-align: justify; }
  .translation b { color: #ffa657; font-weight: 700; }
  .translation .zh { color: #7ee787; font-size: 0.9rem; margin-left: 2px; }
  .refresh-hint { text-align: center; color: #484f58; font-size: 0.85rem; margin-bottom: 1rem; }
  .refresh-hint kbd { background: #21262d; border: 1px solid #30363d; border-radius: 4px; padding: 2px 6px; font-family: monospace; }
  .error { background: #49020233; border: 1px solid #f8514966; border-radius: 8px; padding: 16px; color: #f85149; margin-bottom: 1.5rem; }
  .btn { display: inline-block; background: #238636; color: #fff; border: none; padding: 10px 24px; border-radius: 6px; cursor: pointer; font-size: 1rem; transition: background 0.2s; text-decoration: none; }
  .btn:hover { background: #2ea043; }
  .center { text-align: center; margin-top: 1rem; }
</style>
</head>
<body>
<div class="container">
  <h1>📖 SAT 单词故事</h1>
  <p class="subtitle">TD SAT 黄金单词 5.0 · 刷新即换新故事</p>

  <div class="words-bar">
    {word_tags}
  </div>

  <p class="refresh-hint">按 <kbd>F5</kbd> 或点击下方按钮刷新，生成全新故事</p>

  <div class="section-title">📝 英文故事（目标单词 <b>加粗</b>）</div>
  <div class="story">
    {story_html}
  </div>

  <div class="section-title">🔤 带中文释义</div>
  <div class="translation">
    {translation_html}
  </div>

  <div class="center">
    <a class="btn" href="javascript:location.reload()">🔄 换一个故事</a>
  </div>
</div>
</body>
</html>"""


def load_words():
    if not WORDS_FILE.exists():
        print(f"ERROR: {WORDS_FILE} not found!")
        sys.exit(1)
    with open(WORDS_FILE, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]


def sample_words(all_words, n=WORDS_PER_STORY):
    return random.sample(all_words, min(n, len(all_words)))


def generate_story(words):
    """Call LLM API to generate a short story using the given words."""
    word_list = ', '.join(words)

    system_prompt = """You are a creative English writer. Write a short, engaging story (150-300 words) in natural English.
The story MUST naturally incorporate ALL of the provided vocabulary words.
Make the story coherent, interesting, and appropriate for a high school student.

After the story, you MUST provide the Chinese translation for each vocabulary word used.

Reply in this exact JSON format:
{
  "story": "The full story text here...",
  "translations": {"WORD1": "中文释义1", "WORD2": "中文释义2", ...}
}

IMPORTANT: 
- The story text must NOT contain any markdown, HTML tags, or special formatting. Just plain English text.
- Each word in "translations" must match exactly the words provided.
- Chinese translations should be concise (2-6 characters)."""

    user_prompt = f"Vocabulary words to use: {word_list}\n\nWrite a story that naturally includes ALL of these words. Make it interesting and natural-sounding."

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.9,
        "max_tokens": 2000
    }

    req = urllib.request.Request(
        f"{API_BASE}/chat/completions",
        data=json.dumps(payload).encode('utf-8'),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw_data = json.loads(resp.read().decode('utf-8'))
            content = raw_data['choices'][0]['message']['content']
            print(f"  Raw response: {content[:200]}...")

            # Strip markdown code blocks
            content = content.strip()
            if content.startswith('```'):
                lines = content.split('\n')
                content = '\n'.join(lines[1:])
                if content.endswith('```'):
                    content = content[:-3]
                content = content.strip()

            # Handle Python repr-style wrapping (single quotes around JSON)
            if content.startswith("'") and content.endswith("'"):
                content = content[1:-1]

            result = json.loads(content)
            story = result.get('story', result.get('story_text', ''))
            translations = result.get('translations', result.get('words', {}))
            if not story:
                raise ValueError(f"No story found in response: {list(result.keys())}")
            return story, translations
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        print(f"  Content was: {content[:500]}")
        raise
    except Exception as e:
        print(f"  API Error: {e}")
        raise


def format_story(story_text, words, translations):
    """Bold vocabulary words in story text and prepare translation version."""
    import re

    # Build a mapping of lowercase word -> bold version
    story_html = story_text
    translation_html = story_text

    # Sort by length descending to avoid partial matches (e.g., "act" matching inside "actual")
    sorted_words = sorted(words, key=len, reverse=True)

    for word in sorted_words:
        zh = translations.get(word, translations.get(word.lower(), ''))
        # Case-insensitive replacement preserving original case
        pattern = re.compile(r'\b(' + re.escape(word) + r')\b', re.IGNORECASE)

        story_html = pattern.sub(r'<b>\1</b>', story_html)

        if zh:
            translation_html = pattern.sub(
                lambda m: f'<b>{m.group(1)}</b><span class="zh">（{zh}）</span>',
                translation_html
            )
        else:
            translation_html = pattern.sub(r'<b>\1</b>', translation_html)

    return story_html, translation_html


def build_page(story_text, translations, words):
    story_html, translation_html = format_story(story_text, words, translations)

    # Escape for paragraph display
    story_html = story_html.replace('\n\n', '</p><p>').replace('\n', '<br>')
    story_html = f'<p>{story_html}</p>'
    translation_html = translation_html.replace('\n\n', '</p><p>').replace('\n', '<br>')
    translation_html = f'<p>{translation_html}</p>'

    word_tags = '\n    '.join(f'<span>{w}</span>' for w in words)

    # Use simple string replace to avoid format() choking on { } in story text
    page = HTML_TEMPLATE
    page = page.replace('{word_tags}', word_tags)
    page = page.replace('{story_html}', story_html)
    page = page.replace('{translation_html}', translation_html)
    return page


class StoryHandler(http.server.BaseHTTPRequestHandler):
    all_words = []
    _loaded = False

    @classmethod
    def load(cls):
        if not cls._loaded:
            cls.all_words = load_words()
            cls._loaded = True

    def do_GET(self):
        self.load()
        try:
            words = sample_words(self.all_words)
            print(f"\n📝 Generating story with words: {', '.join(words)}")
            story_text, translations = generate_story(words)
            page = build_page(story_text, translations, words)
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(page.encode('utf-8'))
            print(f"✅ Story generated ({len(story_text.split())} words)")
        except Exception as e:
            error_html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>body{{font-family:sans-serif;background:#0d1117;color:#f85149;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;}}div{{text-align:center;}}a{{color:#58a6ff;}}</style></head><body><div><h2>❌ 生成失败</h2><p>{e}</p><p>请检查 API Key 是否正确配置</p><a href="/">重试</a></div></body></html>"""
            self.send_response(500)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(error_html.encode('utf-8'))

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {args[0]}")


def main():
    print(f"""
╔══════════════════════════════════════════╗
║   📖 SAT Vocabulary Story Generator    ║
║   浏览器打开: http://localhost:{PORT}     ║
║   按 F5 或 Ctrl+R 刷新 → 新故事       ║
║   按 Ctrl+C 停止服务器                  ║
╚══════════════════════════════════════════╝
""")

    # Verify config
    if API_KEY == "YOUR_API_KEY_HERE":
        print("⚠️  警告: 未设置 API Key！")
        print("   设置方法: set DEEPSEEK_API_KEY=your-key-here")
        print("   或在系统环境变量中设置 OPENAI_API_KEY")
        print()

    print(f"📂 单词文件: {WORDS_FILE}")
    print(f"📊 单词总数: {len(load_words())}")
    print(f"🤖 模型: {MODEL}")
    print(f"🔗 API: {API_BASE}")
    print()

    server = http.server.HTTPServer(('127.0.0.1', PORT), StoryHandler)
    print(f"✅ 服务器已启动 → http://localhost:{PORT}")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 已停止")
        server.shutdown()


if __name__ == '__main__':
    main()
