from __future__ import annotations
from pathlib import Path
import xml.etree.ElementTree as ET

def dims(path):
    root=ET.fromstring(Path(path).read_text(encoding="utf-8"))
    return float(root.attrib["width"]), float(root.attrib["height"])

def build():
    p_w,p_h=dims("assets/ascii-portrait.svg")
    c_w,c_h=dims("assets/info-card.svg")
    p_aspect=p_w/p_h; c_aspect=c_w/c_h
    total=850
    pw=total*p_aspect/(p_aspect+c_aspect)
    cw=total*c_aspect/(p_aspect+c_aspect)
    readme=f'''<h3 align="center">mugdhoAI · terminal profile</h3>

<p align="center">
  <img src="./assets/contrib-heatmap.svg" width="100%" alt="GitHub contribution heatmap" />
</p>

<br/>

<table>
  <tr>
    <td width="{pw:.1f}" valign="top">
      <img src="./assets/ascii-portrait.svg" width="100%" alt="Animated ASCII portrait" />
    </td>
    <td width="{cw:.1f}" valign="top">
      <img src="./assets/info-card.svg" width="100%" alt="Animated profile information card" />
    </td>
  </tr>
</table>

<br/>

<p align="center"><sub>Generated from self-contained SVGs · contribution data comes directly from GitHub's public contribution calendar.</sub></p>
'''
    Path("README.md").write_text(readme,encoding="utf-8")

if __name__=="__main__": build()