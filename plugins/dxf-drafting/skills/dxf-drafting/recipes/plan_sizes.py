"""Recipe: FIELD-ENGINEER SIZE PASS (user 2026-10-11: 'detailed measurements for every element, imagine you are a field engineer').
  python plan_sizes.py FILE --box X0 X1 Y0 Y1 [--dry] [--expect MTIME]
Run AFTER plan_lines.py. plan_lines guarantees every FACE coordinate is read; this pass guarantees every ELEMENT's OWN SIZE is a readable item (face to face, X and Y only):
 - wall / pier (82_KIR_OLE closed polygon): width and length; added when no dim line has an item (or consecutive items) spanning exactly its two faces (tol 12);
 - beam (93_KORA lines in parallel pairs <= 250 apart): its WIDTH across the pair (crossing dim, mid-span of the overlap on a free spot).
Each missing size = one linear dim beside the element (offset 60..350, first free line, else forced), never aligned. Idempotent (re-run adds nothing)."""
import argparse, os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import ezdxf
import plan_elements as pe, plan_audit as pa
from dxflib import dim_angle, backup

TOL = 12.0; MIN = 10.0; MAX_BEAM_W = 250.0; OFFS = (60, 90, 130, 180, 250, 350)


def dim_lines(doc, box):
    x0, x1, y0, y1 = box; L = collections.defaultdict(list)
    for e in doc.modelspace().query('DIMENSION'):
        dl = e.dxf.defpoint
        if not (x0 - 500 <= dl.x <= x1 + 500 and y0 - 500 <= dl.y <= y1 + 500) or (e.dxf.dimtype & 7) != 0: continue
        a = round(dim_angle(e)) % 180; p, q = e.dxf.defpoint2, e.dxf.defpoint3
        if a == 0: L[('h', round(dl.y))].append((min(p.x, q.x), max(p.x, q.x)))
        elif a == 90: L[('v', round(dl.x))].append((min(p.y, q.y), max(p.y, q.y)))
    return L


def is_read(L, ax, lo, hi):
    for (k, c), iv in L.items():
        if k != ax: continue
        iv = sorted(iv)
        for i in range(len(iv)):
            if abs(iv[i][0] - lo) > TOL: continue
            cur = iv[i][1]
            if abs(cur - hi) <= TOL: return True
            for j in range(i + 1, len(iv)):
                if abs(iv[j][0] - cur) > TOL: continue
                cur = iv[j][1]
                if abs(cur - hi) <= TOL: return True
    return False


def beam_pairs(doc, box):
    """parallel 93_KORA 2-point segments (axis-aligned) <= MAX_BEAM_W apart with >= 50 overlap -> (axis of the width dim, lo, hi, overlap lo, overlap hi)"""
    V = []; H = []
    for e, p in pa.elements(doc, box):
        if e.dxf.layer != '93_KORA' or len(p) != 2: continue
        (x1, y1), (x2, y2) = p
        if abs(x1 - x2) < 1.5 and abs(y1 - y2) >= 50: V.append((x1, min(y1, y2), max(y1, y2)))
        elif abs(y1 - y2) < 1.5 and abs(x1 - x2) >= 50: H.append((y1, min(x1, x2), max(x1, x2)))
    out = []; seen = set()
    for S, ax in ((V, 'h'), (H, 'v')):
        S.sort()
        for i, a in enumerate(S):
            for b in S[i + 1:]:
                w = b[0] - a[0]
                if w > MAX_BEAM_W: break
                if w < MIN: continue
                lo = max(a[1], b[1]); hi = min(a[2], b[2])
                if hi - lo < 50: continue
                k = (ax, round(a[0]), round(b[0]), round(lo))
                if k in seen: continue
                seen.add(k); out.append((ax, a[0], b[0], lo, hi))
    return out


def run(doc, box, dry=False):
    L = dim_lines(doc, box); out = pe.Out(doc); rep = []; n = 0
    def place(ax, lo, hi, ref_lo, ref_hi, tag):
        """ax 'h' = horizontal dim lo..hi, beside the element whose y extent is ref_lo..ref_hi; 'v' the other way"""
        nonlocal n
        for forced in (False, True):
            for o in OFFS:
                for side, ref in ((1, ref_hi), (-1, ref_lo)):
                    line = ref + side * o
                    a_, b_ = ((lo, line), (hi, line)) if ax == 'h' else ((line, lo), (line, hi))
                    if forced or out.free(a_, b_):
                        if ax == 'h': out.lin((lo, ref), (hi, ref), (lo, line), 0)
                        else: out.lin((ref, lo), (ref, hi), (line, lo), 90)
                        out.stripes.add(a_, b_); n += 1; rep.append((tag, ax, round(hi - lo, 1), 'forced' if forced else '')); return
    for e, p in pa.elements(doc, box):
        if e.dxf.layer != '82_KIR_OLE' or e.dxftype() != 'LWPOLYLINE' or not e.closed: continue
        xs = [a for a, b in p]; ys = [b for a, b in p]
        if max(xs) - min(xs) > 9000 or max(ys) - min(ys) > 9000: continue
        if max(xs) - min(xs) >= MIN and not is_read(L, 'h', min(xs), max(xs)): place('h', min(xs), max(xs), min(ys), max(ys), 'wall ' + e.dxf.handle)
        if max(ys) - min(ys) >= MIN and not is_read(L, 'v', min(ys), max(ys)): place('v', min(ys), max(ys), min(xs), max(xs), 'wall ' + e.dxf.handle)
    for ax, c1, c2, lo, hi in beam_pairs(doc, box):
        if is_read(L, ax, c1, c2): continue
        # crossing dim at the free spot along the beam (mid, then quarters, then ends); beams are crossed by perpendicular lines anyway
        spots = [(lo + hi) / 2, lo + (hi - lo) / 4, lo + 3 * (hi - lo) / 4, lo + 15, hi - 15]
        for s in spots:
            a_, b_ = ((c1, s), (c2, s)) if ax == 'h' else ((s, c1), (s, c2))
            if out.free(a_, b_) or s == spots[-1]:
                if ax == 'h': out.lin((c1, s), (c2, s), (c1, s), 0)
                else: out.lin((s, c1), (s, c2), (s, c1), 90)
                out.stripes.add(a_, b_); n += 1; rep.append(('beam width', ax, round(c2 - c1, 1), round(s))); break
    return out, rep


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--box', nargs=4, type=float, required=True)
    ap.add_argument('--dry', action='store_true'); ap.add_argument('--expect', type=float)
    a = ap.parse_args()
    if a.expect and abs(os.path.getmtime(a.file) - a.expect) > 1: sys.exit('file changed since it was read')
    doc = ezdxf.readfile(a.file); out, rep = run(doc, tuple(a.box))
    for r in rep: print(r)
    print('size dims added:', out.n)
    if a.dry: return
    open(a.file, 'ab').close(); backup(a.file, 'sizes'); doc.saveas(a.file); print('saved', a.file)


if __name__ == '__main__': main()
