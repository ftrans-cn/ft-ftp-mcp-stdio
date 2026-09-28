"""Markdown -> HTML converter for 快速指南 v1.0.
Lightweight, no external deps. Handles: headings, code blocks (fenced),
tables (pipe), blockquotes, ordered/unordered lists, inline code,
bold/italic escapes. Sufficient for this document.
"""
import re
import sys
from html import escape
from pathlib import Path

CSS = """
body { font-family: 'Microsoft YaHei', 'SimSun', sans-serif; max-width: 960px; margin: 0 auto; padding: 40px 60px; font-size: 14px; line-height: 1.8; color: #333; }
h1 { font-size: 24px; text-align: center; margin-bottom: 30px; border-bottom: 2px solid #1a73e8; padding-bottom: 15px; }
h2 { font-size: 18px; margin-top: 30px; border-bottom: 1px solid #e0e0e0; padding-bottom: 8px; }
h3 { font-size: 16px; margin-top: 20px; }
h4 { font-size: 14px; margin-top: 15px; }
table { border-collapse: collapse; width: 100%; margin: 15px 0; }
th, td { border: 1px solid #ccc; padding: 8px 12px; text-align: left; vertical-align: top; }
th { background: #f0f0f0; font-weight: 600; }
code { background: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-family: 'Consolas', 'Courier New', monospace; font-size: 13px; }
pre { background: #f5f5f5; padding: 15px; border-radius: 5px; overflow-x: auto; line-height: 1.5; }
pre code { background: transparent; padding: 0; }
blockquote { border-left: 4px solid #1a73e8; padding: 10px 20px; margin: 15px 0; background: #f8f9ff; color: #444; }
blockquote p { margin: 5px 0; }
hr { border: none; border-top: 1px dashed #ccc; margin: 30px 0; }
ul, ol { padding-left: 28px; }
li { margin: 4px 0; }
strong { font-weight: 600; }
em { font-style: italic; color: #555; }
ul.contains-task-list { list-style: none; padding-left: 20px; }
@media print { body { padding: 20px; } }
"""


def inline(s: str) -> str:
    """Escape HTML and apply inline markdown (code/bold/em)."""
    s = escape(s, quote=False)
    # inline code: `...`
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    # bold: **...**
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    # italic: *...* (avoiding ** already consumed)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    return s


def render_table(lines):
    """Render a GFM pipe table. lines: list of pipe-separated rows."""
    rows = [r for r in lines if r.strip()]
    if len(rows) < 2:
        return None
    header = [c.strip() for c in rows[0].strip("|").split("|")]
    # second row is alignment/separator — skip
    body_rows = []
    for r in rows[2:]:
        cells = [c.strip() for c in r.strip("|").split("|")]
        body_rows.append(cells)
    out = ["<table>", "<thead><tr>"]
    for h in header:
        out.append(f"<th>{inline(h)}</th>")
    out.append("</tr></thead><tbody>")
    for row in body_rows:
        out.append("<tr>")
        for c in row:
            out.append(f"<td>{inline(c)}</td>")
        out.append("</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def convert(md: str) -> str:
    lines = md.splitlines()
    out = []
    i = 0
    in_p = False

    def close_p():
        nonlocal in_p
        if in_p:
            out.append("</p>")
            in_p = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # fenced code block
        if stripped.startswith("```"):
            close_p()
            lang = stripped[3:].strip()
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            cls = f' class="language-{escape(lang)}"' if lang else ""
            out.append(f"<pre><code{cls}>")
            out.append(escape("\n".join(buf)))
            out.append("</code></pre>")
            continue

        # heading
        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            close_p()
            level = len(m.group(1))
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # hr
        if stripped == "---":
            close_p()
            out.append("<hr>")
            i += 1
            continue

        # blank line
        if not stripped:
            close_p()
            i += 1
            continue

        # table
        if "|" in stripped and i + 1 < len(lines) and re.match(
            r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$", lines[i + 1]
        ):
            close_p()
            tbl_lines = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                tbl_lines.append(lines[i])
                i += 1
            rendered = render_table(tbl_lines)
            if rendered:
                out.append(rendered)
            continue

        # blockquote (consecutive `>` lines)
        if stripped.startswith(">"):
            close_p()
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            inner = []
            for b in buf:
                if b:
                    inner.append(f"<p>{inline(b)}</p>")
                else:
                    inner.append("<p></p>")
            out.append("<blockquote>" + "\n".join(inner) + "</blockquote>")
            continue

        # unordered list
        if re.match(r"^[-*]\s+", stripped):
            close_p()
            out.append("<ul>")
            while i < len(lines):
                m2 = re.match(r"^(\s*)[-*]\s+(.*)$", lines[i])
                if not m2:
                    break
                item = m2.group(2)
                # simple continuation handling: if next line is plain (no list marker), append
                out.append(f"<li>{inline(item)}")
                i += 1
                # gather continuation lines
                while i < len(lines) and lines[i].strip() and not re.match(
                    r"^\s*[-*]\s+", lines[i]
                ) and not lines[i].strip().startswith("#") and not lines[i].strip().startswith(">"):
                    out.append(f" {inline(lines[i].strip())}")
                    i += 1
                out.append("</li>")
            out.append("</ul>")
            continue

        # ordered list
        if re.match(r"^\d+\.\s+", stripped):
            close_p()
            out.append("<ol>")
            while i < len(lines):
                m2 = re.match(r"^\s*\d+\.\s+(.*)$", lines[i])
                if not m2:
                    break
                out.append(f"<li>{inline(m2.group(1))}")
                i += 1
                while i < len(lines) and lines[i].strip() and not re.match(
                    r"^\s*\d+\.\s+", lines[i]
                ):
                    out.append(f" {inline(lines[i].strip())}")
                    i += 1
                out.append("</li>")
            out.append("</ol>")
            continue

        # paragraph
        if not in_p:
            out.append("<p>")
            in_p = True
        else:
            out.append(" ")
        out.append(inline(stripped))
        i += 1

    close_p()
    return "\n".join(out)


def main():
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    title = src.stem
    body = convert(src.read_text(encoding="utf-8"))
    html = (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN"><head><meta charset="utf-8">\n'
        f"<title>{escape(title)}</title>\n"
        f"<style>{CSS}</style></head>\n<body>\n{body}\n</body></html>"
    )
    dst.write_text(html, encoding="utf-8")
    print(f"wrote {dst} ({len(html)} chars, {html.count(chr(10))} lines)")


if __name__ == "__main__":
    main()
