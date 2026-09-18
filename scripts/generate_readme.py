from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET


def dims(path):
    root = ET.fromstring(Path(path).read_text(encoding="utf-8"))
    return float(root.attrib["width"]), float(root.attrib["height"])


def build():
    p_w, p_h = dims("assets/ascii-portrait.svg")
    c_w, c_h = dims("assets/info-card.svg")
    p_aspect = p_w / p_h
    c_aspect = c_w / c_h

    total = 850
    pw = total * p_aspect / (p_aspect + c_aspect)
    cw = total * c_aspect / (p_aspect + c_aspect)

    readme = f'''<h1 align="center">All Asmaul Husnain · Mugdho</h1>

<p align="center">
  <strong>AI Engineer · Builder · Computer Science Student</strong><br>
  I build practical software, explore AI systems, and contribute to open source.
</p>

<p align="center">
  <a href="https://github.com/MugdhoAI">GitHub</a>
  ·
  <a href="mailto:allasmaulhusnain715@gmail.com">Email</a>
  ·
  <code>mugdhoAI / profile</code>
</p>

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

<p align="center">
  <sub>AI engineering · developer tooling · automation · cloud</sub>
</p>

<p align="center">
  <img src="./assets/contrib-heatmap.svg" width="100%" alt="Animated GitHub contribution activity" />
</p>

## What I build

I like turning ideas into working software — from AI-powered workflows and developer tools to automation utilities and experiments.

My current technical focus includes:

- **AI & intelligent applications** — Python, Azure AI, LangChain
- **Developer tooling** — CLIs, validation, testing, automation, CI/CD
- **Software engineering** — clean interfaces, regression tests, defensive input handling
- **Cloud & deployment** — Azure, Google Cloud, Netlify

## Open source

I don't just build projects in my own repositories. I also work on existing codebases, fixing concrete bugs and adding regression coverage.

| Contribution | What I worked on |
| --- | --- |
| [Provena #182](https://github.com/rajfirke/provena/pull/182) · **merged** | Added coverage for all top-level CLI commands in the help output |
| [Soup #1053](https://github.com/MakazhanAlpamys/Soup/pull/1053) · **merged** | Fixed Rich markup handling for user-controlled model names and added regression tests |
| [pycubrid #378](https://github.com/cubrid-lab/pycubrid/pull/378) · **open** | Added strict positive-integer validation for `Cursor.arraysize` across sync/async cursors |
| [cubrid-mcp-server #1](https://github.com/MugdhoAI/cubrid-mcp-server/pull/1) · **merged** | Fixed SQL-comment handling in audit categorization with regression coverage |

These contributions are part of a broader habit: find a real problem, understand the existing code, make the smallest reliable change, and prove it with tests.

## Selected projects

### [cubrid-mcp-server](https://github.com/MugdhoAI/cubrid-mcp-server)
A practical MCP server project focused on working with CUBRID databases and reliable SQL/audit behavior.

### [python-projects-showcase](https://github.com/MugdhoAI/python-projects-showcase)
A collection of Python work, reorganized as standalone projects while keeping the code easy to explore.

### [Decision-Simulator](https://github.com/MugdhoAI/Decision-Simulator)
A software experiment around modeling and exploring decisions programmatically.

### [interactive-dna](https://github.com/MugdhoAI/interactive-dna)
An interactive creative-coding project demonstrating experimentation beyond conventional backend/CLI work.

## How I work

**Build → test → document → iterate.**

I care about software that is understandable, reproducible, and useful — not just code that happens to run once.

<p align="center">
  <sub>Profile visuals are generated from self-contained SVGs. The contribution calendar is refreshed automatically from GitHub's public contribution data.</sub>
</p>
'''
    Path("README.md").write_text(readme, encoding="utf-8")


if __name__ == "__main__":
    build()
