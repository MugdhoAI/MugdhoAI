from __future__ import annotations
import argparse, os
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps
import cv2
from common import panel_open, panel_close, INK, MUTED, esc, xml_ok

RAMP = " .`:-=+*csS#%@"

def remove_background(img: Image.Image) -> Image.Image:
    try:
        from rembg import remove
        return remove(img).convert("RGBA")
    except Exception:
        a = np.array(img.convert("RGBA"))
        rgb = a[:, :, :3].astype(np.int16)
        near_white = (rgb.min(axis=2) > 242) & (rgb.max(axis=2) > 248)
        alpha = np.where(near_white, 0, 255).astype(np.uint8)
        alpha = cv2.GaussianBlur(alpha, (5,5), 0)
        out = a.copy()
        out[:, :, 3] = alpha
        return Image.fromarray(out, "RGBA")

def alpha_crop(rgba: Image.Image) -> Image.Image:
    alpha = np.array(rgba.getchannel("A"))
    ys, xs = np.where(alpha > 10)
    if len(xs) == 0:
        return rgba
    y0, y1 = ys.min(), ys.max()
    upper_end = y0 + int((y1-y0) * .60)
    widths = []
    for y in range(y0, max(y0+1, upper_end)):
        xx = np.where(alpha[y] > 10)[0]
        if len(xx): widths.append(xx.max()-xx.min()+1)
    head_width = int(np.median(widths)) if widths else (xs.max()-xs.min()+1)
    cx = int((xs.min()+xs.max())/2)
    pad_x = int(head_width * .16)
    left = max(0, cx - head_width//2 - pad_x)
    right = min(rgba.width, cx + head_width//2 + pad_x)
    top = max(0, y0 - int((y1-y0)*.035))
    bottom = min(rgba.height, y1 + int((y1-y0)*.015))
    return rgba.crop((left, top, right, bottom))

def preprocess(rgba: Image.Image, out_w=92, out_h=56) -> np.ndarray:
    rgb = Image.new("RGB", rgba.size, (13,17,23))
    rgb.paste(rgba.convert("RGB"), mask=rgba.getchannel("A"))
    gray = np.array(ImageOps.grayscale(rgb))
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    gray = clahe.apply(gray)
    gray = np.clip((gray.astype(np.float32)-45.0)*1.22, 0, 255).astype(np.uint8)
    return cv2.resize(gray, (out_w, out_h), interpolation=cv2.INTER_AREA)

def row_runs(chars):
    runs=[]; i=0
    while i < len(chars):
        if chars[i] == " ":
            i += 1; continue
        j=i+1
        while j < len(chars) and chars[j] != " ": j += 1
        runs.append((i, ''.join(chars[i:j])))
        i=j
    return runs

def render(photo: str, output: str, static=False):
    W,H = 480,640
    cut=alpha_crop(remove_background(Image.open(photo).convert("RGBA")))
    arr=preprocess(cut, 64, 40)
    lines=[]
    for row in arr:
        idx=np.clip((row.astype(np.float32)/256*len(RAMP)).astype(int),0,len(RAMP)-1)
        lines.append(''.join(RAMP[i] for i in idx))
    x0,y0=28,72
    char_w=6.5
    line_h=12.2
    parts=[panel_open(W,H,"ascii-portrait.svg","monochrome / camera portrait")]
    parts.append(f'<text x="28" y="52" fill="{MUTED}" font-size="10">$ python scripts/generate_portrait.py</text>')
    parts.append(f'<text x="{W-100}" y="52" fill="{MUTED}" font-size="9">{"STATIC" if static else "LIVE"}</text>')
    parts.append(f'<g fill="{INK}" font-size="7.8">')
    for r, chars in enumerate(lines):
        y=y0+r*line_h
        delay=(r*.055)
        opacity='1' if static else '0'
        runs=row_runs(chars)
        parts.append(f'<g opacity="{opacity}">')
        for start, text in runs:
            x=x0+start*char_w
            width=max(1,len(text)*char_w)
            parts.append(f'<text x="{x:.1f}" y="{y:.1f}" textLength="{width:.1f}" lengthAdjust="spacingAndGlyphs">{esc(text)}</text>')
        if not static:
            parts.append(f'<animate attributeName="opacity" from="0" to="1" begin="{delay:.3f}s" dur="0.08s" fill="freeze"/>')
        parts.append('</g>')
    parts.append('</g>')
    parts.append(f'<text x="28" y="{H-20}" fill="{MUTED}" font-size="9">rows: {len(lines)} · glyphs: {RAMP.strip()} <tspan fill="{INK}">▌</tspan></text>')
    parts.append(panel_close())
    svg=''.join(parts)
    xml_ok(svg)
    Path(output).write_text(svg,encoding="utf-8")

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("photo"); ap.add_argument("output", nargs="?", default="assets/ascii-portrait.svg")
    ap.add_argument("--static", action="store_true")
    a=ap.parse_args()
    render(a.photo,a.output,a.static or os.getenv("STATIC")=="1")