from __future__ import annotations
import argparse, os
from pathlib import Path
from common import panel_open, panel_close, INK, MUTED, GREEN_4, esc, xml_ok

ROWS = [
    ("name", "All Asmaul Husnain (Mugdho)"),
    ("role", "AI Engineer | Entrepreneur | CS Student"),
    ("build", "ApplyFixer · Virtual Farm · Solyn"),
    ("stack", "Python · Azure AI · LangChain · JavaScript"),
    ("cloud", "Azure · Google Cloud · Netlify"),
    ("location", "Meherpur, Bangladesh"),
]

def render(output, static=False):
    W,H=560,640
    parts=[panel_open(W,H,"info-card.svg","identity / build context")]
    parts.append(f'<text x="28" y="58" fill="{MUTED}" font-size="11">$ neofetch --profile MugdhoAI</text>')
    parts.append(f'<text x="28" y="94" fill="{INK}" font-size="20" font-weight="700">MUGDHOAI</text>')
    parts.append(f'<text x="28" y="114" fill="{MUTED}" font-size="10">AI ENGINEERING · PRODUCTS · OPEN SOURCE</text>')
    start_y=158; step=46
    for i,(k,v) in enumerate(ROWS):
        y=start_y+i*step
        delay=0 if static else i*.16
        opacity='1' if static else '0'
        anim='' if static else f'<animate attributeName="opacity" from="0" to="1" begin="{delay:.2f}s" dur="0.30s" fill="freeze"/>'
        parts.append(f'<g opacity="{opacity}"><text x="30" y="{y}" fill="{MUTED}" font-size="10">{esc(k.upper())}</text><text x="132" y="{y}" fill="{INK}" font-size="13">{esc(v)}</text>{anim}</g>')
    y=445
    parts.append(f'<line x1="28" y1="{y}" x2="{W-28}" y2="{y}" stroke="#21262d"/>')
    focus=[
        "Building ApplyFixer — AI resume improvement",
        "Scaling Virtual Farm through product validation",
        "Learning by shipping and contributing",
    ]
    for i,v in enumerate(focus):
        yy=y+35+i*32
        delay=0 if static else 1.0+i*.16
        opacity='1' if static else '0'
        anim='' if static else f'<animate attributeName="opacity" from="0" to="1" begin="{delay:.2f}s" dur="0.30s" fill="freeze"/>'
        parts.append(f'<g opacity="{opacity}"><text x="30" y="{yy}" fill="{GREEN_4}" font-size="10">›</text><text x="45" y="{yy}" fill="{INK}" font-size="11">{esc(v)}</text>{anim}</g>')
    parts.append(f'<text x="28" y="{H-20}" fill="{MUTED}" font-size="10">github.com/MugdhoAI <tspan fill="{GREEN_4}">●</tspan> building in public</text>')
    parts.append(panel_close())
    svg=''.join(parts); xml_ok(svg); Path(output).write_text(svg,encoding="utf-8")

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("output",nargs="?",default="assets/info-card.svg"); ap.add_argument("--static",action="store_true")
    a=ap.parse_args(); render(a.output,a.static or os.getenv("STATIC")=="1")