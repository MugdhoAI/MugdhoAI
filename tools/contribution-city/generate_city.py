#!/usr/bin/env python3
"""Generate a 3D contribution city SVG for a GitHub profile README.

Data comes from GitHub's GraphQL API (contribution calendar, repo stars,
languages). Every building is one day: height and colour follow that day's
contribution count. Quiet days become park plots, some with trees.

Usage:
  GITHUB_TOKEN=... USERNAME=MugdhoAI python3 generate_city.py
  python3 generate_city.py --model model.json --out city.svg   (local test)
"""
import argparse
import datetime
import hashlib
import json
import math
import os
import sys
import urllib.request

WEEKS_SHOWN = 16

# ---------------------------------------------------------------- data fetch

GRAPHQL = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount weekday } }
      }
    }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100) {
      nodes {
        stargazerCount
        forkCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def _get(url, token=None):
    headers = {"User-Agent": "contribution-city"}
    if token:
        headers["Authorization"] = f"bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode()


def fetch_model_fallback(token, username):
    """Fallback if GraphQL rejects the token: public contribution graph for
    the calendar, REST for repo stars, forks and languages."""
    import re
    today = datetime.date.today()
    html = _get(f"https://github.com/users/{username}/contributions"
                f"?to={today.isoformat()}")
    cells = re.findall(r'data-date="(\d{4}-\d{2}-\d{2})"[^>]*data-level="\d"',
                       html)
    tips = re.findall(r'for="contribution-day-component-\d+-\d+"[^>]*>([^<]+)<',
                      html)
    days = []
    for date, tip in zip(cells, tips):
        tip = tip.strip()
        if tip.startswith("No contributions"):
            n = 0
        else:
            m = re.match(r"([\d,]+) contribution", tip)
            n = int(m.group(1).replace(",", "")) if m else 0
        dt = datetime.date.fromisoformat(date)
        days.append({"date": date, "count": n,
                     "weekday": (dt.weekday() + 1) % 7})
    start = today - datetime.timedelta(days=364)
    total = sum(d["count"] for d in days
                if start <= datetime.date.fromisoformat(d["date"]) <= today)
    repos = json.loads(_get(
        f"https://api.github.com/users/{username}/repos?per_page=100", token))
    stars = sum(r["stargazers_count"] for r in repos if not r["fork"])
    forks = sum(r["forks_count"] for r in repos if not r["fork"])
    lang_bytes, lang_color = {}, {}
    palette = {"Python": "#3572A5", "HTML": "#e34c26", "C": "#555555",
               "C++": "#f34b7d", "TypeScript": "#3178c6",
               "JavaScript": "#f1e05a", "CSS": "#563d7c", "Shell": "#89e051"}
    for r in repos:
        if r["fork"]:
            continue
        try:
            langs = json.loads(_get(r["languages_url"], token))
        except Exception:
            continue
        for name, size in langs.items():
            lang_bytes[name] = lang_bytes.get(name, 0) + size
            lang_color[name] = palette.get(name, "#8b949e")
    total_bytes = sum(lang_bytes.values()) or 1
    top = sorted(lang_bytes.items(), key=lambda kv: -kv[1])[:5]
    languages = [{"name": n, "pct": round(100.0 * b / total_bytes, 1),
                  "color": lang_color[n]} for n, b in top]
    other = 100.0 - sum(l["pct"] for l in languages)
    if other > 0.5:
        languages.append({"name": "Other", "pct": round(other, 1),
                          "color": "#6e7681"})
    return {"days": days, "total_year": total, "stars": stars,
            "forks": forks, "languages": languages,
            "today": today.isoformat()}


def fetch_model(token, username):
    today = datetime.date.today()
    to = datetime.datetime(today.year, today.month, today.day, 23, 59, 59)
    frm = to - datetime.timedelta(days=364)
    body = json.dumps({
        "query": GRAPHQL,
        "variables": {"login": username,
                      "from": frm.strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "to": to.strftime("%Y-%m-%dT%H:%M:%SZ")},
    }).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=body,
        headers={"Authorization": f"bearer {token}",
                 "Content-Type": "application/json",
                 "User-Agent": "contribution-city"})
    with urllib.request.urlopen(req) as resp:
        payload = json.load(resp)
    user = payload["data"]["user"]

    days = []
    for week in user["contributionsCollection"]["contributionCalendar"]["weeks"]:
        for d in week["contributionDays"]:
            days.append({"date": d["date"], "count": d["contributionCount"],
                         "weekday": d["weekday"]})
    total = user["contributionsCollection"]["contributionCalendar"]["totalContributions"]

    stars = forks = 0
    lang_bytes = {}
    lang_color = {}
    for repo in user["repositories"]["nodes"]:
        stars += repo["stargazerCount"]
        forks += repo["forkCount"]
        for e in (repo["languages"] or {}).get("edges", []):
            name = e["node"]["name"]
            lang_bytes[name] = lang_bytes.get(name, 0) + e["size"]
            lang_color[name] = e["node"]["color"] or "#8b949e"
    langs = sorted(lang_bytes.items(), key=lambda kv: -kv[1])
    lang_total = sum(lang_bytes.values()) or 1
    languages = [{"name": n, "pct": round(100.0 * b / lang_total, 1),
                  "color": lang_color[n]} for n, b in langs[:5]]
    other = 100.0 - sum(l["pct"] for l in languages)
    if other > 0.5:
        languages.append({"name": "Other", "pct": round(other, 1),
                          "color": "#6e7681"})
    return {"days": days, "total_year": total, "stars": stars,
            "forks": forks, "languages": languages,
            "today": today.isoformat()}


# ------------------------------------------------------------------- helpers

def shade(hex_color, f):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (min(255, max(0, round(c * f))) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def seed_of(text):
    return int(hashlib.md5(text.encode()).hexdigest()[:8], 16)


def level_for(count):
    """GitHub-style level and base colour for a day's count."""
    if count <= 0:
        return 0, None
    if count <= 3:
        return 1, "#0e4429"
    if count <= 9:
        return 2, "#006d32"
    if count <= 19:
        return 3, "#26a641"
    if count <= 39:
        return 4, "#39d353"
    return 5, "#56d364"


# -------------------------------------------------------------------- render

def render(model):
    today = datetime.date.fromisoformat(model["today"])
    by_date = {d["date"]: d for d in model["days"]}
    counts = [d["count"] for d in model["days"]
              if datetime.date.fromisoformat(d["date"]) <= today]
    max_count = max(counts) if counts else 1
    total_year = model["total_year"]
    active_days = sum(1 for c in counts if c > 0)
    busiest = max(model["days"], key=lambda d: d["count"])
    busiest_date = datetime.date.fromisoformat(busiest["date"])

    # window: WEEKS_SHOWN Sunday-start weeks ending with the current week
    last_sunday = today - datetime.timedelta(days=(today.weekday() + 1) % 7)
    first_sunday = last_sunday - datetime.timedelta(weeks=WEEKS_SHOWN - 1)

    TW, TH = 58, 29          # iso tile width / height
    OX, OY = 330, 228        # ground position of week0/Sunday tile centre
    W, H = 1200, 640

    def height(count):
        if count <= 0:
            return 0.0
        return 3 + 118 * math.sqrt(count / max_count)

    cells = []               # (depth, week, weekday, date, count)
    for w in range(WEEKS_SHOWN):
        for d in range(7):
            date = first_sunday + datetime.timedelta(weeks=w, days=d)
            if date > today:
                continue
            info = by_date.get(date.isoformat())
            cells.append((w + d, w, d, date, info["count"] if info else 0))
    cells.sort()

    out = []
    out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
               f'viewBox="0 0 {W} {H}" font-family="-apple-system, \'Segoe UI\', '
               f'Helvetica, Arial, sans-serif">')
    out.append('<defs>'
               '<radialGradient id="glow" cx=".5" cy=".5" r=".5">'
               '<stop offset="0" stop-color="#39d353" stop-opacity=".28"/>'
               '<stop offset="1" stop-color="#39d353" stop-opacity="0"/>'
               '</radialGradient>'
               '<linearGradient id="cardbg" x1="0" y1="0" x2="0" y2="1">'
               '<stop offset="0" stop-color="#0d1117"/>'
               '<stop offset="1" stop-color="#090c10"/>'
               '</linearGradient></defs>')
    out.append(f'<rect width="{W}" height="{H}" rx="14" fill="url(#cardbg)"/>')
    out.append(f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="13" '
               f'fill="none" stroke="#21262d" stroke-width="2"/>')

    # header
    out.append('<text x="42" y="58" font-size="29" font-weight="700" '
               'fill="#f0f6fc">Contribution City</text>')
    out.append(f'<text x="42" y="84" font-size="14" fill="#8b949e">'
               f'My GitHub activity in 3D, the last {WEEKS_SHOWN} weeks. '
               f'Every building is a day.</text>')
    chips = [(f"{total_year:,}", "contributions, last year"),
             (f"{active_days}", "active days"),
             (f"{busiest['count']}", "busiest day, "
              + busiest_date.strftime("%b %-d"))]
    cx = 1200 - 42 - 3 * 168 + 16
    for value, label in chips:
        out.append(f'<rect x="{cx}" y="30" width="152" height="58" rx="9" '
                   f'fill="#161b22" stroke="#30363d"/>')
        out.append(f'<text x="{cx + 14}" y="58" font-size="21" '
                   f'font-weight="700" fill="#3fb950">{value}</text>')
        out.append(f'<text x="{cx + 14}" y="77" font-size="10.5" '
                   f'fill="#8b949e">{label}</text>')
        cx += 168

    # ground slab: the padded parallelogram under the whole tile field
    def tile_cx(w, d):
        return OX + (w - d) * TW / 2
    def tile_cy(w, d):
        return OY + (w + d) * TH / 2
    last = WEEKS_SHOWN - 1
    corners = [(tile_cx(0, 0), tile_cy(0, 0) - TH / 2 - 10),
               (tile_cx(last, 0) + TW / 2 + 10, tile_cy(last, 0)),
               (tile_cx(last, 6), tile_cy(last, 6) + TH / 2 + 10),
               (tile_cx(0, 6) - TW / 2 - 10, tile_cy(0, 6))]
    mid_x = sum(c[0] for c in corners) / 4
    mid_y = sum(c[1] for c in corners) / 4
    out.append(f'<ellipse cx="{mid_x:.0f}" cy="{mid_y + 26:.0f}" rx="350" '
               f'ry="150" fill="#000000" opacity=".35"/>')
    pts = " ".join(f"{x:.0f},{y:.0f}" for x, y in corners)
    out.append(f'<polygon points="{pts}" fill="#0e1510"/>')
    for a, b in ((3, 2), (2, 1)):
        side = [corners[a], corners[b],
                (corners[b][0], corners[b][1] + 12),
                (corners[a][0], corners[a][1] + 12)]
        out.append('<polygon points="'
                   + " ".join(f"{x:.0f},{y:.0f}" for x, y in side)
                   + '" fill="#070a07"/>')

    # Grow-in animation: one master timeline (seconds). Each building scales
    # up from its own ground plot, staggered back to front by week, so the
    # city rises in a wave. Base state is the finished city, so static
    # renderers and the settled frame look identical.
    GROW_TOTAL = 2.6

    def timing(w, d):
        start = 0.12 + w * 0.085 + d * 0.018
        return start / GROW_TOTAL, (start + 0.8) / GROW_TOTAL

    # tiles, buildings, trees (painter order)
    for _, w, d, date, count in cells:
        cxp, cyp = tile_cx(w, d), tile_cy(w, d)
        s = seed_of(date.isoformat())
        sf, ef = timing(w, d)
        base = "#152219" if (w + d) % 2 == 0 else "#121e15"
        top_pts = (f"{cxp:.1f},{cyp - TH / 2:.1f} {cxp + TW / 2:.1f},{cyp:.1f} "
                   f"{cxp:.1f},{cyp + TH / 2:.1f} {cxp - TW / 2:.1f},{cyp:.1f}")
        out.append(f'<polygon points="{top_pts}" fill="{base}" '
                   f'stroke="#0a0f0b" stroke-width="0.6"/>')
        if count <= 0:
            # park plot: a tree on a seeded share of quiet days, drawn in
            # local coords inside a group that sprouts with a small bounce
            if s % 100 < 58:
                sway = (s % 9) - 4
                e1 = sf + 0.3 / GROW_TOTAL
                e2 = e1 + 0.18 / GROW_TOTAL
                out.append(f'<g transform="translate({cxp + sway:.1f} {cyp:.1f})">')
                out.append(f'<animateTransform attributeName="transform" '
                           f'type="scale" additive="sum" '
                           f'values="0;0;1.15;1;1" '
                           f'keyTimes="0;{sf:.3f};{e1:.3f};{e2:.3f};1" '
                           f'keySplines="0 0 1 1;0 .2 .3 1;0 0 1 1;0 0 1 1" '
                           f'calcMode="spline" dur="{GROW_TOTAL}s"/>')
                out.append('<line x1="0" y1="0" x2="0" y2="-7" '
                           'stroke="#7a5230" stroke-width="2"/>')
                out.append('<circle cx="-4.5" cy="-9" r="4" fill="#2ea043"/>')
                out.append('<circle cx="4.5" cy="-9.5" r="4.3" fill="#238636"/>')
                out.append('<circle cx="0" cy="-13.5" r="5.4" fill="#3fb950"/>')
                out.append('<circle cx="-1.6" cy="-15.2" r="1.7" fill="#7ee787" opacity=".85"/>')
                out.append('</g>')
            elif s % 100 < 74:
                out.append(f'<circle cx="{cxp + 6}" cy="{cyp - 2}" r="2.6" fill="#238636"/>')
                out.append(f'<circle cx="{cxp + 9}" cy="{cyp - 3.4}" r="1.9" fill="#3fb950"/>')
            continue
        level, base_col = level_for(count)
        h = height(count)
        top_col = shade(base_col, 1.18)
        left_col = shade(base_col, 0.52)
        right_col = shade(base_col, 0.78)
        if count >= 40:
            out.append(f'<ellipse cx="{cxp}" cy="{cyp + 3}" rx="{TW * 0.78}" '
                       f'ry="{TH * 0.8}" fill="url(#glow)">'
                       f'<animate attributeName="opacity" values="0;0;1;1" '
                       f'keyTimes="0;{sf:.3f};{ef:.3f};1" '
                       f'dur="{GROW_TOTAL}s"/></ellipse>')
        # building in local coords (ground at 0,0), grown by scaling Y
        out.append(f'<g transform="translate({cxp:.1f} {cyp:.1f})">')
        out.append(f'<animateTransform attributeName="transform" type="scale" '
                   f'additive="sum" values="1 0;1 0;1 1;1 1" '
                   f'keyTimes="0;{sf:.3f};{ef:.3f};1" '
                   f'keySplines="0 0 1 1;0 .2 .3 1;0 0 1 1" '
                   f'calcMode="spline" dur="{GROW_TOTAL}s"/>')
        out.append(f'<polygon points="{-TW / 2:.1f},0 0,{TH / 2:.1f} '
                   f'0,{TH / 2 - h:.1f} {-TW / 2:.1f},{-h:.1f}" fill="{left_col}"/>')
        out.append(f'<polygon points="{TW / 2:.1f},0 0,{TH / 2:.1f} '
                   f'0,{TH / 2 - h:.1f} {TW / 2:.1f},{-h:.1f}" fill="{right_col}"/>')
        out.append(f'<polygon points="0,{-h - TH / 2:.1f} {TW / 2:.1f},{-h:.1f} '
                   f'0,{-h + TH / 2:.1f} {-TW / 2:.1f},{-h:.1f}" fill="{top_col}"/>')
        # lit windows on tall towers, right face (local coords)
        if h >= 52:
            for i in range(5):
                ss = seed_of(date.isoformat() + str(i))
                fx = 0.22 + (ss % 55) / 100.0
                fy = 0.2 + ((ss >> 4) % 55) / 100.0
                wx = TW / 2 * (1 - fx)
                wy = (TH / 2) * fx - h * fy
                if ss % 100 < 68:
                    out.append(f'<rect x="{wx:.1f}" y="{wy:.1f}" width="3" '
                               f'height="4.4" fill="#e6ffec" opacity=".8"/>')
        out.append('</g>')

    # right rail: languages
    rx = 838
    out.append(f'<text x="{rx}" y="168" font-size="15" font-weight="700" '
               f'fill="#f0f6fc">Top languages</text>')
    langs = model["languages"][:6]
    bar_x, bar_w, bar_y = rx, 320, 182
    acc = bar_x
    for lg in langs:
        seg = bar_w * lg["pct"] / 100.0
        if seg > 2:
            out.append(f'<rect x="{acc:.0f}" y="{bar_y}" width="{seg:.0f}" '
                       f'height="10" fill="{lg["color"]}"/>')
        acc += seg
    out.append(f'<rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="10" '
               f'rx="5" fill="none" stroke="#30363d"/>')
    ly = bar_y + 34
    for lg in langs:
        out.append(f'<circle cx="{rx + 5}" cy="{ly - 4}" r="4.5" fill="{lg["color"]}"/>')
        out.append(f'<text x="{rx + 18}" y="{ly}" font-size="13" fill="#c9d1d9">'
                   f'{lg["name"]}</text>')
        out.append(f'<text x="{rx + bar_w}" y="{ly}" font-size="13" '
                   f'fill="#8b949e" text-anchor="end">{lg["pct"]:.0f}%</text>')
        ly += 24
    sx_star, sy_star = rx + 6, ly + 10
    star_pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = 7 if i % 2 == 0 else 3
        star_pts.append(f"{sx_star + rad * math.cos(ang):.1f},"
                        f"{sy_star + rad * math.sin(ang):.1f}")
    out.append('<polygon points="' + " ".join(star_pts)
               + '" fill="#e3b341"/>')
    out.append(f'<text x="{rx + 20}" y="{ly + 14}" font-size="13" fill="#c9d1d9">'
               f'{model["stars"]} stars across my projects</text>')
    out.append(f'<text x="{rx}" y="{ly + 36}" font-size="13" fill="#8b949e">'
               f'{model["forks"]} forks</text>')

    # footer
    out.append(f'<text x="42" y="{H - 26}" font-size="12.5" fill="#8b949e">'
               f'Buildings grow with each day\'s contributions. Quiet days '
               f'stay parks. Data refreshes daily from GitHub.</text>')
    out.append(f'<text x="{W - 42}" y="{H - 26}" font-size="12.5" '
               f'fill="#8b949e" text-anchor="end">'
               f'{first_sunday.strftime("%b %-d")} to '
               f'{today.strftime("%b %-d, %Y")}</text>')
    out.append('</svg>')
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="JSON model file (local testing)")
    ap.add_argument("--out", default="assets/contribution-city.svg")
    args = ap.parse_args()
    if args.model:
        model = json.load(open(args.model))
    else:
        token = os.environ.get("GITHUB_TOKEN")
        username = os.environ.get("USERNAME")
        if not token or not username:
            sys.exit("GITHUB_TOKEN and USERNAME are required")
        try:
            model = fetch_model(token, username)
        except Exception as exc:
            print(f"GraphQL fetch failed ({exc}); using fallback",
                  file=sys.stderr)
            model = fetch_model_fallback(token, username)
    svg = render(model)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        f.write(svg)
    print(f"wrote {args.out} ({len(svg)} bytes)")


if __name__ == "__main__":
    main()
