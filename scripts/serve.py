"""Serve the audit planning pack on localhost, read-only.

Browse outputs/ (register, memo, matrix, program, challenges, review, samples,
analytics) in the browser. Markdown is rendered; CSV and JSON are shown as
text. Nothing is written and nothing leaves 127.0.0.1.

Run: .venv/bin/python -I scripts/serve.py [--port 8000] [--root outputs]
"""
import argparse
import html
import http.server
import os
import re
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

STYLE = """
body{font:15px/1.5 system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#1b1f24}
table{border-collapse:collapse;margin:1rem 0;display:block;overflow-x:auto}
th,td{border:1px solid #ccd;padding:.3rem .6rem;text-align:left;vertical-align:top}
th{background:#f0f2f6} code,pre{background:#f6f8fa;border-radius:4px}
pre{padding:.8rem;overflow-x:auto} code{padding:.1rem .3rem}
nav a{margin-right:1rem} .dir{font-weight:600}
"""


def page(title, body):
    return (
        f"<!doctype html><meta charset=utf-8><title>{html.escape(title)}</title>"
        f"<style>{STYLE}</style><nav><a href='/'>Pack index</a></nav>{body}"
    ).encode()


def inline(text):
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    return re.sub(r"(?<!\*)\*([^*\s][^*]*)\*(?!\*)", r"<em>\1</em>", text)


def render_markdown(src):
    out, lines, i = [], src.split("\n"), 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            out.append("<pre>" + html.escape("\n".join(lines[i + 1:j])) + "</pre>")
            i = j + 1
        elif m := re.match(r"(#{1,6})\s+(.*)", line):
            n = len(m.group(1))
            out.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
            i += 1
        elif line.lstrip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            body = [r for r in rows if not all(re.fullmatch(r":?-{2,}:?", c) for c in r)]
            html_rows = []
            for k, r in enumerate(body):
                tag = "th" if k == 0 else "td"
                html_rows.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in r) + "</tr>")
            out.append("<table>" + "".join(html_rows) + "</table>")
        elif re.match(r"\s*[-*]\s+", line):
            items = []
            while i < len(lines) and re.match(r"\s*[-*]\s+", lines[i]):
                items.append("<li>" + inline(re.sub(r"^\s*[-*]\s+", "", lines[i])) + "</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
        elif line.strip():
            para = []
            while i < len(lines) and lines[i].strip() and not re.match(r"(#|```|\s*\||\s*[-*]\s)", lines[i]):
                para.append(lines[i])
                i += 1
            out.append("<p>" + inline(" ".join(para)) + "</p>")
        else:
            i += 1
    return "\n".join(out)


class Handler(http.server.BaseHTTPRequestHandler):
    root = os.path.join(ROOT, "outputs")

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.command, self.path))

    def send(self, code, body, ctype="text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        rel = urllib.parse.unquote(urllib.parse.urlparse(self.path).path).strip("/")
        full = os.path.realpath(os.path.join(self.root, rel))
        if os.path.commonpath([full, self.root]) != self.root:
            return self.send(403, page("Forbidden", "<h1>Forbidden</h1>"))
        if os.path.isdir(full):
            return self.send(200, self.listing(full, rel))
        if not os.path.isfile(full):
            return self.send(404, page("Not found", f"<h1>Not found</h1><p>{html.escape(rel)}</p>"))
        with open(full, encoding="utf-8", errors="replace") as f:
            text = f.read()
        name = html.escape(rel)
        if full.endswith(".md"):
            return self.send(200, page(rel, render_markdown(text)))
        return self.send(200, page(rel, f"<h2>{name}</h2><pre>{html.escape(text)}</pre>"))

    def listing(self, full, rel):
        items = []
        if rel:
            items.append(f"<li class=dir><a href='/{html.escape(os.path.dirname(rel))}'>..</a></li>")
        for name in sorted(os.listdir(full), key=lambda n: (not os.path.isdir(os.path.join(full, n)), n)):
            href = urllib.parse.quote("/" + os.path.join(rel, name))
            cls = " class=dir" if os.path.isdir(os.path.join(full, name)) else ""
            size = "" if cls else f" <small>({os.path.getsize(os.path.join(full, name)):,} bytes)</small>"
            items.append(f"<li{cls}><a href='{href}'>{html.escape(name)}</a>{size}</li>")
        title = "/" + rel
        return page(title, f"<h1>Audit planning pack <small>{html.escape(title)}</small></h1><ul>{''.join(items)}</ul>")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--root", default=os.path.join(ROOT, "outputs"))
    args = ap.parse_args()
    root = os.path.realpath(args.root)
    if not os.path.isdir(root):
        sys.exit(f"STOPPED: {root} does not exist; nothing to serve")
    Handler.root = root
    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Serving {root} at http://localhost:{args.port}  (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
