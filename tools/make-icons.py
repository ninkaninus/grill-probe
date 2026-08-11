#!/usr/bin/env python3
"""Generate every Grill ETA icon from one vector definition.

Run from the repo root:  python3 tools/make-icons.py

The logo is a flame with a grill fork holding a sausage that is browning — the
sausage's pale-to-brown gradient is the app's whole premise in one shape.

Geometry lives in the constants below and is rendered twice: rasterised here
with Pillow, and emitted as favicon.svg / logo.svg. index.html inlines the same
markup in its header, so after changing any constant re-run this and copy the
body of logo.svg into index.html's `.logo` svg.

Outputs: icon-192/512/180.png, icon-maskable-512.png, favicon.ico, favicon.svg,
logo.svg, og-image.png
"""
import math
import struct
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SS = 4  # supersampling factor

# ---- geometry (100x100 design space, y down) --------------------------------
FLAME_D = ("M50,3 C52,22 60,36 70,54 C79,70 72,90 50,91 C28,90 21,70 30,54 "
           "C40,38 36,28 33,18 C39,30 45,18 50,3 Z")
FLAME = [(50, 3), [(52, 22), (60, 36), (70, 54)], [(79, 70), (72, 90), (50, 91)],
         [(28, 90), (21, 70), (30, 54)], [(40, 38), (36, 28), (33, 18)],
         [(39, 30), (45, 18), (50, 3)]]

AX_A, AX_B = (6, 80), (92, 50)   # fork axis: handle end -> tine tips
HANDLE_W, NECK_W, TINE_W = 7.5, 5.2, 4.2
TINE_OFF = 4.8                   # tine separation from the axis
HANDLE_F, CROTCH_F = 0.30, 0.42  # where the handle ends / the tines split
SAUS_F0, SAUS_F1 = 0.42, 0.85    # sausage span along the axis
SAUS_W = 19.0
STRIPES = 4                      # char marks across the sausage
RIM = 3.0                        # dark separation rim around fork + sausage

# ---- palette (matches index.html :root) -------------------------------------
BG_TOP, BG_BOT = (36, 26, 21), (20, 17, 15)           # #241A15 -> #14110F
EMBER_TOP, EMBER_BOT = (255, 194, 89), (255, 78, 46)  # #FFC259 -> #FF4E2E
CREAM = (242, 233, 223)                               # --hi
PALE, BROWN, CHAR = (236, 188, 132), (146, 74, 32), (88, 42, 16)
RIM_RGB = (26, 21, 18)


def on_axis(f):
    return (AX_A[0] + (AX_B[0] - AX_A[0]) * f, AX_A[1] + (AX_B[1] - AX_A[1]) * f)


def axis_frame():
    dx, dy = AX_B[0] - AX_A[0], AX_B[1] - AX_A[1]
    L = math.hypot(dx, dy)
    return dx / L, dy / L, -dy / L, dx / L  # unit along, unit perpendicular


def fork_segments():
    """[(start, end, width)] for handle, neck and the two tines."""
    _, _, px, py = axis_frame()
    M, C = on_axis(HANDLE_F), on_axis(CROTCH_F)
    ox, oy = TINE_OFF * px, TINE_OFF * py
    return [
        (AX_A, M, HANDLE_W), (M, C, NECK_W),
        ((C[0] + ox, C[1] + oy), (AX_B[0] + ox, AX_B[1] + oy), TINE_W),
        ((C[0] - ox, C[1] - oy), (AX_B[0] - ox, AX_B[1] - oy), TINE_W),
    ]


SAUS_A, SAUS_B = on_axis(SAUS_F0), on_axis(SAUS_F1)


def flatten(path, n=64):
    """Cubic bezier path -> polyline points."""
    pts, cur = [path[0]], path[0]
    for c1, c2, end in path[1:]:
        for i in range(1, n + 1):
            t = i / n
            u = 1 - t
            pts.append((
                u**3 * cur[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t**3 * end[0],
                u**3 * cur[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t**3 * end[1],
            ))
        cur = end
    return pts


def vgrad(size, top, bot):
    w, h = size
    img = Image.new("RGB", (1, h))
    px = img.load()
    for y in range(h):
        f = y / max(h - 1, 1)
        px[0, y] = tuple(round(top[i] + (bot[i] - top[i]) * f) for i in range(3))
    return img.resize((w, h), Image.Resampling.BICUBIC)


def axis_grad(P, a, b, c0, c1, K=180):
    """Gradient running along the a->b axis, built small and upscaled."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy or 1
    g = Image.new("RGB", (K, K))
    px = g.load()
    sc = P / K
    for yy in range(K):
        for xx in range(K):
            t = ((xx * sc - a[0]) * dx + (yy * sc - a[1]) * dy) / L2
            t = 0.0 if t < 0 else 1.0 if t > 1 else t
            px[xx, yy] = tuple(round(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))
    return g.resize((P, P), Image.Resampling.BICUBIC)


def capsule(draw, a, b, w, colour):
    """Round-capped thick segment, brush-stamped (PIL's wide lines tear)."""
    r = w / 2
    n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / max(r * 0.18, 0.5)))
    for s in range(n + 1):
        t = s / n
        cx, cy = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=colour)


def draw_art(size, frac, simple=False):
    """Full mark, scaled to `frac` of `size`, centred. Returns RGBA at 4x.

    `simple` renders the flame alone — below ~40px the fork and sausage collapse
    into a smear, so the tiny favicon sizes carry the silhouette only.
    """
    P = size * SS
    flame = flatten(FLAME)
    pts = list(flame)
    if not simple:
        pts += [p for s in fork_segments() for p in s[:2]] + [SAUS_A, SAUS_B]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    scale = frac * P / max(x1 - x0, y1 - y0)
    ox = (P - (x1 - x0) * scale) / 2 - x0 * scale
    oy = (P - (y1 - y0) * scale) / 2 - y0 * scale
    T = lambda p: (p[0] * scale + ox, p[1] * scale + oy)
    blank = lambda: Image.new("RGBA", (P, P), (0, 0, 0, 0))

    art = blank()
    mask = Image.new("L", (P, P), 0)
    ImageDraw.Draw(mask).polygon([T(p) for p in flame], fill=255)
    art.paste(vgrad((P, P), EMBER_TOP, EMBER_BOT).convert("RGBA"), (0, 0), mask)
    if simple:
        return art

    # fork: dark rim first, then the cream body on top
    for colour, extra in ((RIM_RGB + (255,), RIM * 2), (CREAM + (255,), 0)):
        layer = blank()
        d = ImageDraw.Draw(layer)
        for a, b, w in fork_segments():
            capsule(d, T(a), T(b), (w + extra) * scale, colour)
        art.alpha_composite(layer)

    rim = Image.new("L", (P, P), 0)
    capsule(ImageDraw.Draw(rim), T(SAUS_A), T(SAUS_B), (SAUS_W + RIM * 2) * scale, 255)
    art.paste(Image.new("RGBA", (P, P), RIM_RGB + (255,)), (0, 0), rim)

    body = Image.new("L", (P, P), 0)
    capsule(ImageDraw.Draw(body), T(SAUS_A), T(SAUS_B), SAUS_W * scale, 255)
    art.paste(axis_grad(P, T(SAUS_A), T(SAUS_B), PALE, BROWN).convert("RGBA"), (0, 0), body)

    _, _, px, py = axis_frame()
    layer = blank()
    d = ImageDraw.Draw(layer)
    for i in range(STRIPES):
        f = (i + 1) / (STRIPES + 1)
        c = (SAUS_A[0] + (SAUS_B[0] - SAUS_A[0]) * f, SAUS_A[1] + (SAUS_B[1] - SAUS_A[1]) * f)
        h = SAUS_W * 0.44
        capsule(d, T((c[0] - px * h, c[1] - py * h)), T((c[0] + px * h, c[1] + py * h)),
                SAUS_W * 0.20 * scale, CHAR + (255,))
    art.alpha_composite(Image.composite(layer, blank(), body))  # clip stripes to the sausage
    return art


def tile(size, frac=0.80, radius=0.225, simple=False, bg=True):
    """Full icon: rounded dark tile + art. radius=0 gives a full-bleed square."""
    P = size * SS
    img = Image.new("RGBA", (P, P), (0, 0, 0, 0))
    if bg:
        mask = Image.new("L", (P, P), 0)
        d = ImageDraw.Draw(mask)
        if radius:
            d.rounded_rectangle([0, 0, P - 1, P - 1], radius=radius * P, fill=255)
        else:
            d.rectangle([0, 0, P - 1, P - 1], fill=255)
        img.paste(vgrad((P, P), BG_TOP, BG_BOT).convert("RGBA"), (0, 0), mask)
    img.alpha_composite(draw_art(size, frac if not simple else frac, simple))
    return img.resize((size, size), Image.Resampling.LANCZOS)


def write_ico(path, entries):
    """Hand-built ICO with PNG payloads so each size gets its own artwork."""
    blobs = []
    for size, img in entries:
        buf = BytesIO()
        img.save(buf, format="PNG")
        blobs.append((size, buf.getvalue()))
    out = struct.pack("<HHH", 0, 1, len(blobs))
    offset = 6 + 16 * len(blobs)
    for size, data in blobs:
        out += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    path.write_bytes(out + b"".join(d for _, d in blobs))


def hexc(c):
    return "#%02X%02X%02X" % c


def svg_body():
    """The mark as SVG markup — also pasted into index.html's header logo."""
    f = lambda v: f"{v:.2f}".rstrip("0").rstrip(".")
    ang = math.degrees(math.atan2(SAUS_B[1] - SAUS_A[1], SAUS_B[0] - SAUS_A[0]))
    L = math.hypot(SAUS_B[0] - SAUS_A[0], SAUS_B[1] - SAUS_A[1])
    caps = ' stroke-linecap="round" fill="none"'
    rim = "".join(
        f'<line x1="{f(a[0])}" y1="{f(a[1])}" x2="{f(b[0])}" y2="{f(b[1])}" '
        f'stroke="{hexc(RIM_RGB)}" stroke-width="{f(w + RIM * 2)}"{caps}/>'
        for a, b, w in fork_segments())
    body = "".join(
        f'<line x1="{f(a[0])}" y1="{f(a[1])}" x2="{f(b[0])}" y2="{f(b[1])}" '
        f'stroke="{hexc(CREAM)}" stroke-width="{f(w)}"{caps}/>'
        for a, b, w in fork_segments())
    _, _, px, py = axis_frame()
    stripes = ""
    for i in range(STRIPES):
        t = (i + 1) / (STRIPES + 1)
        c = (SAUS_A[0] + (SAUS_B[0] - SAUS_A[0]) * t, SAUS_A[1] + (SAUS_B[1] - SAUS_A[1]) * t)
        h = SAUS_W * 0.44
        stripes += (f'<line x1="{f(c[0] - px * h)}" y1="{f(c[1] - py * h)}" '
                    f'x2="{f(c[0] + px * h)}" y2="{f(c[1] + py * h)}" '
                    f'stroke="{hexc(CHAR)}" stroke-width="{f(SAUS_W * 0.2)}"{caps}/>')
    saus_rect = (f'<rect x="{f(SAUS_A[0] - SAUS_W / 2)}" y="{f(SAUS_A[1] - SAUS_W / 2)}" '
                 f'width="{f(L + SAUS_W)}" height="{f(SAUS_W)}" rx="{f(SAUS_W / 2)}" '
                 f'transform="rotate({f(ang)} {f(SAUS_A[0])} {f(SAUS_A[1])})"')
    return f'''<defs>
<linearGradient id="glEm" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{hexc(EMBER_TOP)}"/><stop offset="1" stop-color="{hexc(EMBER_BOT)}"/></linearGradient>
<linearGradient id="glSa" gradientUnits="userSpaceOnUse" x1="{f(SAUS_A[0])}" y1="{f(SAUS_A[1])}" x2="{f(SAUS_B[0])}" y2="{f(SAUS_B[1])}"><stop offset="0" stop-color="{hexc(PALE)}"/><stop offset="1" stop-color="{hexc(BROWN)}"/></linearGradient>
<clipPath id="glClip">{saus_rect}/></clipPath>
</defs>
<path d="{FLAME_D}" fill="url(#glEm)"/>
{rim}{body}
<line x1="{f(SAUS_A[0])}" y1="{f(SAUS_A[1])}" x2="{f(SAUS_B[0])}" y2="{f(SAUS_B[1])}" stroke="{hexc(RIM_RGB)}" stroke-width="{f(SAUS_W + RIM * 2)}"{caps}/>
<line x1="{f(SAUS_A[0])}" y1="{f(SAUS_A[1])}" x2="{f(SAUS_B[0])}" y2="{f(SAUS_B[1])}" stroke="url(#glSa)" stroke-width="{f(SAUS_W)}"{caps}/>
<g clip-path="url(#glClip)">{stripes}</g>'''


def svg_file(with_tile):
    """Art fills the 100-box; the tile version insets it to leave a margin."""
    if with_tile:
        head = (f'<linearGradient id="glBg" x1="0" y1="0" x2="0" y2="1">'
                f'<stop offset="0" stop-color="{hexc(BG_TOP)}"/>'
                f'<stop offset="1" stop-color="{hexc(BG_BOT)}"/></linearGradient>')
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
                f'<defs>{head}</defs><rect width="100" height="100" rx="22" fill="url(#glBg)"/>'
                f'<g transform="translate(11 12) scale(0.78)">{svg_body()}</g></svg>\n')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
            f'{svg_body()}</svg>\n')


def og_image():
    W, H = 1200, 630
    img = Image.new("RGB", (W, H))
    img.paste(vgrad((W, H), BG_TOP, BG_BOT), (0, 0))
    logo = tile(300, frac=0.82)
    img.paste(logo, (150, (H - 300) // 2), logo)
    d = ImageDraw.Draw(img)
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    try:
        d.text((500, 250), "Grill ETA", font=ImageFont.truetype(font, 86), fill=CREAM)
        d.text((504, 350), "physics-based cook-time estimator",
               font=ImageFont.truetype(font.replace("-Bold", ""), 32), fill=(154, 140, 126))
    except OSError:
        pass
    img.save(ROOT / "og-image.png", optimize=True)


def main():
    tile(512).save(ROOT / "icon-512.png", optimize=True)
    tile(192).save(ROOT / "icon-192.png", optimize=True)
    tile(180).save(ROOT / "icon-180.png", optimize=True)
    # maskable: full-bleed background, art kept inside the 80% safe circle
    tile(512, frac=0.60, radius=0).save(ROOT / "icon-maskable-512.png", optimize=True)
    write_ico(ROOT / "favicon.ico", [
        (16, tile(16, frac=0.82, radius=0.20, simple=True)),
        (32, tile(32, frac=0.78, radius=0.22, simple=True)),
        (48, tile(48, frac=0.80, radius=0.22)),
        (64, tile(64, frac=0.80, radius=0.22)),
    ])
    (ROOT / "favicon.svg").write_text(svg_file(True))
    (ROOT / "logo.svg").write_text(svg_file(False))
    og_image()
    print("wrote icons, favicon.ico/svg, logo.svg, og-image.png")


if __name__ == "__main__":
    main()
