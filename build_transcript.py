import re
import html
import os

def generate():
    source_file = "campuslostandfound1.txt"
    if not os.path.exists(source_file):
        print(f"Error: {source_file} not found.")
        return

    with open(source_file, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # Pattern to split by USER TURN
    pattern = re.compile(r'#{10,}\s*\nUSER TURN (\d+)(?:\s*\([^)]*\))?\s*\n#{10,}', re.DOTALL)
    splits = pattern.split(content)

    turns = []
    for i in range(1, len(splits), 2):
        turn_num = int(splits[i])
        turn_body = splits[i+1].strip()
        
        # Split user prompt and assistant response
        m = re.search(r'-{20,}\s*\nASSISTANT[^\n]*\n-{20,}', turn_body)
        if m:
            user_text = turn_body[:m.start()].strip()
            assistant_text = turn_body[m.end():].strip()
        else:
            user_text = turn_body
            assistant_text = ""
        
        # Separate main user prompt from context document metadata if present
        context_doc = ""
        user_main = user_text
        if "[Context Document:" in user_text:
            parts = user_text.split("[Context Document:", 1)
            user_main = parts[0].strip()
            context_doc = "[Context Document: " + parts[1].strip()

        turns.append({
            "num": turn_num,
            "user_main": user_main,
            "context_doc": context_doc,
            "assistant_text": assistant_text
        })

    print(f"Parsed {len(turns)} turns successfully.")

    # 1. Generate transcript.md
    md_output = []
    md_output.append("# Smart Campus Lost-and-Found Network — Development Transcript\n")
    md_output.append("> **Session ID:** `5383bdac-72bf-426c-942c-4adceb67190f` | **Turns:** 32 | **Methodology:** Spec-Driven Development\n")
    md_output.append("---\n")

    for t in turns:
        md_output.append(f"## Turn {t['num']}\n")
        md_output.append(f"**User:**\n```\n{t['user_main']}\n```\n")
        if t['context_doc']:
            md_output.append(f"*Context:* `{t['context_doc']}`\n\n")
        md_output.append("<details>\n<summary><b>Click to expand Assistant Response & Actions</b></summary>\n\n```\n")
        md_output.append(t['assistant_text'])
        md_output.append("\n```\n</details>\n\n---\n")

    with open("transcript.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md_output))
    print("Generated transcript.md successfully.")

    # 2. Generate transcript.html
    html_parts = []
    html_parts.append("""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Smart Campus Lost &amp; Found — AI Development Transcript</title>
  <style>
    :root {
      --bg: #090d16;
      --card-bg: #111827;
      --card-border: #1f2937;
      --hover-bg: #1e293b;
      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --primary: #6366f1;
      --primary-hover: #4f46e5;
      --accent: #10b981;
      --accent-bg: rgba(16, 185, 129, 0.1);
      --user-bg: #1e1b4b;
      --user-border: #312e81;
      --code-bg: #030712;
      --code-text: #e2e8f0;
      --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
      --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      background-color: var(--bg);
      color: var(--text);
      font-family: var(--font-sans);
      line-height: 1.5;
      padding-bottom: 80px;
    }

    /* Header */
    header {
      background: linear-gradient(180deg, #111827 0%, #090d16 100%);
      border-bottom: 1px solid var(--card-border);
      padding: 40px 24px 30px;
      text-align: center;
    }

    .header-badge {
      display: inline-block;
      padding: 4px 12px;
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--accent);
      background: var(--accent-bg);
      border: 1px solid rgba(16, 185, 129, 0.3);
      border-radius: 9999px;
      margin-bottom: 12px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    h1 {
      font-size: 2.2rem;
      font-weight: 800;
      color: #fff;
      margin-bottom: 8px;
      letter-spacing: -0.02em;
    }

    .subtitle {
      color: var(--text-muted);
      font-size: 1.05rem;
      max-width: 750px;
      margin: 0 auto 20px;
    }

    .meta-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      justify-content: center;
      margin-top: 15px;
    }

    .meta-tag {
      background: #1f2937;
      border: 1px solid #374151;
      border-radius: 6px;
      padding: 4px 10px;
      font-size: 0.82rem;
      color: #d1d5db;
    }

    .meta-tag strong {
      color: #fff;
    }

    /* Sticky Controls Toolbar */
    .controls-wrapper {
      position: sticky;
      top: 0;
      z-index: 100;
      background: rgba(9, 13, 22, 0.92);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--card-border);
      padding: 14px 24px;
    }

    .controls-container {
      max-width: 1000px;
      margin: 0 auto;
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      justify-content: space-between;
    }

    .search-box {
      flex: 1;
      min-width: 250px;
      position: relative;
    }

    .search-input {
      width: 100%;
      background: #1f2937;
      border: 1px solid #374151;
      border-radius: 8px;
      padding: 9px 14px 9px 36px;
      color: #fff;
      font-size: 0.95rem;
      outline: none;
      transition: border-color 0.2s, box-shadow 0.2s;
    }

    .search-input:focus {
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25);
    }

    .search-icon {
      position: absolute;
      left: 12px;
      top: 50%;
      transform: translateY(-50%);
      color: var(--text-muted);
      font-size: 0.9rem;
      pointer-events: none;
    }

    .btn-group {
      display: flex;
      gap: 8px;
    }

    .btn {
      background: #1f2937;
      color: #e5e7eb;
      border: 1px solid #374151;
      padding: 8px 14px;
      border-radius: 8px;
      font-size: 0.88rem;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }

    .btn:hover {
      background: var(--hover-bg);
      border-color: #4b5563;
      color: #fff;
    }

    .btn-primary {
      background: var(--primary);
      border-color: var(--primary);
      color: #fff;
    }

    .btn-primary:hover {
      background: var(--primary-hover);
      border-color: var(--primary-hover);
    }

    select.btn {
      padding-right: 28px;
      appearance: none;
      background-image: url("data:image/svg+xml;charset=UTF-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2212%22%20height%3D%2212%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%239ca3af%22%20stroke-width%3D%222%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpolyline%20points%3D%226%209%2012%2015%2018%209%22%3E%3C%2Fpolyline%3E%3C%2Fsvg%3E");
      background-repeat: no-repeat;
      background-position: right 10px center;
    }

    /* Main Container */
    main {
      max-width: 1000px;
      margin: 30px auto;
      padding: 0 20px;
    }

    .turn-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      margin-bottom: 24px;
      overflow: hidden;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
      transition: border-color 0.2s, box-shadow 0.2s;
    }

    .turn-card:hover {
      border-color: #374151;
    }

    .turn-card.highlight {
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.3);
    }

    /* Turn Header & User Section */
    .turn-header {
      padding: 18px 22px;
      background: linear-gradient(180deg, rgba(31, 41, 55, 0.4) 0%, rgba(17, 24, 39, 0) 100%);
      border-bottom: 1px solid var(--card-border);
    }

    .turn-badge-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }

    .turn-badge {
      background: #3730a3;
      color: #c7d2fe;
      font-weight: 700;
      font-size: 0.85rem;
      padding: 4px 12px;
      border-radius: 9999px;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }

    .turn-time {
      font-size: 0.8rem;
      color: var(--text-muted);
    }

    .user-box {
      background: var(--user-bg);
      border: 1px solid var(--user-border);
      border-radius: 8px;
      padding: 14px 18px;
    }

    .user-label {
      font-size: 0.75rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: #818cf8;
      margin-bottom: 6px;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .user-prompt {
      color: #f8fafc;
      font-size: 1rem;
      white-space: pre-wrap;
      word-break: break-word;
    }

    .context-meta {
      margin-top: 10px;
      font-size: 0.8rem;
      color: #a5b4fc;
      background: rgba(49, 46, 129, 0.5);
      border-radius: 4px;
      padding: 6px 10px;
      word-break: break-all;
    }

    /* Assistant Response Collapsible (<details>) */
    details.assistant-details {
      border-top: 1px solid var(--card-border);
      background: #0d131f;
    }

    summary.assistant-summary {
      padding: 14px 22px;
      cursor: pointer;
      user-select: none;
      display: flex;
      align-items: center;
      justify-content: space-between;
      transition: background 0.2s;
      outline: none;
    }

    summary.assistant-summary:hover {
      background: #151d2d;
    }

    summary.assistant-summary:focus-visible {
      box-shadow: inset 0 0 0 2px var(--primary);
    }

    .summary-left {
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 600;
      color: #e2e8f0;
      font-size: 0.95rem;
    }

    .chevron {
      display: inline-block;
      transition: transform 0.2s ease;
      font-size: 0.8rem;
      color: var(--text-muted);
    }

    details[open] summary .chevron {
      transform: rotate(90deg);
    }

    .summary-badge {
      background: #1f2937;
      color: var(--text-muted);
      font-size: 0.75rem;
      padding: 3px 8px;
      border-radius: 9999px;
      border: 1px solid #374151;
    }

    .response-content {
      padding: 16px 22px 22px;
      border-top: 1px solid var(--card-border);
      background: var(--code-bg);
      overflow-x: auto;
    }

    .response-actions {
      display: flex;
      justify-content: flex-end;
      margin-bottom: 10px;
    }

    .btn-copy {
      background: #1f2937;
      color: #9ca3af;
      border: 1px solid #374151;
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 0.75rem;
      cursor: pointer;
      transition: all 0.2s;
    }

    .btn-copy:hover {
      color: #fff;
      background: #374151;
    }

    pre.response-pre {
      font-family: var(--font-mono);
      font-size: 0.85rem;
      line-height: 1.6;
      color: var(--code-text);
      white-space: pre-wrap;
      word-break: break-word;
      max-height: 800px;
      overflow-y: auto;
      padding: 12px;
      background: rgba(0, 0, 0, 0.4);
      border-radius: 6px;
      border: 1px solid #1f2937;
    }

    /* Scrollbars */
    pre::-webkit-scrollbar {
      width: 8px;
      height: 8px;
    }
    pre::-webkit-scrollbar-track {
      background: #030712;
    }
    pre::-webkit-scrollbar-thumb {
      background: #374151;
      border-radius: 4px;
    }
    pre::-webkit-scrollbar-thumb:hover {
      background: #4b5563;
    }

    /* Empty state */
    .no-results {
      text-align: center;
      padding: 60px 20px;
      color: var(--text-muted);
      font-size: 1.1rem;
    }

    /* Floating Top Button */
    .btn-top {
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: var(--primary);
      color: #fff;
      width: 44px;
      height: 44px;
      border-radius: 50%;
      border: none;
      box-shadow: 0 4px 12px rgba(0,0,0,0.5);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.2rem;
      transition: transform 0.2s, background 0.2s;
      z-index: 99;
    }

    .btn-top:hover {
      background: var(--primary-hover);
      transform: translateY(-2px);
    }
  </style>
</head>
<body>

  <header>
    <div class="header-badge">Spec-Driven Development Transcript</div>
    <h1>Smart Campus Lost &amp; Found</h1>
    <p class="subtitle">Complete turn-by-turn dialogue, tool calls, and implementation log between user and AI assistant.</p>
    <div class="meta-tags">
      <span class="meta-tag">Turns: <strong>32 Interaction Turns</strong></span>
      <span class="meta-tag">Session ID: <strong>5383bdac-72bf...</strong></span>
      <span class="meta-tag">Methodology: <strong>Spec-Driven Development</strong></span>
      <span class="meta-tag">Criteria: <strong>AC-01 to AC-149 Passing</strong></span>
    </div>
  </header>

  <div class="controls-wrapper">
    <div class="controls-container">
      <div class="search-box">
        <span class="search-icon">🔍</span>
        <input type="text" id="searchInput" class="search-input" placeholder="Search turns, commands, keywords..." oninput="handleSearch()">
      </div>
      <div class="btn-group">
        <select id="jumpSelect" class="btn" onchange="jumpToTurn(this.value)">
          <option value="">Jump to Turn...</option>
""")

    for t in turns:
        prompt_snippet = t['user_main'].split('\n')[0][:35]
        html_parts.append(f'          <option value="turn-{t["num"]}">Turn {t["num"]}: {html.escape(prompt_snippet)}...</option>\n')

    html_parts.append("""        </select>
        <button class="btn" onclick="toggleAll(true)">[+] Expand All</button>
        <button class="btn" onclick="toggleAll(false)">[-] Collapse All</button>
      </div>
    </div>
  </div>

  <main id="turnsList">
""")

    for t in turns:
        num = t['num']
        user_main_esc = html.escape(t['user_main'])
        context_doc_esc = html.escape(t['context_doc']) if t['context_doc'] else ""
        asst_text_esc = html.escape(t['assistant_text'])
        asst_char_count = len(t['assistant_text'])

        context_html = f'<div class="context-meta">{context_doc_esc}</div>' if context_doc_esc else ''

        html_parts.append(f"""
    <article class="turn-card" id="turn-{num}">
      <div class="turn-header">
        <div class="turn-badge-row">
          <span class="turn-badge">👤 Turn {num}</span>
          <span class="turn-time">Pair Programming Turn {num} of {len(turns)}</span>
        </div>
        <div class="user-box">
          <div class="user-label">User Prompt</div>
          <div class="user-prompt">{user_main_esc}</div>
          {context_html}
        </div>
      </div>
      <details class="assistant-details" id="details-{num}">
        <summary class="assistant-summary">
          <div class="summary-left">
            <span class="chevron">▶</span>
            <span>🤖 Assistant Response &amp; Implementation Actions</span>
          </div>
          <span class="summary-badge">{asst_char_count:,} chars · Click to toggle</span>
        </summary>
        <div class="response-content">
          <div class="response-actions">
            <button class="btn-copy" onclick="copyTurn('code-{num}', this)">📋 Copy Response</button>
          </div>
          <pre class="response-pre"><code id="code-{num}">{asst_text_esc}</code></pre>
        </div>
      </details>
    </article>
""")

    html_parts.append("""
    <div id="noResults" class="no-results" style="display: none;">
      No matching turns found. Try a different search query.
    </div>
  </main>

  <button class="btn-top" onclick="window.scrollTo({top: 0, behavior: 'smooth'})" title="Back to top">↑</button>

  <script>
    function toggleAll(open) {
      document.querySelectorAll('details.assistant-details').forEach(d => {
        d.open = open;
      });
    }

    function jumpToTurn(turnId) {
      if (!turnId) return;
      const el = document.getElementById(turnId);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        el.classList.add('highlight');
        setTimeout(() => el.classList.remove('highlight'), 2000);
        // open the details
        const det = el.querySelector('details.assistant-details');
        if (det) det.open = true;
      }
    }

    function handleSearch() {
      const q = document.getElementById('searchInput').value.toLowerCase().trim();
      const cards = document.querySelectorAll('.turn-card');
      let visible = 0;

      cards.forEach(card => {
        const text = card.textContent.toLowerCase();
        if (!q || text.includes(q)) {
          card.style.display = 'block';
          visible++;
        } else {
          card.style.display = 'none';
        }
      });

      document.getElementById('noResults').style.display = (visible === 0) ? 'block' : 'none';
    }

    function copyTurn(elemId, btn) {
      const el = document.getElementById(elemId);
      if (!el) return;
      navigator.clipboard.writeText(el.innerText).then(() => {
        const orig = btn.innerText;
        btn.innerText = '✓ Copied!';
        setTimeout(() => btn.innerText = orig, 2000);
      });
    }
  </script>
</body>
</html>
""")

    with open("transcript.html", "w", encoding="utf-8") as f:
        f.write("".join(html_parts))

    print(f"Generated transcript.html successfully ({os.path.getsize('transcript.html')} bytes).")

if __name__ == "__main__":
    generate()
