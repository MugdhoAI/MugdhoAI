from __future__ import annotations

import argparse
import datetime as dt
import os
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from common import (
    GREEN_1,
    GREEN_2,
    GREEN_3,
    GREEN_4,
    INK,
    MUTED,
    panel_close,
    panel_open,
    xml_ok,
)

LEVEL_COLORS = {0: "#161b22", 1: GREEN_1, 2: GREEN_2, 3: GREEN_3, 4: GREEN_4}
CELL = 10
STEP = 13
X0 = 42
Y0 = 72


def fetch_contributions(username):
    url = f"https://github.com/users/{username}/contributions"
    response = requests.get(
        url,
        headers={"User-Agent": "github-profile-readme/1.0"},
        timeout=30,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    cells = soup.select("td[data-date][data-level]")
    tips = {
        tip.get("for"): tip.get_text(" ", strip=True)
        for tip in soup.select("tool-tip[for]")
    }

    data = []
    for cell in cells:
        cell_id = cell.get("id")
        date = cell.get("data-date")
        level = int(cell.get("data-level", "0"))
        text = tips.get(cell_id, "")
        match = re.search(r"([\d,]+)\s+contribution", text)
        count = int(match.group(1).replace(",", "")) if match else 0
        data.append({"date": date, "level": level, "count": count})

    if len(data) < 300:
        raise RuntimeError(f"Expected a 53-week calendar; only found {len(data)} cells")

    return sorted(data, key=lambda item: item["date"])[-371:]


def fallback_data():
    today = dt.date.today()
    start = today - dt.timedelta(days=370)
    return [
        {
            "date": (start + dt.timedelta(days=i)).isoformat(),
            "level": 0,
            "count": 0,
        }
        for i in range(371)
    ]


def render(username, output, static=False, data=None):
    data = data or fetch_contributions(username)
    width, height = 900, 205

    parts = [
        panel_open(width, height, "github-activity.svg", "contribution activity · 53 weeks"),
        f'<text x="24" y="47" fill="{INK}" font-size="12">contribution activity</text>',
        f'<text x="24" y="61" fill="{MUTED}" font-size="9">last 53 weeks · public GitHub contribution calendar</text>',
        "<g>",
    ]

    for index, item in enumerate(data):
        col = index // 7
        row = index % 7
        x = X0 + col * STEP
        y = Y0 + row * STEP
        level = item["level"]
        fill = LEVEL_COLORS[level]

        if static or level == 0:
            parts.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{fill}"/>'
            )
        else:
            delay = (col + row) * 0.018
            parts.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{fill}" opacity="0">'
                f'<animate attributeName="opacity" from="0" to="1" begin="{delay:.3f}s" dur="0.18s" fill="freeze"/></rect>'
            )

    parts.append("</g>")

    seen_months = set()
    for index, item in enumerate(data):
        date = dt.date.fromisoformat(item["date"])
        if date.day <= 7 and date.month not in seen_months:
            seen_months.add(date.month)
            x = X0 + (index // 7) * STEP
            parts.append(
                f'<text x="{x}" y="69" fill="{MUTED}" font-size="8">{date.strftime("%b")}</text>'
            )

    total = sum(item["count"] for item in data)
    active = sum(1 for item in data if item["count"])
    peak = max((item["count"] for item in data), default=0)

    parts.extend(
        [
            f'<text x="24" y="180" fill="{INK}" font-size="10">{total:,} contributions</text>',
            f'<text x="180" y="180" fill="{MUTED}" font-size="10">{active} active days</text>',
            f'<text x="312" y="180" fill="{MUTED}" font-size="10">peak day: {peak}</text>',
            f'<text x="742" y="180" fill="{MUTED}" font-size="8">Less</text>',
        ]
    )

    for index in range(5):
        x = 758 + index * 14
        parts.append(
            f'<rect x="{x}" y="172" width="10" height="10" rx="2" fill="{LEVEL_COLORS[index]}"/>'
        )

    parts.extend(
        [
            f'<text x="832" y="180" fill="{MUTED}" font-size="8">More</text>',
            panel_close(),
        ]
    )

    svg = "".join(parts)
    xml_ok(svg)
    Path(output).write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("username")
    parser.add_argument("output", nargs="?", default="assets/contrib-heatmap.svg")
    parser.add_argument("--static", action="store_true")
    args = parser.parse_args()

    static = args.static or os.getenv("STATIC") == "1"

    try:
        render(args.username, args.output, static=static)
    except Exception:
        if os.getenv("ALLOW_OFFLINE_PREVIEW") == "1":
            render(args.username, args.output, static=True, data=fallback_data())
        else:
            raise
