"""Builds activity-graph.svg: an animated 12-month contribution chart for the profile README.

Input : GitHub GraphQL contributionsCollection JSON (from `gh api graphql`, or fetched here with a token).
Output: a self-contained SVG (SMIL only, no scripts or external assets) in the profile's purple / sky palette.

  python make_activity.py --input contrib.json --out activity-graph.svg
  GH_TOKEN=... python make_activity.py --user Ryzuuuu --out activity-graph.svg      (fetches the data itself)
"""
import argparse
import datetime as dt
import json
import math
import os
import sys
import urllib.request

QUERY = """query($login:String!){user(login:$login){contributionsCollection{
totalCommitContributions totalPullRequestContributions totalIssueContributions totalPullRequestReviewContributions
contributionCalendar{totalContributions weeks{firstDay contributionDays{date contributionCount}}}}}}"""


def fetch(user, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": user}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": "activity-graph"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


ap = argparse.ArgumentParser()
ap.add_argument("--input")
ap.add_argument("--user", default="Ryzuuuu")
ap.add_argument("--out", required=True)
args = ap.parse_args()

if args.input:
    raw = json.load(open(args.input, encoding="utf-8"))
else:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("need --input or GH_TOKEN")
    raw = fetch(args.user, token)
if "errors" in raw:
    sys.exit("GraphQL error: " + json.dumps(raw["errors"])[:300])

cc = raw["data"]["user"]["contributionsCollection"]
cal = cc["contributionCalendar"]
weeks = cal["weeks"]
days = [d for w in weeks for d in w["contributionDays"]]
weekly = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in weeks]
n = len(weekly)
total = cal["totalContributions"]
commits = cc["totalCommitContributions"]
prs = cc["totalPullRequestContributions"]
active_days = sum(1 for d in days if d["contributionCount"] > 0)
peak_i = max(range(n), key=lambda i: weekly[i])
peak_v = weekly[peak_i]

# ---------------- geometry ----------------
W, H = 1000, 330
L, R, T, B = 64, 972, 108, 272
step = (R - L) / (n - 1)
ymax = max(20, int(math.ceil(max(weekly) / 20.0) * 20))
X = [L + i * step for i in range(n)]
Y = [B - (v / ymax) * (B - T) for v in weekly]


def tangents(xs, ys):
    """Fritsch-Carlson monotone cubic: smooth curve that never dips below 0 or overshoots."""
    m = [(ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i]) for i in range(len(xs) - 1)]
    c = [m[0]] + [(m[i - 1] + m[i]) / 2 if m[i - 1] * m[i] > 0 else 0.0 for i in range(1, len(m))] + [m[-1]]
    for k in range(len(m)):
        if m[k] == 0:
            c[k] = c[k + 1] = 0.0
        else:
            a, b = c[k] / m[k], c[k + 1] / m[k]
            s = a * a + b * b
            if s > 9:
                tau = 3 / math.sqrt(s)
                c[k], c[k + 1] = tau * a * m[k], tau * b * m[k]
    return c


C = tangents(X, Y)


def line_path():
    d = f"M{X[0]:.2f},{Y[0]:.2f}"
    for i in range(n - 1):
        dx = X[i + 1] - X[i]
        d += (f" C{X[i] + dx / 3:.2f},{Y[i] + C[i] * dx / 3:.2f} "
              f"{X[i + 1] - dx / 3:.2f},{Y[i + 1] - C[i + 1] * dx / 3:.2f} {X[i + 1]:.2f},{Y[i + 1]:.2f}")
    return d


def y_at(x):
    """Control points sit at thirds, so x(t) is linear in t: y at x is a direct Bezier evaluation."""
    i = min(max(int((x - L) // step), 0), n - 2)
    dx = X[i + 1] - X[i]
    t = (x - X[i]) / dx
    p0, p1, p2, p3 = Y[i], Y[i] + C[i] * dx / 3, Y[i + 1] - C[i + 1] * dx / 3, Y[i + 1]
    u = 1 - t
    return u ** 3 * p0 + 3 * u * u * t * p1 + 3 * u * t * t * p2 + t ** 3 * p3


LINE = line_path()
AREA = LINE + f" L{X[-1]:.2f},{B} L{X[0]:.2f},{B} Z"

SANS = "'Segoe UI', system-ui, -apple-system, 'Helvetica Neue', Arial, sans-serif"
MONO = "ui-monospace, 'SFMono-Regular', 'Cascadia Code', Menlo, Consolas, 'Liberation Mono', monospace"

CYCLE = 14.0
DRAW = 3.4
frac = DRAW / CYCLE

o = []
a = o.append
a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">')
a('<title id="t">Contribution activity</title>')
upd = dt.datetime.now(dt.timezone.utc)
a(f'<desc id="d">{total} contributions in the last 12 months, plotted per week. Peak week: {peak_v} contributions.</desc>')
a('<defs>')
a(f'<clipPath id="card"><rect width="{W}" height="{H}" rx="14"/></clipPath>')
a(f'<clipPath id="reveal"><rect x="0" y="0" width="0" height="{H}"><animate attributeName="width" dur="{CYCLE}s" repeatCount="indefinite" keyTimes="0;{frac:.4f};1" values="0;{W};{W}"/></rect></clipPath>')
a('<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0f172a"/><stop offset="1" stop-color="#0b1222"/></linearGradient>')
a('<linearGradient id="stroke" gradientUnits="userSpaceOnUse" x1="%d" y1="0" x2="%d" y2="0"><stop offset="0" stop-color="#6d28d9"/><stop offset=".5" stop-color="#a78bfa"/><stop offset="1" stop-color="#38bdf8"/></linearGradient>' % (L, R))
a('<linearGradient id="fill" gradientUnits="userSpaceOnUse" x1="0" y1="%d" x2="0" y2="%d"><stop offset="0" stop-color="#7c3aed" stop-opacity=".85"/><stop offset=".5" stop-color="#4f46e5" stop-opacity=".38"/><stop offset="1" stop-color="#0ea5e9" stop-opacity=".04"/></linearGradient>' % (T, B))
a('<radialGradient id="halo" gradientUnits="userSpaceOnUse" cx="860" cy="20" r="420"><stop offset="0" stop-color="#6d28d9" stop-opacity=".28"/><stop offset="1" stop-color="#6d28d9" stop-opacity="0"/></radialGradient>')
a('<linearGradient id="num" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#c4b5fd"/><stop offset="1" stop-color="#7dd3fc"/></linearGradient>')
a('<filter id="glow" x="-5%" y="-30%" width="110%" height="160%"><feGaussianBlur stdDeviation="5"/></filter>')
a('<filter id="dotglow" x="-300%" y="-300%" width="700%" height="700%"><feGaussianBlur stdDeviation="3.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>')
a('</defs>')

a('<g clip-path="url(#card)">')
a(f'<rect width="{W}" height="{H}" fill="url(#bg)"/>')
a(f'<rect width="{W}" height="{H}" fill="url(#halo)"/>')

# header
a(f'<text x="28" y="42" font-family="{SANS}" font-size="19" font-weight="700" fill="#e2e8f0">Contribution Activity</text>')
a(f'<text x="28" y="63" font-family="{SANS}" font-size="12" fill="#94a3b8">Last 12 months · contributions per week</text>')
a(f'<rect x="28" y="74" width="46" height="3" rx="1.5" fill="url(#stroke)"/>')
stats = [(total, "contributions"), (commits, "commits"), (prs, "pull requests"), (active_days, "active days")]
for k, (val, label) in enumerate(stats):
    cx = 560 + k * 120
    a(f'<text x="{cx}" y="50" text-anchor="middle" font-family="{SANS}" font-size="26" font-weight="800" fill="url(#num)">{val}'
      f'<animate attributeName="opacity" values="0;0;1" keyTimes="0;{0.02 + k * 0.03:.3f};{0.08 + k * 0.03:.3f}" dur="{CYCLE}s" repeatCount="indefinite"/></text>')
    a(f'<text x="{cx}" y="68" text-anchor="middle" font-family="{MONO}" font-size="10.5" letter-spacing="1" fill="#64748b">{label.upper()}</text>')

# grid + axes
for tv in range(0, ymax + 1, 20):
    gy = B - (tv / ymax) * (B - T)
    dash = '' if tv == 0 else ' stroke-dasharray="3 6"'
    a(f'<line x1="{L}" y1="{gy:.1f}" x2="{R}" y2="{gy:.1f}" stroke="#1e293b" stroke-width="1"{dash}/>')
    a(f'<text x="{L - 12}" y="{gy + 3.5:.1f}" text-anchor="end" font-family="{MONO}" font-size="10.5" fill="#64748b">{tv}</text>')
prev = None
for i, w in enumerate(weeks):
    d = dt.date.fromisoformat(w["firstDay"])
    if d.month != prev:
        prev = d.month
        lab = d.strftime("%b")
        if d.month == 1 or i == 0:
            lab += " ’" + d.strftime("%y")
        anchor = "start" if i == 0 else ("end" if X[i] > R - 24 else "middle")
        a(f'<text x="{X[i]:.1f}" y="{B + 22}" text-anchor="{anchor}" font-family="{MONO}" font-size="10.5" fill="#64748b">{lab}</text>')

# chart (wipes in left to right, holds, fades, repeats)
a('<g><animate attributeName="opacity" dur="%ss" repeatCount="indefinite" keyTimes="0;.9;.97;1" values="1;1;0;0"/>' % CYCLE)
a('<g clip-path="url(#reveal)">')
a(f'<path d="{AREA}" fill="url(#fill)"/>')
a(f'<path d="{LINE}" fill="none" stroke="url(#stroke)" stroke-width="7" stroke-linecap="round" stroke-linejoin="round" opacity=".5" filter="url(#glow)"/>')
a(f'<path d="{LINE}" fill="none" stroke="url(#stroke)" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>')
# travelling highlight along the finished line
a(f'<path d="{LINE}" pathLength="1" fill="none" stroke="#e0f2fe" stroke-width="3" stroke-linecap="round" stroke-dasharray="0.05 0.95" stroke-dashoffset="0.05" opacity=".9" filter="url(#dotglow)">'
  f'<animate attributeName="stroke-dashoffset" from="0.05" to="-1" dur="4.8s" begin="{DRAW + 0.2}s" repeatCount="indefinite"/></path>')
# peak marker + label
px, py = X[peak_i], Y[peak_i]
pk_date = dt.date.fromisoformat(weeks[peak_i]["firstDay"]).strftime("%b %-d") if os.name != "nt" else dt.date.fromisoformat(weeks[peak_i]["firstDay"]).strftime("%b %d").replace(" 0", " ")
label = f"Peak week · {peak_v}"
bw = 8.2 * len(label) + 18
bx = px - 16 - bw
a(f'<line x1="{px:.1f}" y1="{py + 6:.1f}" x2="{px:.1f}" y2="{B}" stroke="#a78bfa" stroke-opacity=".35" stroke-dasharray="2 4"/>')
a(f'<rect x="{bx:.1f}" y="{py - 13:.1f}" width="{bw:.1f}" height="26" rx="8" fill="#1e1b4b" stroke="#6d28d9" stroke-opacity=".8"/>')
a(f'<text x="{bx + bw / 2:.1f}" y="{py + 4:.1f}" text-anchor="middle" font-family="{SANS}" font-size="12" font-weight="600" fill="#ddd6fe">{label}</text>')
a(f'<text x="{bx + bw / 2:.1f}" y="{py + 28:.1f}" text-anchor="middle" font-family="{MONO}" font-size="10" fill="#64748b">week of {pk_date}</text>')
a(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="#fff" filter="url(#dotglow)"/>')
a('</g>')  # end reveal clip

# scanner dot riding the wipe front, then settling as the "this week" marker
N = 80
xs = [L + (R - L) * k / N for k in range(N + 1)]
kt = ";".join(f"{frac * k / N:.5f}" for k in range(N + 1)) + ";1"
vx = ";".join(f"{x:.1f}" for x in xs) + f";{R}"
vy = ";".join(f"{y_at(x):.1f}" for x in xs) + f";{y_at(R):.1f}"
a(f'<circle r="4.5" fill="#7dd3fc" filter="url(#dotglow)"><animate attributeName="cx" dur="{CYCLE}s" repeatCount="indefinite" keyTimes="{kt}" values="{vx}"/>'
  f'<animate attributeName="cy" dur="{CYCLE}s" repeatCount="indefinite" keyTimes="{kt}" values="{vy}"/></circle>')
a(f'<circle cx="{R}" cy="{Y[-1]:.1f}" r="4" fill="none" stroke="#38bdf8" stroke-width="1.6" opacity="0">'
  f'<animate attributeName="r" values="4;15" dur="2.2s" begin="{DRAW}s" repeatCount="indefinite"/>'
  f'<animate attributeName="opacity" values="0.9;0" dur="2.2s" begin="{DRAW}s" repeatCount="indefinite"/></circle>')
a(f'<text x="{R - 14}" y="{Y[-1] - 14:.1f}" text-anchor="end" font-family="{MONO}" font-size="10.5" fill="#7dd3fc" opacity="0">this week · {weekly[-1]}'
  f'<animate attributeName="opacity" values="0;0;1" keyTimes="0;{frac:.3f};{min(frac + 0.05, 0.95):.3f}" dur="{CYCLE}s" repeatCount="indefinite"/></text>')
a('</g>')  # end fading group

a(f'<text x="{R}" y="{H - 12}" text-anchor="end" font-family="{MONO}" font-size="9.5" fill="#475569">updated {upd.strftime("%d %b %Y").lstrip("0")} · source: GitHub contribution calendar</text>')
a('</g>')
a(f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="13.5" fill="none" stroke="#1e293b"/>')
a('</svg>')

open(args.out, "w", encoding="utf-8").write("\n".join(o))
print(f"wrote {args.out}: weeks={n} total={total} commits={commits} prs={prs} active_days={active_days} peak={peak_v} (week of {pk_date}) ymax={ymax}", file=sys.stderr)
