#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Generador de versión HTML del informe técnico:
Entregable2_Informe_Escalabilidad_de_Datos.html
(Preserva intacto Entregable2_Escalabilidad_de_datos.html)
"""

from pathlib import Path
import markdown

ROOT_DIR = Path(__file__).resolve().parent
MD_PATH = ROOT_DIR / "Entregable2_Informe_Escalabilidad_de_Datos.md"
HTML_PATH = ROOT_DIR / "Entregable2_Informe_Escalabilidad_de_Datos.html"

TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Informe Técnico: Entregable 2 — Escalabilidad de los Datos</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&family=Newsreader:ital,opsz,wght@0,6..72,600;0,6..72,700;1,6..72,400&display=swap" rel="stylesheet">
<style>
  :root {
    --tinta: #0F2240;
    --teal: #17607D;
    --ambar: #D99A2B;
    --ambar-suave: #FDF8ED;
    --panel: #F4F7FA;
    --linea: #DCE3EC;
    --texto: #1F2A37;
    --suave: #4B5563;
    --papel: #FFFFFF;
    --verde: #059669;
    --rojo: #DC2626;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--papel);
    color: var(--texto);
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    font-size: 15px;
    line-height: 1.65;
  }
  .contenedor {
    max-width: 56rem;
    margin: 0 auto;
    padding: 3rem 1.8rem 6rem;
  }
  header.portada {
    border-bottom: 3px solid var(--tinta);
    padding-bottom: 1.8rem;
    margin-bottom: 2.5rem;
  }
  .institucion {
    font-size: 0.85rem;
    letter-spacing: 0.08em;
    color: var(--teal);
    font-weight: 700;
    text-transform: uppercase;
    margin: 0 0 0.8rem;
  }
  h1 {
    font-family: 'Newsreader', Georgia, serif;
    font-weight: 700;
    font-size: 2.5rem;
    line-height: 1.15;
    color: var(--tinta);
    margin: 0 0 0.8rem;
    letter-spacing: -0.02em;
  }
  .metadatos {
    display: flex;
    flex-wrap: wrap;
    gap: 1.5rem;
    font-size: 0.92rem;
    color: var(--suave);
    border-top: 1px solid var(--linea);
    padding-top: 0.9rem;
    margin-top: 1.2rem;
  }
  .metadatos strong { color: var(--tinta); }
  h2 {
    font-family: 'Newsreader', Georgia, serif;
    font-size: 1.65rem;
    color: var(--tinta);
    margin: 2.8rem 0 1rem;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid var(--linea);
  }
  h3 {
    font-size: 1.15rem;
    color: var(--teal);
    margin: 1.8rem 0 0.8rem;
    font-weight: 700;
  }
  p { margin: 0 0 1rem; }
  table {
    border-collapse: collapse;
    width: 100%;
    margin: 1.4rem 0 2rem;
    font-size: 0.88rem;
  }
  th, td {
    border: 1px solid var(--linea);
    padding: 0.6rem 0.75rem;
    text-align: left;
    vertical-align: top;
  }
  thead th {
    background: var(--tinta);
    color: #FFFFFF;
    font-weight: 600;
    font-size: 0.82rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  tbody tr:nth-child(even) { background: #F9FAFB; }
  tbody tr:hover { background: #F3F4F6; }
  img {
    max-width: 100%;
    height: auto;
    border-radius: 6px;
    border: 1px solid var(--linea);
    margin: 1rem 0 0.4rem;
    display: block;
  }
  em {
    display: block;
    font-size: 0.84rem;
    color: var(--suave);
    margin-bottom: 1.6rem;
  }
  pre {
    background: #0F172A;
    color: #E2E8F0;
    padding: 1rem 1.2rem;
    border-radius: 6px;
    overflow-x: auto;
    font-family: 'JetBrains Mono', Consolas, monospace;
    font-size: 0.85rem;
    line-height: 1.55;
    margin: 1rem 0 1.5rem;
  }
  code {
    font-family: 'JetBrains Mono', Consolas, monospace;
    font-size: 0.88em;
    background: var(--panel);
    color: var(--tinta);
    padding: 0.15em 0.35em;
    border-radius: 3px;
  }
  pre code {
    background: transparent;
    color: inherit;
    padding: 0;
  }
  blockquote {
    border-left: 4px solid var(--teal);
    background: var(--panel);
    margin: 1.4rem 0;
    padding: 0.9rem 1.2rem;
    border-radius: 0 6px 6px 0;
  }
  blockquote p { margin: 0; }
  .badge-pasa {
    background: #D1FAE5;
    color: #065F46;
    padding: 0.2em 0.5em;
    border-radius: 3px;
    font-weight: 700;
    font-size: 0.78rem;
  }
  @media print {
    body { font-size: 9.5pt; }
    .contenedor { max-width: none; padding: 0; }
    h2 { page-break-after: avoid; }
    table { page-break-inside: auto; font-size: 8pt; }
    tr { page-break-inside: avoid; }
    pre { font-size: 7.5pt; background: #FFF; color: #000; border: 1px solid #CCC; }
  }
</style>
</head>
<body>
<div class="contenedor">
__BODY__
</div>
</body>
</html>
"""

def main():
    with open(MD_PATH, "r", encoding="utf-8") as f:
        md_text = f.read()

    # Procesar markdown a HTML
    html_body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "toc"]
    )

    # Estilizar badges PASA
    html_body = html_body.replace("<strong>PASA_OBJETIVO</strong>", "<span class='badge-pasa'>PASA_OBJETIVO</span>")
    html_body = html_body.replace("<strong>PASA</strong>", "<span class='badge-pasa'>PASA</span>")
    html_body = html_body.replace("<strong>PASA_MEDIDO</strong>", "<span class='badge-pasa'>PASA_MEDIDO</span>")

    final_html = TEMPLATE.replace("__BODY__", html_body)

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(final_html)

    print(f"[OK] Informe HTML generado con éxito en: {HTML_PATH}")

if __name__ == "__main__":
    main()
