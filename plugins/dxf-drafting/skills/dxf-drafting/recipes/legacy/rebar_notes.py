"""LEGACY (superseded by ../ledge_beam.py; hard-coded coordinates of the older example set)."""
"""Add rebar LEADERS + NOTES to sections already drawn by rebar_section.py, following the finished examples
(yellow box of חתכים.dxf, studied 2026-10-04: 1-1, 3-3, 4-4 ...).

Usage:  python rebar_notes.py FILE N-N [N-N ...] [--dry]      (run rebar_section.py first)
Backs up FILE to FILE.bak, adds to the ORIGINAL, reloads and audits.

Leader anatomy (layer 56_HATAH_ZET, text on 54_HATAH_TEXT, HEBTXT h=6, Sivan for 'לפי תכנית'):
  bar note   : elbow point E; one 2-point polyline E->dot per target dot (a "fork"); for 4Ø12 the two lower dots use
               one V polyline [dotL, E, dotR]; an underline LINE from E (length 21.9, 31.9 for 2Ø8@20) away from the
               section; text at underline start + (1.5..2.0, +1.8)  (left-side notes: text at underline's left end + 2)
  slab note  : polyline [(dot.x -+59.9, yh), (dot.x -+7.2, yh), dot]; dot = slab dot nearest the wall; yh = dot.y+28 (top)
               / dot.y-19.9 (bottom) (T-type sections: top +14.1); text 'ב.ע. לפי תכנית' / 'ב.ת. לפי תכנית' (Sivan) at the
               far-from-dot end... Hebrew SHX runs right-to-left, so the insert is at the RIGHT end of the line.
  stirrup    : under the detail: ' &8@15' at (x0-10.8, y0-11.1), 'L=n' at (x0-6.1, y0-21.2); n = 2*(14+h)+14
               (fits 1-1, 5-5, *4-*4 of the examples; 4-4 of the examples says 136 for h=54, probably stale)
Bar set (the office standard in all examples): 2Ø12 corners, 2Ø8@20 side pair, 4Ø12 at the slab junction, stirrup Ø8@15.
Sections whose geometry does not fit the set (3-3 raised edge, 4-4 7-cm lip, 5-5 lip) get only the notes that map
unambiguously onto dots; the rest are listed in the report and NOT invented.
"""
import os, sys, shutil, argparse
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'scripts'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dxflib import *
import rebar_section as rs

ZET, TXT = '56_HATAH_ZET', '54_HATAH_TEXT'
H = 6.0

def pick(dots, x, y, tol=0.6):
    c = [d for d in dots if abs(d[0]-x) < tol and abs(d[1]-y) < tol]
    if not c: raise SystemExit(f'no dot near ({x:.1f},{y:.1f})')
    return min(c, key=lambda d: abs(d[0]-x)+abs(d[1]-y))

def col_levels(dots, x, y0, y1, tol=0.6):
    return sorted(d[1] for d in dots if abs(d[0]-x) < tol and y0 < d[1] < y1)

class Notes:
    PITCH, UL, XL, XR = 12.0, 31.9, 7.0, 9.0       # min row pitch, common underline length, elbow gaps (left / right of the outer dot column)
    def __init__(self): self.poly, self.lines, self.texts, self.report, self.forks = [], [], [], [], []
    def fork(self, text, side, elbow, upper, vee=(), ul=None, tdx=None):
        self.forks.append(dict(text=text, side=side, y=elbow[1], upper=list(upper), vee=list(vee)))   # elbow x is computed in finish()
    def finish(self):
        """Neat layout: one elbow column per side, equal underlines, rows >= PITCH apart, ordered top to bottom."""
        for side in ('L', 'R'):
            rows = sorted((f for f in self.forks if f['side'] == side), key=lambda f: -f['y'])
            if not rows: continue
            xs = [p[0] for f in rows for p in f['upper'] + f['vee']]
            ex = max(xs) + self.XR if side == 'R' else min(xs) - self.XL
            for i in range(1, len(rows)):
                rows[i]['y'] = min(rows[i]['y'], rows[i-1]['y'] - self.PITCH)
            for f in rows:
                e = (ex, f['y'])
                for d in f['upper']: self.poly.append([e, d])
                if f['vee']: self.poly.append([f['vee'][0], e, f['vee'][1]])
                sgn = 1 if side == 'R' else -1
                self.lines.append((e, (ex + sgn*self.UL, f['y'])))
                self.texts.append((f['text'], 'HEBTXT', (ex + 1.5 if side == 'R' else ex - self.UL + 2.0, f['y'] + 1.8)))
    def slab(self, heb, dot, yh, toward):          # toward = -1 slab runs to the left of the dot, +1 to the right
        far, near = dot[0] + toward*59.9, dot[0] + toward*7.2
        self.poly.append([(far, yh), (near, yh), dot])
        self.texts.append((encode(heb), 'Sivan', (max(far, near) - 1.0, yh + 1.8)))

def stirrup_label(n, plan):
    x0, y0, x1, y1 = plan['rects'][1]
    h = y1 - y0
    n.texts.append((' &8@15', 'HEBTXT', (x0 - 10.8, y0 - 11.1)))
    n.texts.append((f'L={round(2*((x1-x0)+h)+14)}', 'HEBTXT', (x0 - 6.1, y0 - 21.2)))

def build_notes(name, plan):
    D, n = plan['dots'], Notes()
    TOP, BOT = 'ב.ע. לפי תכנית', 'ב.ת. לפי תכנית'
    if name == '2-2':                                    # T-section, 76-76 / example 1-1 layout
        xl, xr, yt, yj, yb = 40635.2, 40646.2, 47953.0, 47937.0, 47888.0
        ym = min(col_levels(D, xl, yb+1, yj-1), key=lambda y: abs(y-(yj-(yj-yb)/4)))
        n.fork('4&12', 'L', (xl-6.1, yt+25.3), [pick(D, xl, yt), pick(D, xr, yt)], [pick(D, xl, yj), pick(D, xr, yj)])
        n.fork('2&8@20', 'R', (xr+13.8, ym-10.8), [pick(D, xl, ym), pick(D, xr, ym)], ul=31.9, tdx=1.0)
        n.fork('2&12', 'L', (xl-6.1, yb-13.0), [pick(D, xl, yb), pick(D, xr, yb)])
        for lvl, yh, t in ((yt, yt+14.1, TOP), (yj, yj-19.9, BOT)):
            dot = max((d for d in D if abs(d[1]-lvl) < .3 and d[0] < xl-5), key=lambda d: d[0]); n.slab(t, dot, yh, -1)
        stirrup_label(n, plan)
    elif name == '1-1':                                  # L: wall on the left, slab to the right; notes on the outer (left) side
        xl, xr, yt, yj, yb = 41127.8, 41138.8, 47950.9, 47934.9, 47885.9
        ym = min(col_levels(D, xl, yb+1, yj-1), key=lambda y: abs(y-(yj-(yj-yb)/4)))
        n.fork('4&12', 'L', (xl-9.9, yt+8.0), [pick(D, xl, yt), pick(D, xr, yt)], [pick(D, xl, yj), pick(D, xr, yj)])
        n.fork('2&8@20', 'L', (xl-13.8, ym-10.8), [pick(D, xl, ym), pick(D, xr, ym)], ul=31.9)
        n.fork('2&12', 'L', (xl-9.9, yb-13.0), [pick(D, xl, yb), pick(D, xr, yb)])
        for lvl, yh, t in ((yt, yt+28.0, TOP), (yj, yj-19.9, BOT)):
            dot = min((d for d in D if abs(d[1]-lvl) < .3 and d[0] > xr+5), key=lambda d: d[0]); n.slab(t, dot, yh, +1)
        stirrup_label(n, plan)
    elif name == '4-4':                                  # slab left, wall right (7-cm lip below the slab)
        xl, xr, yt, ys, yj = 39643.4, 39654.4, 47947.2, 47890.2, 47876.2
        mids = col_levels(D, xl, ys+1, yt-1); ym = mids[len(mids)//2]
        n.fork('2&12', 'R', (xr+13.0, yt+9.7), [pick(D, xl, yt), pick(D, xr, yt)])
        n.fork('2&8@20', 'R', (xr+13.8, ym+6.5), [pick(D, xl, ym), pick(D, xr, ym)], ul=31.9, tdx=1.0)
        for lvl, yh, t in ((ys, ys+28.0, TOP), (yj, yj-19.9, BOT)):
            dot = max((d for d in D if abs(d[1]-lvl) < .3 and d[0] < xr-5 and abs(d[0]-xl) > 1), key=lambda d: d[0]); n.slab(t, dot, yh, -1)
        stirrup_label(n, plan)
        n.report.append('4-4: no 4Ø12 / lower 2Ø8@20 / bottom 2Ø12 - below the slab the wall is only a 7 cm lip with one bar line, not the 2-column layout of the examples')
    elif name == '3-3':
        xc = 40175.0
        for lvl, yh, t in ((47927.9, 47927.9+28.0, TOP), (47913.9, 47913.9-19.9, BOT)):
            dot = max((d for d in D if abs(d[1]-lvl) < .3 and d[0] < xc-5), key=lambda d: d[0]); n.slab(t, dot, yh, -1)
        stirrup_label(n, plan)
        n.report.append('3-3: no 2Ø12 / 4Ø12 / 2Ø8@20 - the 20x10 raised edge has 3 bar levels, the examples have no such shape; tell me which bars go where')
    elif name == '5-5':
        xc = 39174.7
        for lvl, yh, t in ((47905.6, 47905.6+28.0, TOP), (47891.6, 47891.6-19.9, BOT)):
            dot = max((d for d in D if abs(d[1]-lvl) < .3 and d[0] < xc-5), key=lambda d: d[0]); n.slab(t, dot, yh, -1)
        n.report.append('5-5: no bar notes and no stirrup label - 7 cm lip (single bar line, no stirrup)')
    n.finish()
    return n

def apply(doc, n):
    msp = doc.modelspace()
    for pts in n.poly: msp.add_lwpolyline(pts, dxfattribs={'layer': ZET})
    for a, b in n.lines: msp.add_line((*a, 0), (*b, 0), dxfattribs={'layer': ZET})
    for text, style, at in n.texts:
        att = {'layer': TXT, 'style': style, 'insert': (*at, 0)}
        if style == 'Sivan': att['text_generation_flag'] = 2     # slab notes in the examples are mirrored (gen flag 2): text runs LEFT from the insert
        msp.add_text(text, height=H, dxfattribs=att)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('sections', nargs='+'); ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()
    doc = ezdxf.readfile(a.file)
    notes = {}
    for s in a.sections:
        plan = rs.build(doc, s, rs.SECTIONS[s]); notes[s] = build_notes(s, plan)
        n = notes[s]; print(f'{s}: leaders {len(n.poly)}, underlines {len(n.lines)}, texts {[t[0] for t in n.texts]}')
        for r in n.report: print('   NOT PLACED:', r)
    if a.dry: sys.exit()
    shutil.copy2(a.file, a.file + '.bak')
    for n in notes.values(): apply(doc, n)
    doc.saveas(a.file); d2 = ezdxf.readfile(a.file); print('reloaded OK, audit errors:', len(d2.audit().errors))
