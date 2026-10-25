"""Recipe: put every plan SECTION INDICATOR (numbered `hat` cut mark) on the office layer 23_SIM (rule from the user's red cloud in SECTIONS_PLAN.dxf, 2026-10-25).
  python section_indicator_layer.py FILE [--dry] [--layer 23_SIM] [--kontur] [-o OUT]
Indicator = INSERT of block `hat` whose attribute is a section number (1, 2, A..). Star marks (S / SS / ST / *, layer automatic_sections) are the standing 'make a section' order, NOT indicators: untouched.
Marks with an empty / unreadable attribute are reported, never moved. Only the INSERT's layer changes (the block's own entities are on layer 0 / ByLayer-independent, colour comes from the block).
--kontur = only indicators inside a closed claude_Kontur (what sections_round passes: marks outside the contour are never touched).
Missing target layer is imported from the office standard. In place with a timestamped snapshot (-o = test copy)."""
import argparse, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts')); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))      # python -I (sections_round) does not put the script folder on the path: plan_xlines_lf lives here
from dxflib import *

STAR = {'S', 'SS', 'ST', '*'}

def classify(doc, block='hat'):
    """-> (indicators, stars, unknown) lists of INSERTs in model space"""
    ind, stars, unk = [], [], []
    for e in doc.modelspace().query('INSERT'):
        if e.dxf.name.lower() != block: continue
        t = ''.join(a.dxf.text for a in e.attribs).strip()
        (stars if t in STAR else ind if t else unk).append(e)
    return ind, stars, unk

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--layer', default='23_SIM'); ap.add_argument('--dry', action='store_true'); ap.add_argument('--kontur', action='store_true'); ap.add_argument('-o')
    a = ap.parse_args()
    doc = ezdxf.readfile(a.file)
    ind, stars, unk = classify(doc)
    if a.kontur:
        from ezdxf.math import is_point_in_polygon_2d, Vec2
        from plan_xlines_lf import kontur_loops
        loops = kontur_loops(doc.modelspace())
        ind = [e for e in ind if any(is_point_in_polygon_2d(Vec2(e.dxf.insert.x, e.dxf.insert.y), [Vec2(q[0], q[1]) for q in L]) >= 0 for L in loops)]
    move = [e for e in ind if e.dxf.layer != a.layer]
    from collections import Counter
    print(f'indicators: {len(ind)} ({len(ind) - len(move)} already on {a.layer}); to move: {len(move)} from {dict(Counter(e.dxf.layer for e in move))}; star marks untouched: {len(stars)}')
    for e in unk: print(f'REPORT: hat {e.dxf.handle} on {e.dxf.layer} has no attribute text - not moved')
    if a.dry or not move: print('dry run / nothing to do' if a.dry else 'nothing to change'); return
    ensure_standards(doc, (a.layer,))
    for e in move: e.dxf.layer = a.layer
    out = a.o or a.file
    if not a.o: print('snapshot:', backup(a.file, 'indlayer'))
    doc.saveas(out)
    print('saved', out, '| audit errors:', audit_saved(out), '| moved', len(move))

if __name__ == '__main__': main()
