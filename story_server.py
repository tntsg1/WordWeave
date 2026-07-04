#!/usr/bin/env python3
"""
WordWeave — Vocabulary Story Generator
上传任意单词表（一行一单词），自动用 AI 生成英文小故事。
目标单词高亮加粗，附带中文释义。

Usage:
    python story_server.py
    浏览器打开 http://localhost:8888
"""

import http.server
import urllib.request
import urllib.parse
import json
import random
import os
import sys
import re
from pathlib import Path
from io import BytesIO

# ===== CONFIG =====
PORT = 8888
WORDS_PER_STORY = 12
WORDLISTS_DIR = Path(__file__).parent / "wordlists"

# API Key
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

def ensure_wordlists_dir():
    WORDLISTS_DIR.mkdir(exist_ok=True)

def list_wordlists():
    ensure_wordlists_dir()
    lists = []
    for f in sorted(WORDLISTS_DIR.glob("*.txt")):
        with open(f, 'r', encoding='utf-8') as fh:
            count = sum(1 for l in fh if l.strip())
        lists.append({"name": f.stem, "file": f.name, "count": count})
    return lists

def load_wordlist(name):
    path = WORDLISTS_DIR / f"{name}.txt"
    if not path.exists():
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def save_wordlist(name, content):
    ensure_wordlists_dir()
    # Sanitize filename
    safe = re.sub(r'[^\w\-_]', '_', name)
    path = WORDLISTS_DIR / f"{safe}.txt"
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return safe

def delete_wordlist(name):
    path = WORDLISTS_DIR / f"{name}.txt"
    if path.exists():
        path.unlink()
        return True
    return False

def generate_grammar_story():
    """Generate a grammar-rich entertaining story with simple vocabulary."""
    prompt = """You are a witty English writer. Write a short, entertaining story (100-150 words) that uses COMPLEX GRAMMAR but SIMPLE VOCABULARY.

Style: dark humor, gossip, or juicy drama — NOT lame jokes. Think: "my coworker's disastrous wedding" or "the scandal at the retirement home".

Use at least 5 of these grammar structures:
- Subjunctive mood (If I were..., I wish..., It's time that...)
- Inversion (Not only did he..., Never have I..., Had I known...)
- Conditional type 3 (If she had... she would have...)
- Relative clauses (the guy who..., the thing that...)
- Passive voice in complex tenses
- Cleft sentences (It was... that..., What I need is...)
- Participial phrases

Vocabulary must be EASY — words a middle schooler knows. The complexity comes from HOW you arrange them, not the words themselves.

Reply in JSON:
{
  "story": "The story text...",
  "grammar": ["grammar point 1 used", "grammar point 2 used", ...],
  "chinese": "全文中文翻译"
}
"""
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 1.0,
        "max_tokens": 1200
    }
    req = urllib.request.Request(
        f"{API_BASE}/chat/completions",
        data=json.dumps(payload).encode('utf-8'),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = json.loads(resp.read().decode('utf-8'))
        content = raw['choices'][0]['message']['content'].strip()
        if content.startswith('```'):
            content = content.split('\n', 1)[1].rstrip('```').strip()
        data = json.loads(content)
        return data.get('story', ''), data.get('grammar', []), data.get('chinese', '')


def generate_story(words):
    word_list = ', '.join(words)
    system_prompt = """You are a creative English writer. Write a short, engaging story (100-180 words) in natural English.
The story MUST naturally incorporate ALL of the provided vocabulary words.
Make the story coherent and interesting.

After the story, provide:
1. A full Chinese translation of the entire story (natural, flowing Chinese)
2. Chinese translation for EVERY word in the story (not just target words)

Reply in this exact JSON format:
{
  "story": "The full story text here...",
  "all_words": {"every": "每个", "word": "单词", "in": "在", "the": "这", "story": "故事", ...},
  "chinese": "全文中文翻译"
}

IMPORTANT: 
- The story text must NOT contain any markdown, HTML tags, or special formatting. Just plain English text.
- "all_words" must contain EVERY unique word that appears in the story (lowercase). This includes common words like "the", "a", "is", etc.
- Each translation should be concise (1-4 Chinese characters).
- "chinese" should be a natural, paragraph-length Chinese translation of the entire story.
- Keep the story SHORT and CONCISE. 100-180 words is ideal."""

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

    with urllib.request.urlopen(req, timeout=90) as resp:
        raw_data = json.loads(resp.read().decode('utf-8'))
        content = raw_data['choices'][0]['message']['content']
        content = content.strip()
        if content.startswith('```'):
            lines = content.split('\n')
            content = '\n'.join(lines[1:])
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()
        if content.startswith("'") and content.endswith("'"):
            content = content[1:-1]

        # Robust JSON parse with fallback
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            # Try to recover: extract story and chinese by regex
            result = {}
            story_match = re.search(r'"story"\s*:\s*"((?:[^"\\]|\\.)*)"', content, re.DOTALL)
            if story_match:
                result['story'] = story_match.group(1).replace('\\n', '\n').replace('\\"', '"')
            chinese_match = re.search(r'"chinese"\s*:\s*"((?:[^"\\]|\\.)*)"', content, re.DOTALL)
            if chinese_match:
                result['chinese'] = chinese_match.group(1).replace('\\n', '\n').replace('\\"', '"')
            # Try to parse partial all_words
            all_words = {}
            for m in re.finditer(r'"(\w+)"\s*:\s*"((?:[^"\\]|\\.)*)"', content):
                all_words[m.group(1).lower()] = m.group(2)
            result['all_words'] = all_words if all_words else {}
            if not result.get('story'):
                raise ValueError("Could not recover story from response")

        story = result.get('story', result.get('story_text', ''))
        all_words = result.get('all_words', result.get('translations', {}))
        chinese = result.get('chinese', result.get('chinese_translation', ''))
        return story, all_words, chinese


def format_story(story_text, target_words, all_words_dict):
    story_html = story_text
    translation_html = story_text
    sorted_words = sorted(target_words, key=len, reverse=True)
    for word in sorted_words:
        zh = all_words_dict.get(word, all_words_dict.get(word.lower(), ''))
        pattern = re.compile(r'\b(' + re.escape(word) + r')\b', re.IGNORECASE)
        # English section: bold + clickable
        story_html = pattern.sub(
            lambda m, z=zh: f'<b class="vocab" data-zh="{z}" onclick="showPopup(event, this)">{m.group(1)}</b>',
            story_html
        )
        if zh:
            translation_html = pattern.sub(
                lambda m, z=zh: f'<b class="vocab" data-zh="{z}" onclick="showPopup(event, this)">{m.group(1)}</b><span class="zh">（{z}）</span>',
                translation_html
            )
        else:
            translation_html = pattern.sub(
                lambda m: f'<b class="vocab" data-zh="" onclick="showPopup(event, this)">{m.group(1)}</b>',
                translation_html
            )
    return story_html, translation_html, all_words_dict


def wrap_all_words(html, all_words_dict):
    """Wrap every plain-text word in clickable spans, using all_words_dict for translations."""
    import re as _re
    result = []
    parts = _re.split(r'(<[^>]+>)', html)
    for part in parts:
        if part.startswith('<'):
            result.append(part)
        else:
            def replace_word(m):
                word = m.group(1)
                zh = all_words_dict.get(word.lower(), '')
                if zh:
                    return f'<span class="word" data-zh="{zh}" onclick="showPopupWord(event, this)">{word}</span>'
                return f'<span class="word" data-zh="" onclick="showPopupWord(event, this)">{word}</span>'
            wrapped = _re.sub(r"(\b[a-zA-Z][\w'-]*\b)", replace_word, part)
            result.append(wrapped)
    return ''.join(result)


PAGE_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WordWeave · 单词故事</title>
<style>
  :root { --bg: #0d1117; --card: #161b22; --border: #30363d; --text: #c9d1d9; --heading: #f0f6fc; --accent: #ffa657; --green: #7ee787; --blue: #58a6ff; --btn: #238636; --btn-hover: #2ea043; --danger: #da3633; --dim: #8b949e; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Segoe UI', 'Noto Sans SC', system-ui, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; display: flex; flex-direction: column; align-items: center; padding: 1.5rem; }
  .container { max-width: 860px; width: 100%; }
  h1 { text-align: center; font-size: 1.7rem; color: var(--heading); margin-bottom: 0.2rem; }
  .subtitle { text-align: center; color: var(--dim); font-size: 0.85rem; margin-bottom: 1.5rem; }

  /* --- Toolbar --- */
  .toolbar { display: flex; gap: 10px; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; }
  .toolbar select { background: var(--card); color: var(--text); border: 1px solid var(--border); padding: 6px 12px; border-radius: 6px; font-size: 0.9rem; min-width: 180px; }
  .toolbar .btn-sm { font-size: 0.85rem; padding: 6px 14px; border-radius: 6px; border: 1px solid var(--border); cursor: pointer; text-decoration: none; background: var(--card); color: var(--text); white-space: nowrap; }
  .toolbar .btn-sm.danger { color: var(--danger); border-color: var(--danger); }
  .toolbar .btn-sm.danger:hover { background: var(--danger); color: #fff; }
  .toolbar .btn-sm:hover { background: #21262d; }
  .toolbar .info { font-size: 0.8rem; color: var(--dim); margin-left: auto; }

  /* --- Upload --- */
  .upload-area { background: var(--card); border: 2px dashed var(--border); border-radius: 10px; padding: 20px; text-align: center; margin-bottom: 1rem; cursor: pointer; transition: border-color 0.2s; }
  .upload-area:hover { border-color: var(--blue); }
  .upload-area input[type=file] { display: none; }
  .upload-area p { color: var(--dim); font-size: 0.9rem; }
  .upload-area .name-hint { color: var(--blue); }
  .upload-row { display: flex; gap: 10px; align-items: center; margin-top: 10px; justify-content: center; }
  .upload-row input[type=text] { background: var(--bg); color: var(--text); border: 1px solid var(--border); padding: 6px 10px; border-radius: 6px; font-size: 0.9rem; width: 200px; }
  .upload-row button { background: var(--btn); color: #fff; border: none; padding: 7px 16px; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }
  .upload-row button:hover { background: var(--btn-hover); }

  /* --- Story area --- */
  .words-bar { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; margin-bottom: 1rem; display: flex; flex-wrap: wrap; gap: 6px; justify-content: center; }
  .words-bar span { background: #1f6feb22; color: var(--blue); border: 1px solid #1f6feb44; padding: 2px 9px; border-radius: 11px; font-size: 0.82rem; }
  .section-title { font-size: 1.05rem; color: var(--heading); margin: 1rem 0 0.6rem; padding-bottom: 5px; border-bottom: 1px solid var(--border); }
  .story, .translation { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 22px; margin-bottom: 1.2rem; line-height: 1.9; font-size: 1rem; text-align: justify; font-family: 'Georgia', 'Noto Serif SC', serif; }
  .story b, .translation b { color: var(--accent); font-weight: 700; }
  .translation .zh { color: var(--green); font-size: 0.88rem; }
  .refresh-hint { text-align: center; color: #484f58; font-size: 0.8rem; margin: 0.5rem 0; }
  .refresh-hint kbd { background: #21262d; border: 1px solid var(--border); border-radius: 4px; padding: 1px 5px; font-family: monospace; }
  .btn { display: inline-block; background: var(--btn); color: #fff; border: none; padding: 9px 22px; border-radius: 6px; cursor: pointer; font-size: 0.95rem; text-decoration: none; transition: background 0.2s; }
  .btn:hover { background: var(--btn-hover); }
  .center { text-align: center; margin-top: 1rem; }
  .error-box { background: #49020233; border: 1px solid #f8514966; border-radius: 8px; padding: 16px; color: #f85149; margin-bottom: 1rem; }
  .hidden { display: none; }
  .toast { position: fixed; top: 16px; right: 16px; background: var(--btn); color: #fff; padding: 10px 18px; border-radius: 8px; font-size: 0.9rem; z-index: 999; opacity: 0; transition: opacity 0.3s; pointer-events: none; }
  .toast.show { opacity: 1; }

  /* Loading spinner */
  .spinner { display: inline-block; width: 18px; height: 18px; border: 2px solid var(--dim); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.8s linear infinite; vertical-align: middle; margin-right: 6px; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .loading-text { color: var(--dim); font-style: italic; }

  /* --- Popup --- */
  .vocab-popup { position: fixed; background: #1a1f2e; border: 1px solid var(--accent); border-radius: 8px; padding: 8px 14px; color: #fff; font-size: 0.9rem; z-index: 9999; pointer-events: none; opacity: 0; transform: translateY(4px); transition: opacity 0.15s, transform 0.15s; box-shadow: 0 4px 16px rgba(0,0,0,0.5); max-width: 220px; text-align: center; }
  .vocab-popup.show { opacity: 1; transform: translateY(0); }
  .vocab-popup .zh-big { font-size: 1.3rem; font-weight: 700; color: var(--green); }
  .vocab-popup .en-sm { font-size: 0.8rem; color: var(--dim); margin-top: 2px; }
  .vocab { cursor: pointer; border-bottom: 1px dashed var(--accent); }
  .vocab:hover { background: rgba(255,166,87,0.15); border-radius: 3px; }
  .word { cursor: pointer; }
  .word:hover { background: rgba(88,166,255,0.12); border-radius: 2px; }

  /* --- Grammar section --- */
  .grammar-title { color: #d2a8ff; margin-top: 2rem; }
  .grammar-card { background: var(--card); border: 1px solid #d2a8ff33; border-radius: 10px; padding: 20px; margin-bottom: 1.5rem; }
  .grammar-story { line-height: 1.9; font-size: 1rem; text-align: justify; font-family: 'Georgia', 'Noto Serif SC', serif; margin-bottom: 0.8rem; }
  .grammar-points { background: #1a1228; border: 1px solid #d2a8ff22; border-radius: 8px; padding: 12px 16px; margin-top: 12px; }
  .grammar-points .gp { color: #d2a8ff; font-size: 0.85rem; padding: 3px 0; }
  .grammar-points .gp::before { content: '▸ '; color: #8b949e; }
  .grammar-chinese { margin-top: 12px; color: var(--dim); font-size: 0.92rem; line-height: 1.8; }

</style>
</head>
<body>
<div class="container">
  <h1>📖 WordWeave</h1>
  <p class="subtitle">单词故事生成器 · 上传你的词库，AI 编故事</p>

  <!-- Toast -->
  <div class="toast" id="toast"></div>

  <!-- Vocab popup -->
  <div class="vocab-popup" id="vocabPopup"><div class="zh-big"></div><div class="en-sm"></div></div>

  <!-- Upload area -->
  <div class="upload-area" id="uploadArea" onclick="document.getElementById('fileInput').click()">
    <p>📂 拖放或点击上传单词表 <span class="name-hint">（.txt，一行一个单词）</span></p>
    <input type="file" id="fileInput" accept=".txt" onchange="onFileSelected(event)">
    <div class="upload-row hidden" id="uploadRow">
      <input type="text" id="listName" placeholder="输入词库名称">
      <button onclick="doUpload()">⬆️ 上传</button>
    </div>
  </div>

  <!-- Toolbar -->
  <div class="toolbar">
    <select id="listSelect" onchange="switchList()"></select>
    <button class="btn-sm danger hidden" id="deleteBtn" onclick="deleteList()">🗑 删除</button>
    <span class="info" id="wordCount"></span>
  </div>

  <!-- Grammar Practice Section -->
  <div class="section-title grammar-title">🧠 语法实战 · 地狱难度</div>
  <div class="grammar-card" id="grammarCard">
    <div class="grammar-story" id="grammarStory"></div>
    <div class="grammar-points hidden" id="grammarPoints"></div>
    <div class="grammar-chinese hidden" id="grammarChinese"></div>
    <div class="loading-text" id="grammarLoading">⏳ <span class="spinner"></span> AI 正在编...</div>
    <button class="btn-sm" style="margin-top:10px;" onclick="loadGrammarStory()">🔄 换一篇</button>
  </div>

  <!-- Word Story Section -->
  <p class="refresh-hint">按 <kbd>F5</kbd> 或点击按钮刷新，生成新故事</p>

  <!-- Loading -->
  <div class="center loading-text hidden" id="loading">⏳ <span class="spinner"></span> AI 正在编故事...</div>

  <!-- Story area — replaced by server -->
  <div id="storyArea"></div>

  <div class="center">
    <a class="btn" href="javascript:location.reload()">🔄 换一个故事</a>
  </div>

  <div class="error-box hidden" id="errorBox"></div>
</div>

<script>
let currentList = '__CURRENT__';

async function fetchLists() {
  const r = await fetch('/api/lists');
  const data = await r.json();
  const sel = document.getElementById('listSelect');
  sel.innerHTML = '';
  data.lists.forEach(l => {
    const opt = document.createElement('option');
    opt.value = l.name;
    opt.textContent = `${l.name} (${l.count} 词)`;
    opt.selected = (l.name === currentList);
    sel.appendChild(opt);
  });
  document.getElementById('wordCount').textContent = '';
  const active = data.lists.find(l => l.name === currentList);
  if (active) document.getElementById('wordCount').textContent = `共 ${active.count} 词`;
  document.getElementById('deleteBtn').classList.toggle('hidden', !active || active.name === 'TD_SAT_Golden_Words');
}

function switchList() {
  const name = document.getElementById('listSelect').value;
  window.location.href = '/?list=' + encodeURIComponent(name);
}

async function deleteList() {
  if (!confirm('确定删除这个词库？')) return;
  await fetch('/api/delete?list=' + encodeURIComponent(currentList), { method: 'POST' });
  toast('已删除');
  window.location.href = '/';
}

function onFileSelected(e) {
  const file = e.target.files[0];
  if (!file) return;
  const row = document.getElementById('uploadRow');
  row.classList.remove('hidden');
  const nameInput = document.getElementById('listName');
  nameInput.value = file.name.replace(/\.txt$/i, '');
}

async function doUpload() {
  const file = document.getElementById('fileInput').files[0];
  const name = document.getElementById('listName').value.trim();
  if (!file || !name) return toast('请选择文件并输入名称');
  const form = new FormData();
  form.append('file', file);
  form.append('name', name);
  const r = await fetch('/upload', { method: 'POST', body: form });
  if (r.ok) {
    toast('上传成功！');
    window.location.href = '/?list=' + encodeURIComponent(name);
  } else {
    const t = await r.text();
    toast('上传失败: ' + t);
  }
}

function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2500);
}

// Drag & drop
const ua = document.getElementById('uploadArea');
ua.addEventListener('dragover', e => { e.preventDefault(); ua.style.borderColor = 'var(--accent)'; });
ua.addEventListener('dragleave', () => ua.style.borderColor = '');
ua.addEventListener('drop', e => {
  e.preventDefault();
  ua.style.borderColor = '';
  const file = e.dataTransfer.files[0];
  if (file && file.name.endsWith('.txt')) {
    document.getElementById('fileInput').files = e.dataTransfer.files;
    onFileSelected({ target: { files: [file] } });
  }
});

fetchLists();

// --- Grammar story ---
async function loadGrammarStory() {
  const card = document.getElementById('grammarCard');
  const storyEl = document.getElementById('grammarStory');
  const pointsEl = document.getElementById('grammarPoints');
  const chineseEl = document.getElementById('grammarChinese');
  const loadingEl = document.getElementById('grammarLoading');

  storyEl.innerHTML = '';
  pointsEl.innerHTML = '';
  pointsEl.classList.add('hidden');
  chineseEl.classList.add('hidden');
  loadingEl.classList.remove('hidden');

  try {
    const r = await fetch('/api/grammar');
    const data = await r.json();
    if (data.error) throw new Error(data.error);

    storyEl.innerHTML = '<p>' + data.story.replace(/\n\n/g, '</p><p>').replace(/\n/g, '<br>') + '</p>';

    if (data.grammar && data.grammar.length) {
      pointsEl.innerHTML = '<div style="color:#d2a8ff;font-weight:700;margin-bottom:4px;">📐 语法点</div>' +
        data.grammar.map(g => '<div class="gp">' + g + '</div>').join('');
      pointsEl.classList.remove('hidden');
    }

    if (data.chinese) {
      chineseEl.innerHTML = '<div style="color:#d2a8ff;font-weight:700;margin-bottom:4px;">🇨🇳 中文翻译</div>' + data.chinese;
      chineseEl.classList.remove('hidden');
    }
  } catch(e) {
    storyEl.innerHTML = '<p style="color:var(--danger);">❌ ' + e.message + '</p>';
  }
  loadingEl.classList.add('hidden');
}
loadGrammarStory();

// --- Vocab popup ---
let popupTimer = null;
const popup = document.getElementById('vocabPopup');

function showPopup(e, el) {
  e.stopPropagation();
  const zh = el.getAttribute('data-zh');
  const en = el.textContent;
  popup.querySelector('.zh-big').textContent = zh;
  popup.querySelector('.en-sm').textContent = en;

  const rect = el.getBoundingClientRect();
  let top = rect.top - popup.offsetHeight - 8;
  let left = rect.left + rect.width/2 - popup.offsetWidth/2;
  if (top < 8) top = rect.bottom + 8;
  if (left < 8) left = 8;
  if (left + popup.offsetWidth > window.innerWidth - 8) left = window.innerWidth - popup.offsetWidth - 8;

  popup.style.top = top + 'px';
  popup.style.left = left + 'px';
  popup.classList.add('show');

  clearTimeout(popupTimer);
  popupTimer = setTimeout(() => popup.classList.remove('show'), 2500);
}

document.addEventListener('click', () => popup.classList.remove('show'));

// --- Any-word popup (中英对照区所有单词) ---
function showPopupWord(e, el) {
  e.stopPropagation();
  const zh = el.getAttribute('data-zh') || '';
  const en = el.textContent.trim();

  if (zh) {
    popup.querySelector('.zh-big').textContent = zh;
    popup.querySelector('.en-sm').textContent = en;
  } else {
    popup.querySelector('.zh-big').textContent = en;
    popup.querySelector('.en-sm').textContent = '—';
  }

  const rect = el.getBoundingClientRect();
  let top = rect.top - popup.offsetHeight - 8;
  let left = rect.left + rect.width/2 - popup.offsetWidth/2;
  if (top < 8) top = rect.bottom + 8;
  if (left < 8) left = 8;
  if (left + popup.offsetWidth > window.innerWidth - 8) left = window.innerWidth - popup.offsetWidth - 8;

  popup.style.top = top + 'px';
  popup.style.left = left + 'px';
  popup.classList.add('show');

  clearTimeout(popupTimer);
  popupTimer = setTimeout(() => popup.classList.remove('show'), 2000);
}
</script>
</body>
</html>"""


STORY_SECTION = """
  <div class="words-bar">{word_tags}</div>
  <div class="section-title">📝 英文故事（目标单词 <b>加粗</b>）</div>
  <div class="story">{story_html}</div>
  <div class="section-title">🔤 中英对照（点击单词看释义）</div>
  <div class="translation" id="transBox">{translation_html}</div>
  <div class="section-title">🇨🇳 全文中文翻译</div>
  <div class="translation chinese">{chinese_html}</div>
"""

ERROR_SECTION = """
  <div class="error-box"><b>❌ 生成失败</b><br>{error}</div>
"""


def build_story_html(story_text, all_words_dict, chinese, target_words):
    story_html, translation_html, all_words_dict = format_story(story_text, target_words, all_words_dict)
    story_html = story_html.replace('\n\n', '</p><p>').replace('\n', '<br>')
    story_html = f'<p>{story_html}</p>'
    translation_html = translation_html.replace('\n\n', '</p><p>').replace('\n', '<br>')
    translation_html = f'<p>{translation_html}</p>'
    chinese_html = f'<p>{chinese.replace(chr(10), "</p><p>")}</p>' if chinese else '<p style="color:var(--dim);">（未生成）</p>'
    # Wrap every word in translation section as clickable
    translation_html = wrap_all_words(translation_html, all_words_dict)
    word_tags = '\n    '.join(f'<span>{w}</span>' for w in target_words)
    return STORY_SECTION.format(
        word_tags=word_tags,
        story_html=story_html,
        translation_html=translation_html,
        chinese_html=chinese_html
    )


class WordWeaveHandler(http.server.BaseHTTPRequestHandler):

    def _json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html, code=200):
        body = html.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, msg, code=400):
        self._html(f'<html><body style="font-family:sans-serif;background:#0d1117;color:#f85149;padding:2rem;"><h2>Error</h2><p>{msg}</p></body></html>', code)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        # API: list wordlists
        if path == '/api/lists':
            return self._json({"lists": list_wordlists()})

        # API: grammar story
        if path == '/api/grammar':
            try:
                story, grammar, chinese = generate_grammar_story()
                return self._json({"story": story, "grammar": grammar, "chinese": chinese})
            except Exception as e:
                return self._json({"error": str(e)}, 500)

        # Main page
        if path == '/' or path == '':
            list_name = (qs.get('list', [None])[0] or '').strip()
            wordlists = list_wordlists()

            # Pick list
            active_list = None
            if list_name:
                active_list = next((l for l in wordlists if l['name'] == list_name), None)
            if not active_list and wordlists:
                active_list = wordlists[0]
            if not active_list:
                # No lists at all — show bare upload page
                page = PAGE_HTML.replace('__CURRENT__', '')
                page = page.replace('<div id="storyArea">', '<div id="storyArea"><p style="text-align:center;color:var(--dim);margin:2rem;">还没有词库，上传一个 .txt 开始吧 👆</p>')
                return self._html(page)

            words = load_wordlist(active_list['name'])
            if len(words) < 3:
                story_section = '<p style="text-align:center;color:var(--dim);margin:2rem;">词库单词太少（至少需要 3 个），请上传更多单词</p>'
            else:
                try:
                    sample = random.sample(words, min(WORDS_PER_STORY, len(words)))
                    print(f"\n📝 [{active_list['name']}] Generating story with: {', '.join(sample)}")
                    story_text, all_words_dict, chinese = generate_story(sample)
                    story_section = build_story_html(story_text, all_words_dict, chinese, sample)
                    print(f"✅ Story generated ({len(story_text.split())} words)")
                except Exception as e:
                    story_section = ERROR_SECTION.format(error=str(e))
                    print(f"❌ Error: {e}")

            page = PAGE_HTML.replace('__CURRENT__', active_list['name'])
            page = page.replace('<div id="storyArea">', f'<div id="storyArea">{story_section}')
            return self._html(page)

        # 404
        return self._error("Not found", 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        # Upload
        if path == '/upload':
            content_type = self.headers.get('Content-Type', '')
            if 'multipart/form-data' not in content_type:
                return self._error("Expected multipart/form-data", 400)

            # Parse multipart
            boundary = content_type.split('boundary=')[1].strip()
            body = self.rfile.read(int(self.headers.get('Content-Length', 0)))

            # Simple multipart parser
            parts = body.split(b'--' + boundary.encode())
            name_val = None
            file_content = None

            for part in parts:
                if b'Content-Disposition' not in part:
                    continue
                headers, _, data = part.partition(b'\r\n\r\n')
                data = data.rstrip(b'\r\n--')

                hdr_text = headers.decode('utf-8', errors='replace')
                if 'name="name"' in hdr_text:
                    name_val = data.decode('utf-8').strip()
                elif 'name="file"' in hdr_text:
                    # Skip the trailing boundary marker
                    file_content = data

            if not name_val or not file_content:
                return self._error("Missing name or file", 400)

            safe_name = save_wordlist(name_val, file_content.decode('utf-8', errors='replace'))
            print(f"📂 Uploaded wordlist: {safe_name}")
            return self._html("<html><body style='font-family:sans-serif;background:#0d1117;color:#7ee787;padding:2rem;text-align:center;'><h2>✅ 上传成功</h2><p><a href='/?list=" + urllib.parse.quote(safe_name) + "' style='color:#58a6ff;'>点击查看</a></p></body></html>")

        # Delete wordlist
        if path == '/api/delete':
            list_name = (qs.get('list', [None])[0] or '').strip()
            if not list_name:
                return self._error("Missing list name", 400)
            if list_name == 'TD_SAT_Golden_Words':
                return self._error("不能删除默认词库", 403)
            if delete_wordlist(list_name):
                return self._json({"ok": True})
            return self._error("Not found", 404)

        return self._error("Not found", 404)

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {args[0]}")


def main():
    ensure_wordlists_dir()

    # Seed with default SAT list if wordlists/ is empty
    default_source = Path(__file__).parent / "TD_SAT_Golden_Words.txt"
    default_dest = WORDLISTS_DIR / "TD_SAT_Golden_Words.txt"
    if default_source.exists() and not default_dest.exists():
        import shutil
        shutil.copy(default_source, default_dest)
        print("📋 已导入默认 SAT 词库")

    print(f"""
╔══════════════════════════════════════════╗
║       📖 WordWeave · 单词故事          ║
║   浏览器打开: http://localhost:{PORT}     ║
║   上传 .txt → 自动编故事               ║
║   按 F5 刷新 → 换新故事               ║
╚══════════════════════════════════════════╝
""")
    if API_KEY == "YOUR_API_KEY_HERE":
        print("⚠️  警告: 未设置 API Key！请编辑 .env 文件\n")

    wl = list_wordlists()
    print(f"📚 已加载词库: {len(wl)} 个")
    for l in wl:
        print(f"   · {l['name']} ({l['count']} 词)")
    print()

    server = http.server.HTTPServer(('127.0.0.1', PORT), WordWeaveHandler)
    print(f"✅ 服务器已启动 → http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 已停止")
        server.shutdown()


if __name__ == '__main__':
    main()
