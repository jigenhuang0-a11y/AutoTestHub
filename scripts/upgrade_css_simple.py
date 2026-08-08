"""Simple CSS block replacement for KnowledgeChat.vue"""
import sys

filepath = r"d:\AI_Project\ai-test-platform\frontend\src\views\KnowledgeChat.vue"

with open(filepath, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find the start and end of the markdown CSS block
start = None
end = None
for i, line in enumerate(lines):
    if "AI 消息 Markdown 渲染优化" in line and ("豆包" in line or "AI 消息" in line):
        start = i  # 0-indexed
    if start is not None and ".ai-message-bubble em" in line and "font-style: italic" in lines[i+1] if i+1 < len(lines) else False:
        # Check if next line ends the block (just "}\n")
        if i+1 < len(lines) and "font-style: italic;" in lines[i+1]:
            end = i + 2  # include the closing '}' line
            break

if start is None or end is None:
    print(f"ERROR: Could not find markers. start={start}, end={end}")
    sys.exit(1)

print(f"Found CSS block: lines {start+1}-{end} (0-indexed: {start}-{end-1})")
print(f"Start line: {lines[start].rstrip()}")
print(f"End line: {lines[end-1].rstrip()}")

new_css = """/* ========== AI 消息 Markdown 渲染优化 ========== */
.ai-message-bubble {
  font-size: 14.5px;
  color: #1d1f23;
  line-height: 1.72;
  overflow-wrap: break-word;
  word-break: break-word;
  letter-spacing: -0.005em;
}

/* 段落间距 */
.ai-message-bubble p {
  margin: 0 0 12px 0;
  line-height: 1.72;
  color: #2c3038;
}
.ai-message-bubble p:last-child {
  margin-bottom: 0;
}

/* 标题样式 */
.ai-message-bubble h1,
.ai-message-bubble h2,
.ai-message-bubble h3,
.ai-message-bubble h4 {
  margin: 26px 0 12px 0;
  font-weight: 650;
  color: #0f1115;
  line-height: 1.35;
  letter-spacing: -0.02em;
}
.ai-message-bubble h1 { font-size: 21px; font-weight: 700; }
.ai-message-bubble h2 { font-size: 18px; }
.ai-message-bubble h3 { font-size: 16px; }
.ai-message-bubble h4 { font-size: 14.5px; text-transform: uppercase; letter-spacing: 0.04em; color: #5d626d; }

/* 列表样式 */
.ai-message-bubble ul,
.ai-message-bubble ol { margin: 10px 0; padding-left: 24px; }
.ai-message-bubble li { margin: 6px 0; line-height: 1.7; color: #2c3038; }
.ai-message-bubble ul li::marker { color: #9199a6; }
.ai-message-bubble ol li::marker { color: #9199a6; font-weight: 500; }

/* 任务列表 */
.ai-message-bubble ul li input[type="checkbox"] {
  margin-right: 8px; vertical-align: middle; width: 16px; height: 16px;
  accent-color: #3b82f6;
}

/* 引用块 */
.ai-message-bubble blockquote {
  margin: 14px 0; padding: 13px 18px;
  border-left: 2.5px solid #c8cdd4; background: #f6f7f9;
  border-radius: 0 6px 6px 0; color: #595d66;
}
.ai-message-bubble blockquote p { margin: 0; color: #595d66; }

/* 代码块 */
::deep(.ai-message-bubble pre) {
  position: relative; margin: 14px 0; padding: 36px 14px 12px 14px;
  background: #f4f5f7; border-radius: 8px; overflow-x: auto;
  font-family: 'JetBrains Mono', 'SF Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 13px; line-height: 1.65; border: 1px solid #e1e4e8;
}
::deep(.ai-message-bubble pre code) {
  background: transparent; padding: 0; border-radius: 0;
  color: #24292f; font-family: inherit; font-size: inherit; line-height: inherit;
}

/* 行内代码 */
.ai-message-bubble code {
  background: #eef0f3; padding: 2px 7px; border-radius: 5px;
  font-family: 'JetBrains Mono', 'SF Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 12.5px; color: #cf3a4e; font-weight: 500;
}

/* ========== 测试用例专用表格 ========== */
.ai-message-bubble .tc-table-wrap {
  margin: 18px 0; border: 1px solid #e3e6ea; border-radius: 12px;
  overflow: hidden; background: #fff;
}
.ai-message-bubble .tc-table-wrap table {
  display: table; width: 100%; border-collapse: collapse; border-spacing: 0;
  font-size: 13.5px; border-radius: 0; box-shadow: none; margin: 0;
  overflow: visible; background: transparent;
}
.ai-message-bubble .tc-table-wrap thead th {
  background: #f8f9fb; padding: 12px 16px; text-align: left;
  font-weight: 650; font-size: 12px; color: #4a4f5a;
  text-transform: uppercase; letter-spacing: 0.04em;
  border-bottom: 2px solid #e3e6ea; white-space: nowrap;
}
.ai-message-bubble .tc-table-wrap tbody td {
  padding: 11px 16px; color: #2c3038; line-height: 1.55;
  vertical-align: top; font-size: 13.5px;
}
.ai-message-bubble .tc-table-wrap tbody tr {
  transition: background 0.12s ease; border-bottom: 1px solid #eff0f2;
}
.ai-message-bubble .tc-table-wrap tbody tr:last-child { border-bottom: none; }
.ai-message-bubble .tc-table-wrap tbody tr:hover { background: #f5f7fa; }
.ai-message-bubble .tc-table-wrap td:first-child {
  font-family: 'JetBrains Mono', 'SF Mono', 'Consolas', monospace;
  font-size: 12.5px; color: #545a66; white-space: nowrap;
}

/* 优先级徽章 */
.ai-message-bubble .tc-priority {
  display: inline-block; padding: 2px 10px; border-radius: 100px;
  font-size: 11.5px; font-weight: 650; text-transform: uppercase;
  letter-spacing: 0.03em; white-space: nowrap;
}
.ai-message-bubble .tc-priority.p0 { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
.ai-message-bubble .tc-priority.p1 { background: #fff7ed; color: #ea580c; border: 1px solid #fed7aa; }
.ai-message-bubble .tc-priority.p2 { background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe; }
.ai-message-bubble .tc-priority.p3 { background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; }

/* 普通表格 */
.ai-message-bubble table:not(.tc-table-wrap table) {
  width: 100%; border-collapse: collapse; margin: 14px 0;
  font-size: 13.5px; border: 1px solid #e3e6ea; border-radius: 8px; overflow: hidden;
}
.ai-message-bubble table:not(.tc-table-wrap table) th {
  background: #f8f9fb; padding: 10px 14px; text-align: left;
  font-weight: 600; color: #3a3f4a; border-bottom: 2px solid #e3e6ea; font-size: 13px;
}
.ai-message-bubble table:not(.tc-table-wrap table) td {
  padding: 10px 14px; color: #2c3038; line-height: 1.55;
}
.ai-message-bubble table:not(.tc-table-wrap table) tr:not(:last-child) td {
  border-bottom: 1px solid #eff0f2;
}
.ai-message-bubble table:not(.tc-table-wrap table) tr:hover td { background: #f5f7fa; }

/* 分隔线 */
.ai-message-bubble hr { margin: 20px 0; border: none; border-top: 1px solid #e3e6ea; }

/* 链接 */
.ai-message-bubble a {
  color: #1d4ed8; text-decoration: none;
  border-bottom: 1px solid #c7d2fe; transition: border-color 0.15s, color 0.15s;
}
.ai-message-bubble a:hover { color: #1e40af; border-bottom-color: #1d4ed8; }

/* 图片 */
.ai-message-bubble img { max-width: 100%; border-radius: 8px; margin: 10px 0; }

/* 强调 */
.ai-message-bubble strong { font-weight: 650; color: #0f1115; }
.ai-message-bubble em { font-style: italic; color: #4a4f5a; }
"""

# Replace
new_lines = lines[:start] + [new_css] + lines[end:]

with open(filepath, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print(f"Done! Replaced lines {start+1}-{end} with new CSS block ({len(new_css.split(chr(10)))} lines).")
