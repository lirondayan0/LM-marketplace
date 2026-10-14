"""Per-layer inventory of one plan (box-limited) + floor test: what each layer holds, sizes, decoded texts, which labelled items lie inside the slab edge.

  python plan_layers.py FILE --box X0 Y0 X1 Y1 [-o OUT.txt] [--contour-layer 9_KONTUR]
Writes UTF-8 (the Windows console garbles Hebrew: read OUT.txt, do not print). One ezdxf load (~60 s on a 8 MB plan): run it ONCE per session.
Sections: layers (types, counts, most common closed-rect sizes, texts), CONTOUR (the main closed 9_KONTUR polygon in the box = slab edge; floor is inside),
INSIDE (every 4_TEXT label and every 40xN pier: inside / outside the contour), CLAUDE (user markup layer 'claude': bbox + colour).
"""
import sys, os, argparse, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ezdxf
from matplotlib.path import Path
from dxflib import text_of
from layer_roles import guess_all

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--box', nargs=4, type=float, required=True)
    ap.add_argument('-o', default='plan_layers.txt'); ap.add_argument('--contour-layer', default='9_KONTUR'); a = ap.parse_args()
    x0, y0, x1, y1 = a.box; inb = lambda x, y: x0 <= x <= x1 and y0 <= y <= y1
    doc = ezdxf.readfile(a.file); msp = doc.modelspace()
    L = collections.defaultdict(lambda: collections.defaultdict(list)); labels = []; piers = []; contour = None; claude = []; items = []
    for e in msp:
        t, ly = e.dxftype(), e.dxf.layer
        try:
            if t == 'LWPOLYLINE':
                p = list(e.get_points('xyb'))
                if not any(inb(q[0], q[1]) for q in p): continue
                xs = [q[0] for q in p]; ys = [q[1] for q in p]; w, h = round(max(xs) - min(xs)), round(max(ys) - min(ys))
                if ly.lower() == 'claude':
                    claude.append((e.dxf.handle, e.dxf.color, e.dxf.get('true_color'), (round(min(xs)), round(min(ys)), round(max(xs)), round(max(ys))), len(p))); continue
                L[ly]['PL'].append((w, h, e.closed)); items.append((ly, 'PL', ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2), (w, h) if e.closed else None))
                if ly == a.contour_layer and e.closed and w > 5000: contour = [(round(float(q[0])), round(float(q[1]))) for q in p]
                if ly == '82_KIR_OLE' and sorted((w, h)) in ([40, 150], [40, 200]): piers.append(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2))
            elif t == 'LINE' and inb(e.dxf.start.x, e.dxf.start.y): L[ly]['LINE'].append(1); items.append((ly, 'LINE', (e.dxf.start.x, e.dxf.start.y), None))
            elif t == 'TEXT' and inb(e.dxf.insert.x, e.dxf.insert.y):
                raw, dt = text_of(doc, e)     # decoded only for Hebrew styles AND when it has lowercase letters (keeps '200/100', '30/65', 'D=20+5')
                if not any('a' <= c <= 'z' for c in raw): dt = raw
                L[ly]['TEXT'].append(dt); items.append((ly, 'TEXT', (e.dxf.insert.x, e.dxf.insert.y), dt))
                if ly == '4_TEXT': labels.append((dt, round(e.dxf.insert.x), round(e.dxf.insert.y)))
            elif t == 'INSERT' and inb(e.dxf.insert.x, e.dxf.insert.y): L[ly]['INSERT'].append(e.dxf.name); items.append((ly, 'INSERT', (e.dxf.insert.x, e.dxf.insert.y), e.dxf.name))
            elif t == 'DIMENSION' and inb(e.dxf.defpoint.x, e.dxf.defpoint.y): L[ly]['DIM'].append(1); items.append((ly, 'DIMENSION', (e.dxf.defpoint.x, e.dxf.defpoint.y), None))
            elif t == 'LEADER' and inb(*list(e.vertices)[0][:2]): L[ly]['LEADER'].append(1); items.append((ly, 'LEADER', tuple(list(e.vertices)[0][:2]), None))
            elif t == 'HATCH': L[ly]['HATCH(whole file)'].append(1)
        except Exception: pass
    with open(a.o, 'w', encoding='utf-8') as o:
        for ly, g in sorted(L.items()):
            o.write(f'== {ly}  (ACI {doc.layers.get(ly).color}, {doc.layers.get(ly).dxf.linetype})\n')
            for k, v in g.items():
                if k == 'TEXT': o.write(f'  TEXT {len(v)}: ' + ' | '.join(sorted(set(v)))[:600] + '\n')
                elif k == 'PL':
                    c = collections.Counter((w, h) for w, h, cl in v); o.write(f'  PL {len(v)} closed={sum(1 for z in v if z[2])} common={c.most_common(6)}\n')
                elif k == 'INSERT': o.write(f'  INSERT {len(v)} {collections.Counter(v).most_common(4)}\n')
                else: o.write(f'  {k} {len(v)}\n')
        o.write('\n== ROLE GUESSES (name tokens + linetype + content + neighbours; unknown = ask the user):\n')
        for ly, role, conf, ev in guess_all(doc, items): o.write(f'  [{conf}] {ly}: {role}\n      ' + '; '.join(ev) + '\n')
        o.write(f'\n== CONTOUR ({a.contour_layer}, closed, w>5000): {contour}\n')
        if contour:
            pa = Path(contour); o.write('== INSIDE the slab edge (floor exists):\n')
            for txt, x, y in sorted(labels): o.write(f'  {"IN " if pa.contains_point((x, y)) else "OUT"} {txt!r} @({x},{y})\n')
            n_in = sum(1 for p in piers if pa.contains_point(p)); o.write(f'  piers 40x150/40x200: {n_in} inside, {len(piers) - n_in} outside\n')
        o.write('\n== CLAUDE layer (user markup; ignore every other layer):\n')
        for c in claude: o.write(f'  {c}\n')
    print('written', a.o)
if __name__ == '__main__': main()
