#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Generador de versión HTML del informe técnico del Entregable 3:
Entregable3_Informe_Laboratorio_Fallas_Observabilidad.html
"""

from pathlib import Path
import markdown

ROOT_DIR = Path(__file__).resolve().parent
MD_PATH = ROOT_DIR / "Entregable3_Informe_Laboratorio_Fallas_Observabilidad.md"
HTML_PATH = ROOT_DIR / "Entregable3_Informe_Laboratorio_Fallas_Observabilidad.html"

TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Informe Técnico: Entregable 3 — El Corazón del Proyecto</title>
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
    --verde-bg: #ECFDF5;
    --rojo: #DC2626;
    --rojo-bg: #FEF2F2;
    --azul-bg: #EFF6FF;
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
    max-width: 62rem;
    margin: 0 auto;
    padding: 3rem 2rem 6rem;
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
    font-size: 2.3rem;
    line-height: 1.2;
    color: var(--tinta);
    margin: 0 0 0.8rem;
    letter-spacing: -0.02em;
  }
  .subtitulo {
    font-size: 1.15rem;
    color: var(--teal);
    font-weight: 600;
    margin: 0 0 1.2rem;
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
    font-size: 1.6rem;
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
    padding: 0.65rem 0.8rem;
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
  pre {
    background: #0F172A;
    color: #E2E8F0;
    padding: 1rem 1.2rem;
    border-radius: 8px;
    overflow-x: auto;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.86rem;
    line-height: 1.55;
    margin: 1.2rem 0 1.8rem;
  }
  code {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.88em;
    background: #F1F5F9;
    color: #0F172A;
    padding: 0.15rem 0.35rem;
    border-radius: 4px;
    border: 1px solid #E2E8F0;
  }
  pre code {
    background: transparent;
    color: inherit;
    padding: 0;
    border: none;
  }
  blockquote {
    margin: 1.4rem 0;
    padding: 1rem 1.2rem;
    background: var(--panel);
    border-left: 4px solid var(--teal);
    border-radius: 0 6px 6px 0;
    color: var(--texto);
    font-size: 0.93rem;
  }
  blockquote p { margin: 0; }
  .badge-pasa {
    background: var(--verde-bg);
    color: var(--verde);
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    font-weight: 700;
    font-size: 0.8rem;
    display: inline-block;
    border: 1px solid #A7F3D0;
  }
  .badge-destacado {
    background: var(--azul-bg);
    color: var(--teal);
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    font-weight: 700;
    font-size: 0.8rem;
    display: inline-block;
    border: 1px solid #BFDBFE;
  }
  footer.pie {
    margin-top: 4rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--linea);
    font-size: 0.82rem;
    color: var(--suave);
    text-align: center;
  }
  @media print {
    body { font-size: 11pt; }
    .contenedor { max-width: 100%; padding: 0; }
    h2 { page-break-before: always; }
    table, pre { page-break-inside: avoid; }
  }
</style>
</head>
<body>
<div class="contenedor">
  <header class="portada">
    <div class="institucion">Universidad EAFIT · Aplicaciones y Sistemas Escalables (2026-2)</div>
    <h1>Informe Técnico: Entregable 3 — El Corazón del Proyecto</h1>
    <div class="subtitulo">Fallas Configurables · Experimentación · Observabilidad · Meta de Mejora del 10%</div>
    <div class="metadatos">
      <div><strong>Proyecto:</strong> Portal B2B Retail</div>
      <div><strong>Equipo:</strong> Grupo EKS (Sara López Marín / Luis Alejandro Castrillón Pulgarin)</div>
      <div><strong>Fecha:</strong> Octubre 2026</div>
      <div><strong>Código:</strong> <a href="https://github.com/lacastrilp/Sistemas-Escalables" target="_blank">github.com/lacastrilp/Sistemas-Escalables</a></div>
    </div>
  </header>

  <main>
    {cuerpo}
  </main>

  <footer class="pie">
    Portal B2B Retail · Aplicaciones y Sistemas Escalables · Universidad EAFIT 2026-2 · Entregable 3
  </footer>
</div>
</body>
</html>
"""

def main():
    if not MD_PATH.exists():
        print(f"ERROR: No se encontró {MD_PATH}")
        return

    raw_md = MD_PATH.read_text(encoding="utf-8")

    # Reemplazar encabezados repetidos de título que ya están en la portada HTML
    lineas = raw_md.splitlines()
    i = 0
    while i < len(lineas) and not lineas[i].startswith("## 1. Momento 1"):
        i += 1
    cuerpo_md = "\n".join(lineas[i:])

    html_content = markdown.markdown(
        cuerpo_md,
        extensions=["tables", "fenced_code", "nl2br", "toc"]
    )

    # Estilos enriquecidos para badges
    html_content = html_content.replace("<strong>SÍ (SUPERADA)</strong>", '<span class="badge-pasa">SÍ (SUPERADA)</span>')
    html_content = html_content.replace("<strong>PASA_OBJETIVO</strong>", '<span class="badge-pasa">PASA_OBJETIVO</span>')

    full_html = TEMPLATE.replace("{cuerpo}", html_content)
    HTML_PATH.write_text(full_html, encoding="utf-8")
    print(f"Informe HTML generado con éxito en: {HTML_PATH}")


if __name__ == "__main__":
    main()
