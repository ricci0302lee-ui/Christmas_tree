# Christmas Tree
# Port of the ASCII Christmas tree animation from the original web version.
# Inspired by the structure of black_hole.py (JIN2).
#
#   pip install pygame numpy
#   python xmas_tree.py
#
# Put xmastree.mp3 next to this script for looping background music.
# Space pause, R restart, S screenshot, Esc quit

import math
import sys
import time
from pathlib import Path

import numpy as np
import pygame

# ---------------------------------------------------------------------------
# Constants (matched to the original JS)
# ---------------------------------------------------------------------------
TAU = math.pi * 2
DUR = 18.0          # slightly faster overall animation
FPS = 30

# Character cell size & logical canvas (only the tree area)
CW, CH = 9, 13
W, H = 1080, 1300          # window content size (no code editor)
COLS = W // CW             # 120
ROWS = H // CH             # 100
SH = 1250                  # original tree render height

# Camera / projection (from original)
F = 1560.0
D = 4.6
CX = 540.0
CY = 700.0
LOOKY = 1.0
TILT = 0.14

Y0, Y1 = 0.32, 1.88
RAMP = " .,:;=+*%#@"
N_RAMP = len(RAMP)

# Timing of progressive reveal (slightly faster overall, star appears earlier)
T0, T1 = 0.6, 14.5
S_T0, S_T1 = 14.8, 17.8

# Light direction
L = np.array([-0.5, 0.6, 0.62], dtype=np.float64)
L /= np.linalg.norm(L)

MONO = "consolas,menlo,dejavusansmono,couriernew,monospace"
BG = (5, 7, 13)
DIM = (140, 148, 175)
PINK = (255, 90, 122)
GOLD = (255, 210, 90)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


# Deterministic RNG matching the original style (LCG)
class RNG:
    def __init__(self, seed=1225):
        self.s = seed & 0xFFFFFFFF

    def __call__(self):
        self.s = (self.s * 1664525 + 1013904223) & 0xFFFFFFFF
        return self.s / 4294967296.0


R = RNG(1225)


def env(f):
    return 0.04 + 0.62 * (1.0 - clamp(f)) ** 1.0


# ---------------------------------------------------------------------------
# Geometry generation (one-time, matches original point counts & distribution)
# ---------------------------------------------------------------------------
def generate_scene():
    R = RNG(1225)
    OBJ = {k: [] for k in ("ground", "trunk", "needles", "snow", "garland", "balls", "gifts")}
    TIPS = []

    def add(o, x, y, z, nx, ny, nz, c, glow=0.0):
        OBJ[o].append([x, y, z, nx, ny, nz, c[0], c[1], c[2], glow])

    # ground
    for _ in range(7000):
        a = R() * TAU
        d = math.sqrt(R()) * 1.05
        add("ground", d * math.cos(a), 0.0, d * math.sin(a), 0, 1, 0, [170, 178, 205])

    # trunk
    for _ in range(1500):
        h = R() * 0.6
        a = R() * TAU
        b = 0.75 + 0.25 * math.sin(h * 90 + a * 3)
        add("trunk", 0.085 * math.cos(a), h, 0.085 * math.sin(a),
            math.cos(a), 0, math.sin(a), [107 * b, 66 * b, 36 * b])

    # needles
    for t in range(22):
        f = t / 22
        y = Y0 + f * (Y1 - Y0)
        L = env(f)
        nb = math.floor(7 + 11 * (1 - f))
        for b in range(nb):
            a = (b / nb) * TAU + t * 0.618 * TAU + R() * 0.3
            per = math.floor(150 * L + 40)
            for _ in range(per):
                s = R() ** 0.6
                spread = (0.035 + 0.11 * s) * L
                aa = a + (R() - 0.5) * spread * 3 / (s * L + 0.05)
                r = s * L + (R() - 0.5) * spread
                yy = y - 0.22 * s * s * L + (R() - 0.5) * spread * 0.8
                nx, nz = math.cos(aa), math.sin(aa)
                up = 0.35 + 0.65 * s
                tone = 0.75 + R() * 0.35
                col = [(45 + R() * 35) * tone, (150 + R() * 75) * tone, (70 + R() * 35) * tone]
                p = [r * nx, yy, r * nz, nx * 0.8, up, nz * 0.8, col]
                add("needles", *p[:6], col)
                # fewer tip candidates so snow stays sparse
                if s > 0.78 and R() < 0.045:
                    TIPS.append(p)

    # snow on tips — keep only a thinner, more even subset
    # sort by height then angle-ish so we can thin uniformly
    TIPS.sort(key=lambda p: (round(p[1], 2), math.atan2(p[2], p[0])))
    keep = max(1, len(TIPS) // 3)          # about 1/3 of the candidates
    step = max(1, len(TIPS) // keep)
    for i in range(0, len(TIPS), step):
        p = TIPS[i]
        add("snow", p[0], p[1] + 0.012, p[2], p[3] * 0.3, 1.0, p[5] * 0.3, [235, 240, 255])

    # gold garland
    u = 0.0
    while u < 1.0:
        y = 1.75 - u * 1.4 - 0.05 * abs(math.sin(u * 40))
        f = (y - Y0) / (Y1 - Y0)
        a = u * 3.6 * TAU
        r = env(f) * 0.92 + 0.02
        for _ in range(2):
            rr = r + (R() - 0.5) * 0.02
            add("garland", rr * math.cos(a), y + (R() - 0.5) * 0.015, rr * math.sin(a),
                math.cos(a), 0.3, math.sin(a), [255, 200, 70], 0.35)
        u += 0.0004

    # ornaments — even spiral so red / gold / silver don't clump
    BALLC = [[220, 30, 40], [255, 195, 60], [205, 210, 225]]
    N_BALLS = 48
    GOLDEN = 0.6180339887 * TAU
    for i in range(N_BALLS):
        # uniform height band + golden-angle azimuth
        f = 0.06 + (i + 0.5) / N_BALLS * 0.82
        y = Y0 + f * (Y1 - Y0) - 0.04
        a = i * GOLDEN + 0.7
        r = env(f) * 0.90
        br = 0.055 + (i % 5) * 0.005
        cx, cz = r * math.cos(a), r * math.sin(a)
        c = BALLC[i % 3]
        for _ in range(420):
            u = R() * 2 - 1
            v = R() * TAU
            s = math.sqrt(max(0.0, 1 - u * u))
            nx, ny, nz = s * math.cos(v), u, s * math.sin(v)
            add("balls", cx + nx * br, y + ny * br, cz + nz * br, nx, ny, nz, c, 0.15)

    # lights
    LIGHTS = []
    for _ in range(170):
        f = R() * 0.95
        y = Y0 + f * (Y1 - Y0) - 0.03
        a = R() * TAU
        r = env(f) * 0.95 + 0.01
        col = [255, 225, 140] if R() < 0.75 else [255, 250, 230]
        LIGHTS.append([r * math.cos(a), y, r * math.sin(a), col[0], col[1], col[2], R() * TAU])

    # gifts
    GIFTC = [[200, 30, 40], [40, 80, 200], [230, 180, 50], [235, 235, 240], [40, 150, 70], [200, 30, 40]]
    RIB = [[255, 215, 90], [255, 255, 255], [200, 30, 40], [200, 30, 40], [255, 215, 90], [40, 150, 70]]
    for i, c in enumerate(GIFTC):
        a = i / 6 * TAU + 0.3
        d = 0.5 + (i % 2) * 0.2
        cx, cz = d * math.cos(a), d * math.sin(a)
        sx = 0.2 + (i % 3) * 0.05
        sy = 0.16 + (i % 2) * 0.08
        sz = 0.2
        for _ in range(2600):
            f = math.floor(R() * 5)
            u, v = R() - 0.5, R() - 0.5
            if f < 2:
                x = 0.5 if f else -0.5
                y = u + 0.5
                z = v
                nx, ny, nz = (1 if f else -1), 0, 0
            elif f == 2:
                y = 1.0
                x, z = u, v
                nx, ny, nz = 0, 1, 0
            else:
                z = 0.5 if (f - 3) else -0.5
                x, y = u, v + 0.5
                nx, ny, nz = 0, 0, (1 if (f - 3) else -1)
            rib = abs(x) < 0.08 or abs(z) < 0.08
            col = RIB[i] if rib else c
            add("gifts", cx + x * sx, y * sy, cz + z * sz, nx, ny, nz, col)

    # sort for painter's algorithm / progressive reveal
    for k in OBJ:
        OBJ[k].sort(key=lambda q: q[1] + (R() - 0.5) * 0.03)
    OBJ["ground"].sort(key=lambda q: math.hypot(q[0], q[2]))

    # convert to numpy for speed
    for k in OBJ:
        if OBJ[k]:
            OBJ[k] = np.array(OBJ[k], dtype=np.float32)
        else:
            OBJ[k] = np.zeros((0, 10), dtype=np.float32)
    LIGHTS = np.array(LIGHTS, dtype=np.float32)
    return OBJ, LIGHTS


# Section progress (approximate original lengths for reveal timing)
SECTION_ORDER = ["ground", "trunk", "needles", "snow", "garland", "balls", "lights", "star", "gifts", "santa", "run"]
# Relative weights: star moved earlier (right after lights) and given more weight so it appears sooner
SECTION_WEIGHTS = {
    "ground": 240, "trunk": 110, "needles": 420, "snow": 95,
    "garland": 180, "balls": 120, "lights": 100, "star": 50,
    "gifts": 130, "santa": 130, "run": 55,
}
TOTAL_W = sum(SECTION_WEIGHTS.values())
_cum = 0
SECTION_RANGE = {}
for name in SECTION_ORDER:
    w = SECTION_WEIGHTS[name]
    SECTION_RANGE[name] = (_cum / TOTAL_W, (_cum + w) / TOTAL_W)
    _cum += w


def progress(name, t):
    """0..1 how much of this section is revealed at time t."""
    if t < T0:
        return 0.0
    u = clamp((t - T0) / (T1 - T0))
    a, b = SECTION_RANGE[name]
    if u <= a:
        return 0.0
    if u >= b:
        return 1.0
    return (u - a) / (b - a)


# ---------------------------------------------------------------------------
# Projection & shading
# ---------------------------------------------------------------------------
def project(x, y, z, ang):
    ca, sa = math.cos(ang), math.sin(ang)
    X = x * ca + z * sa
    Z = -x * sa + z * ca
    Y = y - LOOKY
    ct, st = math.cos(TILT), math.sin(TILT)
    Y2 = Y * ct - Z * st
    Z2 = Y * st + Z * ct
    s = F / (D - Z2)
    return CX + X * s, CY - Y2 * s, Z2


def rot_n(nx, ny, nz, ang):
    ca, sa = math.cos(ang), math.sin(ang)
    X = nx * ca + nz * sa
    Z = -nx * sa + nz * ca
    ct, st = math.cos(TILT), math.sin(TILT)
    return X, ny * ct - Z * st, ny * st + Z * ct


def shade(n):
    m = math.hypot(n[0], n[1], n[2]) or 1.0
    d = (n[0] * L[0] + n[1] * L[1] + n[2] * L[2]) / m
    return 0.28 + 0.72 * max(0.0, d)


# ---------------------------------------------------------------------------
# Santa (simplified character drawing, timed like original)
# ---------------------------------------------------------------------------
def draw_santa_chars(surf, font, t, cell_w=CW, cell_h=CH):
    """Draw Santa + reindeer as ASCII characters flying across."""
    u = (t - S_T0) / (S_T1 - S_T0)
    if u < 0 or u > 1.15:
        return
    # flight path
    x0 = W + 40 - u * (W + 900)
    y0 = 190 - math.sin(u * math.pi) * 90 - u * 40

    if u > 1.0:
        return

    # Approximate Santa+reindeer silhouette with characters
    # (original paints detailed pixels then samples; we use a compact glyph pattern)
    phase = t * 7
    base_x = int(x0)
    base_y = int(y0)

    # simple reindeer + sleigh pattern (right to left)
    # Reindeer bodies
    deer = [
        (0, 0, "o", (154, 102, 52)),
        (8, -4, "o", (168, 113, 60)),
        (16, 0, "o", (154, 102, 52)),
        (24, -3, "o", (168, 113, 60)),
        (32, 0, "o", (154, 102, 52)),
        (40, -2, "o", (168, 113, 60)),
    ]
    # legs
    for i, (dx, dy, ch, col) in enumerate(deer):
        bounce = math.sin(phase + i * 0.9) * 3
        px = base_x + dx * 8
        py = base_y + 40 + bounce
        for leg in (-6, 4):
            k = math.sin(phase * 2 + i)
            lx = px + leg
            ly = py + 18 + k * 6
            img = font.render("|", True, (94, 58, 30))
            surf.blit(img, (int(lx), int(ly)))
        img = font.render(ch, True, col)
        surf.blit(img, (int(px), int(py)))
        # antlers
        img = font.render("Y", True, (232, 207, 168))
        surf.blit(img, (int(px - 2), int(py - 14)))

    # Rudolph nose (character only, no circular glow)
    nx = base_x - 10
    ny = base_y + 28 + math.sin(phase) * 3
    img = font.render("@", True, (255, 40, 50))
    surf.blit(img, (int(nx), int(ny)))

    # sleigh + Santa
    sx = base_x + 280
    sy = base_y + 50
    # sleigh body
    for i, ch in enumerate("====="):
        img = font.render(ch, True, (200, 30, 40))
        surf.blit(img, (int(sx + i * 9), int(sy + 20)))
    img = font.render("___", True, (255, 210, 70))
    surf.blit(img, (int(sx + 5), int(sy + 30)))
    # Santa
    img = font.render("O", True, (246, 210, 173))
    surf.blit(img, (int(sx + 20), int(sy - 10)))
    img = font.render("#", True, (224, 42, 52))
    surf.blit(img, (int(sx + 18), int(sy + 2)))
    img = font.render("^", True, (255, 255, 255))
    surf.blit(img, (int(sx + 20), int(sy - 18)))
    # sack
    img = font.render("o", True, (138, 90, 44))
    surf.blit(img, (int(sx + 55), int(sy)))
    img = font.render("#", True, (210, 48, 64))
    surf.blit(img, (int(sx + 50), int(sy - 8)))


# ---------------------------------------------------------------------------
# Main renderer
# ---------------------------------------------------------------------------
class TreeCanvas:
    def __init__(self, font):
        self.font = font
        # snowman-style flake font (slightly larger so * + . read clearly)
        self.snow_font = pygame.font.SysFont(MONO, 16)
        self.OBJ, self.LIGHTS = generate_scene()
        self.N = COLS * ROWS
        # background snow — same style as snowman.py snowfall():
        #   FLAKES[:, 0] x-seed, [:, 1] y-seed, [:, 2] depth/speed, [:, 3] phase
        rng = np.random.default_rng(5)
        self.FLAKES = rng.random((420, 4)).astype(np.float32)
        # pre-render character glyphs for speed
        self.glyphs = {}
        for ch in RAMP + "*o#.@Y|=_^+":
            g = font.render(ch, True, (255, 255, 255))
            self.glyphs[ch] = g

    def reset(self):
        pass  # geometry is static; only time changes (snow keeps its own clock)

    def render(self, t):
        surf = pygame.Surface((W, H))
        surf.fill(BG)

        # soft ground snow band at the bottom (height similar to the white ellipse under the tree)
        # fades outward into the background
        ground_top = 980
        ground_bottom = H
        for y in range(ground_top, ground_bottom, CH):
            # vertical fade: strongest near the ellipse, softer toward the very bottom edge
            fy = (y - ground_top) / max(1, ground_bottom - ground_top)
            # peak brightness roughly in the middle of the band, then soft falloff
            edge = 1.0 - abs(fy - 0.35) * 1.6
            edge = clamp(edge)
            for x in range(0, W, CW):
                # horizontal soft falloff toward left/right edges of the screen
                fx = abs(x - W * 0.5) / (W * 0.55)
                fall = clamp(1.0 - fx * fx)
                a = 0.12 + 0.55 * edge * fall
                if a < 0.08:
                    continue
                # slight density variation
                if ((x // CW) + (y // CH)) % 3 == 0:
                    ch = "."
                elif ((x // CW) + (y // CH)) % 5 == 0:
                    ch = ":"
                else:
                    ch = ","
                col = (200, 210, 235)
                img = self.font.render(ch, True, col)
                img.set_alpha(int(a * 255))
                surf.blit(img, (x, y))

        # z-buffer & buffers
        zb = np.full(self.N, -1e9, dtype=np.float32)
        lum = np.zeros(self.N, dtype=np.float32)
        cr = np.zeros(self.N, dtype=np.float32)
        cg = np.zeros(self.N, dtype=np.float32)
        cb = np.zeros(self.N, dtype=np.float32)
        kind = np.zeros(self.N, dtype=np.uint8)  # 0 empty, 1 solid, 3 light, 5 ground

        ang = math.radians((t * 17 + 300) % 360)

        def plot(sx, sy, z, l, col, k):
            col_i = int(sx // CW)
            row_i = int(sy // CH)
            if col_i < 0 or col_i >= COLS or row_i < 0 or row_i >= ROWS:
                return
            i = row_i * COLS + col_i
            if z <= zb[i]:
                return
            zb[i] = z
            lum[i] = l
            cr[i], cg[i], cb[i] = col
            kind[i] = k

        # progressive parts
        parts = ["ground", "trunk", "needles", "snow", "garland", "balls", "gifts"]
        for name in parts:
            arr = self.OBJ[name]
            m = int(len(arr) * progress(name, t))
            for i in range(m):
                q = arr[i]
                sx, sy, z = project(q[0], q[1], q[2], ang)
                nn = rot_n(q[3], q[4], q[5], ang)
                l = shade(nn)
                if name == "garland":
                    l = min(1.0, l + 0.25 + 0.2 * math.sin(t * 4 + i * 0.05))
                elif name == "balls":
                    sp = max(0.0, nn[0] * L[0] + nn[1] * L[1] + nn[2] * L[2])
                    l = 0.25 + 0.6 * sp + (0.6 if sp > 0.93 else 0.0)
                k = 5 if name == "ground" else 1
                plot(sx, sy, z, l, (q[6], q[7], q[8]), k)

        # lights
        lit = int(170 * progress("lights", t))
        for i in range(lit):
            x, y, z, r, g, b, p = self.LIGHTS[i]
            sx, sy, zz = project(x, y, z, ang)
            tw = 0.55 + 0.45 * math.sin(t * 5 + p)
            plot(sx, sy, zz + 0.02, tw, (r, g, b), 3)

        # draw characters
        letters = 0
        for i in range(self.N):
            if kind[i] == 0:
                continue
            x = (i % COLS) * CW
            y = (i // COLS) * CH
            l = lum[i]
            k = kind[i]
            if k == 3:
                ch = "@" if l > 0.7 else "o"
                b = 0.6 + 0.6 * l
            elif k == 5:
                idx = 3 + int(l * 5)
                ch = RAMP[min(N_RAMP - 1, idx)]
                b = 0.65 + 0.45 * l   # brighter ground snow under the tree
            else:
                idx = 2 + int(l * 9)
                ch = RAMP[min(N_RAMP - 1, idx)]
                b = 0.5 + 0.8 * l
            r = min(255, int(cr[i] * b))
            g = min(255, int(cg[i] * b))
            bb = min(255, int(cb[i] * b))
            img = self.font.render(ch, True, (r, g, bb))
            surf.blit(img, (x, y))
            letters += 1

        # star
        ps = progress("star", t)
        if ps > 0:
            sx, sy, _ = project(0, 1.98, 0, ang)
            s = ps * (1 + 0.06 * math.sin(t * 4))
            # rays (no circular glow)

            for r in range(8):
                a = r / 8 * TAU + t * 0.3
                length = (70 if r % 2 else 120) * s
                d = 40
                while d < length:
                    xx = sx + math.cos(a) * d
                    yy = sy + math.sin(a) * d
                    alpha = 0.8 * (1 - d / length)
                    ch = "." if r % 2 else ":"
                    img = self.font.render(ch, True, (255, 215, 110))
                    img.set_alpha(int(alpha * 255))
                    surf.blit(img, (int(xx - 4), int(yy - 6)))
                    d += 11
            # star body
            rO, rI = 58 * s, 24 * s
            pts = []
            for k in range(10):
                aa = -math.pi / 2 + k * math.pi / 5
                rr = rI if k % 2 else rO
                pts.append((sx + rr * math.cos(aa), sy + rr * math.sin(aa)))
            # fill with # characters
            minx = int(sx - rO)
            maxx = int(sx + rO)
            miny = int(sy - rO)
            maxy = int(sy + rO)
            for yy in range(miny, maxy, CH):
                for xx in range(minx, maxx, CW):
                    # point-in-star test (ray casting)
                    gx, gy = xx + CW / 2, yy + CH / 2
                    inside = False
                    j = 9
                    for i in range(10):
                        xi, yi = pts[i]
                        xj, yj = pts[j]
                        if ((yi > gy) != (yj > gy)) and (gx < (xj - xi) * (gy - yi) / (yj - yi + 1e-9) + xi):
                            inside = not inside
                        j = i
                    if inside:
                        col = (255, 243, 176) if math.hypot(gx - sx, gy - sy) < rI else (255, 204, 58)
                        img = self.font.render("#", True, col)
                        surf.blit(img, (xx, yy))

        # Santa
        if progress("santa", t) > 0 or t >= S_T0:
            draw_santa_chars(surf, self.font, t)

        # falling snow — port of snowman.py snowfall() into screen space
        # resets with the tree loop (uses animation time t); soft fade-in at the start of each cycle
        snow_on = 0.90 * smooth(t / 1.4)
        f = self.FLAKES
        # constant base speed; mild per-flake variation from depth seed (fixed, not time-varying)
        fall_spd = 0.32 + 0.12 * f[:, 2]
        sx = (f[:, 0] * 5 - 2.5 + 0.12 * np.sin(t * 0.8 + f[:, 3] * TAU))
        sy = (f[:, 1] * 3.2 - t * fall_spd) % 3.2
        # depth seed → brightness (nearer flakes brighter), same as snowman
        depth = 0.3 + 0.7 * f[:, 2]
        # project world coords onto the full letter grid
        # sy decreases over time (fall); flip so smaller sy → larger row → downward on screen
        cols_f = (sx / 2.5 * 0.5 + 0.5) * COLS
        rows_f = (1.0 - sy / 3.2) * ROWS
        for i in range(len(f)):
            c = int(cols_f[i]) % COLS
            r = int(rows_f[i]) % ROWS
            gx = c * CW
            gy = r * CH
            fs = float(depth[i])
            # same glyph rule as snowman: * / + / .
            if fs > 0.75:
                ch = "*"
            elif fs > 0.5:
                ch = "+"
            else:
                ch = "."
            a = (0.35 + 0.65 * fs) * snow_on
            img = self.snow_font.render(ch, True, (206, 222, 255))
            img.set_alpha(int(a * 255))
            surf.blit(img, (gx, gy))

        # HUD
        small = pygame.font.SysFont(MONO, 18)
        t_txt = small.render(f"t {t:05.2f}s", True, PINK)
        surf.blit(t_txt, (W - 24 - t_txt.get_width(), 20))
        sign = small.render("@ricci32lee @grok · Christmas 2026", True, (160, 168, 200))
        surf.blit(sign, (24, H - 90))
        temp = -6.0 if int(t) % 2 == 0 else -7.0
        info1 = small.render(f"temp {temp:+05.1f}°C", True, DIM)
        surf.blit(info1, (24, H - 62))
        info2 = small.render(f"lights  {lit}", True, DIM)
        surf.blit(info2, (280, H - 62))
        info3 = small.render(f"letters {letters:,}", True, DIM)
        surf.blit(info3, (24, H - 34))

        return surf, letters, lit


# ---------------------------------------------------------------------------
# Window / main loop (mirrors black_hole.py style)
# ---------------------------------------------------------------------------
TITLE = "Christmas Tree"
SIGN = "@ricci32lee @grok · Christmas 2026"


def window_size():
    info = pygame.display.Info()
    k = 1.0
    if info.current_w > 0 and info.current_h > 0:
        k = min(1.0, 0.90 * info.current_h / H, 0.95 * info.current_w / W)
    return int(W * k), int(H * k)


def main():
    pygame.init()
    pygame.mixer.init()

    # loop background music if xmastree.mp3 is next to this script
    music_path = Path(__file__).with_name("xmastree.mp3")
    if music_path.exists():
        try:
            pygame.mixer.music.load(str(music_path))
            pygame.mixer.music.play(-1)  # -1 = loop forever
            print(f"playing {music_path.name} (loop)")
        except pygame.error as e:
            print(f"could not play music: {e}")
    else:
        print(f"music file not found: {music_path} (place xmastree.mp3 next to the script)")

    size = window_size()
    window = pygame.display.set_mode(size)
    pygame.display.set_caption(TITLE)
    screen = pygame.Surface((W, H))
    font = pygame.font.SysFont(MONO, 12)
    canvas = TreeCanvas(font)
    clock = pygame.time.Clock()
    t = 0.0
    paused = False

    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                pygame.mixer.music.stop()
                pygame.quit()
                return
            if e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                paused = not paused
                if paused:
                    pygame.mixer.music.pause()
                else:
                    pygame.mixer.music.unpause()
            if e.type == pygame.KEYDOWN and e.key == pygame.K_r:
                t = 0.0
                canvas.reset()
            if e.type == pygame.KEYDOWN and e.key == pygame.K_s:
                out = Path(__file__).with_name(f"xmas_tree_{int(time.time())}.png")
                pygame.image.save(screen, str(out))
                print(f"saved {out}")

        dt = clock.tick(FPS) / 1000.0
        if not paused:
            t += min(dt, 1 / 15)
            if t > DUR:
                t = 0.0
                canvas.reset()

        art, letters, lit = canvas.render(t)
        screen.blit(art, (0, 0))

        if size == (W, H):
            window.blit(screen, (0, 0))
        else:
            window.blit(pygame.transform.smoothscale(screen, size), (0, 0))
        pygame.display.flip()


if __name__ == "__main__":
    sys.exit(main() or 0)
