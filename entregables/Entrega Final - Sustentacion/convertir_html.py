#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Compilador de Guia_Sustentacion.md a HTML limpio y sobrio.
Universidad EAFIT - Aplicaciones y Sistemas Escalables
"""

from pathlib import Path
import markdown

ROOT_DIR = Path(__file__).resolve().parent
MD_PATH = ROOT_DIR / "Sustentacion.md"
HTML_PATH = ROOT_DIR / "Sustentacion.html"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Guía de Sustentación - Portal B2B Retail (100 Puntos)</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {
    --primary: #1e3a8a;
    --primary-light: #eff6ff;
    --text: #1f2937;
    --text-muted: #4b5563;
    --border: #e5e7eb;
    --bg-light: #f9fafb;
    --code-bg: #111827;
    --success-bg: #ecfdf5;
    --success-text: #065f46;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: #ffffff;
    color: var(--text);
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    font-size: 15px;
    line-height: 1.6;
    padding: 2.5rem 1.5rem;
  }
  .container {
    max-width: 900px;
    margin: 0 auto;
  }
  header {
    border-bottom: 2px solid var(--primary);
    padding-bottom: 1.5rem;
    margin-bottom: 2rem;
  }
  h1 {
    font-size: 1.9rem;
    color: var(--primary);
    margin-bottom: 0.5rem;
    font-weight: 700;
  }
  h2 {
    font-size: 1.4rem;
    color: var(--primary);
    margin: 2.2rem 0 1rem;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid var(--border);
    font-weight: 600;
  }
  h3 {
    font-size: 1.15rem;
    color: #111827;
    margin: 1.5rem 0 0.6rem;
    font-weight: 600;
  }
  p { margin-bottom: 1rem; }
  ul, ol { margin: 0 0 1rem 1.5rem; }
  li { margin-bottom: 0.35rem; }
  table {
    width: 100%;
    border-collapse: collapse;
    margin: 1.5rem 0;
    font-size: 0.9rem;
  }
  th, td {
    border: 1px solid var(--border);
    padding: 0.65rem 0.8rem;
    text-align: left;
    vertical-align: top;
  }
  th {
    background: var(--bg-light);
    color: #111827;
    font-weight: 600;
  }
  tr:nth-child(even) td { background: #fafafa; }
  pre {
    background: var(--code-bg);
    color: #f3f4f6;
    padding: 1rem;
    border-radius: 6px;
    overflow-x: auto;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.88rem;
    margin: 1rem 0 1.5rem;
  }
  code {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.88em;
    background: #f3f4f6;
    padding: 0.15rem 0.35rem;
    border-radius: 4px;
    color: #111827;
  }
  pre code {
    background: transparent;
    padding: 0;
    color: inherit;
  }
  blockquote {
    border-left: 4px solid var(--primary);
    background: var(--primary-light);
    padding: 0.8rem 1rem;
    margin: 1rem 0;
    border-radius: 0 4px 4px 0;
  }
  blockquote p { margin: 0; }
  .badge-success {
    background: var(--success-bg);
    color: var(--success-text);
    padding: 0.15rem 0.45rem;
    border-radius: 4px;
    font-weight: 600;
    font-size: 0.82rem;
  }
  footer {
    margin-top: 3rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--border);
    font-size: 0.85rem;
    color: var(--text-muted);
    text-align: center;
  }
  @media print {
    body { padding: 0; font-size: 11pt; }
    h2 { page-break-before: always; }
  }
</style>
</head>
<body>
<div class="container">
  <main>
    {content}
  </main>
  <footer>
    Universidad EAFIT · Aplicaciones y Sistemas Escalables (2026-2) · Sara López Marín & Luis Alejandro Castrillón Pulgarin
  </footer>
</div>
</body>
</html>
"""

def main():
    if not MD_PATH.exists():
        print(f"Error: {MD_PATH} no existe.")
        return

    text = MD_PATH.read_text(encoding="utf-8")
    html_body = markdown.markdown(text, extensions=["tables", "fenced_code", "nl2br"])
    html_body = html_body.replace("<strong>SÍ</strong>", '<span class="badge-success">SÍ</span>')
    html_body = html_body.replace("<td>SÍ</td>", '<td><span class="badge-success">SÍ</span></td>')

    full_html = HTML_TEMPLATE.replace("{content}", html_body)
    HTML_PATH.write_text(full_html, encoding="utf-8")
    print(f"Guia HTML generada exitosamente en: {HTML_PATH}")

if __name__ == "__main__":
    main()
