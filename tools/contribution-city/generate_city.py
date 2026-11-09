#!/usr/bin/env python3
"""Generate the Contribution City SVG for the MugdhoAI profile README.

v2 layout: a long isometric strip of the last 24 weeks of contributions
that starts at the top of the card and flows down to the bottom right,
oldest weeks at the top, newest towers at the front. Stats sit in the
top left corner. On load, buildings grow from their plots and trees
sprout, staggered along the strip, then everything settles. The base
state is the finished city so static renderers show the same picture.

Data comes from the GitHub GraphQL API using GITHUB_TOKEN. Set the
repository secret CITY_TOKEN to a personal access token owned by the
profile user to make the contribution total match what the owner sees
on their own profile (including private contributions); when the
secret is absent the workflow falls back to the built-in token, which
sees public contributions only. If the GraphQL call fails, a fallback
path scrapes the public contributions page and the REST API.
"""
import argparse
import colorsys
import hashlib
import json
import math
import os
import random
import re
import subprocess
import sys
from datetime import date, datetime, timedelta

API = "https://api.github.com/graphql"
LEVEL_COLORS = ["#9be9a8", "#40c463", "#30a14e", "#216e39"]
PARK = "#17351f"
GROW_TOTAL = 2.8
WEEKS_SHOWN = 24
LANG_COLORS = {
    "Python": "#3572A5", "HTML": "#e34c26", "CSS": "#563d7c",
    "C": "#a8b9cc", "C++": "#f34b7d", "TypeScript": "#3178c6",
    "JavaScript": "#d8b93c", "Shell": "#89e051", "Dockerfile": "#384d54",
    "Jupyter Notebook": "#DA5B0B", "Go": "#00ADD8", "Rust": "#dea584",
}


def curl_json(url, payload=None, token=""):
    args = ["curl", "-s", "--fail", "--max-time", "30", url]
    if token:
        args += ["-H", f"Authorization: bearer {token}"]
    args += ["-H", "Accept: application/vnd.github+json",
             "-H", "User-Agent: contribution-city"]
    if payload is not None:
        args += ["-H", "Content-Type: application/json",
                 "-d", json.dumps(payload)]
    out = subprocess.run(args, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"curl failed for {url}: {out.stderr.strip()[:200]}")
    return json.loads(out.stdout)


def fetch_graphql(user, token):
    q = """query($login:String!){
      user(login:$login){
        contributionsCollection{
          contributionCalendar{ totalContributions
            weeks{ contributionDays{ date contributionCount } } }
        }
        repositories(first:100, ownerAffiliations:OWNER, isFork:false,
                     orderBy:{field:STARGAZERS, direction:DESC}){
          totalCount
          nodes{ stargazerCount forkCount
                 languages(first:12, orderBy:{field:SIZE, direction:DESC}){
                   edges{ size node{ name } } } }
        }
      }
    }"""
    data = curl_json(API, {"query": q, "variables": {"login": user}}, token)
    u = data["data"]["user"]
    cal = u["contributionsCollection"]["contributionCalendar"]
    days, total = {}, cal["totalContributions"]
    for wk in cal["weeks"]:
        for d in wk["contributionDays"]:
            days[d["date"]] = d["contributionCount"]
    lang_bytes, stars, forks = {}, 0, 0
    for repo in u["repositories"]["nodes"]:
        stars += repo["stargazerCount"]
        forks += repo["forkCount"]
        for e in repo["languages"]["edges"]:
            name = e["node"]["name"]
            lang_bytes[name] = lang_bytes.get(name, 0) + e["size"]
    return model_from(days, total, lang_bytes, stars, forks)


def fetch_fallback(user, token):
    html = subprocess.run(
        ["curl", "-s", "--fail", "--max-time", "30",
         f"https://github.com/users/{user}/contributions",
         "-H", "User-Agent: contribution-city"],
        capture_output=True, text=True)
    if html.returncode != 0:
        raise RuntimeError("fallback page fetch failed")
    cells = dict(re.findall(
        r'data-date="(\d{4}-\d{2}-\d{2})"[^>]*'
        r'id="(contribution-day-component-[\d-]+)"', html.stdout))
    tips = dict(re.findall(
        r'<tool-tip[^>]*for="(contribution-day-component-[\d-]+)"[^>]*>'
        r'\s*(?:No contributions|(\d+)\s+contribution)', html.stdout))
    days = {}
    for dstr, cid in cells.items():
        tip = tips.get(cid, "")
        days[dstr] = int(tip) if tip else 0
    repos = curl_json(
        f"https://api.github.com/users/{user}/repos?per_page=100&type=owner",
        token=token)
    lang_bytes, stars, forks = {}, 0, 0
    for r in repos:
        if r.get("fork"):
            continue
        stars += r.get("stargazers_count", 0)
        forks += r.get("forks_count", 0)
        if r.get("language"):
            lang_bytes[r["language"]] = \
                lang_bytes.get(r["language"], 0) + r.get("size", 0)
    return model_from(days, sum(days.values()), lang_bytes, stars, forks)


def model_from(days, total, lang_bytes, stars, forks):
    langs = []
    tot_bytes = sum(lang_bytes.values()) or 1
    for name, size in sorted(lang_bytes.items(), key=lambda kv: -kv[1]):
        pct = size / tot_bytes * 100
        if pct >= 2:
            langs.append((name, round(pct, 1)))
    shown = sum(p for _, p in langs)
    if langs and shown < 99.5:
        langs.append(("Other", round(100 - shown, 1)))
    return {"days": days, "total": total, "languages": langs,
            "stars": stars, "forks": forks,
            "today": date.today().isoformat()}


def fetch_model(user, token):
    try:
        return fetch_graphql(user, token)
    except Exception as exc:
        print(f"GraphQL path failed ({exc}); using fallback", file=sys.stderr)
        return fetch_fallback(user, token)


def shade(hexcolor, factor):
    h = hexcolor.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    hue, light, sat = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    light = max(0.0, min(1.0, light * factor))
    r, g, b = colorsys.hls_to_rgb(hue, light, sat)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def seed_of(datestr):
    return int(hashlib.md5(datestr.encode()).hexdigest()[:8], 16)


def level_for(count):
    if count <= 0:
        return -1
    if count <= 2:
        return 0
    if count <= 5:
        return 1
    if count <= 11:
        return 2
    return 3


def render(model):
    today = date.fromisoformat(model["today"])
    raw_days = model["days"]
    if isinstance(raw_days, list):
        raw_days = dict(raw_days)
    days = {date.fromisoformat(k): v for k, v in raw_days.items()}
    one = timedelta(days=1)
    start = today - timedelta(days=364)
    counts = [c for d, c in days.items() if start <= d <= today]
    max_count = max(counts) if counts else 0
    active_days = sum(1 for c in counts if c > 0)
    busiest_date = max((d for d in days if start <= d <= today),
                       key=lambda d: days[d], default=today)
    busiest = days.get(busiest_date, 0)

    first_sunday = today - timedelta(days=today.weekday() + 1) \
        - timedelta(weeks=WEEKS_SHOWN - 1)
    cells = []
    for w in range(WEEKS_SHOWN):
        for d in range(7):
            day = first_sunday + timedelta(days=w * 7 + d)
            if day > today:
                continue
            cells.append((w, d, day, days.get(day, 0)))

    TW, TH = 46, 23
    OX, OY = 470, 140
    W, H = 1200, 540

    def tile_x(w, d):
        return OX + (w - d) * TW / 2

    def tile_y(w, d):
        return OY + (w + d) * TH / 2

    def height(count):
        if count <= 0 or max_count <= 0:
            return 0.0
        return 3 + 118 * math.sqrt(count / max_count)

    def timing(w, d):
        start_t = 0.12 + w * 0.07 + d * 0.015
        return start_t, start_t + 0.75

    def anim(name, dur, values, kt, spline=True):
        sp = 'keySplines="0.33 1.4 0.5 1"' if spline else ""
        return (f'<animateTransform attributeName="transform" type="{name}" '
                f'additive="sum" dur="{dur:.2f}s" fill="freeze" '
                f'values="{values}" keyTimes="{kt}" {sp}/>')

    top_x, top_y = OX - 6 * TW / 2, OY + WEEKS_SHOWN * 7
    pts = {
        "TL": (tile_x(0, 6), tile_y(0, 6) - 6),
        "TR": (tile_x(WEEKS_SHOWN - 1, 0) + TW / 2, tile_y(WEEKS_SHOWN - 1, 0)),
        "BR": (tile_x(WEEKS_SHOWN - 1, 6), tile_y(WEEKS_SHOWN - 1, 6) + TH / 2 + 6),
        "BL": (tile_x(0, 6) - TW / 2 + 6, tile_y(0, 6) + 30),
    }
    slab_top = (f"{pts['TL'][0]:.0f},{pts['TL'][1]:.0f} "
                f"{tile_x(WEEKS_SHOWN-1,0):.0f},{tile_y(WEEKS_SHOWN-1,0)-TH/2:.0f} "
                f"{pts['TR'][0]:.0f},{pts['TR'][1]:.0f} "
                f"{pts['BR'][0]:.0f},{pts['BR'][1]:.0f} "
                f"{tile_x(0,6):.0f},{tile_y(0,6)+TH/2+6:.0f}")

    FONT = "Segoe UI, Ubuntu, Helvetica, Arial, sans-serif"
    MONOF = "ui-monospace, SFMono-Regular, Menlo, monospace"
    out = []
    out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" '
               f'height="{H}" viewBox="0 0 {W} {H}" '
               f'font-family="{FONT}">')
    out.append("<defs>"
               '<radialGradient id="glow" cx="50%" cy="50%" r="50%">'
               '<stop offset="0%" stop-color="#3fb950" stop-opacity="0.5"/>'
               '<stop offset="100%" stop-color="#3fb950" stop-opacity="0"/>'
               "</radialGradient>"
               '<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
               '<stop offset="0%" stop-color="#0a120d"/>'
               '<stop offset="100%" stop-color="#060807"/>'
               "</linearGradient></defs>")
    out.append(f'<rect width="{W}" height="{H}" rx="14" fill="url(#bg)"/>')
    out.append(f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="14" '
               f'fill="none" stroke="#1d2b20"/>')

    # ---- stats, top left corner ----
    out.append(f'<text x="44" y="54" font-size="13" font-weight="700" '
               f'letter-spacing="3.5" fill="#3fb950">CONTRIBUTION CITY</text>')
    out.append(f'<text x="44" y="106" font-size="47" font-weight="800" '
               f'fill="#f0f6fc">{model["total"]:,}</text>')
    out.append(f'<text x="44" y="132" font-size="14.5" fill="#8fae97">'
               f'contributions in the last year</text>')
    out.append(f'<text x="44" y="164" font-size="14" fill="#c9d1d9">'
               f'<tspan font-weight="700" fill="#3fb950">{active_days}</tspan>'
               f' active days</text>')
    out.append(f'<text x="44" y="188" font-size="14" fill="#8fae97">'
               f'Busiest day: <tspan font-weight="700" fill="#3fb950">'
               f'{busiest}</tspan> · {busiest_date.strftime("%b %-d")}</text>')
    out.append(f'<path transform="translate(50 208) scale(0.85)" '
               f'fill="#e3b341" d="M0-7 L2.1-2.4 7-2.1 3.4 1.3 4.2 6.2 '
               f'0 3.6 -4.2 6.2 -3.4 1.3 -7-2.1 -2.1-2.4 Z"/>')
    out.append(f'<text x="63" y="213" font-size="14" fill="#c9d1d9">'
               f'{model["stars"]} stars across my projects · '
               f'{model["forks"]} forks</text>')

    # ---- ground slab ----
    midx = (pts["TL"][0] + pts["BR"][0]) / 2
    midy = (pts["TL"][1] + pts["BR"][1]) / 2
    out.append(f'<ellipse cx="{midx:.0f}" cy="{midy + 30:.0f}" rx="360" '
               f'ry="130" fill="#000000" opacity="0.35"/>')
    out.append(f'<polygon points="{slab_top}" fill="#101a12"/>')
    left_face = (f"{pts['TL'][0]:.0f},{pts['TL'][1]:.0f} "
                 f"{tile_x(0,6):.0f},{tile_y(0,6)+TH/2+6:.0f} "
                 f"{pts['BR'][0]:.0f},{pts['BR'][1]:.0f} "
                 f"{pts['BR'][0]:.0f},{pts['BR'][1]+13:.0f} "
                 f"{tile_x(0,6):.0f},{tile_y(0,6)+TH/2+19:.0f} "
                 f"{pts['TL'][0]:.0f},{pts['TL'][1]+13:.0f}")
    right_face = (f"{pts['TR'][0]:.0f},{pts['TR'][1]:.0f} "
                  f"{pts['BR'][0]:.0f},{pts['BR'][1]:.0f} "
                  f"{pts['BR'][0]:.0f},{pts['BR'][1]+13:.0f} "
                  f"{pts['TR'][0]:.0f},{pts['TR'][1]+13:.0f}")
    out.append(f'<polygon points="{left_face}" fill="#0a120c"/>')
    out.append(f'<polygon points="{right_face}" fill="#070c08"/>')
    out.append(f'<polygon points="{slab_top}" fill="none" '
               f'stroke="#22402a" stroke-width="1"/>')

    # ---- cells, back to front ----
    for w, d, day, count in sorted(cells, key=lambda c: (c[0] + c[1], c[0])):
        cx, cy = tile_x(w, d), tile_y(w, d)
        s, e = timing(w, d)
        kt_anim = f"0;{s / GROW_TOTAL:.4f};{e / GROW_TOTAL:.4f};1"
        lvl = level_for(count)
        tile = (f"{cx:.1f},{cy - TH/2:.1f} {cx + TW/2:.1f},{cy:.1f} "
                f"{cx:.1f},{cy + TH/2:.1f} {cx - TW/2:.1f},{cy:.1f}")
        if count <= 0:
            out.append(f'<polygon points="{tile}" fill="{PARK}"/>')
            rng = random.Random(seed_of(day.isoformat()))
            roll = rng.random()
            if roll < 0.58:
                tx = cx + rng.uniform(-7, 7)
                ty = cy + rng.uniform(-2, 3)
                leaf = shade("#2ea043", rng.uniform(0.8, 1.25))
                trunk = (
                    f'<g transform="translate({tx:.1f} {ty:.1f})">'
                    + anim("scale", GROW_TOTAL, "0 0;0 0;1.18 1.18;1 1",
                           kt_anim)
                    + f'<rect x="-1" y="-4" width="2" height="5" '
                      f'fill="#5b4632"/>'
                    + f'<circle cx="0" cy="-8.5" r="5" fill="{leaf}"/>'
                    + f'<circle cx="-3.4" cy="-5.6" r="3.4" '
                      f'fill="{shade(leaf, 0.85)}"/></g>')
                out.append(trunk)
            elif roll < 0.78:
                bx = cx + rng.uniform(-8, 8)
                by = cy + rng.uniform(-2, 3)
                bush = (
                    f'<g transform="translate({bx:.1f} {by:.1f})">'
                    + anim("scale", GROW_TOTAL, "0 0;0 0;1.15 1.15;1 1",
                           kt_anim)
                    + f'<circle cx="0" cy="-2" r="3" fill="#1f4429"/></g>')
                out.append(bush)
            continue
        base = LEVEL_COLORS[lvl]
        h = height(count)
        top_poly = (f"{cx:.1f},{cy - TH/2 - h:.1f} {cx + TW/2:.1f},{cy - h:.1f} "
                    f"{cx:.1f},{cy + TH/2 - h:.1f} {cx - TW/2:.1f},{cy - h:.1f}")
        left_poly = (f"{cx - TW/2:.1f},{cy - h:.1f} {cx:.1f},{cy + TH/2 - h:.1f} "
                     f"{cx:.1f},{cy + TH/2:.1f} {cx - TW/2:.1f},{cy:.1f}")
        right_poly = (f"{cx + TW/2:.1f},{cy - h:.1f} {cx:.1f},{cy + TH/2 - h:.1f} "
                      f"{cx:.1f},{cy + TH/2:.1f} {cx + TW/2:.1f},{cy:.1f}")
        if h >= 44:
            gr = 90 + h * 1.1
            out.append(
                f'<g opacity="0">'
                f'<animate attributeName="opacity" dur="{GROW_TOTAL:.2f}s" '
                f'fill="freeze" values="0;0;0.55;0.55" '
                f'keyTimes="0;{e / GROW_TOTAL:.4f};'
                f'{min(1.0, e / GROW_TOTAL + 0.08):.4f};1"/>'
                f'<ellipse cx="{cx:.1f}" cy="{cy + 6:.1f}" rx="{gr:.0f}" '
                f'ry="{gr * 0.36:.0f}" fill="url(#glow)"/></g>')
        windows = ""
        if h >= 52:
            rng = random.Random(seed_of(day.isoformat()) + 7)
            rows = int(h // 15)
            for r_i in range(rows):
                wy = cy - h + 12 + r_i * 15
                for side, sx in (("L", cx - TW / 4 - 2), ("R", cx + TW / 4 - 4)):
                    if rng.random() < 0.55:
                        wy2 = wy + (3.8 if side == "R" else 0)
                        windows += (f'<rect x="{sx:.1f}" y="{wy2:.1f}" '
                                    f'width="4.4" height="6" rx="1" '
                                    f'fill="#ffd76a" opacity="0.85"/>')
        building = (
            f'<g transform="translate({cx:.1f} {cy:.1f})">'
            + anim("scale", GROW_TOTAL, "1 0;1 0;1 1.03;1 1", kt_anim)
            + f'<g transform="translate({-cx:.1f} {-cy:.1f})">'
            + f'<polygon points="{left_poly}" fill="{shade(base, 0.55)}"/>'
            + f'<polygon points="{right_poly}" fill="{shade(base, 0.78)}"/>'
            + f'<polygon points="{top_poly}" fill="{shade(base, 1.22)}"/>'
            + windows + "</g></g>")
        out.append(f'<polygon points="{tile}" fill="{shade(base, 0.3)}"/>')
        out.append(building)

    # ---- languages footer line ----
    lx = 44
    ly = 520
    for name, pct in model["languages"][:6]:
        color = LANG_COLORS.get(name, "#8b949e")
        out.append(f'<circle cx="{lx + 4}" cy="{ly - 4}" r="4" '
                   f'fill="{color}"/>')
        label = f"{name} {pct:.0f}%"
        out.append(f'<text x="{lx + 14}" y="{ly}" font-size="12.5" '
                   f'fill="#9fb3a8">{label}</text>')
        lx += 30 + len(label) * 7.3
    first_day = first_sunday
    out.append(f'<text x="{W - 44}" y="{ly}" font-size="11.5" '
               f'fill="#5b7263" text-anchor="end" font-family="{MONOF}">'
               f'{first_day.strftime("%b %-d")} to '
               f'{today.strftime("%b %-d, %Y")} · refreshes daily</text>')

    out.append("</svg>")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="city.svg")
    ap.add_argument("--model", help="render from a saved model JSON instead "
                                    "of fetching (for local testing)")
    args = ap.parse_args()
    if args.model:
        with open(args.model) as fh:
            model = json.load(fh)
    else:
        user = os.environ.get("USERNAME", "MugdhoAI")
        token = os.environ.get("GITHUB_TOKEN", "")
        model = fetch_model(user, token)
    svg = render(model)
    with open(args.out, "w") as fh:
        fh.write(svg)
    print(f"wrote {args.out}: total={model['total']} "
          f"stars={model['stars']} langs={len(model['languages'])} "
          f"bytes={len(svg)}")


if __name__ == "__main__":
    main()
