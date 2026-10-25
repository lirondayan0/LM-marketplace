"""Text width for AutoCAD-86 'shapes 1.0' SHX fonts (MIRYL, sivan_m, hebtxt) - the real glyph advance.

    from shx_width import text_width
    text_width('MIRYL', 'c/g/ kph ,fbh,', height=6, width_factor=0.876)

Fonts are looked up in FONT_DIRS (AutoCAD temp copies / user dirs); cached advances per font. Arcs use their chord
(fractional arcs are ignored), good to a few percent - enough to size a leader shelf.
"""
import glob, math, os, struct

FONT_DIRS = [os.path.expanduser('~/.claude/skills/dxf-drafting/fonts'), 'C:/Windows/Fonts',
             'C:/Program Files/Autodesk/*/Fonts', '/tmp/cop*.tmp/Fonts']
FILES = {'MIRYL': 'MIRYL.shx', 'SIVAN': 'sivan_m.shx', 'HEBREW_NEW': 'hebtxt 500.shx', 'HEBTXT': 'hebtxt 500.shx'}      # HEBTXT = the template's style for $ notes before sivan_text.py turns them into HEBREW_NEW: SAME font; the KeyError made the hoop-note centring fall back to the left (netivot 2026-10-24)
_DIR8 = [(1, 0), (1, .5), (1, 1), (.5, 1), (0, 1), (-.5, 1), (-1, 1), (-1, .5), (-1, 0), (-1, -.5), (-1, -1), (-.5, -1),
         (0, -1), (.5, -1), (1, -1), (1, -.5)]
_cache = {}


def _find(fname):
    for d in FONT_DIRS:
        for p in glob.glob(os.path.join(d, fname)):
            return p
    raise FileNotFoundError(fname)


def _signed(b):
    return b - 256 if b > 127 else b


def _load(style):
    if style in _cache:
        return _cache[style]
    data = open(_find(FILES[style]), 'rb').read()
    i = data.index(b'\x1a') + 1
    first, last, cnt = struct.unpack_from('<HHH', data, i)
    i += 6
    idx = [struct.unpack_from('<HH', data, i + 4 * k) for k in range(cnt)]
    p = i + 4 * cnt
    shapes = {}
    for num, ln in idx:
        body = data[p:p + ln]
        p += ln
        n = body.index(b'\0')
        shapes[num] = body[n + 1:]
    above = shapes[0][0] or 1
    adv = {c: _advance(shapes[c], shapes) / above for c in shapes if c}
    _cache[style] = adv
    return adv


def _advance(code, shapes, depth=0):
    x = y = 0.0
    sc = 1.0
    stack = []
    vert = False
    i = 0
    while i < len(code):
        c = code[i]; i += 1
        if c == 0: break
        if c in (1, 2): continue
        if c == 3: sc /= code[i]; i += 1; continue
        if c == 4: sc *= code[i]; i += 1; continue
        if c == 5: stack.append((x, y)); continue
        if c == 6:
            if stack: x, y = stack.pop()
            continue
        if c == 7:
            s = shapes.get(code[i]); i += 1
            if s and depth < 4:
                dx, dy = _sub(s, shapes, depth + 1)
                x += dx * sc; y += dy * sc
            continue
        if c == 8:
            x += _signed(code[i]) * sc; y += _signed(code[i + 1]) * sc; i += 2; continue
        if c == 9:
            while i + 1 < len(code) and (code[i] or code[i + 1]):
                x += _signed(code[i]) * sc; y += _signed(code[i + 1]) * sc; i += 2
            i += 2; continue
        if c == 0xA:
            r = code[i] * sc; b = _signed(code[i + 1]); i += 2
            so = (b >> 4) & 7; span = (b & 7) or 8; cw = b < 0
            a0 = math.radians(so * 45); a1 = a0 + math.radians(span * 45) * (-1 if cw else 1)
            x += r * (math.cos(a1) - math.cos(a0)); continue
        if c == 0xB: i += 5; continue
        if c == 0xC:
            x += _signed(code[i]) * sc; y += _signed(code[i + 1]) * sc; i += 3; continue
        if c == 0xD:
            while i + 1 < len(code) and (code[i] or code[i + 1]):
                x += _signed(code[i]) * sc; y += _signed(code[i + 1]) * sc; i += 3
            i += 2; continue
        if c == 0xE: vert = True; continue
        if c in (0xF,): continue
        ln = c >> 4; d = c & 15
        dx, dy = _DIR8[d]
        x += dx * ln * sc; y += dy * ln * sc
    return x


def _sub(code, shapes, depth):
    return _advance(code, shapes, depth), 0.0


def text_width(style, text, height, width_factor=1.0):
    """Advance width of `text` in drawing units (SHX style `style`, text height, style width factor x text width)."""
    adv = _load(style)
    return sum(adv.get(ord(ch), adv.get(ord('?'), 0.5)) for ch in text) * height * width_factor


def text_extent(style, text, ins_x, height, width_factor=1.0, mirrored=False):
    """(a, b) = x range of the VISIBLE glyphs (leading / trailing spaces dropped) of a one-line SHX TEXT with insert x `ins_x`.
    MIRYL runs right-to-left (negative advance); a mirrored TEXT (text_generation_flag 2) runs the other way, so the office's notes all extend leftwards from the insert."""
    adv = _load(style)
    a = [adv.get(ord(c), adv.get(ord('?'), 0.5)) * height * width_factor for c in text]
    total = sum(a)
    d = (1 if total >= 0 else -1) * (-1 if mirrored else 1)
    lead = sum(abs(v) for v in a[:len(text) - len(text.lstrip())])
    trail = sum(abs(v) for v in a[len(text.rstrip()):])
    s, e = ins_x + d * lead, ins_x + d * (abs(total) - trail)
    return (min(s, e), max(s, e))
