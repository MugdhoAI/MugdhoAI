from __future__ import annotations
from html import escape

BG = "#0d1117"
BORDER = "#21262d"
INK = "#e6edf3"
MUTED = "#8b949e"
GREEN_1 = "#0e4429"
GREEN_2 = "#006d32"
GREEN_3 = "#26a641"
GREEN_4 = "#39d353"
MONO = "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, DejaVu Sans Mono, monospace"

def esc(s: str) -> str:
    return escape(str(s), quote=True)

def panel_open(width: int, height: int, title: str, subtitle: str = "") -> str:
    title = esc(title)
    subtitle = esc(subtitle)
    sub = f'<text x="22" y="30" fill="{MUTED}" font-size="11">{subtitle}</text>' if subtitle else ""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">
<rect width="{width}" height="{height}" rx="10" fill="{BG}" stroke="{BORDER}" stroke-width="1"/><g font-family="{MONO}">
<circle cx="18" cy="18" r="4" fill="#ff5f56"/>
<circle cx="32" cy="18" r="4" fill="#ffbd2e"/>
<circle cx="46" cy="18" r="4" fill="#27c93f"/>
<text x="62" y="22" fill="{MUTED}" font-size="11">{title}</text>
{sub}
'''
def panel_close() -> str:
    return "</g></svg>"

def xml_ok(svg: str):
    import xml.etree.ElementTree as ET
    ET.fromstring(svg)
    assert "<script" not in svg.lower()
    low = svg.lower()
    assert 'href="http' not in low and "href='http" not in low
    assert 'xlink:href="http' not in low and "xlink:href='http" not in low