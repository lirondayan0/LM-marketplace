"""Recipe: add a section cut-mark pair (blocks `hat`) across a beam, copying the user's existing marks of the same view direction.
  python cut_marks.py FILE --num 1 --view E|W|N|S --at X Y --beam-width B [--dry] [-o OUT]
(X, Y) = point on the beam's centre line where the cut crosses it; --view = direction the section LOOKS (rot 270 E, 90 W, 0 N, 180 S; see scripts/plan_cuts.py).
The new pair is a COPY of an existing pair with the same view (insert, rotation, mirror, layer, attribute style), moved to the beam and renumbered, so it matches the
user's marks exactly; the two marks sit on both sides of the beam at +-max(81, B/2 + 70) from the centre line (fits the user's pairs within ~6: 25 wall -> 81, 30/65 -> ~92, 65/65 -> ~97, 80/65 -> ~109).
Which section number / view a beam needs: scripts/plan_cuts.py (panel span vs cut direction) + conventions/section-drawings.md. Writes a timestamped snapshot first."""
import argparse, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
from dxflib import *

ROT = {'E': 270, 'W': 90, 'N': 0, 'S': 180}
# per view: axis the two marks are spread along, and which mirror sign (sx) goes to the NEGATIVE side (user's pairs; see 1-1 E/W, 4-4 N, 2-2 S)
LAYOUT = {'E': ('y', -1), 'W': ('y', +1), 'N': ('x', +1), 'S': ('x', -1)}

def sources(doc, view, block='hat'):
    out = {}
    for e in doc.modelspace().query('INSERT'):
        if e.dxf.name == block and round(e.dxf.rotation) % 360 == ROT[view]:
            out.setdefault(-1 if e.dxf.xscale < 0 else 1, e)
    return out

def clone(doc, src, x, y, num):
    n = src.copy(); doc.modelspace().add_entity(n); dx, dy = x - src.dxf.insert.x, y - src.dxf.insert.y
    n.dxf.insert = (x, y, 0)
    for a, sa in zip(n.attribs, src.attribs): a.dxf.insert = (sa.dxf.insert.x + dx, sa.dxf.insert.y + dy, 0); a.dxf.text = str(num)
    return n

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--num', required=True); ap.add_argument('--view', required=True, choices=list(ROT))
    ap.add_argument('--at', nargs=2, type=float, required=True); ap.add_argument('--beam-width', type=float, required=True); ap.add_argument('--profile', default='israeli-structural')
    ap.add_argument('-o'); ap.add_argument('--dry', action='store_true'); a = ap.parse_args()
    block = load_profile(a.profile).get('cut_mark', {}).get('block', 'hat'); doc = ezdxf.readfile(a.file)
    src = sources(doc, a.view, block)
    if len(src) < 2: sys.exit(f'need an existing pair of marks looking {a.view} (rotation {ROT[a.view]}) to copy; found {len(src)}. Copy one by hand first.')
    axis, neg_sign = LAYOUT[a.view]; half = max(81.0, a.beam_width / 2 + 70.0); x, y = a.at
    pos = {neg_sign: (x - half, y) if axis == 'x' else (x, y - half), -neg_sign: (x + half, y) if axis == 'x' else (x, y + half)}
    plan = [(src[s], pos[s]) for s in (-1, 1)]
    print(f'section {a.num} looking {a.view}: marks at', [(round(p[0], 1), round(p[1], 1)) for _, p in plan], f'(half spacing {half:.0f})')
    if a.dry: return
    out = a.o or a.file
    if out == a.file: backup(a.file, 'marks')
    for s, (px, py) in plan: clone(doc, s, px, py, a.num)
    doc.saveas(out); print('saved', out, '| audit errors', len(ezdxf.readfile(out).audit().errors))

if __name__ == '__main__': main()
