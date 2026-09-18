from __future__ import annotations
import argparse, os, re, datetime as dt
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from common import panel_open, panel_close, INK, MUTED, GREEN_1,GREEN_2,GREEN_3,GREEN_4, xml_ok

LEVEL_COLORS={0:"#161b22",1:GREEN_1,2:GREEN_2,3:GREEN_3,4:GREEN_4}

def fetch_contributions(username):
    url=f"https://github.com/users/{username}/contributions"
    r=requests.get(url,headers={"User-Agent":"github-profile-readme/1.0"},timeout=30)
    r.raise_for_status()
    soup=BeautifulSoup(r.text,"html.parser")
    cells=soup.select("td[data-date][data-level]")
    tips={t.get("for"): t.get_text(" ",strip=True) for t in soup.select("tool-tip[for]")}
    data=[]
    for c in cells:
        cid=c.get("id"); date=c.get("data-date")
        level=int(c.get("data-level","0"))
        tip=tips.get(cid,"")
        m=re.search(r"([\d,]+)\s+contribution",tip)
        count=int(m.group(1).replace(",","")) if m else 0
        data.append({"date":date,"level":level,"count":count})
    if len(data)<300:
        raise RuntimeError(f"Expected a 53-week calendar; only found {len(data)} cells")
    return sorted(data,key=lambda x:x["date"])[-371:]

def fallback_data():
    today=dt.date.today()
    start=today-dt.timedelta(days=370)
    return [{"date":(start+dt.timedelta(days=i)).isoformat(),"level":0,"count":0} for i in range(371)]

def render(username, output, static=False, data=None):
    data=data or fetch_contributions(username)
    W,H=900,230
    parts=[panel_open(W,H,"contrib-heatmap.svg","public contribution calendar · 53 weeks")]
    parts.append(f'<text x="24" y="52" fill="{MUTED}" font-size="10">$ curl github.com/users/{username}/contributions</text>')
    x0,y0=34,74; cell=11; gap=3
    # Level 0 is the panel background, so omit those cells to keep the SVG small.
    parts.append(f'<g>')
    for i,d in enumerate(data):
        if d["level"] == 0:
            continue
        col=i//7; row=i%7
        x=x0+col*(cell+gap); y=y0+row*(cell+gap)
        delay=(col+row)*.018
        if static:
            parts.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{LEVEL_COLORS[d["level"]]}"/>')
        else:
            parts.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{LEVEL_COLORS[d["level"]]}" opacity="0"><animate attributeName="opacity" from="0" to="1" begin="{delay:.3f}s" dur="0.18s" fill="freeze"/></rect>')
    parts.append('</g>')
    seen={}
    for i,d in enumerate(data):
        date=dt.date.fromisoformat(d["date"])
        if date.day<=7 and date.month not in seen:
            seen[date.month]=i//7
            x=x0+(i//7)*(cell+gap)
            parts.append(f'<text x="{x}" y="68" fill="{MUTED}" font-size="8">{date.strftime("%b")}</text>')
    lx=720; ly=164
    parts.append(f'<text x="{lx}" y="{ly}" fill="{MUTED}" font-size="8">Less</text>')
    for j,c in enumerate([LEVEL_COLORS[i] for i in range(5)]):
        x=748+j*14
        parts.append(f'<rect x="{x}" y="{ly-8}" width="10" height="10" rx="2" fill="{c}"/>')
    parts.append(f'<text x="822" y="{ly}" fill="{MUTED}" font-size="8">More</text>')
    total=sum(d["count"] for d in data)
    active=sum(1 for d in data if d["count"])
    best=max((d["count"] for d in data),default=0)
    parts.append(f'<text x="34" y="183" fill="{INK}" font-size="10">{total:,} contributions</text>')
    parts.append(f'<text x="190" y="183" fill="{MUTED}" font-size="10">{active} active days</text>')
    parts.append(f'<text x="310" y="183" fill="{MUTED}" font-size="10">peak day: {best}</text>')
    parts.append(f'<text x="34" y="204" fill="{MUTED}" font-size="8">Levels 0–4 · source: GitHub public contributions HTML · generated {dt.date.today().isoformat()}</text>')
    parts.append(panel_close())
    svg=''.join(parts); xml_ok(svg); Path(output).write_text(svg,encoding="utf-8")

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("username"); ap.add_argument("output",nargs="?",default="assets/contrib-heatmap.svg"); ap.add_argument("--static",action="store_true")
    a=ap.parse_args(); static=a.static or os.getenv("STATIC")=="1"
    try:
        render(a.username,a.output,static=static)
    except Exception:
        if os.getenv("ALLOW_OFFLINE_PREVIEW")=="1":
            render(a.username,a.output,static=True,data=fallback_data())
        else:
            raise