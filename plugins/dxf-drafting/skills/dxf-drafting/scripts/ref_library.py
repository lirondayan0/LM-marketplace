"""Reference library of the user's HAND-DRAWN reinforcement of XREF sections ('how he details a geometry the engine has no rule for').
  python ref_library.py build REF.dxf ORIG.dxf [OUT.json]   # ORIG = the file whose XREF blocks hold the outlines (REF's blocks may be empty); default OUT = assets/ref_library.json
  python ref_library.py list                                # what the library holds
API: match(doc, ins) -> (entry, info) | (None, why);  place(doc, entry, info) -> new entities
A section = beam outline (S-BEAM-1 lines, signature = their vertex set relative to the outline's lower-left corner) + slab lines + his entities (local coords = world - that corner).
Matching = same beam outline (identity or mirrored); the slab-side entities follow the slab top (dy) and the mirror. Rule 9 of the skill: copy the nearest taught example, never invent bars.
Source: 3841-CON_claude_.dxf (user 2026-10-25: 'a resource whenever you are unsure how to detail the reinforcement for a geometry'); level 01 sections 46-50 (+ every other detailed level-01 section)."""
import os, sys, re, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'recipes'))
LIB = os.path.join(HERE, '..', 'assets', 'ref_library.json')
KEEP = ('57_HATAH_ZIUN', '56_HATAH_ZET', '2000_DOT_HELP_LINE', '54_HATAH_TEXT', '57_HATAH_DASHED', '51_HATAH_DASHED')   # his reinforcement layers (voids 10_PLADA_HATAH come from xref_cores)
BEAM = ('S-BEAM-1', 'S-280-M_STRUCT_FRAME-1'); FLOOR = ('A-FLOR-1', 'A-230-M_FLOOR-1')
MARGIN = (115.0, 115.0, 80.0, 70.0)      # window around the outline: left, right, below, above
TOL = 1.0
TAG = 'DXFSKILL_TEMPLATE'      # XDATA on every copied entity: the post passes (xref_extend_bars / dots, xref_text_clear) leave his hand-drawn example as it is


def tagged(e): return e.has_xdata(TAG)


def _lay(e): return e.dxf.layer.split('$0$')[-1]


def outline(block, layers=BEAM):
    """beam outline vertices of an XREF section block, in block coordinates"""
    pts = []
    for s in block:
        if s.dxftype() == 'LINE' and _lay(s) in layers: pts += [(s.dxf.start.x, s.dxf.start.y), (s.dxf.end.x, s.dxf.end.y)]
    return pts


def slab_info(block, ax=0.0, ay=0.0):
    """slab top / soffit / centre-x of a section block relative to the outline corner (ax, ay)"""
    ys, xs, mcut = [], [], False
    for s in block:
        if s.dxftype() != 'LINE': continue
        if _lay(s) in FLOOR and abs(s.dxf.start.y - s.dxf.end.y) < 0.5: ys.append(s.dxf.start.y); xs += [s.dxf.start.x, s.dxf.end.x]
        if _lay(s) == 'A-FLOR-MCUT': mcut = True
    return dict(top=max(ys) - ay if ys else None, soffit=min(ys) - ay if ys else None, x=(sum(xs) / len(xs)) - ax if xs else None, hollow=mcut)


def _uniq(pts):
    out = []
    for p in pts:
        if not any(abs(p[0] - q[0]) < TOL and abs(p[1] - q[1]) < TOL for q in out): out.append(p)
    return out


def norm(pts):
    a = (min(p[0] for p in pts), min(p[1] for p in pts))
    return a, _uniq([(p[0] - a[0], p[1] - a[1]) for p in pts])


def same_set(A, B):
    return len(A) == len(B) and all(any(abs(p[0] - q[0]) < TOL and abs(p[1] - q[1]) < TOL for q in B) for p in A)


def mirror_pts(V):
    w = max(p[0] for p in V); return [(w - p[0], p[1]) for p in V]


def ser(e, ax, ay):
    """one of his entities -> plain dict in local coordinates (None = not carried)"""
    t = e.dxftype(); d = dict(t=t, layer=e.dxf.layer, color=e.dxf.get('color', 256))
    if t == 'LINE': d.update(p=[(e.dxf.start.x - ax, e.dxf.start.y - ay), (e.dxf.end.x - ax, e.dxf.end.y - ay)])
    elif t == 'LWPOLYLINE': d.update(p=[(p[0] - ax, p[1] - ay, p[2], p[3], p[4]) for p in e.get_points('xyseb')], closed=bool(e.closed), cw=e.dxf.get('const_width', 0.0))
    elif t == 'TEXT': d.update(text=e.dxf.text, p=[(e.dxf.insert.x - ax, e.dxf.insert.y - ay)], h=e.dxf.height, style=e.dxf.style, rot=e.dxf.get('rotation', 0.0), wf=e.dxf.get('width', 1.0), ha=e.dxf.get('halign', 0), va=e.dxf.get('valign', 0), al=((e.dxf.align_point.x - ax, e.dxf.align_point.y - ay) if e.dxf.hasattr('align_point') else None))
    elif t == 'INSERT' and e.dxf.name == 'dot barzel': d.update(name=e.dxf.name, p=[(e.dxf.insert.x - ax, e.dxf.insert.y - ay)], sx=e.dxf.get('xscale', 1.0), sy=e.dxf.get('yscale', 1.0), rot=e.dxf.get('rotation', 0.0))
    else: return None
    return d


def build(ref_path, orig_path, out=LIB):
    import ezdxf
    from ezdxf import bbox as BB
    R = ezdxf.readfile(ref_path); O = ezdxf.readfile(orig_path)
    cand = []
    for e in R.modelspace():
        if e.dxf.layer not in KEEP or e.dxftype() not in ('LINE', 'LWPOLYLINE', 'TEXT', 'INSERT'): continue
        if e.dxftype() == 'INSERT' and e.dxf.name != 'dot barzel': continue
        try:
            if e.dxftype() in ('TEXT', 'INSERT'): x, y = e.dxf.insert.x, e.dxf.insert.y
            else:
                b = BB.extents([e]); x, y = b.center.x, b.center.y
            cand.append((x, y, e))
        except Exception: pass
    lib = []
    for ins in O.modelspace().query('INSERT'):
        m = re.search(r'Sec[^0-9]*(\d+)-(\d+)$', ins.dxf.name)
        if not m or m.group(1) != m.group(2): continue
        blk = O.blocks.get(ins.dxf.name); pts = outline(blk)
        if len(pts) < 6: continue
        (ax, ay), V = norm(pts); ix, iy = ins.dxf.insert.x, ins.dxf.insert.y; wx, wy = ix + ax, iy + ay
        x0, y0 = wx - MARGIN[0], wy - MARGIN[2]; x1, y1 = wx + max(p[0] for p in V) + MARGIN[1], wy + max(p[1] for p in V) + MARGIN[3]
        ents = [ser(e, wx, wy) for x, y, e in cand if x0 <= x <= x1 and y0 <= y <= y1]; ents = [d for d in ents if d]
        if sum(1 for d in ents if d['layer'] == '57_HATAH_ZIUN') < 3: continue          # not detailed by him
        lib.append(dict(src=f'{os.path.basename(ref_path)} Sec {m.group(1)} @({round(ix)},{round(iy)})', n=int(m.group(1)), outline=V, slab=slab_info(blk, ax, ay), ents=ents))
    json.dump(dict(source=os.path.basename(ref_path), sections=lib), open(out, 'w'))
    print(f'{len(lib)} detailed sections -> {out}')
    return lib


_CACHE = {}


def load(path=LIB):
    if path not in _CACHE: _CACHE[path] = json.load(open(path)) if os.path.exists(path) else dict(sections=[])
    return _CACHE[path]['sections']


def match(doc, ins, path=LIB):
    """-> (entry, info) with info = dict(anchor=(world x, y of the target outline corner), mirror, dy, width, ...) | (None, reason)"""
    blk = doc.blocks.get(ins.dxf.name); pts = outline(blk)
    if len(pts) < 6: return None, 'no beam outline to compare with the reference library'
    (ax, ay), V = norm(pts); sl = slab_info(blk, ax, ay); best = None
    for ent in load(path):
        for mir in (False, True):
            W = mirror_pts(ent['outline']) if mir else [tuple(p) for p in ent['outline']]
            if not same_set(V, W): continue
            ts = ent['slab']; dy = sl['top'] - ts['top'] if (sl['top'] is not None and ts['top'] is not None) else 0.0
            dso = abs((sl['soffit'] - ts['soffit']) if (sl['soffit'] is not None and ts['soffit'] is not None) else 0.0)
            score = abs(dy) + dso + (0 if sl['hollow'] == ts['hollow'] else 30) + (3 if mir else 0)
            if best is None or score < best[0]: best = (score, ent, mir, dy)
    if not best: return None, 'no reference section with this beam outline (assets/ref_library.json)'
    _, ent, mir, dy = best; ix, iy = ins.dxf.insert.x, ins.dxf.insert.y
    info = dict(anchor=(ix + ax, iy + ay), mirror=mir, dy=dy, width=max(p[0] for p in V), hollow=sl['hollow'], ref_hollow=ent['slab']['hollow'],
                note=f"copied from the hand-drawn reference {ent['src']}" + (' (mirrored)' if mir else '') + (f', slab part moved {dy:+.1f}' if abs(dy) > 0.05 else ''))
    return ent, info


def _slab_right(ent):
    sx = ent['slab'].get('x'); w = max(p[0] for p in ent['outline']); return sx is None or sx > w / 2


def place(doc, ent, info):
    """copy his entities to the target; returns the new entities. Entities whose centre lies on the slab side of the beam follow the slab top (dy)."""
    msp = doc.modelspace()
    if TAG not in doc.appids: doc.appids.add(TAG)
    ax, ay = info['anchor']; mir = info['mirror']; w = info['width']; dy = info['dy']; new = []
    right = _slab_right(ent); thr_r = max(p[0] for p in ent['outline']) - 0.5; thr_l = min(p[0] for p in ent['outline']) + 0.5
    fx = (lambda x: w - x) if mir else (lambda x: x)
    for d in ent['ents']:
        pts = [(q[0], q[1]) for q in d['p']]; cx = sum(q[0] for q in pts) / len(pts)      # template coordinates (before the mirror)
        sh = dy if ((cx >= thr_r) if right else (cx <= thr_l)) else 0.0
        T = lambda x, y, sh=sh: (ax + fx(x), ay + y + sh)
        at = dict(layer=d['layer'])
        if d.get('color', 256) != 256: at['color'] = d['color']
        t = d['t']
        if t == 'LINE': e = msp.add_line((*T(*d['p'][0]), 0), (*T(*d['p'][1]), 0), dxfattribs=at)
        elif t == 'LWPOLYLINE':
            pp = []
            for x, y, s_, e_, b in d['p']:
                X, Y = T(x, y); pp.append((X, Y, s_, e_, -b if mir else b))
            e = msp.add_lwpolyline(pp, format='xyseb', close=d['closed'], dxfattribs=at)
            if d.get('cw'): e.dxf.const_width = d['cw']
        elif t == 'TEXT':
            X, Y = T(*d['p'][0]); at.update(height=d['h'], style=d['style'], rotation=d['rot'], width=d['wf'])
            e = msp.add_text(d['text'], dxfattribs=at); e.dxf.insert = (X, Y, 0)
            if d.get('ha') or d.get('va'):
                e.dxf.halign = d['ha']; e.dxf.valign = d['va']
                if d.get('al'): e.dxf.align_point = (*T(*d['al']), 0)
        else:
            e = msp.add_blockref(d['name'], T(*d['p'][0]), dxfattribs=dict(at, xscale=d['sx'], yscale=d['sy'], rotation=d['rot']))
        e.set_xdata(TAG, [(1000, 'template')]); new.append(e)
    return new


def main():
    a = sys.argv[1:]
    if a and a[0] == 'build': build(a[1], a[2], a[3] if len(a) > 3 else LIB)
    elif a and a[0] == 'list':
        for s in load(): print(s['n'], s['src'], 'hollow' if s['slab']['hollow'] else 'solid', 'ents', len(s['ents']), 'outline', len(s['outline']))
    else: print(__doc__)


if __name__ == '__main__': main()
