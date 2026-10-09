"""Read the section cuts of a structural plan: every numbered cut mark pair, its view direction, and the beam / slab labels found next to it.
  python plan_cuts.py FILE [--profile NAME] [--box X0 Y0 X1 Y1] [--radius 150]
Output (one line per cut, then one suggestion per section number): where the cut is, which way it looks (N/S/E/W), the beam label `b/h` and slab label `D=a+b` nearest to the
cut line, so a drawing can be started without typing sizes: `ledge_beam.py ... --beam b h --slab a --topping b --sides ...`. WHICH SIDE the slab is on is not in the labels:
the view direction + the plan decide (left/right of the beam as seen in the view) - check it on the plan or ask.
Cut mark = block named in the profile (`cut_mark.block`, attribute = section number); the view direction is the block's local +y rotated by the insert rotation
(rot 270 -> east, 180 -> south, 0 -> north, 90 -> west); mirrored scales (negative x) do not change it. Verified on the Level -1 mezzanine of ramla.dxf (user's description of 1-1)."""
import argparse, collections, math, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dxflib import *

NAMES = {(0, 1): 'N', (0, -1): 'S', (1, 0): 'E', (-1, 0): 'W'}

def view_dir(e):
    th = math.radians(e.dxf.rotation); ys = 1 if e.dxf.yscale >= 0 else -1
    v = (-math.sin(th) * ys, math.cos(th) * ys)
    return v, NAMES.get((round(v[0]), round(v[1])), f'{math.degrees(math.atan2(v[1], v[0])):.0f}deg')

def cuts(doc, block, box=None):
    marks = []
    for e in doc.modelspace().query('INSERT'):
        if e.dxf.name != block: continue
        p = e.dxf.insert
        if box and not (box[0] < p.x < box[2] and box[1] < p.y < box[3]): continue
        num = next((a.dxf.text for a in e.attribs), '?'); v, nm = view_dir(e)
        marks.append(dict(num=num, p=(p.x, p.y), v=v, dir=nm))
    out, used = [], set()
    for i, m in enumerate(marks):                        # pair each mark with the nearest same-number, same-direction mark
        if i in used: continue
        best = None
        for j, n in enumerate(marks):
            if j <= i or j in used or n['num'] != m['num'] or n['v'][0] * m['v'][0] + n['v'][1] * m['v'][1] < 0.9: continue
            d = math.dist(m['p'], n['p'])
            if d < 600 and (best is None or d < best[0]): best = (d, j)
        if best: used.update({i, best[1]}); n = marks[best[1]]; out.append(dict(num=m['num'], a=m['p'], b=n['p'], dir=m['dir'], mid=((m['p'][0] + n['p'][0]) / 2, (m['p'][1] + n['p'][1]) / 2), length=best[0]))
    return out

def labels(doc, pat):
    rx = re.compile(pat); out = []
    for e in doc.modelspace().query('TEXT'):
        if rx.match(e.dxf.text.strip()): out.append((e.dxf.text.strip(), e.dxf.insert.x, e.dxf.insert.y))
    return out

def span_axes(doc, slab_lbls, layer, r=80):
    """Panel span direction next to each slab label: the double-arrow LEADERs the plan draws beside `D=a+b` (horizontal = E-W, vertical = N-S). Returns {label position: 'EW'|'NS'}."""
    out = {}
    leaders = [[(q[0], q[1]) for q in e.vertices] for e in doc.modelspace().query('LEADER') if e.dxf.layer == layer]
    for t, x, y in slab_lbls:
        best = None
        for v in leaders:
            if len(v) < 2: continue
            c = ((v[0][0] + v[-1][0]) / 2, (v[0][1] + v[-1][1]) / 2); d = math.dist(c, (x, y))
            if d < r and (best is None or d < best[0]): best = (d, 'EW' if abs(v[-1][0] - v[0][0]) >= abs(v[-1][1] - v[0][1]) else 'NS')
        if best: out[(x, y)] = best[1]
    return out

def panel_relation(view, span):
    """Cut plane vs panel span. View direction parallel to the span -> the cut crosses the panels: CORES show as circles, panels run past this beam (cast edge beam, no bearing).
    View direction perpendicular to the span -> the plane contains the span: panels are seen LENGTHWISE and bear on this beam (ledge beam). (User, 2026-10-06: 1-1 vs 3-3/4-4.)"""
    if not span: return '?'
    return 'CORES (panels run past the beam; cast edge beam, no bearing)' if (view in 'EW') == (span == 'EW') else 'LENGTHWISE (panels bear on the beam; ledge beam)'

def nearest(lbls, p, r):
    c = sorted(((math.dist((x, y), p), t) for t, x, y in lbls if math.dist((x, y), p) <= r))
    return [(t, round(d)) for d, t in c[:3]]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--profile', default='israeli-structural')
    ap.add_argument('--box', nargs=4, type=float); ap.add_argument('--radius', type=float, default=150)
    a = ap.parse_args(); prof = load_profile(a.profile); plan = prof.get('plan', {})
    doc = ezdxf.readfile(a.file)
    cs = cuts(doc, prof.get('cut_mark', {}).get('block', 'hat'), a.box)
    beams = labels(doc, plan.get('beam_label', r'^\d{2,3}/\d{2,3}$')); slabs = labels(doc, plan.get('slab_label', r'^D=\d+(\+\d+)?$'))
    spans = span_axes(doc, slabs, plan.get('span_leader_layer', '0_LUHADIM_HEZ'))
    pos = {(x, y): t for t, x, y in slabs}
    sug = collections.defaultdict(collections.Counter)
    for c in sorted(cs, key=lambda c: (c['num'], c['mid'])):
        b = nearest(beams, c['mid'], max(a.radius, c['length'])); s = nearest(slabs, c['mid'], 450)
        near = min(slabs, key=lambda t: math.dist((t[1], t[2]), c['mid']), default=None); span = spans.get((near[1], near[2])) if near else None
        rel = panel_relation(c['dir'], span)
        print(f"section {c['num']}: mid ({c['mid'][0]:.0f},{c['mid'][1]:.0f}) length {c['length']:.0f} looks {c['dir']} | beam {b[:1]} | slab label {s[:1]} | panels span {span or '?'} -> {rel}")
        sug[c['num']][(b[0][0] if b else '?', s[0][0] if s else '?', c['dir'], rel.split()[0])] += 1
    print('\nsuggestions (beam, slab label, view) per section number:')
    for n in sorted(sug): print(f'  {n}-{n}:', dict(sug[n]))

if __name__ == '__main__': main()
