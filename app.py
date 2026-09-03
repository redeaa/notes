# app.py
import os
import json
import uuid
import re
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

NOTES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notes")
TAGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tags.json")

os.makedirs(NOTES_DIR, exist_ok=True)
if not os.path.exists(TAGS_FILE):
    with open(TAGS_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)


def load_tags():
    try:
        with open(TAGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def save_tags(tags):
    with open(TAGS_FILE, "w", encoding="utf-8") as f:
        json.dump(tags, f, ensure_ascii=False, indent=2)


def add_tag(tag_name):
    tag_name = (tag_name or "").strip()
    if not tag_name:
        return
    tags = load_tags()
    if tag_name not in tags:
        tags.append(tag_name)
        save_tags(tags)


def note_path(note_id):
    return os.path.join(NOTES_DIR, f"{note_id}.json")


def read_note(note_id):
    path = note_path(note_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_note(note_id, data):
    with open(note_path(note_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def list_notes():
    notes = []
    for fname in os.listdir(NOTES_DIR):
        if not fname.endswith(".json"):
            continue
        nid = fname[:-5]
        try:
            with open(os.path.join(NOTES_DIR, fname), "r", encoding="utf-8") as f:
                data = json.load(f)
            data["id"] = nid
            notes.append(data)
        except Exception:
            continue
    return notes



def extract_urls(text):
    """Извлекает все URL из текста."""
    urls = re.findall(r'https?://[^\s<>\"\')\]]+', text)
    return urls


def auto_link_urls(html):
    """Заменяет все URL в HTML на кликабельные ссылки, сохраняя существующие <a> теги."""
    temp = html

    def replace_url(match):
        url = match.group(0)
        return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a>'

    temp = re.sub(r'https?://[^\s<>"\')\]]+', replace_url, temp)
    return temp


INDEX_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Заметки \ Промты</title>
<style>
  :root {
    --bg: #f6f7fb;
    --panel: #ffffff;
    --text: #1f2430;
    --muted: #6b7280;
    --border: rgba(20, 25, 40, 0.18);
    --border-strong: rgba(20, 25, 40, 0.35);
    --accent: #3b5bdb;
    --success: #2f9e44;
    --danger: #c92a2a;
    --warning: #e67700; }

  * { box-sizing: border-box; }

  html, body {
    margin: 0; padding: 0;
    background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 14px; line-height: 1.5; }

  header {
    position: sticky; top: 0; z-index: 10;
    display: grid; grid-template-columns: auto 1fr auto;
    align-items: center; padding: 14px 22px;
    background: rgba(255,255,255,0.92); backdrop-filter: blur(10px);
    border-bottom: 1px solid var(--border); gap: 16px; }

  .new-btn {
    background: transparent; border: 1px solid var(--border); color: var(--muted);
    padding: 8px 14px; border-radius: 10px; cursor: pointer; font-size: 14px;
    transition: all 0.15s; white-space: nowrap; }
  .new-btn:hover { border-color: var(--border-strong); color: var(--text);
    background: rgba(0,0,0,0.02); }

  h1.title { margin: 0; text-align: center; font-weight: 500; font-size: 20px;
    letter-spacing: 0.5px; color: #394152; }

  .header-controls { display: flex; gap: 10px; align-items: center; }
  .search-input, .filter-select, .sort-select {
    padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px;
    font-size: 13px; background: #fff; color: var(--text); outline: none;
    transition: border-color 0.15s; }
  .search-input { width: 200px; }
  .search-input:focus, .filter-select:focus, .sort-select:focus { border-color: var(--accent); }

  main { padding: 18px 22px 40px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 14px; }

  /* Tile */
  .tile {
    position: relative; background: var(--panel); border: 1px solid var(--border-strong);
    border-radius: 14px; padding: 14px 16px; min-height: 140px; cursor: pointer;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04), inset 0 0 0 1px rgba(255,255,255,0.4);
    transition: transform 0.12s, box-shadow 0.12s, border-color 0.12s;
    overflow: hidden; user-select: none; display: flex; flex-direction: column;
    justify-content: space-between; }
  .tile:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(20,25,40,0.12); }
  .tile.pinned { border-color: var(--accent); border-width: 2px; }
  .tile .pin-icon { position: absolute; top: 8px; right: 8px; font-size: 14px; opacity: 0.6; z-index: 5; }

  /* Header row: tags + topic */
  .tile .header-row {
    display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; margin-bottom: 4px; }
  .tile .topic { font-weight: 600; font-size: 14px; line-height: 1.3; flex: 1; min-width: 0; }
  .tile .tags { display: inline-flex; gap: 4px; flex-wrap: nowrap; }
  .tile .tag { font-size: 10px; padding: 2px 6px; background: rgba(59,91,219,0.12);
    color: var(--accent); border-radius: 4px; white-space: nowrap; }

  /* Content area — text + image side by side */
  .tile .content-area {
    display: flex; gap: 8px; align-items: flex-start; margin-top: 4px; }
  .tile .preview-text {
    font-size: 11.5px; color: var(--text); white-space: pre-wrap; word-break: break-word;
    overflow: hidden; max-height: 80px; line-height: 1.4; flex: 1; min-width: 0; }

  .tile .preview-img {
    flex-shrink: 0;
    width: 80px; height: 80px;
    object-fit: cover; border-radius: 10px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15); background: #fff; }

  .tile .actions { position: absolute; top: 8px; right: 8px; display: none; gap: 4px;
    background: rgba(255,255,255,0.95); padding: 4px; border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1); z-index: 10; }
  .tile:hover .actions { display: flex; }
  .tile.pinned:hover .actions { right: 28px; }
  .tile .action-btn { background: transparent; border: none; padding: 4px 8px; border-radius: 4px;
    cursor: pointer; font-size: 13px; color: var(--muted); transition: all 0.15s;
    display: flex; align-items: center; justify-content: center; width: 28px; height: 28px; }
  .tile .action-btn:hover { background: rgba(0,0,0,0.06); color: var(--text); }

  /* Tile date */
  .tile .date {
    font-size: 10px;
    color: var(--muted);
  }

  /* Skeleton */
  .skeleton {
    background: linear-gradient(90deg,#f0f0f0 25%,#e0e0f0 50%,#f0f0f0 75%);
    background-size: 200% 100%; animation: loading 1.5s infinite; border-radius: 14px; min-height: 140px; }
  @keyframes loading { 0%{background-position:200% 0} 100%{background-position:-200% 0} }

  /* Modal */
  .modal-backdrop {
    position: fixed; inset: 0; background: rgba(20,25,40,0.4); display: none;
    align-items: center; justify-content: center; z-index: 100; backdrop-filter: blur(3px);
    opacity: 0; transition: opacity 0.2s; }
  .modal-backdrop.active { display: flex; opacity: 1; }

  .modal {
    background: #fff; border-radius: 16px; width: min(900px, 94vw); max-height: 90vh;
    display: flex; flex-direction: column; overflow: hidden;
    border: 1px solid var(--border-strong); box-shadow: 0 20px 60px rgba(0,0,0,0.25);
    transform: scale(0.95); transition: transform 0.2s; }
  .modal-backdrop.active .modal { transform: scale(1); }

  .modal header.mh {
    padding: 14px 18px; border-bottom: 1px solid var(--border);
    display: flex; justify-content: space-between; align-items: center; gap: 12px; background: #fafbfd; }
  .modal header.mh .mtitle { font-weight: 600; font-size: 16px; }
  .modal .mb { padding: 18px; overflow: auto; flex: 1; }
  .modal footer.mf {
    padding: 12px 18px; border-top: 1px solid var(--border);
    display: flex; justify-content: flex-end; gap: 10px; background: #fafbfd; }

  .btn {
    border: 1px solid var(--border-strong); background: #fff; color: var(--text);
    padding: 8px 16px; border-radius: 10px; cursor: pointer; font-size: 14px; transition: all 0.15s; }
  .btn:hover { background: #f1f3f9; }
  .btn.primary { background: var(--accent); color: #fff; border-color: var(--accent); }
  .btn.primary:hover { background: #2f4bc0; }
  .btn.ghost { background: transparent; }
  .btn.danger { color: var(--danger); border-color: rgba(201,42,42,0.4); }
  .btn.danger:hover { background: rgba(201,42,42,0.08); }

  .field { margin-bottom: 14px; }
  .field label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 6px;
    text-transform: uppercase; letter-spacing: 0.5px; font-weight: 500; }

  .field input[type=text], .field select, .field textarea {
    width: 100%; padding: 10px 12px; border: 1px solid var(--border-strong); border-radius: 10px;
    font-size: 14px; background: #fff; color: var(--text); outline: none; transition: border-color 0.15s;
    font-family: inherit; }
  .field input[type=text]:focus, .field select:focus, .field textarea:focus { border-color: var(--accent); }
  .field textarea { min-height: 120px; resize: vertical; }

  .colors { display: flex; gap: 8px; flex-wrap: wrap; }
  .color-swatch {
    width: 32px; height: 32px; border-radius: 50%; cursor: pointer; border: 2px solid transparent;
    transition: all 0.15s; box-shadow: inset 0 0 0 1px rgba(0,0,0,0.08); }
  .color-swatch.selected { border-color: #1f2430; transform: scale(1.1); }

  .tags-input { display: flex; flex-wrap: wrap; gap: 6px; padding: 8px;
    border: 1px solid var(--border-strong); border-radius: 10px; background: #fff; min-height: 42px; align-items: center; }
  .tags-input:focus-within { border-color: var(--accent); }
  .tag-item { display: flex; align-items: center; gap: 4px; padding: 4px 8px;
    background: rgba(59,91,219,0.12); color: var(--accent); border-radius: 6px; font-size: 12px; }
  .tag-item .remove-tag { cursor: pointer; font-weight: bold; opacity: 0.6; }
  .tag-item .remove-tag:hover { opacity: 1; }
  .tags-input input { border: none; outline: none; flex: 1; min-width: 100px; font-size: 13px; padding: 4px; }

  .checkbox-field { display: flex; align-items: center; gap: 8px; }
  .checkbox-field input[type=checkbox] { width: 18px; height: 18px; cursor: pointer; }
  .checkbox-field label { margin: 0; text-transform: none; font-size: 14px; color: var(--text); cursor: pointer; }

  /* ===== WYSIWYG Editor ===== */
  .editor-wrapper {
    border: 1px solid var(--border-strong);
    border-radius: 10px;
    overflow: hidden;
  }

  .editor-toolbar {
    display: flex; gap: 4px; flex-wrap: wrap; padding: 6px;
    border-bottom: 1px solid var(--border); background: #fafbfd;
  }
  .editor-toolbar button {
    background: transparent; border: 1px solid transparent; padding: 5px 9px;
    border-radius: 6px; cursor: pointer; font-size: 13px; color: #394152;
    min-width: 30px; transition: all 0.15s; }
  .editor-toolbar button:hover { background: #eef0f6; border-color: var(--border); }
  .editor-toolbar button.active { background: var(--accent); color: #fff; border-color: var(--accent); }

  .editor-container {
    position: relative;
    min-height: 400px;
    max-height: 60vh;
    display: flex;
    flex-direction: column;
  }

  .editor-area {
    width: 100%;
    min-height: 400px;
    max-height: 60vh;
    padding: 16px 18px;
    border: none; outline: none;
    font-size: 15px; line-height: 1.7;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    resize: vertical;
    overflow-y: auto;
    background: #fff;
  }

  .editor-area img {
    max-width: 100%;
    height: auto;
    border-radius: 8px;
    margin: 8px 0;
    display: block;
    cursor: pointer;
    transition: opacity 0.2s;
  }
  .editor-area img:hover { opacity: 0.9; }

  .editor-area p { margin: 0.5em 0; }
  .editor-area ul, .editor-area ol { padding-left: 24px; }
  .editor-area blockquote { border-left: 3px solid var(--border-strong); padding: 4px 14px; color: #555; margin: 8px 0; }
  .editor-area pre { background: #f1f3f9; padding: 12px; border-radius: 6px; overflow: auto; }
  .editor-area code { background: #f1f3f9; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }
  .editor-area pre code { background: transparent; padding: 0; }

  /* Image overlay for editing */
  .image-overlay {
    position: fixed; inset: 0; background: rgba(0,0,0,0.85); z-index: 999;
    display: none; align-items: center; justify-content: center; cursor: zoom-out;
  }
  .image-overlay.active { display: flex; }
  .image-overlay img {
    max-width: 90vw; max-height: 90vh; border-radius: 8px;
    box-shadow: 0 8px 40px rgba(0,0,0,0.5);
  }

  /* View */
  .view-field { margin-bottom: 14px; }
  .view-field .lbl { font-size: 11px; color: var(--muted); text-transform: uppercase;
    letter-spacing: 0.5px; margin-bottom: 4px; font-weight: 500; }
  .view-field .val { font-size: 15px; }
  .view-message {
    border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px;
    background: #fafbfd; max-height: 50vh; overflow: auto; line-height: 1.7; }
  .view-message img { max-width: 100%; height: auto; border-radius: 8px; margin: 8px 0; cursor: pointer; }
  .view-message h1, .view-message h2, .view-message h3 { margin: 0.6em 0 0.4em; }
  .view-message pre { background: #eef0f6; padding: 10px 12px; border-radius: 6px; overflow: auto; }
  .view-message code { background: #eef0f6; padding: 2px 6px; border-radius: 4px; }
  .view-message pre code { background: transparent; padding: 0; }
  .view-message blockquote { border-left: 3px solid var(--border-strong); margin: 0;
    padding: 4px 14px; color: #555; }
  .view-message ul, .view-message ol { padding-left: 24px; }
  .view-message a { color: var(--accent); text-decoration: underline; }

  /* Toast */
  .toast {
    position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%) translateY(20px);
    padding: 10px 20px; border-radius: 10px; font-size: 13px; opacity: 0;
    transition: all 0.25s; pointer-events: none; z-index: 200; color: #fff;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
  .toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
  .toast.success { background: var(--success); }
  .toast.error { background: var(--danger); }
  .toast.warning { background: var(--warning); }
  .toast.info { background: var(--accent); }

  .empty { text-align: center; color: var(--muted); padding: 60px 20px; font-size: 15px; }

  /* Drop zone indicator */
  .editor-area.drop-active {
    outline: 3px dashed var(--accent);
    outline-offset: -3px;
    background: rgba(59,91,219,0.04);
  }

  /* Image insert button */
  .insert-image-btn {
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .insert-image-btn input[type="file"] {
    position: absolute; inset: 0; opacity: 0; cursor: pointer; width: 100%; height: 100%;
  }

  @media (max-width: 768px) {
    header { grid-template-columns: 1fr; gap: 10px; }
    .header-controls { flex-wrap: wrap; }
    .search-input { width: 100%; }
  }
</style>
</head>
<body>

<header>
  <button class="new-btn" onclick="openCreate()" title="Ctrl+N">+ Новая заметка</button>
  <h1 class="title">Заметки \ Промты</h1>
  <div class="header-controls">
    <input type="text" class="search-input" id="searchInput" placeholder="Поиск..." oninput="debounceSearch()">
    <select class="sort-select" id="sortBy" onchange="applyFilters()">
      <option value="date-desc">Дата ↓</option>
      <option value="date-asc">Дата ↑</option>
      <option value="topic-asc">Имя А-Я</option>
      <option value="topic-desc">Имя Я-А</option>
    </select>
  </div>
</header>

<main>
  <div class="grid" id="grid"></div>
  <div class="empty" id="empty" style="display:none;">Пока нет заметок. Создайте первую.</div>
</main>

<!-- Модалка просмотра -->
<div class="modal-backdrop" id="viewModal" role="dialog" aria-modal="true" aria-labelledby="viewTitle">
  <div class="modal">
    <header class="mh">
      <div class="mtitle" id="viewTitle">Просмотр</div>
      <button class="btn ghost" onclick="closeModal('viewModal')" aria-label="Закрыть">✕</button>
    </header>
    <div class="mb">
      <div class="view-field"><div class="lbl">Имя</div><div class="val" id="vTopic"></div></div>
      <div class="view-field"><div class="lbl">Теги</div><div class="val" id="vTags"></div></div>
      <div class="view-field"><div class="lbl">Дата</div><div class="val" id="vDate"></div></div>
      <div class="view-field">
        <div class="lbl" style="display:flex;justify-content:space-between;align-items:center;">
          <span>Промт</span>
          <button class="btn" style="padding:4px 10px;font-size:12px;" onclick="copyMessage()">Копировать текст</button>
        </div>
        <div class="view-message" id="vMessage"></div>
      </div>
    </div>
    <footer class="mf">
      <button class="btn" onclick="closeModal('viewModal')">Закрыть</button>
      <button class="btn primary" onclick="editCurrent()">Редактировать</button>
    </footer>
  </div>
</div>

<!-- Модалка создания/редактирования -->
<div class="modal-backdrop" id="editModal" role="dialog" aria-modal="true" aria-labelledby="editTitle">
  <div class="modal">
    <header class="mh">
      <div class="mtitle" id="editTitle">Новая заметка</div>
      <button class="btn ghost" onclick="closeModal('editModal')" aria-label="Закрыть">✕</button>
    </header>
    <div class="mb">
      <div class="field">
        <label>Имя</label>
        <input type="text" id="fTopic" placeholder="Название заметки">
      </div>
      <div class="field">
        <label>Теги</label>
        <div class="tags-input" id="tagsInput">
          <input type="text" id="tagInput" placeholder="Добавить тег и нажать Enter" list="savedTagList">
        </div>
      </div>
      <div class="field">
        <label>Цвет плитки</label>
        <div class="colors" id="colorPicker"></div>
      </div>
      <div class="field checkbox-field">
        <input type="checkbox" id="fPinned">
        <label for="fPinned">Закрепить (избранное)</label>
      </div>
      <div class="field">
        <label>Промт</label>
        <div class="editor-wrapper">
          <div class="editor-toolbar">
            <button type="button" onclick="execCmd('bold')" title="Жирный (Ctrl+B)"><b>B</b></button>
            <button type="button" onclick="execCmd('italic')" title="Курсив (Ctrl+I)"><i>I</i></button>
            <button type="button" onclick="execCmd('underline')" title="Подчёркнутый (Ctrl+U)"><u>U</u></button>
            <button type="button" onclick="execCmd('strikeThrough')" title="Зачёркнутый"><s>S</s></button>
            <span style="width:1px;background:var(--border);margin:0 4px;"></span>
            <button type="button" onclick="execCmd('formatBlock','<h1>')" title="Заголовок 1">H1</button>
            <button type="button" onclick="execCmd('formatBlock','<h2>')" title="Заголовок 2">H2</button>
            <button type="button" onclick="execCmd('formatBlock','<h3>')" title="Заголовок 3">H3</button>
            <span style="width:1px;background:var(--border);margin:0 4px;"></span>
            <button type="button" onclick="execCmd('insertUnorderedList')" title="Маркированный список">• Список</button>
            <button type="button" onclick="execCmd('insertOrderedList')" title="Нумерованный список">1. Список</button>
            <button type="button" onclick="execCmd('formatBlock','<blockquote>')" title="Цитата">❝ Цитата</button>
            <span style="width:1px;background:var(--border);margin:0 4px;"></span>
            <button type="button" onclick="insertCode()" title="Код">{ } Код</button>
            <div class="insert-image-btn">
              <button type="button" title="Вставить изображение">🖼 Изображение</button>
              <input type="file" accept="image/*" onchange="handleImageFile(event)">
            </div>
            <span style="width:1px;background:var(--border);margin:0 4px;"></span>
            <button type="button" onclick="execCmd('removeFormat')" title="Очистить форматирование">✕ Формат</button>
          </div>
          <div class="editor-container">
            <div class="editor-area" id="fMessage" contenteditable="true" spellcheck="true"></div>
          </div>
        </div>
      </div>
    </div>
    <footer class="mf">
      <button class="btn danger" id="deleteBtn" style="margin-right:auto;display:none;" onclick="deleteCurrent()">Удалить</button>
      <button class="btn" onclick="closeModal('editModal')">Отмена</button>
      <button class="btn primary" onclick="saveNote()" title="Ctrl+S">Сохранить</button>
    </footer>
  </div>
</div>

<!-- Полноэкранный просмотр изображения -->
<div class="image-overlay" id="imageOverlay" onclick="closeImageOverlay()">
  <img id="overlayImage" src="" alt="">
</div>

<datalist id="savedTagList"></datalist>

<div class="toast" id="toast"></div>

<script>
const COLORS = [
  "rgba(255,182,193,0.38)", "rgba(173,216,230,0.40)", "rgba(152,220,170,0.38)",
  "rgba(255,218,185,0.40)", "rgba(221,170,221,0.38)", "rgba(255,245,180,0.45)",
  "rgba(200,210,225,0.45)", "rgba(185,210,230,0.40)", "rgba(255,200,210,0.38)",
  "rgba(210,230,200,0.40)"
];

let allNotes = [];
let currentEditId = null;
let currentViewId = null;
let selectedColor = COLORS[0];
let currentTags = [];
let hasUnsavedChanges = false;
let searchTimeout = null;
let savedTags = [];

// Toast
function toast(msg, type = 'info') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast show ' + type;
  setTimeout(() => t.classList.remove('show'), 2000);
}

// Escape HTML
function escapeHtml(s) {
  return (s || "").replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

// URL auto-linking — исправлено на re.sub
function autoLinkUrls(html) {
  function replaceUrl(match) {
    const url = match[0];
    return '<a href="' + url + '" target="_blank" rel="noopener noreferrer">' + escapeHtml(url) + '</a>';
  }
  // Используем exec вместо replace для надёжной замены
  let result = '';
  let lastIndex = 0;
  const regex = /https?:\/\/[^\s<>"')\]]+/g;
  let m;
  while ((m = regex.exec(html)) !== null) {
    // Проверяем, что не попали внутрь существующего <a>
    if (html.lastIndexOf('<a', m.index) > html.lastIndexOf('</a>', m.index)) continue;
    result += html.slice(lastIndex, m.index) + replaceUrl(m);
    lastIndex = regex.lastIndex;
  }
  return result + html.slice(lastIndex);
}

// Color picker
function renderColorPicker() {
  const cp = document.getElementById('colorPicker');
  cp.innerHTML = '';
  COLORS.forEach(c => {
    const d = document.createElement('div');
    d.className = 'color-swatch' + (c === selectedColor ? ' selected' : '');
    d.style.background = c;
    d.onclick = () => { selectedColor = c; renderColorPicker(); markUnsaved(); };
    cp.appendChild(d);
  });
}

// Tags
function renderTags() {
  const container = document.getElementById('tagsInput');
  const input = document.getElementById('tagInput');
  container.querySelectorAll('.tag-item').forEach(el => el.remove());
  currentTags.forEach((tag, idx) => {
    const tagEl = document.createElement('div');
    tagEl.className = 'tag-item';
    tagEl.innerHTML = escapeHtml(tag) + ' <span class="remove-tag" onclick="removeTag(' + idx + ')">×</span>';
    container.insertBefore(tagEl, input);
  });
}

function addTag(tag) {
  tag = tag.trim();
  if (tag && !currentTags.includes(tag)) { currentTags.push(tag); renderTags(); markUnsaved(); }
  const dl = document.getElementById('savedTagList');
  if (!dl.querySelector('option[value="' + escapeHtml(tag) + '"]')) {
    const opt = document.createElement('option');
    opt.value = tag;
    dl.appendChild(opt);
  }
}
function removeTag(idx) { currentTags.splice(idx, 1); renderTags(); markUnsaved(); }

// Load notes
async function loadNotes() {
  showSkeletons();
  const res = await fetch('/api/notes');
  allNotes = await res.json();
  applyFilters();
}

function showSkeletons() {
  const grid = document.getElementById('grid');
  grid.innerHTML = '';
  for (let i = 0; i < 8; i++) { const sk = document.createElement('div'); sk.className = 'skeleton'; grid.appendChild(sk); }
}

// Load saved tags from disk
async function loadSavedTags() {
  try {
    const res = await fetch('/api/tags');
    savedTags = await res.json();
    populateTagDatalist();
  } catch (e) {
    savedTags = [];
  }
}

function populateTagDatalist() {
  const dl = document.getElementById('savedTagList');
  if (!dl) return;
  dl.innerHTML = '';
  savedTags.forEach(tag => {
    const opt = document.createElement('option');
    opt.value = tag;
    dl.appendChild(opt);
  });
}

// Strip HTML for search and preview
function stripHtml(html) {
  // Сохраняем URL-адреса перед обработкой
  const urlPattern = /https?:\/\/[^\s<>"')\]]+/g;
  let urls = [];
  let counter = 0;
  html = html.replace(urlPattern, function(match) {
    const placeholder = '%%URL' + (counter++) + '%%';
    urls.push(match);
    return placeholder;
  });

  // Обрабатываем HTML
  const tmp = document.createElement('div');
  tmp.innerHTML = html;
  let text = tmp.textContent || tmp.innerText || '';

  // Восстанавливаем URL
  for (let i = 0; i < urls.length; i++) {
    text = text.replace('%%URL' + i + '%%', urls[i]);
  }

  // Преобразуем HTML-теги в переносы строк
  text = text.replace(/<br\s*\/?>/gi, '\n');
  text = text.replace(/<p[^>]*>/gi, '\n\n');
  text = text.replace(/<\/p>/gi, '');
  text = text.replace(/<li[^>]*>/gi, '• ');
  text = text.replace(/<\/li>/gi, '\n');
  text = text.replace(/<h[1-6][^>]*>/gi, '\n\n---\n');
  text = text.replace(/<\/h[1-6]>/gi, '\n---\n');

  return text;
}

// Strip HTML для превью в плитке — заменяет div/br на \n
function stripHtmlForTile(html) {
  // Удаляем <div> в самом начале строки (если стоит первым тегом)
  let cleaned = html.replace(/^<div[^>]*>/gi, '');
  // Удаляем <br> в самом начале строки (если стоит первым тегом)
  cleaned = cleaned.replace(/^<br\s*\/?>/gi, '');
  // Затем заменяем </div><div> на один \n (чтобы не было двойных переносов)
  cleaned = cleaned.replace(/<\/div>\s*<div>/gi, '\n');
  // Затем заменяем оставшиеся <div>, </div>, <br> на переносы
  cleaned = cleaned.replace(/<\/?div[^>]*>/gi, '\n');
  cleaned = cleaned.replace(/<br\s*\/?>/gi, '\n');
  // Затем вызываем оригинальную stripHtml
  return stripHtml(cleaned);
}


// Extract first image src from HTML message
function extractFirstImageSrc(messageHtml) {
  if (!messageHtml) return null;
  const match = messageHtml.match(/<img[^>]+src\s*=\s*["']([^"']+)["']/i);
  return match ? match[1] : null;
}

// Render notes
function renderNotes(notes) {
  const grid = document.getElementById('grid');
  const empty = document.getElementById('empty');
  grid.innerHTML = '';

  if (!notes.length) { empty.style.display = 'block'; return; }
  empty.style.display = 'none';

  notes.forEach(n => {
    const tile = document.createElement('div');
    tile.className = 'tile' + (n.pinned ? ' pinned' : '');
    tile.style.background = n.color || COLORS[0];

    // Preview: strip images, auto-link URLs, escape HTML
    //let previewText = stripHtml(n.message || '').replace(/[#*`>\-]/g, '').substring(0, 100);
    let previewText = stripHtmlForTile(n.message || '').replace(/[#*`>\-]/g, '').substring(0, 100);
    previewText = autoLinkUrls(previewText);

    // Tags HTML
    const tagsHtml = (n.tags || []).slice(0, 3).map(t => '<span class="tag">' + escapeHtml(t) + '</span>').join('');

    // Check for first image
    const firstImgSrc = extractFirstImageSrc(n.message);

    tile.innerHTML = `
      ${n.pinned ? '<div class="pin-icon">📌</div>' : ''}
      <div class="header-row">
        <div class="topic">${escapeHtml(n.topic)}</div>
        ${tagsHtml ? '<div class="tags">' + tagsHtml + '</div>' : ''}
      </div>
      <div class="divider"></div>
      <div class="content-area">
        ${previewText ? '<div class="preview-text">' + previewText + '</div>' : ''}
        ${firstImgSrc ? '<img class="preview-img" src="' + escapeHtml(firstImgSrc) + '" alt="Превью">' : ''}
      </div>
      <div class="actions">
        <button class="action-btn" onclick="event.stopPropagation(); openView('${n.id}')" title="Просмотр"></button>
        <button class="action-btn" onclick="event.stopPropagation(); openEdit('${n.id}')" title="Редактировать"></button>
      </div>
      <div class="date">${escapeHtml(n.date || '')}</div>
    `;

    // Add SVG icons to action buttons
    const actionBtns = tile.querySelectorAll('.action-btn');
    if (actionBtns[0]) {
      actionBtns[0].innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
    }
    if (actionBtns[1]) {
      actionBtns[1].innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>';
    }

    tile.addEventListener('click', (e) => { if (!e.target.closest('.action-btn')) openView(n.id); });
    grid.appendChild(tile);
  });
}

function debounceSearch() { clearTimeout(searchTimeout); searchTimeout = setTimeout(applyFilters, 300); }

// Apply filters — full-text search across all note content
function applyFilters() {
  const search = document.getElementById('searchInput').value.toLowerCase();
  const sortBy = document.getElementById('sortBy').value;

  let filtered = allNotes.filter(n => {
    if (!search) return true;
    const matchTopic = (n.topic || '').toLowerCase().includes(search);
    const matchTags = (n.tags || []).some(t => t.toLowerCase().includes(search));
    const matchMessage = stripHtml(n.message || '').toLowerCase().includes(search);
    return matchTopic || matchTags || matchMessage;
  });

  filtered.sort((a, b) => {
    if (a.pinned && !b.pinned) return -1;
    if (!a.pinned && b.pinned) return 1;
    switch (sortBy) {
      case 'date-desc': return (b.created_at || '').localeCompare(a.created_at || '');
      case 'date-asc': return (a.created_at || '').localeCompare(b.created_at || '');
      case 'topic-asc': return (a.topic || '').localeCompare(b.topic || '');
      case 'topic-desc': return (b.topic || '').localeCompare(a.topic || '');
      default: return 0;
    }
  });

  renderNotes(filtered);
}

function openCreate() {
  currentEditId = null; hasUnsavedChanges = false;
  document.getElementById('editTitle').textContent = 'Новая заметка';
  document.getElementById('fTopic').value = '';
  document.getElementById('fMessage').innerHTML = '';
  document.getElementById('fPinned').checked = false;
  document.getElementById('deleteBtn').style.display = 'none';
  currentTags = []; renderTags(); selectedColor = COLORS[0]; renderColorPicker(); loadSavedTags();
  document.getElementById('editModal').classList.add('active');
  setTimeout(() => document.getElementById('fTopic').focus(), 100);
}

async function openEdit(id) {
  const res = await fetch('/api/notes/' + id);
  if (!res.ok) return;
  const n = await res.json();
  currentEditId = id; hasUnsavedChanges = false;
  document.getElementById('editTitle').textContent = 'Редактирование';
  document.getElementById('fTopic').value = n.topic || '';
  document.getElementById('fMessage').innerHTML = n.message || '';
  document.getElementById('fPinned').checked = n.pinned || false;
  document.getElementById('deleteBtn').style.display = 'inline-block';
  currentTags = n.tags || []; renderTags(); selectedColor = n.color || COLORS[0]; renderColorPicker(); loadSavedTags();
  document.getElementById('editModal').classList.add('active');
}

async function openView(id) {
  const res = await fetch('/api/notes/' + id);
  if (!res.ok) return;
  const n = await res.json();
  currentViewId = id;
  document.getElementById('viewTitle').textContent = n.topic || 'Заметка';
  document.getElementById('vTopic').textContent = n.topic || '';
  document.getElementById('vTags').innerHTML = (n.tags || []).map(t => '<span class="tag" style="margin-right:4px;">' + escapeHtml(t) + '</span>').join('') || '—';
  document.getElementById('vDate').textContent = n.date || '';
  // Set HTML content with image click handlers and auto-linked URLs
  const msgEl = document.getElementById('vMessage');
  let htmlContent = (n.message || '');
  htmlContent = htmlContent.replace(/<img/g, '<img onclick="showImageOverlay(this)" ');
  msgEl.innerHTML = autoLinkUrls(htmlContent);
  document.getElementById('viewModal').classList.add('active');
}

function closeModal(id) {
  if (id === 'editModal' && hasUnsavedChanges) {
    if (!confirm('У вас есть несохраненные изменения. Уйти?')) return;
  }
  document.getElementById(id).classList.remove('active'); hasUnsavedChanges = false;
}

function editCurrent() { closeModal('viewModal'); if (currentViewId) openEdit(currentViewId); }

// Save note
async function saveNote() {
  const topic = document.getElementById('fTopic').value.trim();
  const message = document.getElementById('fMessage').innerHTML; // WYSIWYG content

  if (!topic) { toast('Укажите имя', 'error'); return; }

  const payload = { topic, message, color: selectedColor, tags: currentTags, pinned: false };

  if (document.getElementById('fPinned').checked) payload.pinned = true;

  const url = currentEditId ? '/api/notes/' + currentEditId : '/api/notes';
  const method = currentEditId ? 'PUT' : 'POST';

  try {
    const res = await fetch(url, {
      method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
    });
    if (res.ok) {
      hasUnsavedChanges = false;
      closeModal('editModal');
      toast(currentEditId ? 'Сохранено' : 'Создано', 'success');
      loadNotes();
    } else {
      toast('Ошибка сохранения', 'error');
    }
  } catch (e) { toast('Ошибка сети', 'error'); }
}

// Delete — no confirmation
async function deleteCurrent() {
  if (!currentEditId) return;
  try {
    const res = await fetch('/api/notes/' + currentEditId, { method: 'DELETE' });
    if (res.ok) { hasUnsavedChanges = false; closeModal('editModal'); toast('Удалено', 'success'); loadNotes(); }
  } catch (e) { toast('Ошибка удаления', 'error'); }
}

// Copy message text (strip images, keep line breaks)
async function copyMessage() {
  const el = document.getElementById('vMessage');
  
  // Берем innerHTML — там HTML-разметка
  let text = el.innerHTML || '';
  
  // 1. Закрывающие блочные теги -> два переноса строки
  const blockTags = [
    'h1','h2','h3','h4','h5','h6',
    'p','div','blockquote','pre',
    'ul','ol','li','dl','dt','dd',
    'hr','figure','figcaption'
  ];
  
  for (const tag of blockTags) {
    const re = new RegExp('</' + tag + '\\s*>', 'gi');
    text = text.replace(re, '\n');
  }
  
  // 2. <br> и <br/> -> один перенос строки
  text = text.replace(/<br\s*\/?>/gi, '\n');
  
  // 3. Все открывающие теги -> удаляем
  text = text.replace(/<[^>]+>/g, '');
  
  // 4. Лишние пустые строки (оставляем максимум 2 подряд)
  text = text.replace(/\n{3,}/g, '\n\n');
  
  // 5. Убираем пробелы в начале и конце каждой строки
  text = text.split('\n').map(s => s.trim()).join('\n');
  
  try { await navigator.clipboard.writeText(text); toast('Скопировано', 'success'); }
  catch (e) {
    const ta = document.createElement('textarea'); ta.value = text;
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); toast('Скопировано', 'success'); }
    catch (_) { toast('Ошибка копирования', 'error'); }
    document.body.removeChild(ta);
  }
}

// ===== WYSIWYG Editor Functions =====

function execCmd(command, value) {
  document.execCommand(command, false, value || null);
  document.getElementById('fMessage').focus();
  markUnsaved();
}

function insertCode() {
  const sel = window.getSelection();
  const text = sel.toString() || 'код';
  const codeHtml = '<pre><code>' + escapeHtml(text) + '</code></pre><p><br></p>';
  document.execCommand('insertHTML', false, codeHtml);
  markUnsaved();
}

// Handle image file selection
function handleImageFile(event) {
  const file = event.target.files[0];
  if (!file) return;

  if (file.size > 5 * 1024 * 1024) {
    toast('Изображение слишком большое (макс. 5 МБ)', 'warning');
    event.target.value = '';
    return;
  }

  const reader = new FileReader();
  reader.onload = function(e) {
    const dataUrl = e.target.result;
    const imgHtml = '<img src="' + dataUrl + '" alt="Изображение">';
    document.execCommand('insertHTML', false, imgHtml);
    markUnsaved();
  };
  reader.readAsDataURL(file);
  event.target.value = '';
}

// Handle paste of images (Ctrl+V)
function handlePaste(event) {
  const items = event.clipboardData?.items;
  if (!items) return;

  for (let i = 0; i < items.length; i++) {
    if (items[i].type.indexOf('image') !== -1) {
      event.preventDefault();
      const file = items[i].getAsFile();
      const reader = new FileReader();
      reader.onload = function(e) {
        const imgHtml = '<img src="' + e.target.result + '" alt="Вставленное изображение">';
        document.execCommand('insertHTML', false, imgHtml);
        markUnsaved();
      };
      reader.readAsDataURL(file);
      return;
    }
  }
}

// Handle drag and drop of images
function handleDragOver(event) {
  event.preventDefault();
  event.stopPropagation();
  document.getElementById('fMessage').classList.add('drop-active');
}

function handleDragLeave(event) {
  event.preventDefault();
  event.stopPropagation();
  document.getElementById('fMessage').classList.remove('drop-active');
}

function handleDrop(event) {
  event.preventDefault();
  event.stopPropagation();
  document.getElementById('fMessage').classList.remove('drop-active');

  const files = event.dataTransfer?.files;
  if (!files) return;

  for (let i = 0; i < files.length; i++) {
    if (files[i].type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = function(e) {
        const imgHtml = '<img src="' + e.target.result + '" alt="Перетащенное изображение">';
        document.execCommand('insertHTML', false, imgHtml);
        markUnsaved();
      };
      reader.readAsDataURL(files[i]);
    }
  }
}

// Image overlay for full-screen viewing
function showImageOverlay(img) {
  const overlay = document.getElementById('imageOverlay');
  const overlayImg = document.getElementById('overlayImage');
  overlayImg.src = img.src;
  overlay.classList.add('active');
}

function closeImageOverlay() {
  document.getElementById('imageOverlay').classList.remove('active');
}

// Mark unsaved changes
function markUnsaved() { hasUnsavedChanges = true; }

// Track changes
document.getElementById('fTopic').addEventListener('input', markUnsaved);
document.getElementById('fPinned').addEventListener('change', markUnsaved);
document.getElementById('tagInput').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); addTag(e.target.value); e.target.value = ''; }
});

// Editor paste handler
const editorArea = document.getElementById('fMessage');
editorArea.addEventListener('paste', handlePaste);
editorArea.addEventListener('dragover', handleDragOver);
editorArea.addEventListener('dragleave', handleDragLeave);
editorArea.addEventListener('drop', handleDrop);

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'n') { e.preventDefault(); openCreate(); }
  if ((e.ctrlKey || e.metaKey) && e.key === 's') {
    e.preventDefault();
    if (document.getElementById('editModal').classList.contains('active')) saveNote();
  }
  if ((e.ctrlKey || e.metaKey) && e.key === 'f') { e.preventDefault(); document.getElementById('searchInput').focus(); }
  if (e.key === 'Escape') {
    const activeOverlay = document.getElementById('imageOverlay');
    if (activeOverlay.classList.contains('active')) { closeImageOverlay(); return; }
    const activeModal = document.querySelector('.modal-backdrop.active');
    if (activeModal) closeModal(activeModal.id);
  }
});

// Close on backdrop click
document.querySelectorAll('.modal-backdrop').forEach(bd => {
  bd.addEventListener('click', (e) => { if (e.target === bd) closeModal(bd.id); });
});

// Focus trap for modals
document.querySelectorAll('.modal-backdrop').forEach(bd => {
  bd.addEventListener('keydown', (e) => {
    if (e.key !== 'Tab') return;
    const modal = bd.querySelector('.modal');
    const focusable = modal.querySelectorAll('button, input, select, textarea, [tabindex]:not([tabindex="-1"])');
    const first = focusable[0]; const last = focusable[focusable.length - 1];
    if (e.shiftKey) { if (document.activeElement === first) { e.preventDefault(); last.focus(); } }
    else { if (document.activeElement === last) { e.preventDefault(); first.focus(); } }
  });
});

// Init
loadNotes();
loadSavedTags();
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(INDEX_TEMPLATE)


@app.route("/api/notes", methods=["GET"])
def api_list():
    return jsonify(list_notes())


@app.route("/api/notes", methods=["POST"])
def api_create():
    data = request.get_json(force=True) or {}
    note_id = uuid.uuid4().hex
    now = datetime.now()
    note = {
        "topic": (data.get("topic") or "").strip(),
        "message": data.get("message") or "",
        "color": data.get("color") or "rgba(200,210,225,0.45)",
        "tags": data.get("tags") or [],
        "pinned": data.get("pinned") or False,
        "date": now.strftime("%d-%m-%y %H:%M"),
        "created_at": now.isoformat(),
    }
    if not note["topic"]:
        return jsonify({"error": "topic required"}), 400
    write_note(note_id, note)
    for tag in note.get("tags", []):
        add_tag(tag)
    return jsonify({"id": note_id}), 201


@app.route("/api/notes/<note_id>", methods=["GET"])
def api_get(note_id):
    n = read_note(note_id)
    if not n:
        return jsonify({"error": "not found"}), 404
    n["id"] = note_id
    return jsonify(n)


@app.route("/api/notes/<note_id>", methods=["PUT"])
def api_update(note_id):
    n = read_note(note_id)
    if not n:
        return jsonify({"error": "not found"}), 404
    data = request.get_json(force=True) or {}
    n["topic"] = (data.get("topic") or n.get("topic") or "").strip()
    if "message" in data:
        n["message"] = data["message"]
    if "color" in data:
        n["color"] = data["color"]
    if "tags" in data:
        n["tags"] = data["tags"]
    if "pinned" in data:
        n["pinned"] = data["pinned"]
    now = datetime.now()
    n["date"] = now.strftime("%d-%m-%y %H:%M")
    write_note(note_id, n)
    for tag in n.get("tags", []):
        add_tag(tag)
    return jsonify({"id": note_id})


@app.route("/api/notes/<note_id>", methods=["DELETE"])
def api_delete(note_id):
    path = note_path(note_id)
    if os.path.exists(path):
        os.remove(path)
    return jsonify({"ok": True})


@app.route("/api/tags", methods=["GET"])
def api_tags():
    return jsonify(load_tags())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
