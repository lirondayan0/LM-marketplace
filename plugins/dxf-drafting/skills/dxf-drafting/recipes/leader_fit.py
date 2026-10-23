#!/usr/bin/env python
"""Tidy the leaders of section sheets (user 2026-10-21: leaders point to the relevant reinforcing bars, length adjusted to the text, neat and orderly; example = section 1).

For every leader of a section cell (shelf = horizontal line on 56_HATAH_ZET, note = TEXT on 54_HATAH_TEXT standing on it):
  1. SHELF = TEXT: the shelf covers the visible text (real SHX advances, scripts/shx_width.py) with MARGIN each side. The free end (the one with no fork) moves; if the text
     hangs over the joint (the end the forks start at) the TEXT is moved outward instead so it stands on the shelf (MIRYL runs right-to-left, SIVAN-mirrored too).
  2. ORPHAN = a shelf + note with no fork at all (the S-mark fix of 8-8 had deleted the beam-bar forks): forks are drawn to the beam's top pair / bottom pair of bar dots
     (the two columns of the lowest dot row; 57_HATAH_ZIUN dots < 4 wide).
  Notes the user sized on purpose are kept: 'X$XX' (SS, shelf = 2 x text, conventions 5e). Only a text that overhangs its shelf, hangs over the joint, or a shelf more than EXCESS too long is changed; the user's own lengths (+-3) stay.

    python leader_fit.py FILE --box X Y W H [--box ...] [--dry]
Snapshot first (.bak-leaderfit-HHMMSS), in place. Importable: fit_box(doc, box, dry) -> list of change strings.
"""
import argparse, math, os, shutil, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import ezdxf
from shx_width import text_extent

MARGIN, EXCESS, KEEP = 1.4, 6.0, ('X$XX',)
SNAP_NOTES = ('$12@20', '2$8@20', '4$12', '2$12', 'X$XX', '2$8', 'c/g/ kph ,fw', 'c/,/ kph ,fw', 'c/g/ kph ,fbh,', 'c/,/ kph ,fbh,')
SNAP_R = 6.0     # slab-bar notes too (user's 7-7 / 8-8 corrections); each fork gets its OWN dot     # bar-callout notes: fork tips sit ON a bar dot centre (user 2026-10-21, 2-2)
STYLES = ('MIRYL', 'SIVAN', 'HEBREW_NEW')


def _segs(e):
    if e.dxftype() == 'LINE': return [((e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y))]
    if e.dxftype() == 'LWPOLYLINE':
        v = [(p[0], p[1]) for p in e.get_points()]
        return list(zip(v, v[1:]))
    return []


def _near(p, q): return math.hypot(p[0] - q[0], p[1] - q[1]) < 0.7


def _set_end(e, old, new):
    """Move the vertex `old` of shelf entity e to `new`."""
    if e.dxftype() == 'LINE':
        for k in ('start', 'end'):
            p = e.dxf.get(k)
            if _near((p.x, p.y), old): e.dxf.set(k, (new[0], new[1], 0))
    else:
        pts = list(e.get_points('xyseb'))
        pts = [(new[0], new[1], s, en, b) if _near((x, y), old) else (x, y, s, en, b) for x, y, s, en, b in pts]
        e.set_points(pts, format='xyseb')


def fit_box(doc, box, dry=False):
    msp = doc.modelspace(); x0, y0, w, h = box; out = []
    inb = lambda x, y: x0 <= x <= x0 + w and y0 <= y <= y0 + h
    st = {s.dxf.name: s for s in doc.styles}
    leads, texts = [], []
    for e in msp:
        t = e.dxftype()
        if e.dxf.layer == '56_HATAH_ZET' and t in ('LINE', 'LWPOLYLINE'):
            s = _segs(e)
            if s and inb(*s[0][0]): leads.append(e)
        elif e.dxf.layer == '54_HATAH_TEXT' and t == 'TEXT' and e.dxf.style in STYLES and '%%U' not in e.dxf.text and inb(e.dxf.insert.x, e.dxf.insert.y):
            texts.append(e)
    allseg = [(e, s) for e in leads for s in _segs(e)]
    shelves = [(e, s) for e, s in allseg if abs(s[0][1] - s[1][1]) < 0.01 and abs(s[0][0] - s[1][0]) > 10]
    dots = []
    for e in msp.query('LWPOLYLINE'):
        if e.dxf.layer == '57_HATAH_ZIUN' and len(e) <= 3:
            P = [(p[0], p[1]) for p in e.get_points()]
            xs = [p[0] for p in P]; ys = [p[1] for p in P]
            if inb(P[0][0], P[0][1]) and max(xs) - min(xs) < 4 and max(ys) - min(ys) < 4: dots.append(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2))
    for ins in msp.query('INSERT'):                                          # bar dots inside associative arrays (bar_arrays.py)
        if ins.dxf.layer == '57_HATAH_ZIUN' and ins.dxf.name.startswith('*U') and inb(ins.dxf.insert.x, ins.dxf.insert.y):
            stack = list(ins.virtual_entities())
            while stack:
                v = stack.pop()
                if v.dxftype() == 'INSERT': stack += list(v.virtual_entities())
                elif v.dxftype() == 'LWPOLYLINE' and len(v) == 2:
                    P = [(p[0], p[1]) for p in v.get_points()]
                    if abs(P[0][1] - P[1][1]) < 1e-6 and abs(abs(P[0][0] - P[1][0]) - 1) < 1e-4: dots.append(((P[0][0] + P[1][0]) / 2, P[0][1]))
    for t in texts:
        if t.dxf.text.strip() in KEEP: continue
        sty = t.dxf.style; wf = t.dxf.get('width', st[sty].dxf.width); mir = bool(t.dxf.get('text_generation_flag', 0) & 2)
        a, b = text_extent(sty, t.dxf.text, t.dxf.insert.x, t.dxf.height, wf, mir)
        best = None
        for e, s in shelves:
            lo, hi = sorted((s[0][0], s[1][0])); dy = t.dxf.insert.y - s[0][1]
            if -1 <= dy <= 8 and min(b, hi + 12) - max(a, lo - 12) > 0.5 * (b - a):
                if best is None or abs(dy - 1.5) < best[0]: best = (abs(dy - 1.5), e, s)
        if best is None: continue
        _, e, s = best; y = s[0][1]
        nb = lambda p: any(_near(p, q) for e2, s2 in allseg if not (e2 is e and s2 == s) for q in s2)
        ja, jb = nb(s[0]), nb(s[1])
        name = repr(t.dxf.text.strip())
        if not ja and not jb:                                              # orphan: forks to the beam's bar dots
            if len(dots) < 4: out.append(f'{name}: no fork and no dot columns found - left'); continue
            ymin = min(d[1] for d in dots); cols = sorted({round(d[0], 1) for d in dots if abs(d[1] - ymin) < 0.5})
            if len(cols) != 2: out.append(f'{name}: orphan, bar columns unclear {cols} - left'); continue
            top = y > (ymin + max(d[1] for d in dots)) / 2
            yb = max(d[1] for d in dots if round(d[0], 1) in cols) if top else ymin
            ctr = sum(cols) / 2; J = s[0] if abs(s[0][0] - ctr) < abs(s[1][0] - ctr) else s[1]
            out.append(f'{name}: orphan -> forks to the {"top" if top else "bottom"} pair at y={yb - y0:.1f}')
            if not dry:
                for cx_ in cols: msp.add_line((J[0], J[1]), (cx_, yb), dxfattribs={'layer': '56_HATAH_ZET'})
            ja, jb = _near(s[0], J), _near(s[1], J)
        if ja == jb: out.append(f'{name}: both ends joined - left'); continue
        if t.dxf.text.strip() in SNAP_NOTES and dots:                         # fork tips land on the dot centre, not 1-5 cm beside it
            Jp = s[0] if ja else s[1]; taken = []
            for e2, s2 in allseg:
                if e2 is e or e2.dxftype() != 'LINE': continue
                for k, (p1, p2) in ((0, s2), (1, s2[::-1])):
                    if _near(p1, Jp):
                        cand = sorted(dots, key=lambda d: math.hypot(d[0] - p2[0], d[1] - p2[1]))
                        q = next((c for c in cand if not any(_near(c, tk) for tk in taken)), None)
                        if q is None: continue
                        dd = math.hypot(q[0] - p2[0], q[1] - p2[1]); taken.append(q)
                        if 0.2 < dd <= SNAP_R:
                            out.append(f'{name}: fork tip {dd:.1f} off its dot -> on the dot centre')
                            if not dry: e2.dxf.set('end' if k == 0 else 'start', (q[0], q[1], 0))
        J, F = (s[0], s[1]) if ja else (s[1], s[0]); sg = 1 if F[0] > J[0] else -1
        dx = 0.0
        if sg > 0 and a < J[0] - 3: dx = (J[0] + MARGIN) - a                # text hangs over the joint -> move the text outward
        if sg < 0 and b > J[0] + 3: dx = (J[0] - MARGIN) - b
        a2, b2 = a + dx, b + dx
        newF = (b2 + MARGIN) if sg > 0 else (a2 - MARGIN)
        over = (F[0] - a2) if sg < 0 else (b2 - F[0])                       # text beyond the free end (>0) / spare shelf (<0)
        if dx == 0 and -over - MARGIN <= EXCESS and over <= 0.3: continue   # the user's own lengths stay unless the text overhangs or the shelf is way too long
        out.append(f'{name}: shelf {abs(F[0] - J[0]):.1f} -> {abs(newF - J[0]):.1f}' + (f', text moved {dx:+.1f}' if dx else ''))
        if not dry:
            _set_end(e, F, (newF, F[1]))
            if dx: t.dxf.insert = (t.dxf.insert.x + dx, t.dxf.insert.y, 0)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file'); ap.add_argument('--box', nargs=4, type=float, action='append', required=True); ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()
    doc = ezdxf.readfile(a.file)
    for b in a.box:
        print(tuple(b), *fit_box(doc, tuple(b), a.dry), sep='\n  ')
    if not a.dry:
        shutil.copy2(a.file, f'{a.file}.bak-leaderfit-{time.strftime("%H%M%S")}'); doc.saveas(a.file)


if __name__ == '__main__':
    main()
