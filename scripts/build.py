"""Genera los SVG animados del README con el estilo de afont.dev ("Losa").

Uso:  pip install fonttools brotli  &&  python scripts/build.py
Salida: assets/*.svg

GitHub no permite CSS ni JS en el README, pero si SVG con animaciones CSS
dentro. Las fuentes y las imagenes se incrustan (las fuentes recortadas a los
caracteres usados) porque un SVG servido como <img> no puede cargar nada externo.

El estilo: brutal por escala y contraste, no por cajas. Grotesca muy pesada con
las letras juntas, imagenes a sangre, franjas naranjas macizas y lineas finas.
Sin sombras, sin bordes gruesos, sin etiquetas en mayusculas espaciadas.
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
BG = "#0b0b0b"
LINE = "#262626"
ACCENT = "#ff6b00"
ON_ACCENT = "#0b0b0b"
TEXT = "#f2f2f2"
MUTED = "#b5b5b5"
FAINT = "#8a8a8a"
GHOST = "#5c5c5c"
EASE_OUT = "cubic-bezier(0.16, 1, 0.3, 1)"
EASE_IN_OUT = "cubic-bezier(0.76, 0, 0.24, 1)"
W = 1000
PAD = 40

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
    "d9": "schibsted-grotesk-latin-900-normal.woff2",
    "d8": "schibsted-grotesk-latin-800-normal.woff2",
    "d7": "schibsted-grotesk-latin-700-normal.woff2",
    "b4": "geist-latin-400-normal.woff2",
    "b5": "geist-latin-500-normal.woff2",
    "m4": "geist-mono-latin-400-normal.woff2",
    "m5": "geist-mono-latin-500-normal.woff2",
}
_font_cache = {}


def font(key):
    if key not in _font_cache:
        _font_cache[key] = TTFont(ROOT / "fonts" / FONTS[key])
    return _font_cache[key]


def tight(size, k=0.055):
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
    f"@keyframes up{{from{{transform:translateY(110%)}}to{{transform:none}}}}"
    f".up{{transform-box:fill-box;animation:up 1.1s {EASE_OUT} both}}"
    f"@keyframes fade{{from{{opacity:0;transform:translateY(10px)}}to{{opacity:1;transform:none}}}}"
    f".fade{{animation:fade .9s {EASE_OUT} both}}"
    f"@keyframes draw{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}"
    f".draw{{transform-box:fill-box;transform-origin:left;animation:draw 1.4s {EASE_OUT} both}}"
)


def base(s, fill=BG):
    s.css.append(ANIM)
    s.add(f'<rect width="{s.w}" height="{s.h}" fill="{fill}"/>')


def label_row(s, y, left, right=""):
    """Cabecera de seccion: linea fina y la etiqueta en mono, como .section-label."""
    s.add(f'<rect x="{PAD}" y="{y}" width="{s.w - 2 * PAD}" height="1" fill="{LINE}"/>')
    s.add('<g class="fade">')
    s.text(PAD, y + 26, left, "m4", 13, FAINT)
    if right:
        s.text(s.w - PAD, y + 26, right, "m4", 13, FAINT, anchor="end")
    s.add("</g>")


def rising_lines(s, x, y0, lines, key, size, fill, step, delay=0.1, cid="l"):
    """Titular que entra linea a linea desde una mascara. lines: str o [(texto, color)]."""
    for i, line in enumerate(lines):
        top = y0 + i * step - size
        s.defs.append(f'<clipPath id="{cid}{i}"><rect x="0" y="{top - size * 0.08:.0f}" width="{s.w}" height="{size * 1.24:.0f}"/></clipPath>')
        s.add(f'<g clip-path="url(#{cid}{i})"><g class="up" style="animation-delay:{delay + i * 0.09:.2f}s">')
        if isinstance(line, str):
            s.text(x, y0 + i * step, line, key, size, fill, ls=tight(size, 0.06))
        else:
            s.runs(x, y0 + i * step, line, key, size, ls=tight(size, 0.06))
        s.add("</g></g>")


# ---------- secciones ----------

def hero():
    h = 540
    s = Svg(W, h, "Alejandro Font Muñiz — Software developer, Barcelona")
    base(s)
    s.css.append(
        f"@keyframes ph{{from{{transform:scale(1.08)}}to{{transform:none}}}}"
        f".ph{{transform-box:fill-box;transform-origin:center;animation:ph 1.8s {EASE_OUT} both}}"
        f"@keyframes cur{{from{{transform:scaleY(1)}}to{{transform:scaleY(0)}}}}"
        f".cur{{transform-box:fill-box;transform-origin:top;animation:cur 1.1s {EASE_IN_OUT} .2s both}}"
    )
    # foto a sangre, mitad derecha, destapada por una cortina
    px = W // 2
    s.defs.append(f'<clipPath id="pc"><rect x="{px}" y="0" width="{W - px}" height="{h}"/></clipPath>')
    s.add(f'<g clip-path="url(#pc)"><image class="ph" x="{px}" y="-30" width="{W - px}" height="{W - px + 40}" '
          f'preserveAspectRatio="xMidYMid slice" href="{jpeg("me.jpg")}"/></g>')
    s.add(f'<rect class="cur" x="{px}" y="0" width="{W - px}" height="{h}" fill="{BG}"/>')
    # etiqueta "available"
    lab = "Available for projects"
    lw = measure(lab, "m4", 13) + 24
    s.add('<g class="fade" style="animation-delay:1.2s">')
    s.add(f'<rect x="{px + 18}" y="{h - 52}" width="{lw:.0f}" height="32" fill="{BG}"/>')
    s.text(px + 30, h - 31, lab, "m4", 13, TEXT)
    s.add("</g>")

    # texto
    s.add('<g class="fade" style="animation-delay:.1s">')
    s.text(PAD, 150, "Software developer — Barcelona", "m4", 13, FAINT)
    s.add("</g>")
    rising_lines(s, PAD - 4, 246, ["Alejandro", "Font", "Muñiz"], "d9", 92, TEXT, 82, delay=0.2)
    s.add('<g class="fade" style="animation-delay:.8s">')
    y = 460
    for line in wrap("Developer at Infini. I build management platforms, web applications and AI agents.", "b4", 16, 400):
        s.text(PAD, y, line, "b4", 16, MUTED)
        y += 25
    s.add("</g>")
    s.render("hero.svg")


def slab(words):
    """La franja naranja: 'i build' y una palabra gigante que rota, cortada por el borde."""
    h = 170
    size = 150
    step = size * 1.25
    s = Svg(W, h, "I build " + ", ".join(words))
    base(s, ACCENT)
    n = len(words)
    kf = []
    for i in range(n):
        a, b = i * 100 / n, (i + 1) * 100 / n
        kf.append(f"{a:.2f}%,{b - 4:.2f}%{{transform:translateY({-i * step:.1f}px)}}")
    kf.append(f"100%{{transform:translateY({-n * step:.1f}px)}}")
    s.css.append("@keyframes rot{" + "".join(kf) + "}" + f".rot{{animation:rot 12s {EASE_IN_OUT} 1s infinite}}")
    s.text(PAD, 34, "i build", "m5", 14, ON_ACCENT)
    base_y = h + 14  # la linea base cae por debajo del borde: la palabra queda cortada
    top = base_y - size * 1.0
    s.defs.append(f'<clipPath id="slot"><rect x="0" y="{top:.0f}" width="{W}" height="{h - top:.0f}"/></clipPath>')
    s.add('<g clip-path="url(#slot)"><g class="rot">')
    for i, w in enumerate(words + words[:1]):
        s.text(PAD - 6, base_y + i * step, w, "d9", size, ON_ACCENT, ls=tight(size, 0.07))
    s.add("</g></g>")
    s.render("slab.svg")


def about():
    statement = [
        ("I work at ", GHOST), ("Infini", TEXT), (", a Barcelona consultancy specialising in automation and AI. I build ", GHOST),
        ("management platforms", TEXT), (", ", GHOST), ("web applications", TEXT), (" and ", GHOST), ("AI agents", ACCENT),
        (", and every project is from a different sector.", GHOST),
    ]
    size, maxw = 38, W - 2 * PAD
    # partir en lineas respetando colores, palabra a palabra
    words = []
    for t, c in statement:
        for k, word in enumerate(t.split(" ")):
            if k > 0:
                words.append((" ", c))
            if word:
                words.append((word, c))
    lines, cur, curw = [], [], 0.0
    ls = tight(size, 0.045)
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
    # juntar tramos consecutivos del mismo color
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
    h = 70 + len(merged) * lh + 210
    s = Svg(W, h, "About me — " + "".join(t for t, _ in statement))
    base(s)
    label_row(s, 1, "About me")
    rising_lines(s, PAD, 96, merged, "d7", size, TEXT, lh, delay=0.15, cid="a")
    y = 96 + len(merged) * lh + 40
    colw = (W - 2 * PAD) / 3
    for i, (v, l) in enumerate(stats):
        x = PAD + i * colw
        s.add(f'<g class="fade" style="animation-delay:{0.5 + i * 0.12:.2f}s">')
        s.text(x, y + 16, l, "m4", 12, FAINT)
        s.text(x - 4, y + 112, v, "d9", 104, TEXT, ls=tight(104, 0.06))
        s.add("</g>")
    s.render("about.svg")


def project_lead(name, url_label, desc, fname, img):
    h = 440
    s = Svg(W, h, f"{name} — {desc}")
    base(s)
    s.css.append(
        f"@keyframes ph{{from{{transform:scale(1.06)}}to{{transform:none}}}}"
        f".ph{{transform-box:fill-box;transform-origin:center;animation:ph 1.8s {EASE_OUT} both}}"
    )
    s.defs.append(f'<clipPath id="lc"><rect width="{W}" height="{h}"/></clipPath>')
    s.defs.append(
        '<linearGradient id="sh" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset=".15" stop-color="{BG}" stop-opacity="0"/><stop offset=".95" stop-color="{BG}" stop-opacity=".96"/></linearGradient>'
    )
    s.add(f'<g clip-path="url(#lc)"><image class="ph" x="0" y="0" width="{W}" height="{W * 0.625:.0f}" '
          f'preserveAspectRatio="xMidYMin slice" href="{jpeg(img)}"/></g>')
    s.add(f'<rect width="{W}" height="{h}" fill="{BG}" opacity=".68"/>')
    s.add(f'<rect width="{W}" height="{h}" fill="url(#sh)"/>')
    s.add('<g class="fade" style="animation-delay:.3s">')
    s.text(PAD, h - 150, f"01 — Live — {url_label}", "m4", 13, ACCENT)
    s.add("</g>")
    rising_lines(s, PAD - 6, h - 46, [name], "d9", 116, TEXT, 0, delay=0.35, cid="p")
    s.add('<g class="fade" style="animation-delay:.7s">')
    y = h - 92
    for line in wrap(desc, "b5", 15, 300):
        s.text(W - PAD, y, line, "b5", 15, TEXT, anchor="end")
        y += 22
    s.text(W - PAD, y + 4, "View live →", "b5", 15, ACCENT, anchor="end")
    s.add("</g>")
    s.render(fname)


def project_half(idx, name, url_label, desc, tags, fname, visual):
    w, h = 488, 520
    s = Svg(w, h, f"{name} — {desc}")
    base(s)
    vh = 290
    if visual[0] == "img":
        s.css.append(
            f"@keyframes ph{{from{{transform:scale(1.06)}}to{{transform:none}}}}"
            f".ph{{transform-box:fill-box;transform-origin:center;animation:ph 1.8s {EASE_OUT} both}}"
        )
        s.defs.append(f'<clipPath id="vc"><rect width="{w}" height="{vh}"/></clipPath>')
        s.add(f'<g clip-path="url(#vc)"><image class="ph" x="0" y="0" width="{w}" height="{w * 0.625 + 20:.0f}" '
              f'preserveAspectRatio="xMinYMin slice" href="{jpeg(visual[1])}"/></g>')
    else:
        # Winkit: sus atajos reales, en plano
        s.add(f'<rect width="{w}" height="{vh}" fill="#151515"/>')
        s.css.append(
            "@keyframes key{0%,30%,100%{fill:#222}10%,20%{fill:" + ACCENT + "}}"
            ".key{animation:key 3.2s ease-out infinite}"
        )
        rows = visual[1]
        y = 52
        for ri, (keys, does) in enumerate(rows):
            x = 34
            for ki, k in enumerate(keys):
                kw = max(40, measure(k, "m4", 13) + 22)
                s.add(f'<rect class="key" style="animation-delay:{ri * 0.8:.1f}s" x="{x}" y="{y}" width="{kw:.0f}" height="40" fill="#222"/>')
                s.text(x + kw / 2, y + 25, k, "m4", 13, TEXT, anchor="middle")
                x += kw + (18 if ki < len(keys) - 1 else 0)
                if ki < len(keys) - 1:
                    s.text(x - 12, y + 25, "+", "m4", 13, GHOST, anchor="middle")
            s.text(w - 34, y + 30, does, "d8", 28, GHOST, ls=tight(28, 0.04), anchor="end")
            y += 56
    s.add('<g class="fade" style="animation-delay:.3s">')
    s.text(0, vh + 42, f"{idx} — Open source — {url_label}", "m4", 12, FAINT)
    s.add("</g>")
    rising_lines(s, -3, vh + 104, [name], "d9", 56, TEXT, 0, delay=0.35, cid="t")
    s.add('<g class="fade" style="animation-delay:.6s">')
    y = vh + 140
    for line in wrap(desc, "b4", 15, w - 20):
        s.text(0, y, line, "b4", 15, MUTED)
        y += 22
    s.text(0, y + 12, " / ".join(tags), "m4", 12, FAINT)
    s.text(0, y + 44, "View code →", "b5", 15, ACCENT)
    s.add("</g>")
    s.render(fname)


def experience():
    jobs = [
        ("Jul 2023 — Present", duration(INFINI_START), "Infini", "Software Developer — Barcelona · AI consultancy",
         ["Build management platforms and custom web applications for clients across different sectors.",
          "Create AI agents.", "Automate business processes with RPA.",
          "Work on international projects with clients and teams in the Middle East."],
         ["React", "Java", "Python", "AI", "RPA", "AWS"], True),
        ("Oct 2022 — Mar 2023", "", "Tetravol SL", "Software Developer — Internship",
         ["Software development internship on projects using React, Unity and MySQL."],
         ["React", "Unity", "MySQL"], False),
    ]
    cx, wx = PAD + 170, 560
    blocks, y = [], 70
    for j in jobs:
        lines = [wrap(p, "b4", 15, W - PAD - wx - 22) for p in j[4]]
        bh = max(150, 20 + sum(len(l) * 22 + 10 for l in lines) + 40)
        blocks.append((y, lines, j))
        y += bh + 30
    h = y + 10
    s = Svg(W, h, "Experience — Infini (Jul 2023–present), Tetravol SL (Oct 2022–Mar 2023)")
    base(s)
    label_row(s, 1, "Experience", "(02)")
    for bi, (by, lines, (period, dur, company, role, _, tags, current)) in enumerate(blocks):
        if bi > 0:
            s.add(f'<rect x="{PAD}" y="{by - 16}" width="{W - 2 * PAD}" height="1" fill="{LINE}"/>')
        if current:
            s.add(f'<rect class="draw" style="animation-delay:.4s" x="{PAD}" y="{by - 17 if bi else 0}" width="{W - 2 * PAD}" height="2" fill="{ACCENT}"/>')
        s.add(f'<g class="fade" style="animation-delay:{0.3 + bi * 0.25:.2f}s">')
        s.text(PAD, by + 30, period, "m4", 12, FAINT)
        if dur:
            s.text(PAD, by + 50, dur, "m4", 12, ACCENT)
        s.text(cx - 3, by + 66, company, "d9", 54, TEXT, ls=tight(54, 0.055))
        for k, part in enumerate(wrap(role, "b4", 14, wx - cx - 30)):
            s.text(cx, by + 96 + k * 20, part, "b4", 14, MUTED)
        yy = by + 34
        for para in lines:
            s.text(wx, yy, "—", "b5", 15, ACCENT)
            for line in para:
                s.text(wx + 22, yy, line, "b4", 15, MUTED)
                yy += 22
            yy += 10
        s.text(wx, yy + 12, " / ".join(tags), "m4", 12, FAINT)
        s.add("</g>")
    s.render("experience.svg")


def stack():
    groups = [
        ("Frontend", ["React", "Next.js", "Astro", "TypeScript", "Tailwind CSS", "Vue.js"]),
        ("Backend", ["Bun", "Hono", "Node.js", "Java", "Spring Boot", "Python", "Odoo"]),
        ("Data", ["PostgreSQL", "MongoDB", "Redis", "MySQL", "MinIO"]),
        ("Cloud & tooling", ["AWS", "Cloudflare", "Docker", "Vercel", "Linux", "GraphQL"]),
        ("AI & automation", ["AI agents", "RPA", "Process automation", "REST APIs"]),
    ]
    row = 34
    h = 70 + 70 + max(len(i) for _, i in groups) * row + 30
    s = Svg(W, h, "Stack — " + "; ".join(f"{g}: {', '.join(i)}" for g, i in groups))
    base(s)
    label_row(s, 1, "Stack", f"({sum(len(i) for _, i in groups)})")
    colw = (W - 2 * PAD + 20) / len(groups)
    for gi, (label, items) in enumerate(groups):
        x = PAD + gi * colw
        s.add(f'<g class="fade" style="animation-delay:{0.2 + gi * 0.1:.2f}s">')
        s.text(x - 1, 112, label, "d8", 24, ACCENT if gi == len(groups) - 1 else TEXT, ls=tight(24, 0.04))
        for k, it in enumerate(items):
            yy = 140 + k * row
            s.add(f'<rect x="{x:.1f}" y="{yy}" width="{colw - 20:.1f}" height="1" fill="{LINE}"/>')
            s.text(x, yy + 23, it, "b4", 14, MUTED)
        s.add("</g>")
    s.render("stack.svg")


def education():
    studies = [
        ("2021–2023", "Cross-platform App Development", "CampusNet · Higher Vocational Degree (DAM)"),
        ("2019–2021", "Science & Technology Baccalaureate", "Col·legi Pare Manyanet Les Corts"),
    ]
    certs = [
        ("SQL Server", True),
        ("Python Programming — Advanced", True),
        ("AWS Cloud Practitioner", False),
        ("Oracle Certified Java SE", False),
        ("Google AI Essentials", False),
        ("Professional Scrum Master I", False),
    ]
    row = 40
    h = 70 + len(studies) * 100 + 50 + len(certs) * row + 30
    s = Svg(W, h, "Education — Cross-platform App Development (DAM), CampusNet, 2021–2023. Certifications: "
            + ", ".join(f"{n} ({'obtained' if d else 'in progress'})" for n, d in certs))
    base(s)
    label_row(s, 1, "Education")
    cx = PAD + 170
    y = 70
    for i, (years, title, school) in enumerate(studies):
        s.add(f'<g class="fade" style="animation-delay:{0.2 + i * 0.15:.2f}s">')
        s.text(PAD, y + 34, years, "m4", 12, FAINT)
        s.text(cx - 2, y + 44, title, "d9", 36, TEXT, ls=tight(36, 0.05))
        s.text(cx, y + 72, school, "b4", 14, MUTED)
        s.add("</g>")
        s.add(f'<rect x="{PAD}" y="{y + 94}" width="{W - 2 * PAD}" height="1" fill="{LINE}"/>')
        y += 100
    y += 40
    s.add('<g class="fade" style="animation-delay:.5s">')
    s.text(PAD - 1, y + 28, "Certifications", "d8", 22, TEXT, ls=tight(22, 0.04))
    for i, (name, done) in enumerate(certs):
        yy = y + i * row
        s.add(f'<rect x="{cx}" y="{yy}" width="{W - PAD - cx}" height="1" fill="{LINE}"/>')
        s.text(cx, yy + 26, name, "b4", 15, TEXT if done else MUTED)
        s.text(W - PAD, yy + 26, "Obtained" if done else "In progress", "m4", 12, ACCENT if done else FAINT, anchor="end")
    s.add(f'<rect x="{cx}" y="{y + len(certs) * row}" width="{W - PAD - cx}" height="1" fill="{LINE}"/>')
    s.add("</g>")
    s.render("education.svg")


def contact():
    h = 360
    s = Svg(W, h, "Got a project in mind? Let's talk — fontalejandro0@gmail.com")
    base(s, ACCENT)
    s.text(PAD, 50, "Got a project in mind?", "m5", 14, ON_ACCENT)
    s.add('<g class="fade" style="animation-delay:.2s">')
    y = 40
    for line in wrap("Open to new opportunities, job offers and collaborations. I reply within 24 hours.", "b4", 15, 320):
        s.text(W - PAD, y + 10, line, "b4", 15, ON_ACCENT, anchor="end")
        y += 22
    s.add("</g>")
    rising_lines(s, PAD - 5, 186, ["fontalejandro0", "@gmail.com →"], "d9", 104, ON_ACCENT, 92, delay=0.25, cid="c")
    s.add(f'<rect class="draw" style="animation-delay:.6s" x="{PAD}" y="{h - 44}" width="{W - 2 * PAD}" height="2" fill="{ON_ACCENT}"/>')
    s.render("contact.svg")


def button(label, fname, solid):
    w = measure(label, "b5", 15) + 70
    s = Svg(int(w) + 2, 52, label)
    fill, fg = (ACCENT, ON_ACCENT) if solid else (BG, TEXT)
    s.add(f'<rect width="{s.w}" height="52" fill="{fill}"/>')
    s.text(22, 31, label, "b5", 15, fg)
    s.text(s.w - 18, 31, "→" if solid else "↗", "b5", 15, ON_ACCENT if solid else ACCENT, anchor="end")
    s.render(fname)


def footer():
    h = 190
    s = Svg(W, h, "Alejandro Font · Barcelona · Since 2022")
    base(s)
    s.add(f'<rect x="{PAD}" y="0" width="{W - 2 * PAD}" height="1" fill="{LINE}"/>')
    s.text(PAD, 30, "© Alejandro Font Muñiz", "m4", 12, FAINT)
    s.text(W - PAD, 30, "Barcelona · Available for projects", "m4", 12, FAINT, anchor="end")
    size = 172
    while measure("Alejandro Font", "d9", size, tight(size, 0.06)) > W - 2 * PAD + 10:
        size -= 2
    rising_lines(s, PAD - 6, h + size * 0.16, ["Alejandro Font"], "d9", size, ACCENT, 0, delay=0.2, cid="f")
    s.render("footer.svg")


# Proyectos publicados. El primero sale a sangre, a todo el ancho; los otros dos, en mitades.
PROJECTS = [
    ("Rax Custom", "raxcustom.com",
     "Website, 3D seat configurator and quote requests for an upholstery workshop in Tenerife.",
     "project-rax.svg", "rax-custom.jpg"),
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
    slab(["AI agents", "web apps", "platforms", "RPA"])
    about()
    lead = PROJECTS[0]
    project_lead(*lead)
    for i, p in enumerate(PROJECTS[1:]):
        project_half(f"{i + 2:02d}", *p)
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
