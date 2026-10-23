#!/usr/bin/env python
"""Label a SLOPED slab in a section (user 2026-10-22): text ABOVE the sloped slab, geometry stays flat (never draw the incline).
  cast-in-place -> "תקרה יצוקה בשיפוע" ("Sloped cast-in-place slab");  hollow-core -> "תקרת פלדלת טרומית בשיפוע" ("Sloped precast hollow-core slabs") - Hebrew wording UNVERIFIED.
    python slope_label.py FILE --box X0 X1 Y0 Y1 --side left|right --kind cast|hollow [--dry]
--box = the section's extent (outline + notes). The slab = the 9_KONTUR horizontal line with the outermost end on that side; the label's far end sits on the slab's far end,
text 7.3 above the slab top with a slope ARROW under it (user's own 3-3 arrangement, supersedes 'above the notes'); top-bar notes in that zone are moved aside. Text style/attributes copied from a bar note of the section (SIVAN 0.7, mirrored).  Snapshot first (.bak-slope-HHMMSS)."""
import argparse, os, shutil, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/../scripts')
import ezdxf, dxflib as DL
TEXT_UP, END_IN, ARROW_DOWN, PITCH = 7.3, 7.8, 3.5, 15.0   # user's 3-3 arrangement (2026-10-22)
TXT = {'cast': 'תקרה יצוקה בשיפוע', 'hollow': 'תקרת פלדלת טרומית בשיפוע'}
UP = 20.0

def label(doc, box, side, kind, arrow='right', dry=False):
    x0, x1, y0, y1 = box; msp = doc.modelspace()
    hl = []
    for e in msp.query('LINE'):
        if e.dxf.layer != '9_KONTUR': continue
        a, b = e.dxf.start, e.dxf.end
        if abs(a.y - b.y) < .01 and x0 <= min(a.x, b.x) and max(a.x, b.x) <= x1 and y0 <= a.y <= y1: hl.append((min(a.x, b.x), max(a.x, b.x), a.y))
    if not hl: raise SystemExit('no 9_KONTUR horizontal lines in the box')
    far = (max(h[1] for h in hl) if side == 'right' else min(h[0] for h in hl))
    slab = [h for h in hl if (h[1] == far if side == 'right' else h[0] == far)]
    top = max(h[2] for h in slab); xs = (far if side == 'right' else far)
    notes = [t for t in msp.query('TEXT') if t.dxf.layer == '54_HATAH_TEXT' and t.dxf.style == 'SIVAN' and x0 <= t.dxf.insert.x <= x1 and y0 <= t.dxf.insert.y <= y1 and t.dxf.get('text_generation_flag', 0) & 2]
    if not notes: raise SystemExit('no mirrored SIVAN note to copy the style from')
    ref = min(notes, key=lambda t: abs(t.dxf.insert.x - xs))
    from shx_width import text_extent
    import text_overlap as TO
    t = ref.copy(); msp.add_entity(t); t.dxf.text = DL.encode(TXT[kind])
    h = t.dxf.height; wf = t.dxf.get('width', 1.0)
    w = abs(text_extent(t.dxf.style, t.dxf.text, 0, h, wf, True)[1] - text_extent(t.dxf.style, t.dxf.text, 0, h, wf, True)[0])
    ins_x = far - END_IN if side == 'right' else far + END_IN + w          # mirrored SIVAN text runs LEFT from its insert
    y = top + TEXT_UP; t.dxf.insert = (ins_x, y, 0)
    if t.dxf.hasattr('align_point'): t.dxf.align_point = (ins_x, y, 0)
    lx0, lx1 = text_extent(t.dxf.style, t.dxf.text, ins_x, h, wf, True)
    # slope arrow under the text (user's 3-3: LEADER, dim_100, tip 7 inside the text end, tail 12 inside the other end, 3.5 under the baseline); points OUTWARD (away from the beam) = the plan arrow's head, UNVERIFIED in general
    tip_x, tail_x = ((lx1 - 7.1, lx0 + 12.0) if arrow == 'right' else (lx0 + 7.1, lx1 - 12.0))
    ld = msp.add_leader([(tip_x, y - ARROW_DOWN), (tail_x, y - ARROW_DOWN)], dimstyle='dim_100', dxfattribs={'layer': '54_HATAH_TEXT'})
    ld.set_xdata('ACAD', [(1000, 'DSTYLE'), (1002, '{'), (1070, 41), (1040, 1.0), (1070, 147), (1040, 6.0), (1070, 77), (1070, 0), (1002, '}')])   # his override: DIMASZ 1.0 (small head), DIMGAP 6, DIMTAD 0
    # notes of this slab that stand in the label's zone move aside: the one nearest the slab's far end goes beyond the label (whole note, a multiple of the dot pitch so tips stay on dots), the others go to the other side (shelf end only, tips stay)
    zone = [n for n in msp.query('TEXT') if n is not t and n.dxf.layer == '54_HATAH_TEXT' and n.dxf.style == 'SIVAN' and top - 1 <= n.dxf.insert.y <= top + 22 and x0 <= n.dxf.insert.x <= x1
            and text_extent(n.dxf.style, n.dxf.text, n.dxf.insert.x, n.dxf.height, n.dxf.get('width', 1.0), True)[0] < lx1 + 4 and text_extent(n.dxf.style, n.dxf.text, n.dxf.insert.x, n.dxf.height, n.dxf.get('width', 1.0), True)[1] > lx0 - 4]
    zone.sort(key=lambda n: n.dxf.insert.x, reverse=(side == 'right'))
    moved = []
    for k, n in enumerate(zone):
        nx0, nx1 = text_extent(n.dxf.style, n.dxf.text, n.dxf.insert.x, n.dxf.height, n.dxf.get('width', 1.0), True)
        if k == 0:                                                       # beyond the label, towards the far end
            need = (lx1 + 9.0 - nx0) if side == 'right' else (lx0 - 9.0 - nx1)
            dx = (-(-need // PITCH) * PITCH) if need > 0 else -((-need) // PITCH) * PITCH
            TO.move_note(doc, n, 0, dx, whole=True)
        else:                                                            # other side of the label, further in
            dx = (lx0 - 12.0 - nx1) if side == 'right' else (lx1 + 12.0 - nx0)
            TO.move_note(doc, n, 0, dx)
        moved.append((n.dxf.handle, round(dx, 1)))
    return t, top, moved

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--box', nargs=4, type=float, required=True); ap.add_argument('--side', required=True, choices=('left', 'right'))
    ap.add_argument('--kind', required=True, choices=('cast', 'hollow')); ap.add_argument('--arrow', choices=('left', 'right'), default='right', help='slope arrow direction in the section'); ap.add_argument('--dry', action='store_true'); a = ap.parse_args()
    doc = ezdxf.readfile(a.file); t, top, mv = label(doc, a.box, a.side, a.kind, a.arrow)
    print('label', a.kind, 'at', (round(t.dxf.insert.x, 1), round(t.dxf.insert.y, 1)), 'slab top', round(top, 1), 'notes moved', mv)
    if not a.dry:
        shutil.copy2(a.file, a.file + time.strftime('.bak-slope-%H%M%S')); doc.saveas(a.file); print('saved')
