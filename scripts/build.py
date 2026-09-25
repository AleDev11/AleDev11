"""Genera los SVG animados del README a partir del estilo de afont.dev.

Uso:  pip install fonttools brotli  &&  python scripts/build.py
Salida: assets/*.svg

GitHub no permite CSS ni JS en el README, pero si SVG con animaciones CSS
dentro. Las fuentes se incrustan (recortadas a los caracteres usados) porque
un SVG servido como <img> no puede cargar nada externo.
"""

import base64
import io
from datetime import date
from pathlib import Path

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "assets"

# ---- tokens (src/styles/global.css de afont.dev) ----
BG = "#0a0a0a"
BG_ALT = "#111111"
BORDER = "#2a2a2a"
BORDER_SOFT = "#1f1f1f"
ACCENT = "#ff6b00"
ACCENT_DARK = "#cc4e00"
ACCENT_DEEP = "#7a2e00"
ACCENT_LIGHT = "#ff8a2b"
TEXT = "#ffffff"
MUTED = "#cccccc"
DIM = "#b0b0b0"
FAINT = "#888888"
GHOST = "#555555"
GREEN = "#25d366"
EASE_OUT = "cubic-bezier(0.16, 1, 0.3, 1)"

# Fechas de las que salen los contadores. La Action .github/workflows/readme.yml
# vuelve a generar los SVG cada mes, asi que las cifras se actualizan solas.
CAREER_START = date(2021, 9, 1)  # inicio del grado DAM
INFINI_START = date(2023, 7, 1)


def months_since(start, today=None):
    today = today or date.today()
    return (today.year - start.year) * 12 + today.month - start.month


def duration(start):
    y, m = divmod(months_since(start), 12)
    parts = ([f"{y} YR" + ("S" if y != 1 else "")] if y else []) + ([f"{m} MO" + ("S" if m != 1 else "")] if m else [])
    return " ".join(parts) or "1 MO"


FONTS = {
    "d9": "barlow-condensed-latin-900-normal.woff2",
    "d8": "barlow-condensed-latin-800-normal.woff2",
    "l6": "oswald-latin-600-normal.woff2",
    "l5": "oswald-latin-500-normal.woff2",
    "b4": "inter-latin-400-normal.woff2",
    "b5": "inter-latin-500-normal.woff2",
}
_font_cache = {}


def font(key):
    if key not in _font_cache:
        _font_cache[key] = TTFont(ROOT / "fonts" / FONTS[key])
    return _font_cache[key]


def measure(text, key, size, ls=0.0):
    f = font(key)
    cmap = f.getBestCmap()
    hmtx = f["hmtx"]
    upm = f["head"].unitsPerEm
    w = sum(hmtx[cmap.get(ord(c), cmap[ord("?")])][0] for c in text)
    return w * size / upm + ls * len(text)


def wrap(text, key, size, maxw):
    lines, cur = [], ""
    for word in text.split():
        nxt = f"{cur} {word}".strip()
        if cur and measure(nxt, key, size) > maxw:
            lines.append(cur)
            cur = word
        else:
            cur = nxt
    if cur:
        lines.append(cur)
    return lines


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Svg:
    def __init__(self, w, h, title):
        self.w, self.h, self.title = w, h, title
        self.body, self.css, self.defs = [], [], []
        self.chars = {}

    def use(self, key, text):
        self.chars.setdefault(key, set()).update(text)

    def text(self, x, y, s, key, size, fill, ls=0.0, anchor="start", cls="", extra=""):
        self.use(key, s)
        a = f' text-anchor="{anchor}"' if anchor != "start" else ""
        c = f' class="{cls}"' if cls else ""
        l = f' letter-spacing="{ls:.2f}"' if ls else ""
        self.body.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-family="{key}" font-size="{size}" '
            f'fill="{fill}"{l}{a}{c}{extra}>{esc(s)}</text>'
        )

    def add(self, s):
        self.body.append(s)

    def _font_faces(self):
        out = []
        for key, chars in sorted(self.chars.items()):
            f = TTFont(ROOT / "fonts" / FONTS[key])
            opts = Options()
            opts.flavor = "woff2"
            opts.layout_features = ["kern", "liga"]
            sub = Subsetter(opts)
            sub.populate(text="".join(sorted(chars)) + " ")
            sub.subset(f)
            buf = io.BytesIO()
            f.flavor = "woff2"
            # sin fecha de guardado: misma entrada, mismo SVG, y la Action solo commitea si algo cambia
            f.recalcTimestamp = False
            f["head"].modified = f["head"].created
            f.save(buf)
            b64 = base64.b64encode(buf.getvalue()).decode()
            out.append(f"@font-face{{font-family:'{key}';src:url(data:font/woff2;base64,{b64}) format('woff2');}}")
        return "\n".join(out)

    def render(self, name):
        reduce = "@media (prefers-reduced-motion: reduce){*{animation:none!important}}"
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{esc(self.title)}">\n'
            f"<title>{esc(self.title)}</title>\n"
            f"<defs>\n<style>\n{self._font_faces()}\n"
            f"text{{font-kerning:normal}}\n" + "\n".join(self.css) + f"\n{reduce}\n</style>\n"
            + "\n".join(self.defs)
            + "\n</defs>\n"
            + "\n".join(self.body)
            + "\n</svg>\n"
        )
        (OUT / name).write_text(svg, encoding="utf-8")
        print(f"  {name:22} {len(svg) / 1024:6.1f} KB")


# ---------- piezas reutilizables ----------

def frame(s, fill=BG, stroke=BORDER):
    s.add(f'<rect x="0.5" y="0.5" width="{s.w - 1}" height="{s.h - 1}" fill="{fill}" stroke="{stroke}"/>')


def grid(s, id_="g", step=40, opacity=0.045):
    s.defs.append(
        f'<pattern id="{id_}" width="{step}" height="{step}" patternUnits="userSpaceOnUse">'
        f'<path d="M {step} 0 L 0 0 0 {step}" fill="none" stroke="#fff" stroke-opacity="{opacity}"/></pattern>'
        f'<linearGradient id="{id_}f" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="#fff" stop-opacity="1"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        f'<mask id="{id_}m"><rect width="{s.w}" height="{s.h}" fill="url(#{id_}f)"/></mask>'
    )
    s.add(f'<rect width="{s.w}" height="{s.h}" fill="url(#{id_})" mask="url(#{id_}m)"/>')


def section_head(s, x, y, title, delay=0.0):
    """'/// TITULO' como .section-head del sitio, con las barras moviendose."""
    s.css.append(
        "@keyframes sl{0%,70%,100%{transform:translateX(0) skewX(0)}80%{transform:translateX(5px) skewX(-14deg)}}"
        ".sl{animation:sl 4s cubic-bezier(0.34,1.4,0.64,1) infinite;transform-box:fill-box}"
        f"@keyframes hd{{from{{opacity:0;transform:translateY(14px)}}to{{opacity:1;transform:none}}}}"
        f".hd{{animation:hd .8s {EASE_OUT} both}}"
    )
    s.add(f'<g class="hd" style="animation-delay:{delay}s">')
    s.text(x, y, "///", "d9", 24, ACCENT, ls=-1.2, cls="sl")
    tx = x + measure("///", "d9", 24, -1.2) + 12
    s.text(tx, y, title.upper(), "d9", 40, TEXT, ls=0.4)
    lx = tx + measure(title.upper(), "d9", 40, 0.4) + 22
    s.add(f'<line x1="{lx:.0f}" y1="{y - 13}" x2="{s.w - x}" y2="{y - 13}" stroke="{BORDER_SOFT}"/>')
    s.add("</g>")


def chip(s, x, y, label, delay=0.0, wave=None):
    """Chip del sitio. `delay` es la entrada; `wave` el retardo de la ola naranja."""
    label = label.upper()
    ls = 1.4
    w = measure(label, "l5", 11.5, ls) + 24 - ls
    wv = f' style="animation-delay:{delay if wave is None else wave:.2f}s"'
    s.add(f'<g class="chip" style="animation-delay:{delay:.2f}s">')
    s.add(f'<rect class="cr"{wv} x="{x:.1f}" y="{y}" width="{w:.1f}" height="30" rx="4" fill="{BG}" stroke="{BORDER}"/>')
    s.text(x + 12, y + 19.5, label, "l5", 11.5, DIM, ls=ls, cls="ct", extra=wv)
    s.add("</g>")
    return w


def chip_css(s, cycle):
    s.css.append(
        f"@keyframes cin{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:none}}}}"
        f"@keyframes chl{{0%,6%,100%{{stroke:{BORDER};fill:{BG}}}2%,4%{{stroke:{ACCENT};fill:#2a1405}}}}"
        f"@keyframes cth{{0%,6%,100%{{fill:{DIM}}}2%,4%{{fill:{TEXT}}}}}"
        f".chip{{animation:cin .6s {EASE_OUT} both}}"
        f".chip .cr{{animation:chl {cycle}s linear infinite}}"
        f".chip .ct{{animation:cth {cycle}s linear infinite}}"
    )


# ---------- secciones ----------

def hero():
    s = Svg(1000, 460, "Alejandro Font Muñiz — Software Developer · Barcelona")
    frame(s)
    grid(s)
    s.defs.append(
        f'<radialGradient id="glow" cx="0.5" cy="0.5" r="0.5">'
        f'<stop offset="0" stop-color="{ACCENT}" stop-opacity="0.22"/>'
        f'<stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/></radialGradient>'
    )
    s.css.append(
        "@keyframes glow{0%,100%{opacity:.55}50%{opacity:1}}"
        ".glow{animation:glow 6s ease-in-out infinite}"
        f"@keyframes up{{from{{transform:translateY(130px)}}to{{transform:none}}}}"
        f".up{{animation:up 1.1s {EASE_OUT} both}}"
        f"@keyframes fade{{from{{opacity:0;transform:translateY(10px)}}to{{opacity:1;transform:none}}}}"
        f".fade{{animation:fade .9s {EASE_OUT} both}}"
        f"@keyframes grow{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}"
        f".rule{{transform-box:fill-box;transform-origin:left;animation:grow .9s {EASE_OUT} 1s both}}"
        "@keyframes blink{0%,100%{opacity:1}50%{opacity:.25}}"
        ".dot{animation:blink 2.4s ease-in-out infinite}"
        "@keyframes ring{0%{transform:scale(1);opacity:.6}100%{transform:scale(3.2);opacity:0}}"
        ".ring{transform-box:fill-box;transform-origin:center;animation:ring 2.4s ease-out infinite}"
        f"@keyframes badge{{0%,76%,100%{{transform:rotate(0) scale(1)}}84%{{transform:rotate(10deg) scale(1.1)}}92%{{transform:rotate(-4deg) scale(1)}}}}"
        ".badge{transform-box:fill-box;transform-origin:center;animation:badge 5s ease-in-out 2s infinite}"
        f"@keyframes photo{{from{{opacity:0;transform:scale(1.08)}}to{{opacity:1;transform:none}}}}"
        f".photo{{transform-box:fill-box;transform-origin:center;animation:photo 1.4s {EASE_OUT} .4s both}}"
        "@keyframes run{to{stroke-dashoffset:-1080}}"
        ".run{animation:run 7s linear infinite}"
    )
    s.add(f'<circle class="glow" cx="860" cy="70" r="360" fill="url(#glow)"/>')

    x = 56
    # kicker
    s.add('<g class="fade" style="animation-delay:.1s">')
    s.text(x, 92, "///", "d9", 22, ACCENT, ls=-1.1)
    s.text(x + 40, 91, "SOFTWARE DEVELOPER · BARCELONA, SPAIN", "l6", 13, DIM, ls=2.3)
    s.add("</g>")

    # nombre, cada linea sube desde su mascara como en el hero del sitio
    s.defs.append('<clipPath id="l1"><rect x="0" y="100" width="640" height="112"/></clipPath>')
    s.defs.append('<clipPath id="l2"><rect x="0" y="212" width="640" height="116"/></clipPath>')
    s.add('<g clip-path="url(#l1)">')
    s.text(x - 4, 205, "ALEJANDRO", "d9", 128, TEXT, ls=-2.5, cls="up", extra=' style="animation-delay:.25s"')
    s.add("</g>")
    s.use("d9", "FONT MUÑIZ")
    s.add(
        f'<g clip-path="url(#l2)"><text class="up" style="animation-delay:.4s" x="{x - 4}" y="322" '
        f'font-family="d9" font-size="128" letter-spacing="-2.5" fill="{TEXT}">'
        f'<tspan fill="{ACCENT}">FONT</tspan> MUÑIZ</text></g>'
    )

    s.add(f'<rect class="rule" x="{x}" y="348" width="120" height="4" fill="{ACCENT}"/>')

    # palabra rotatoria
    s.add('<g class="fade" style="animation-delay:1.2s">')
    s.text(x, 402, "I BUILD", "l6", 14, FAINT, ls=2.5)
    words = ["WEB APPS", "MANAGEMENT PLATFORMS", "AI AGENTS", "RPA AUTOMATIONS"]
    wx = x + measure("I BUILD", "l6", 14, 2.5) + 14
    step = 40
    n = len(words)
    kf = []
    for i in range(n):
        a, b = i * 100 / n, (i + 1) * 100 / n
        kf.append(f"{a:.2f}%,{b - 4:.2f}%{{transform:translateY({-i * step}px)}}")
    kf.append(f"100%{{transform:translateY({-n * step}px)}}")
    s.css.append(
        "@keyframes rot{" + "".join(kf) + "}"
        f".rot{{animation:rot 12s {EASE_OUT} 1.8s infinite}}"
    )
    s.defs.append(f'<clipPath id="slot"><rect x="{wx - 4:.0f}" y="375" width="460" height="38"/></clipPath>')
    s.add('<g clip-path="url(#slot)"><g class="rot">')
    for i, w in enumerate(words + words[:1]):
        s.text(wx, 405 + i * step, w, "d8", 30, ACCENT, ls=0.6)
    s.add("</g></g></g>")

    # retrato
    img = base64.b64encode((ROOT / "me.jpg").read_bytes()).decode()
    px, py, pw = 694, 70, 250
    s.defs.append(f'<clipPath id="pf"><rect x="{px}" y="{py}" width="{pw}" height="{pw + 20}"/></clipPath>')
    s.defs.append(
        '<linearGradient id="shade" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset=".55" stop-color="{BG}" stop-opacity="0"/><stop offset="1" stop-color="{BG}" stop-opacity=".55"/></linearGradient>'
    )
    s.add(f'<rect x="{px}" y="{py}" width="{pw}" height="{pw + 20}" fill="{BG_ALT}"/>')
    s.add(
        f'<g clip-path="url(#pf)"><image class="photo" x="{px - 10}" y="{py}" width="{pw + 20}" '
        f'height="{pw + 20}" preserveAspectRatio="xMidYMid slice" href="data:image/jpeg;base64,{img}"/>'
        f'<rect x="{px}" y="{py}" width="{pw}" height="{pw + 20}" fill="url(#shade)"/></g>'
    )
    per = 2 * (pw + pw + 20)
    s.add(f'<rect x="{px}" y="{py}" width="{pw}" height="{pw + 20}" fill="none" stroke="{BORDER}"/>')
    s.add(
        f'<rect class="run" x="{px}" y="{py}" width="{pw}" height="{pw + 20}" fill="none" stroke="{ACCENT}" '
        f'stroke-width="2" stroke-dasharray="120 {per - 120}"/>'
    )
    s.add(f'<g class="badge"><rect x="{px + pw - 34}" y="{py - 10}" width="44" height="44" rx="4" fill="{ACCENT}"/>')
    s.text(px + pw - 12, py + 19, "///", "d9", 18, BG, ls=-0.9, anchor="middle")
    s.add("</g>")

    # estado
    sy = py + pw + 20 + 32
    s.add('<g class="fade" style="animation-delay:1.4s">')
    s.add(f'<circle class="ring" cx="{px + 5}" cy="{sy - 4}" r="4" fill="{GREEN}"/>')
    s.add(f'<circle class="dot" cx="{px + 5}" cy="{sy - 4}" r="4" fill="{GREEN}"/>')
    s.text(px + 18, sy, "AVAILABLE FOR PROJECTS", "l5", 11, DIM, ls=1.8)
    s.add("</g>")

    s.text(x, 436, "41.38° N · 2.17° E", "l5", 10, GHOST, ls=2)
    s.render("hero.svg")


def marquee(items, name, fill, fg, sep, reverse=False, h=62, size=26, speed=34):
    s = Svg(1000, h, "Stack: " + ", ".join(items))
    s.add(f'<rect width="{s.w}" height="{h}" fill="{fill}"/>')
    ls, gap = size * 0.04, 34
    xs, x = [], 0
    for it in items:
        it = it.upper()
        xs.append((x, it, False))
        x += measure(it, "d8", size, ls) + gap
        xs.append((x, "///", True))
        x += measure("///", "d8", size, ls) + gap
    total = x
    d = "reverse" if reverse else "normal"
    s.css.append(
        f"@keyframes mq{{from{{transform:translateX(0)}}to{{transform:translateX(-{total:.1f}px)}}}}"
        f".mq{{animation:mq {speed}s linear infinite {d}}}"
    )
    y = h / 2 + size * 0.36
    s.add('<g class="mq">')
    rep = int(s.w // total) + 2
    for r in range(rep):
        for xx, t, is_sep in xs:
            s.text(xx + r * total, y, t, "d8", size, sep if is_sep else fg, ls=ls)
    s.add("</g>")
    s.defs.append(
        f'<linearGradient id="fl"><stop offset="0" stop-color="{fill}"/><stop offset="1" stop-color="{fill}" stop-opacity="0"/></linearGradient>'
        f'<linearGradient id="fr"><stop offset="0" stop-color="{fill}" stop-opacity="0"/><stop offset="1" stop-color="{fill}"/></linearGradient>'
    )
    s.add(f'<rect width="80" height="{h}" fill="url(#fl)"/><rect x="{s.w - 80}" width="80" height="{h}" fill="url(#fr)"/>')
    s.render(name)


def odometer(s, x, y, value, size, step, cls, style, delay):
    """Numero que rueda de 0 a `value`, cifra a cifra, como un cuentakilometros."""
    s.use("d9", "0123456789+.")
    s.css.append(
        f"@keyframes odo{{from{{transform:translateY(0)}}}}"
        f".odo{{animation:odo 1.8s {EASE_OUT} both}}"
    )
    s.defs.append(f'<clipPath id="oc{x:.0f}"><rect x="{x - 4:.0f}" y="{y - size * 0.8:.0f}" width="200" height="{size * 0.9:.0f}"/></clipPath>')
    s.add(f'<g class="{cls}" style="{style}" fill="{TEXT}">')
    s.add(f'<g clip-path="url(#oc{x:.0f})">')
    for ch in value:
        if ch.isdigit():
            n = int(ch)
            s.add(f'<g class="odo" style="animation-delay:{delay:.2f}s;transform:translateY({n * step}px)">')
            for k in range(n + 1):
                s.add(f'<text x="{x:.1f}" y="{y - k * step}" font-family="d9" font-size="{size}">{k}</text>')
            s.add("</g>")
        else:
            s.add(f'<text x="{x:.1f}" y="{y}" font-family="d9" font-size="{size}">{ch}</text>')
        x += measure(ch, "d9", size)
    s.add(f'<text x="{x:.1f}" y="{y}" font-family="d9" font-size="{size}" fill="{ACCENT}">.</text>')
    s.add("</g></g>")


def stats():
    years = months_since(CAREER_START) // 12
    data = [(f"+{years}", "YEARS BUILDING SOFTWARE"), ("2", "PRODUCTS LIVE"), ("3", "LANGUAGES · ES · EN · CA")]
    s = Svg(1000, 132, f"+{years} years building software · 2 products live · 3 languages")
    s.add(f'<rect width="{s.w}" height="{s.h}" fill="{BORDER}"/>')
    cw = (s.w - 2 - 2) / 3
    s.css.append(
        f"@keyframes st{{from{{opacity:0;transform:translateY(16px)}}to{{opacity:1;transform:none}}}}"
        f".st{{animation:st .9s {EASE_OUT} both}}"
        f"@keyframes sv{{0%,28%,100%{{fill:{TEXT}}}6%,22%{{fill:{ACCENT}}}}}"
        f"@keyframes sb{{0%,28%,100%{{fill:{BG}}}6%,22%{{fill:#121212}}}}"
        ".sv{animation:sv 9s ease-in-out infinite}.sb{animation:sb 9s ease-in-out infinite}"
    )
    for i, (v, l) in enumerate(data):
        x = 1 + i * (cw + 1)
        d = f"animation-delay:{i * 3 + 3}s"
        s.add(f'<rect class="sb" style="{d}" x="{x:.1f}" y="1" width="{cw:.1f}" height="{s.h - 2}" fill="{BG}"/>')
        s.add(f'<g class="st" style="animation-delay:{0.15 * i:.2f}s">')
        odometer(s, x + 28, 76, v, 60, 64, "sv", d, 0.3 + 0.2 * i)
        s.text(x + 30, 104, l, "l5", 11, FAINT, ls=2)
        s.add("</g>")
    s.render("stats.svg")


def about():
    bio = [
        "I work as a developer at Infini, a Barcelona-based consultancy specialising in intelligent "
        "automation and AI. Day to day I build management platforms, develop web applications, create "
        "AI agents and automate processes with RPA.",
        "I've worked on international projects with clients in the Middle East — every project is from a "
        "different sector, so no two weeks are alike. What motivates me most is seeing what I build "
        "actually work and make someone's life easier.",
    ]
    facts = [
        ("LOCATION", "Barcelona, Catalonia"),
        ("COMPANY", "Infini · AI consultancy"),
        ("FOCUS", "Web · AI agents · RPA"),
        ("LANGUAGES", "Spanish · English · Catalan"),
        ("STATUS", "Available for projects"),
    ]
    lines = []
    for p in bio:
        lines += wrap(p, "b4", 16, 540) + [""]
    lines.pop()
    h = max(110 + len(lines) * 28, 110 + len(facts) * 48) + 36
    s = Svg(1000, h, "About me")
    frame(s)
    section_head(s, 48, 74, "About me")
    s.css.append(
        f"@keyframes ln{{from{{opacity:0;transform:translateX(-10px)}}to{{opacity:1;transform:none}}}}"
        f".ln{{animation:ln .8s {EASE_OUT} both}}"
        "@keyframes blink{0%,100%{opacity:1}50%{opacity:.25}}.dot{animation:blink 2.4s ease-in-out infinite}"
    )
    y = 130
    for i, l in enumerate(lines):
        if l:
            s.add(f'<g class="ln" style="animation-delay:{0.3 + i * 0.06:.2f}s">')
            # Infini en negrita blanca, como el <strong> del sitio
            if "Infini" in l:
                a, b = l.split("Infini", 1)
                s.use("b4", a + b)
                s.use("b5", "Infini")
                s.add(
                    f'<text x="48" y="{y}" font-family="b4" font-size="16" fill="{MUTED}">{esc(a)}'
                    f'<tspan font-family="b5" fill="{TEXT}">Infini</tspan>{esc(b)}</text>'
                )
            else:
                s.text(48, y, l, "b4", 16, MUTED)
            s.add("</g>")
        y += 28
    fx, fy = 640, 104
    s.add(f'<line x1="{fx - 30}" y1="{fy}" x2="{fx - 30}" y2="{fy + len(facts) * 48}" stroke="{BORDER_SOFT}"/>')
    for i, (k, v) in enumerate(facts):
        yy = fy + i * 48
        s.add(f'<g class="ln" style="animation-delay:{0.5 + i * 0.1:.2f}s">')
        s.text(fx, yy + 30, k, "l5", 10.5, FAINT, ls=2)
        if k == "STATUS":
            s.add(f'<circle class="dot" cx="{fx + 116}" cy="{yy + 26}" r="4" fill="{GREEN}"/>')
            s.text(fx + 128, yy + 31, v, "b5", 14, TEXT)
        else:
            s.text(fx + 110, yy + 31, v, "b5", 14, TEXT)
        s.add(f'<line x1="{fx}" y1="{yy + 48}" x2="{s.w - 48}" y2="{yy + 48}" stroke="{BORDER_SOFT}"/>')
        s.add("</g>")
    s.render("about.svg")


def stack():
    groups = [
        ("FRONTEND", ["React", "Next.js", "Astro", "TypeScript", "Tailwind CSS", "Vue.js"]),
        ("BACKEND", ["Bun", "Hono", "Node.js", "Java", "Spring Boot", "Python", "Odoo"]),
        ("DATA", ["PostgreSQL", "MongoDB", "Redis", "MySQL", "MinIO"]),
        ("CLOUD & TOOLING", ["AWS", "Cloudflare", "Docker", "Vercel", "Linux", "GraphQL"]),
        ("AI & AUTOMATION", ["AI Agents", "RPA", "Process automation", "REST APIs"]),
    ]
    row = 52
    h = 118 + len(groups) * row + 20
    s = Svg(1000, h, "Stack — " + "; ".join(f"{g}: {', '.join(i)}" for g, i in groups))
    frame(s)
    section_head(s, 48, 74, "Stack")
    total = sum(len(i) for _, i in groups)
    cycle = round(total * 0.28 + 3, 1)
    chip_css(s, cycle)
    s.css.append(
        f"@keyframes lb{{from{{opacity:0}}to{{opacity:1}}}}.lb{{animation:lb .8s {EASE_OUT} both}}"
    )
    n = 0
    for gi, (label, items) in enumerate(groups):
        y = 112 + gi * row
        s.add(f'<g class="lb" style="animation-delay:{0.2 + gi * 0.12:.2f}s">')
        s.text(48, y + 20, label, "l6", 11.5, FAINT, ls=2.2)
        s.add("</g>")
        x = 230
        for it in items:
            w = chip(s, x, y, it, delay=0.3 + gi * 0.12 + n * 0.02, wave=1.5 + n * 0.28)
            x += w + 10
            n += 1
        if gi < len(groups) - 1:
            s.add(f'<line x1="48" y1="{y + row - 11}" x2="{s.w - 48}" y2="{y + row - 11}" stroke="{BORDER_SOFT}" stroke-dasharray="2 4"/>')
    s.render("stack.svg")


def experience():
    jobs = [
        (f"JUL 2023 — PRESENT · {duration(INFINI_START)}", "INFINI", "SOFTWARE DEVELOPER · BARCELONA · AI CONSULTANCY",
         "I build management platforms, develop web applications, create AI agents and automate processes "
         "with RPA for clients across different sectors. International projects with teams in the Middle East.",
         ["React", "Java", "Python", "AI", "RPA", "AWS"], True),
        ("OCT 2022 — MAR 2023", "TETRAVOL SL", "SOFTWARE DEVELOPER · INTERNSHIP",
         "Software development internship, contributing to projects using React, Unity and MySQL.",
         ["React", "Unity", "MySQL"], False),
    ]
    blocks, y = [], 118
    for j in jobs:
        lines = wrap(j[3], "b4", 15, 780)
        bh = 100 + len(lines) * 24 + 84
        blocks.append((y, lines, j))
        y += bh
    h = y + 10
    s = Svg(1000, h, "Experience — Infini (Jul 2023–present), Tetravol SL (Oct 2022–Mar 2023)")
    frame(s)
    section_head(s, 48, 74, "Experience")
    chip_css(s, 8)
    tx = 64
    s.css.append(
        f"@keyframes tl{{from{{transform:scaleY(0)}}to{{transform:scaleY(1)}}}}"
        f".tl{{transform-box:fill-box;transform-origin:top;animation:tl 1.6s {EASE_OUT} .3s both}}"
        "@keyframes ring{0%{transform:scale(1);opacity:.7}100%{transform:scale(3.4);opacity:0}}"
        ".ring{transform-box:fill-box;transform-origin:center;animation:ring 2.2s ease-out infinite}"
        f"@keyframes jb{{from{{opacity:0;transform:translateX(-14px)}}to{{opacity:1;transform:none}}}}"
        f".jb{{animation:jb .9s {EASE_OUT} both}}"
    )
    s.add(f'<line x1="{tx}" y1="118" x2="{tx}" y2="{h - 40}" stroke="{BORDER}"/>')
    s.add(f'<rect class="tl" x="{tx - 1}" y="118" width="2" height="{blocks[-1][0] - 118 + 20}" fill="{ACCENT}"/>')
    for bi, (by, lines, (period, company, role, _, tags, current)) in enumerate(blocks):
        s.add(f'<g class="jb" style="animation-delay:{0.5 + bi * 0.35:.2f}s">')
        if current:
            s.add(f'<circle class="ring" cx="{tx}" cy="{by + 12}" r="6" fill="{ACCENT}"/>')
        s.add(f'<rect x="{tx - 7}" y="{by + 5}" width="14" height="14" fill="{ACCENT if current else BG}" stroke="{ACCENT}" stroke-width="2" transform="rotate(45 {tx} {by + 12})"/>')
        cx = 104
        s.text(cx, by + 17, period, "l6", 12, ACCENT, ls=2.2)
        s.text(cx, by + 60, company, "d9", 42, TEXT, ls=0.4)
        s.text(cx, by + 84, role, "l5", 11, FAINT, ls=1.8)
        yy = by + 114
        for l in lines:
            s.text(cx, yy, l, "b4", 15, MUTED)
            yy += 24
        x = cx
        for ti, t in enumerate(tags):
            x += chip(s, x, yy - 8, t, delay=0.9 + bi * 0.35 + ti * 0.08, wave=1.5 + (bi * 6 + ti) * 0.3) + 8
        s.add("</g>")
    s.render("experience.svg")


def project(tag, name, url_label, desc, tags, fname):
    s = Svg(488, 300, f"{name} — {desc}")
    frame(s, fill=BG_ALT)
    s.css.append(
        "@keyframes sw{0%{transform:translateX(-160px)}60%,100%{transform:translateX(488px)}}"
        ".sw{animation:sw 4.5s cubic-bezier(0.65,0,0.35,1) infinite}"
        "@keyframes blink{0%,100%{opacity:1}50%{opacity:.25}}.dot{animation:blink 2.4s ease-in-out infinite}"
        "@keyframes arr{0%,100%{transform:translate(0,0)}50%{transform:translate(3px,-3px)}}"
        ".arr{animation:arr 1.8s ease-in-out infinite}"
        f"@keyframes pin{{from{{opacity:0;transform:translateY(14px)}}to{{opacity:1;transform:none}}}}"
        f".pin{{animation:pin .9s {EASE_OUT} both}}"
    )
    chip_css(s, 6)
    s.defs.append(
        f'<linearGradient id="sg"><stop offset="0" stop-color="{ACCENT}" stop-opacity="0"/>'
        f'<stop offset=".5" stop-color="{ACCENT}"/><stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/></linearGradient>'
    )
    s.add(f'<rect x="1" y="1" width="486" height="2" fill="{BORDER}"/>')
    s.add(f'<rect class="sw" x="0" y="1" width="160" height="2" fill="url(#sg)"/>')
    s.text(470, 290, tag, "d9", 170, "#161616", anchor="end")
    s.add('<g class="pin">')
    s.text(28, 50, tag, "d9", 22, ACCENT)
    s.text(28 + measure(tag, "d9", 22) + 10, 49, "///", "d9", 16, ACCENT_DEEP, ls=-0.8)
    s.add(f'<circle class="dot" cx="{460 - measure("LIVE", "l5", 11, 1.8) - 12}" cy="45" r="4" fill="{GREEN}"/>')
    s.text(460, 49, "LIVE", "l5", 11, DIM, ls=1.8, anchor="end")
    s.text(28, 112, name.upper(), "d9", 48, TEXT, ls=0.4)
    y = 146
    for l in wrap(desc, "b4", 14.5, 420):
        s.text(28, y, l, "b4", 14.5, MUTED)
        y += 23
    s.add("</g>")
    x = 28
    for i, t in enumerate(tags):
        x += chip(s, x, 206, t, delay=0.4 + i * 0.08, wave=1.2 + i * 0.3) + 8
    s.add(f'<line x1="28" y1="256" x2="460" y2="256" stroke="{BORDER}"/>')
    s.text(28, 281, "VIEW LIVE", "l6", 12, ACCENT, ls=2)
    ax = 28 + measure("VIEW LIVE", "l6", 12, 2) + 6
    s.add(
        f'<g class="arr"><path d="M{ax:.1f} 281 l8 -8 M{ax + 2:.1f} 273 h6 v6" stroke="{ACCENT}" stroke-width="1.8" fill="none"/></g>'
    )
    s.text(460, 281, url_label.upper(), "l5", 11, GHOST, ls=1.6, anchor="end")
    s.render(fname)


def contact():
    s = Svg(1000, 300, "Got a project in mind? Let's talk — fontalejandro0@gmail.com")
    s.add(f'<rect width="{s.w}" height="{s.h}" fill="{ACCENT}"/>')
    s.defs.append(
        f'<pattern id="dg" width="14" height="14" patternUnits="userSpaceOnUse" patternTransform="rotate(-30)">'
        f'<rect width="4" height="14" fill="{ACCENT_DARK}" opacity=".35"/></pattern>'
    )
    s.css.append(
        "@keyframes dg{to{transform:translateX(-56px)}}.dgm{animation:dg 3s linear infinite}"
        f"@keyframes cu{{from{{transform:translateY(90px)}}to{{transform:none}}}}"
        f".cu{{animation:cu 1s {EASE_OUT} both}}"
        f"@keyframes cf{{from{{opacity:0}}to{{opacity:1}}}}.cf{{animation:cf 1s {EASE_OUT} both}}"
        "@keyframes big{0%,100%{transform:translateX(0) skewX(0)}50%{transform:translateX(18px) skewX(-8deg)}}"
        ".big{animation:big 5s ease-in-out infinite;transform-box:fill-box}"
    )
    s.defs.append('<clipPath id="rc"><rect x="640" y="0" width="360" height="300"/></clipPath>')
    s.add('<g clip-path="url(#rc)"><g class="dgm"><rect x="640" y="0" width="420" height="300" fill="url(#dg)"/></g></g>')
    s.text(952, 250, "///", "d9", 260, ACCENT_DEEP, ls=-14, anchor="end", cls="big")
    s.add('<g class="cf" style="animation-delay:.1s">')
    s.text(56, 70, "/// LET'S TALK", "l6", 13, BG, ls=2.4)
    s.add("</g>")
    s.defs.append('<clipPath id="c1"><rect x="0" y="82" width="700" height="84"/></clipPath>')
    s.defs.append('<clipPath id="c2"><rect x="0" y="160" width="700" height="80"/></clipPath>')
    s.add('<g clip-path="url(#c1)">')
    s.text(52, 152, "GOT A PROJECT", "d9", 84, BG, ls=-1, cls="cu", extra=' style="animation-delay:.2s"')
    s.add('</g><g clip-path="url(#c2)">')
    s.text(52, 228, "IN MIND?", "d9", 84, BG, ls=-1, cls="cu", extra=' style="animation-delay:.35s"')
    s.add("</g>")
    s.add('<g class="cf" style="animation-delay:.8s">')
    s.text(56, 266, "Tell me what you need — I'll get back to you within 24 hours.", "b5", 15, BG)
    s.add("</g>")
    s.render("contact.svg")


def button(label, fname, solid):
    lab = label.upper()
    w = measure(lab, "l6", 13, 1.3) + 60
    s = Svg(int(w) + 2, 52, label)
    s.css.append(
        "@keyframes sh{0%,70%{transform:translateX(-80px)}100%{transform:translateX(" + str(int(w) + 80) + "px)}}"
        ".sh{animation:sh 3.5s ease-in-out infinite}"
    )
    s.defs.append('<clipPath id="bc"><rect x="1" y="1" width="' + f"{w:.1f}" + '" height="50" rx="6"/></clipPath>')
    s.defs.append(
        '<linearGradient id="shg"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        '<stop offset=".5" stop-color="#fff" stop-opacity=".35"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
    )
    if solid:
        s.add(f'<rect x="1" y="1" width="{w:.1f}" height="50" rx="6" fill="{ACCENT}"/>')
    else:
        s.add(f'<rect x="2" y="2" width="{w - 2:.1f}" height="48" rx="6" fill="{BG}" stroke="{ACCENT}" stroke-width="2"/>')
    s.add(f'<g clip-path="url(#bc)"><rect class="sh" x="0" y="0" width="60" height="52" fill="url(#shg)" transform="skewX(-20)"/></g>')
    s.text(1 + w / 2, 31, lab, "l6", 13, BG if solid else ACCENT, ls=1.3, anchor="middle")
    s.render(fname)


def main():
    OUT.mkdir(exist_ok=True)
    hero()
    marquee(
        ["Astro", "React", "TypeScript", "Next.js", "Bun", "Hono", "Java", "Spring Boot", "Python",
         "AI Agents", "RPA", "Cloudflare", "AWS", "Docker", "PostgreSQL"],
        "marquee.svg", ACCENT, BG, ACCENT_DEEP,
    )
    stats()
    about()
    stack()
    experience()
    project("01", "afont/ui", "ui.afont.dev",
            "My own UI component registry, installable straight into any project from the command line.",
            ["React", "TypeScript", "shadcn/ui", "Tailwind"], "project-ui.svg")
    project("02", "Fleetly", "fleetly.afont.dev",
            "Company portal for internal fleet management, with a separate administration panel.",
            ["TypeScript", "React", "PostgreSQL"], "project-fleetly.svg")
    contact()
    button("Email me", "btn-email.svg", True)
    button("afont.dev", "btn-web.svg", False)
    button("LinkedIn", "btn-linkedin.svg", False)
    marquee(["Alejandro Font", "Barcelona", "Since 2022", "Web · AI · Automation"],
            "footer.svg", BG, "#3a3a3a", ACCENT, reverse=True, h=48, size=18, speed=40)


if __name__ == "__main__":
    main()
