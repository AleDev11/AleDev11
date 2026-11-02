"""Genera los SVG animados del README con el estilo de afont.dev ("Órbita").

Uso:  pip install fonttools brotli  &&  python scripts/build.py
Salida: assets/*.svg

GitHub no permite CSS ni JS en el README, pero si SVG con animaciones CSS
dentro. Las fuentes y las imagenes se incrustan (las fuentes recortadas a los
caracteres usados) porque un SVG servido como <img> no puede cargar nada externo.

El estilo: nada en cuadricula y nada cortado. Tarjetas redondeadas, el retrato
con un anillo de tecnologias girando, cintas cruzadas y el stack en orbita
alrededor de un sol naranja.
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
BG = "#0f0c0a"
SURFACE = "#1a1512"
SURFACE_2 = "#251d18"
ACCENT = "#ff6b00"
ACCENT_SOFT = "#ff9a4d"
ON_ACCENT = "#1a0d04"
TEXT = "#f6ede4"
MUTED = "#b3a497"
FAINT = "#8f8176"
EASE = "cubic-bezier(0.16, 1, 0.3, 1)"
W = 1000
PAD = 44
R = 30  # radio de las tarjetas

# Fechas de las que salen los contadores. La Action .github/workflows/readme.yml
# vuelve a generar los SVG cada mes, asi que las cifras se actualizan solas.
CAREER_START = date(2021, 9, 1)  # inicio del grado DAM
INFINI_START = date(2023, 7, 1)


def months_since(start, today=None):
    today = today or date.today()
    return (today.year - start.year) * 12 + today.month - start.month


def duration(start):
    y, m = divmod(months_since(start), 12)
    parts = ([f"{y} yr" + ("s" if y != 1 else "")] if y else []) + ([f"{m} mo" + ("s" if m != 1 else "")] if m else [])
    return " ".join(parts) or "1 mo"


FONTS = {
    "d8": "bricolage-grotesque-latin-800-normal.woff2",
    "d7": "bricolage-grotesque-latin-700-normal.woff2",
    "b4": "hanken-grotesk-latin-400-normal.woff2",
    "b5": "hanken-grotesk-latin-500-normal.woff2",
    "b6": "hanken-grotesk-latin-600-normal.woff2",
}
_font_cache = {}


def font(key):
    if key not in _font_cache:
        _font_cache[key] = TTFont(ROOT / "fonts" / FONTS[key])
    return _font_cache[key]


def tight(size, k=0.035):
    """Espaciado negativo de los titulares, en px para el tamaño dado."""
    return -k * size


def measure(text, key, size, ls=0.0):
    f = font(key)
    cmap = f.getBestCmap()
    hmtx = f["hmtx"]
    upm = f["head"].unitsPerEm
    w = sum(hmtx[cmap.get(ord(c), cmap[ord("?")])][0] for c in text)
    return w * size / upm + ls * len(text)


def wrap(text, key, size, maxw, ls=0.0):
    lines, cur = [], ""
    for word in text.split():
        nxt = f"{cur} {word}".strip()
        if cur and measure(nxt, key, size, ls) > maxw:
            lines.append(cur)
            cur = word
        else:
            cur = nxt
    if cur:
        lines.append(cur)
    return lines


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def jpeg(name):
    return "data:image/jpeg;base64," + base64.b64encode((ROOT / name).read_bytes()).decode()


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

    def runs(self, x, y, parts, key, size, ls=0.0):
        """Una linea con tramos de distinto color: [(texto, color), ...]."""
        spans = []
        for t, color in parts:
            self.use(key, t)
            spans.append(f'<tspan fill="{color}">{esc(t)}</tspan>')
        l = f' letter-spacing="{ls:.2f}"' if ls else ""
        self.body.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-family="{key}" font-size="{size}"{l} xml:space="preserve">'
            + "".join(spans) + "</text>"
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
        print(f"  {name:24} {len(svg) / 1024:6.1f} KB")


# ---------- piezas reutilizables ----------

ANIM = (
    f"@keyframes fade{{from{{opacity:0;transform:translateY(16px)}}to{{opacity:1;transform:none}}}}"
    f".fade{{animation:fade 1s {EASE} both}}"
    "@keyframes spin{to{transform:rotate(360deg)}}"
    "@keyframes unspin{to{transform:rotate(-360deg)}}"
    ".spin{transform-box:view-box;animation:spin linear infinite}"
    ".unspin{transform-box:fill-box;transform-origin:center;animation:unspin linear infinite}"
    "@keyframes breathe{0%,100%{transform:scale(1)}50%{transform:scale(1.08)}}"
    ".breathe{transform-box:fill-box;transform-origin:center;animation:breathe 9s ease-in-out infinite}"
)


def base(s, fill=BG, radius=36):
    s.css.append(ANIM)
    s.add(f'<rect width="{s.w}" height="{s.h}" rx="{radius}" fill="{fill}"/>')


def card(s, x, y, w, h, fill=SURFACE, r=R, extra=""):
    s.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r}" fill="{fill}"{extra}/>')


def pill(s, x, y, label, hot=False, size=14, soft=False, center=False, cls="", style=""):
    """Pildora redondeada. Con center=True, (x, y) es su centro."""
    w = measure(label, "b6", size) + size * 1.8
    h = size * 2.3
    if center:
        x, y = x - w / 2, y - h / 2
    fill = ACCENT if hot else (SURFACE_2 if not soft else "#3a2414")
    fg = ON_ACCENT if hot else (ACCENT_SOFT if soft else TEXT)
    c = f' class="{cls}"' if cls else ""
    st = f' style="{style}"' if style else ""
    s.add(f"<g{c}{st}>")
    s.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{h / 2:.1f}" fill="{fill}"/>')
    s.text(x + w / 2, y + h / 2 + size * 0.36, label, "b6", size, fg, anchor="middle")
    s.add("</g>")
    return w


def title(s, x, y, parts, size, delay=0.1):
    """Titular con una palabra en naranja y cursiva: parts = [(texto, naranja?)]."""
    s.add(f'<g class="fade" style="animation-delay:{delay:.2f}s">')
    cx = x
    ls = tight(size)
    for t, hot in parts:
        # los espacios al principio o al final no se pintan en <text>: se suman a mano
        lead = len(t) - len(t.lstrip(" "))
        trail = len(t) - len(t.rstrip(" "))
        cx += measure(" ", "d8", size, ls) * lead
        t = t.strip(" ")
        if not t:
            continue
        if hot:
            s.use("d7", t)
            s.add(f'<text transform="translate({cx:.1f},{y}) skewX(-11)" font-family="d7" font-size="{size}" '
                  f'letter-spacing="{ls:.2f}" fill="{ACCENT}">{esc(t)}</text>')
            cx += measure(t, "d7", size, ls) + measure(" ", "d8", size, ls) * trail
        else:
            s.text(cx, y, t, "d8", size, TEXT, ls=ls)
            cx += measure(t, "d8", size, ls) + measure(" ", "d8", size, ls) * trail
    s.add("</g>")


def orbit(s, cx, cy, r, items, period, reverse=False, size=13):
    """Anillo discontinuo que gira, con pildoras que se mantienen derechas."""
    import math
    d = "reverse" if reverse else "normal"
    s.add(f'<g class="spin" style="transform-origin:{cx}px {cy}px;animation-duration:{period}s;animation-direction:{d}">')
    s.add(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{TEXT}" stroke-opacity=".2" stroke-dasharray="3 6"/>')
    for label, angle, hot in items:
        a = math.radians(angle)
        px, py = cx + r * math.cos(a), cy + r * math.sin(a)
        pill(s, px, py, label, hot=hot, size=size, center=True, cls="unspin",
             style=f"animation-duration:{period}s;animation-direction:{d}")
    s.add("</g>")


# ---------- secciones ----------

def hero():
    h = 520
    s = Svg(W, h, "Alejandro Font Muñiz — Software developer, Barcelona")
    base(s)
    s.defs.append(
        f'<radialGradient id="glow"><stop offset="0" stop-color="{ACCENT}" stop-opacity=".7"/>'
        f'<stop offset=".45" stop-color="{ACCENT}" stop-opacity=".22"/><stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/></radialGradient>'
    )
    s.defs.append(f'<clipPath id="hc"><rect width="{W}" height="{h}" rx="36"/></clipPath>')
    cx, cy = 742, 262
    s.add(f'<g clip-path="url(#hc)"><circle class="breathe" cx="{cx}" cy="{cy}" r="330" fill="url(#glow)"/></g>')

    # texto
    title(s, PAD, 200, [("Alejandro", False)], 92, delay=0.15)
    title(s, PAD, 290, [("Font", True), (" Muñiz", False)], 92, delay=0.25)
    s.add('<g class="fade" style="animation-delay:.45s">')
    y = 352
    for k, line in enumerate(wrap("Developer at Infini. I build management platforms, web applications and AI agents.", "b4", 18, 470)):
        s.text(PAD, y + k * 28, line, "b4", 18, MUTED)
    s.add("</g>")
    s.add('<g class="fade" style="animation-delay:.6s">')
    w = pill(s, PAD, 432, "Get in touch →", hot=True, size=15)
    pill(s, PAD + w + 10, 432, "afont.dev", size=15)
    s.add("</g>")

    # retrato redondo con un anillo de tecnologias y un sello
    s.defs.append(f'<clipPath id="pc"><circle cx="{cx}" cy="{cy}" r="170"/></clipPath>')
    s.add(f'<g class="fade" style="animation-delay:.2s"><image x="{cx - 180}" y="{cy - 190}" width="360" height="360" '
          f'preserveAspectRatio="xMidYMid slice" clip-path="url(#pc)" href="{jpeg("me.jpg")}"/></g>')
    s.render("hero.svg")


def ribbons():
    h = 190
    a = ["AI agents", "Astro", "React", "TypeScript", "Bun", "Java", "Python", "RPA"]
    b = ["Barcelona", "Software developer", "Since 2021", "Infini", "Español · English · Català"]
    s = Svg(W, h, "I build AI agents, web apps, platforms and RPA automations")
    s.css.append(ANIM)
    s.defs.append(f'<clipPath id="rc"><rect width="{W}" height="{h}" rx="36"/></clipPath>')
    s.add(f'<g clip-path="url(#rc)">')

    def band(words, fill, fg, angle, speed, reverse, name):
        size, gap = 32, 30
        xs, x = [], 0
        for wd in words:
            xs.append((x, wd))
            x += measure(wd, "d8", size, tight(size)) + gap + 14 + gap
        total = x
        d = "reverse" if reverse else "normal"
        s.css.append(f"@keyframes {name}{{to{{transform:translateX(-{total:.1f}px)}}}}"
                     f".{name}{{animation:{name} {speed}s linear infinite {d}}}")
        s.add(f'<g transform="rotate({angle} {W / 2} {h / 2})">')
        s.add(f'<rect x="-100" y="{h / 2 - 34}" width="{W + 200}" height="68" fill="{fill}"/>')
        s.add(f'<g class="{name}">')
        for rep in range(3):
            for xx, wd in xs:
                X = xx + rep * total - 60
                s.text(X, h / 2 + 11, wd, "d8", size, fg, ls=tight(size))
                dx = X + measure(wd, "d8", size, tight(size)) + gap
                s.add(f'<circle cx="{dx + 7:.1f}" cy="{h / 2}" r="7" fill="{fg}" opacity=".55"/>')
        s.add("</g></g>")

    band(b, SURFACE, MUTED, 3, 40, True, "mb")
    band(a, ACCENT, ON_ACCENT, -4, 32, False, "ma")
    s.add("</g>")
    s.render("ribbons.svg")


def about():
    statement = [
        ("I work at ", MUTED), ("Infini", TEXT), (", a Barcelona consultancy specialising in automation and AI. I build ", MUTED),
        ("management platforms", TEXT), (", ", MUTED), ("web applications", TEXT), (" and ", MUTED), ("AI agents", ACCENT),
        (", and every project is from a different sector.", MUTED),
    ]
    size, maxw = 34, W - 2 * PAD - 20
    words = []
    for t, c in statement:
        for k, word in enumerate(t.split(" ")):
            if k > 0:
                words.append((" ", c))
            if word:
                words.append((word, c))
    ls = tight(size, 0.02)
    lines, cur, curw = [], [], 0.0
    for tok, c in words:
        tw = measure(tok, "d7", size, ls)
        if tok != " " and cur and curw + tw > maxw:
            while cur and cur[-1][0] == " ":
                cur.pop()
            lines.append(cur)
            cur, curw = [], 0.0
        if tok == " " and not cur:
            continue
        cur.append((tok, c))
        curw += tw
    if cur:
        lines.append(cur)
    merged = []
    for line in lines:
        m = []
        for t, c in line:
            if m and m[-1][1] == c:
                m[-1] = (m[-1][0] + t, c)
            else:
                m.append((t, c))
        merged.append(m)

    years = months_since(CAREER_START) // 12
    stats = [(f"+{years}", "years developing"), ("3", "projects shipped"), ("3", "languages · es en ca")]
    lh = 42
    top = 104
    h = top + len(merged) * lh + 170
    s = Svg(W, h, "About me — " + "".join(t for t, _ in statement))
    base(s, SURFACE)
    title(s, PAD, 74, [("About ", False), ("me", True)], 46)
    s.add('<g class="fade" style="animation-delay:.25s">')
    for i, line in enumerate(merged):
        s.runs(PAD, top + 34 + i * lh, line, "d7", size, ls=ls)
    s.add("</g>")
    y = top + len(merged) * lh + 30
    cw = (W - 2 * PAD - 28) / 3
    for i, (v, l) in enumerate(stats):
        x = PAD + i * (cw + 14)
        s.add(f'<g class="fade" style="animation-delay:{0.4 + i * 0.12:.2f}s">')
        card(s, x, y, cw, 112, SURFACE_2, 24)
        s.text(x + 22, y + 66, v, "d8", 54, TEXT, ls=tight(54))
        s.add(f'<circle cx="{x + 30 + measure(v, "d8", 54, tight(54)):.1f}" cy="{y + 60}" r="6" fill="{ACCENT}"/>')
        s.text(x + 22, y + 94, l, "b5", 14, MUTED)
        s.add("</g>")
    s.render("about.svg")


def project_lead(name, url_label, desc, tags, fname, img):
    h = 420
    s = Svg(W, h, f"{name} — {desc}")
    base(s, SURFACE)
    s.add('<g class="fade" style="animation-delay:.1s">')
    pill(s, PAD, 52, f"Live · {url_label}", soft=True, size=14)
    s.add("</g>")
    title(s, PAD, 170, [(name, False)], 64, delay=0.2)
    s.add('<g class="fade" style="animation-delay:.35s">')
    y = 214
    for line in wrap(desc, "b4", 17, 360):
        s.text(PAD, y, line, "b4", 17, MUTED)
        y += 27
    x = PAD
    for t in tags[:4]:
        x += pill(s, x, y + 6, t, size=13) + 8
    pill(s, PAD, y + 62, "View live →", hot=True, size=15)
    s.add("</g>")
    ix, iy, iw = 470, 34, W - 470 - 34
    ih = h - 68
    s.defs.append(f'<clipPath id="ic"><rect x="{ix}" y="{iy}" width="{iw}" height="{ih}" rx="24"/></clipPath>')
    s.add(f'<g class="fade" style="animation-delay:.25s"><image x="{ix}" y="{iy}" width="{iw}" height="{iw * 0.625:.0f}" '
          f'preserveAspectRatio="xMidYMin slice" clip-path="url(#ic)" href="{jpeg(img)}"/></g>')
    s.render(fname)


def project_half(name, url_label, desc, tags, fname, visual):
    w, h = 488, 560
    s = Svg(w, h, f"{name} — {desc}")
    base(s, SURFACE, 32)
    vx, vy, vw, vh = 22, 22, w - 44, 256
    s.defs.append(f'<clipPath id="vc"><rect x="{vx}" y="{vy}" width="{vw}" height="{vh}" rx="22"/></clipPath>')
    if visual[0] == "img":
        s.add(f'<g class="fade"><image x="{vx}" y="{vy}" width="{vw}" height="{vw * 0.625 + 10:.0f}" '
              f'preserveAspectRatio="xMinYMin slice" clip-path="url(#vc)" href="{jpeg(visual[1])}"/></g>')
    else:
        s.defs.append(
            f'<radialGradient id="kg" cx=".85" cy=".1" r=".8"><stop offset="0" stop-color="{ACCENT}" stop-opacity=".4"/>'
            f'<stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/></radialGradient>'
        )
        card(s, vx, vy, vw, vh, SURFACE_2, 22)
        card(s, vx, vy, vw, vh, "url(#kg)", 22)
        s.css.append("@keyframes key{0%,30%,100%{fill:" + BG + "}10%,20%{fill:" + ACCENT + "}}.key{animation:key 3.2s ease-out infinite}")
        y = vy + 30
        for ri, (keys, does) in enumerate(visual[1]):
            x = vx + 26
            for k in keys:
                kw = max(38, measure(k, "b6", 13) + 22)
                s.add(f'<rect class="key" style="animation-delay:{ri * 0.8:.1f}s" x="{x:.0f}" y="{y}" width="{kw:.0f}" height="38" rx="10" fill="{BG}"/>')
                s.text(x + kw / 2, y + 24, k, "b6", 13, TEXT, anchor="middle")
                x += kw + 6
            s.text(vx + vw - 26, y + 27, does, "d7", 24, MUTED, ls=tight(24), anchor="end")
            y += 52
    s.add('<g class="fade" style="animation-delay:.2s">')
    pill(s, 26, vy + vh + 26, "Open source · MIT", size=13)
    s.add("</g>")
    title(s, 26, vy + vh + 112, [(name, False)], 46, delay=0.3)
    s.add('<g class="fade" style="animation-delay:.45s">')
    y = vy + vh + 148
    for line in wrap(desc, "b4", 15, w - 52):
        s.text(26, y, line, "b4", 15, MUTED)
        y += 23
    s.text(26, y + 22, " · ".join(tags), "b5", 13, FAINT)
    s.text(26, y + 56, "View code →", "b6", 15, ACCENT)
    s.add("</g>")
    s.render(fname)


def experience():
    jobs = [
        ("Jul 2023 — Present · " + duration(INFINI_START), "Infini", "Software Developer · Barcelona · AI consultancy",
         ["Build management platforms and custom web applications for clients across different sectors.",
          "Create AI agents.", "Automate business processes with RPA.",
          "Work on international projects with clients and teams in the Middle East."],
         ["React", "Java", "Python", "AI", "RPA", "AWS"], True),
        ("Oct 2022 — Mar 2023", "Tetravol SL", "Software Developer · Internship",
         ["Software development internship on projects using React, Unity and MySQL."],
         ["React", "Unity", "MySQL"], False),
    ]
    lx = PAD + 60
    wx = 560
    blocks, y = [], 110
    for j in jobs:
        lines = [wrap(p, "b4", 15, W - PAD - wx - 40) for p in j[3]]
        inner = 30 + sum(len(l) * 22 + 8 for l in lines) + 60
        bh = max(160, inner)
        blocks.append((y, bh, lines, j))
        y += bh + 16
    h = y + 24
    s = Svg(W, h, "Experience — Infini (Jul 2023–present), Tetravol SL (Oct 2022–Mar 2023)")
    base(s)
    title(s, PAD, 76, [("Where I've ", False), ("worked", True)], 46)
    s.defs.append(f'<linearGradient id="tl" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{ACCENT}"/><stop offset="1" stop-color="{SURFACE_2}"/></linearGradient>')
    s.add(f'<rect x="{PAD + 16}" y="{blocks[0][0] + 20}" width="3" height="{blocks[-1][0] - blocks[0][0] + 20}" rx="2" fill="url(#tl)"/>')
    s.css.append(f"@keyframes pulse{{0%,100%{{r:12}}50%{{r:16}}}}.pulse{{animation:pulse 2.4s ease-in-out infinite;fill:{ACCENT};fill-opacity:.25}}")
    for bi, (by, bh, lines, (period, company, role, _, tags, current)) in enumerate(blocks):
        s.add(f'<g class="fade" style="animation-delay:{0.2 + bi * 0.25:.2f}s">')
        if current:
            s.add(f'<circle class="pulse" cx="{PAD + 17.5}" cy="{by + 36}" r="12"/>')
        s.add(f'<circle cx="{PAD + 17.5}" cy="{by + 36}" r="8" fill="{ACCENT if current else BG}" stroke="{ACCENT}" stroke-width="3"/>')
        card(s, lx - 16, by, W - PAD - lx + 16, bh, SURFACE, 26)
        s.text(lx + 10, by + 40, period, "b6", 13, ACCENT_SOFT)
        s.text(lx + 8, by + 92, company, "d8", 44, TEXT, ls=tight(44))
        for k, part in enumerate(wrap(role, "b4", 14, wx - lx - 50)):
            s.text(lx + 10, by + 122 + k * 20, part, "b4", 14, MUTED)
        yy = by + 40
        for para in lines:
            s.add(f'<circle cx="{wx + 4}" cy="{yy - 5}" r="4.5" fill="{ACCENT}"/>')
            for line in para:
                s.text(wx + 20, yy, line, "b4", 15, MUTED)
                yy += 22
            yy += 8
        x = wx
        for t in tags:
            x += pill(s, x, yy + 2, t, size=12) + 6
        s.add("</g>")
    s.render("experience.svg")


def stack():
    """Las cinco areas, cada una con sus tecnologias en pildoras. IA y automatizacion, en naranja."""
    groups = [
        ("AI & automation", "AI agents and automations that remove repetitive work.", ["AI agents", "RPA", "Process automation", "REST APIs"]),
        ("Frontend", "Fast, accessible interfaces.", ["React", "Next.js", "Astro", "TypeScript", "Tailwind CSS", "Vue.js"]),
        ("Backend", "Custom APIs and services.", ["Bun", "Hono", "Node.js", "Java", "Spring Boot", "Python", "Odoo"]),
        ("Data", "Data models, search and storage.", ["PostgreSQL", "MongoDB", "Redis", "MySQL", "MinIO"]),
        ("Cloud & tooling", "Deployment and infrastructure.", ["AWS", "Cloudflare", "Docker", "Vercel", "Linux", "GraphQL"]),
    ]

    def pills_height(items, width, size):
        x, rows = 0, 1
        for it in items:
            w = measure(it, "b6", size) + size * 1.8
            if x and x + w > width:
                rows += 1
                x = 0
            x += w + 8
        return rows * (size * 2.3 + 8)

    def draw_pills(x0, y0, items, width, size, hot_first=False):
        x, y = x0, y0
        for k, it in enumerate(items):
            w = measure(it, "b6", size) + size * 1.8
            if x > x0 and x + w > x0 + width:
                x = x0
                y += size * 2.3 + 8
            pill(s, x, y, it, hot=hot_first and k == 0, size=size)
            x += w + 8

    gap = 14
    top = 110
    # fila 1: IA a todo el ancho; filas 2 y 3: dos areas por fila, misma altura por fila
    lead = groups[0]
    lead_h = 96 + pills_height(lead[2], W - 2 * PAD - 52, 18)
    half = (W - 2 * PAD - gap) / 2
    rows = [groups[1:3], groups[3:5]]
    row_h = [max(96 + pills_height(g[2], half - 52, 14) for g in r) for r in rows]
    h = top + lead_h + gap + row_h[0] + gap + row_h[1] + 34
    s = Svg(W, h, "Stack — " + "; ".join(f"{g}: {', '.join(i)}" for g, _, i in groups))
    base(s)
    title(s, PAD, 76, [("My ", False), ("stack", True)], 46)

    s.add('<g class="fade" style="animation-delay:.2s">')
    card(s, PAD, top, W - 2 * PAD, lead_h, ACCENT, 26)
    s.text(PAD + 26, top + 44, lead[0], "d8", 28, ON_ACCENT, ls=tight(28))
    s.text(PAD + 26, top + 70, lead[1], "b5", 15, ON_ACCENT)
    x, y = PAD + 26, top + 88
    for it in lead[2]:
        w = measure(it, "b6", 18) + 18 * 1.8
        s.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="41.4" rx="20.7" fill="{ON_ACCENT}"/>')
        s.text(x + w / 2, y + 27, it, "b6", 18, ACCENT, anchor="middle")
        x += w + 8
    s.add("</g>")

    y = top + lead_h + gap
    for ri, r in enumerate(rows):
        for ci, (label, note, items) in enumerate(r):
            x = PAD + ci * (half + gap)
            s.add(f'<g class="fade" style="animation-delay:{0.3 + (ri * 2 + ci) * 0.08:.2f}s">')
            card(s, x, y, half, row_h[ri], SURFACE, 24)
            s.text(x + 26, y + 42, label, "d8", 24, TEXT, ls=tight(24))
            s.text(x + 26, y + 66, note, "b4", 14, MUTED)
            draw_pills(x + 26, y + 82, items, half - 52, 14)
            s.add("</g>")
        y += row_h[ri] + gap
    s.render("stack.svg")


def education():
    """Tres tarjetas iguales: grado, bachillerato y certificaciones obtenidas."""
    items = [
        ("2021–2023", ["Cross-platform App", "Development (DAM)"], ["CampusNet", "Higher Vocational Degree"], True),
        ("2019–2021", ["Science & Technology", "Baccalaureate"], ["Col·legi Pare Manyanet", "Les Corts"], False),
        ("Certifications", ["SQL Server", "Python Programming", "(Advanced)"], ["Certifications obtained"], False),
    ]
    h = 380
    s = Svg(W, h, "Education — Cross-platform App Development (DAM), CampusNet, 2021–2023. Science and Technology "
            "Baccalaureate, 2019–2021. Certifications: SQL Server, Advanced Python Programming.")
    base(s)
    title(s, PAD, 76, [("What I've ", False), ("studied", True)], 46)
    gap = 14
    cw = (W - 2 * PAD - 2 * gap) / 3
    top, ch = 110, h - 110 - 34
    s.defs.append(
        f'<linearGradient id="eg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{ACCENT}" stop-opacity=".22"/>'
        f'<stop offset=".65" stop-color="{ACCENT}" stop-opacity="0"/></linearGradient>'
    )
    for i, (tag, ttl, foot, main_) in enumerate(items):
        x = PAD + i * (cw + gap)
        s.add(f'<g class="fade" style="animation-delay:{0.2 + i * 0.12:.2f}s">')
        card(s, x, top, cw, ch, SURFACE, 26)
        if main_:
            card(s, x, top, cw, ch, "url(#eg)", 26)
        pill(s, x + 24, top + 24, tag, soft=True, size=13)
        for k, line in enumerate(ttl):
            # en las certificaciones, la primera va separada: son dos titulos distintos
            extra = 14 if (tag == "Certifications" and k > 0) else 0
            s.text(x + 24, top + 104 + k * 30 + extra, line, "d8", 25, TEXT, ls=tight(25))
        fy = top + ch - 26 - (len(foot) - 1) * 20
        s.add(f'<rect x="{x + 24}" y="{fy - 32}" width="{cw - 48:.1f}" height="1" fill="{SURFACE_2}"/>')
        for k, line in enumerate(foot):
            s.text(x + 24, fy + k * 20, line, "b4", 14, MUTED)
        s.add("</g>")
    s.render("education.svg")


def contact():
    h = 360
    s = Svg(W, h, "Let's talk — fontalejandro0@gmail.com")
    s.css.append(ANIM)
    s.defs.append(f'<clipPath id="cc"><rect width="{W}" height="{h}" rx="40"/></clipPath>')
    s.add(f'<g clip-path="url(#cc)"><rect width="{W}" height="{h}" fill="{ACCENT}"/>'
          f'<circle class="breathe" cx="{W - 80}" cy="{h + 60}" r="240" fill="{ACCENT_SOFT}" opacity=".5"/></g>')
    title_y = 140
    s.add('<g class="fade" style="animation-delay:.1s">')
    s.text(PAD + 10, title_y, "Let's talk", "d8", 110, ON_ACCENT, ls=tight(110, 0.045))
    s.add("</g>")
    s.add('<g class="fade" style="animation-delay:.3s">')
    y = 190
    for line in wrap("Open to job offers, projects and collaborations. I reply within 24 hours.", "b5", 18, 480):
        s.text(PAD + 12, y, line, "b5", 18, ON_ACCENT)
        y += 27
    mail = "fontalejandro0@gmail.com"
    s.text(PAD + 12, h - 56, mail, "d7", 30, ON_ACCENT, ls=tight(30, 0.02))
    mw = measure(mail, "d7", 30, tight(30, 0.02))
    s.add(f'<rect x="{PAD + 12}" y="{h - 46}" width="{mw:.0f}" height="3" fill="{ON_ACCENT}"/>')
    s.add("</g>")
    bx, by = W - 150, 170
    s.add(f'<g class="breathe"><circle cx="{bx}" cy="{by}" r="72" fill="{ON_ACCENT}"/></g>')
    s.text(bx, by - 2, "Email", "b6", 16, ACCENT, anchor="middle")
    s.text(bx, by + 20, "me →", "b6", 16, ACCENT, anchor="middle")
    s.render("contact.svg")


def button(label, fname, solid):
    w = measure(label, "b6", 15) + 66
    s = Svg(int(w) + 2, 52, label)
    fill, fg, arrow = (ACCENT, ON_ACCENT, ON_ACCENT) if solid else (SURFACE, TEXT, ACCENT)
    s.add(f'<rect width="{s.w}" height="52" rx="26" fill="{fill}"/>')
    s.text(24, 31, label, "b6", 15, fg)
    s.text(s.w - 22, 31, "→" if solid else "↗", "b6", 15, arrow, anchor="end")
    s.render(fname)


def footer():
    h = 120
    s = Svg(W, h, "Alejandro Font Muñiz · Barcelona")
    base(s, SURFACE, 32)
    title(s, PAD, 74, [("Alejandro ", False), ("Font", True), (" Muñiz", False)], 40, delay=0.1)
    s.text(W - PAD, 58, "Software developer · Barcelona", "b5", 15, MUTED, anchor="end")
    s.text(W - PAD, 82, "afont.dev", "b6", 15, ACCENT, anchor="end")
    s.render("footer.svg")


# Proyectos publicados. El primero va a todo el ancho; los otros dos, en mitades.
PROJECTS = [
    ("Rax Custom", "raxcustom.com",
     "Website, 3D seat configurator and quote requests for an upholstery workshop in Tenerife.",
     ["Astro", "Bun", "Three.js", "Leaflet"], "project-rax.svg", "rax-custom.jpg"),
    ("Meeting Notes", "github.com/AleDev11/meeting-notes",
     "Open-source desktop app that transcribes meetings, tells speakers apart and writes AI minutes.",
     ["Electron", "React", "TypeScript", "Claude"], "project-meeting-notes.svg", ("img", "meeting-notes.jpg")),
    ("Winkit", "github.com/AleDev11/winkit",
     "Open-source Windows tools with Claude: fix, translate and search from any app with a shortcut.",
     ["Electron", "React", "TypeScript", "Claude"], "project-winkit.svg",
     ("keys", [(["Alt", "Space"], "Launcher"), (["Ctrl", "Alt", "C"], "Fix"),
               (["Ctrl", "Alt", "T"], "Translate"), (["Ctrl", "Alt", "L"], "Read")])),
]


def main():
    OUT.mkdir(exist_ok=True)
    hero()
    ribbons()
    about()
    project_lead(*PROJECTS[0])
    for p in PROJECTS[1:]:
        project_half(p[0], p[1], p[2], p[3], p[4], p[5])
    experience()
    stack()
    education()
    contact()
    button("Email me", "btn-email.svg", True)
    button("afont.dev", "btn-web.svg", False)
    button("LinkedIn", "btn-linkedin.svg", False)
    footer()


if __name__ == "__main__":
    main()
