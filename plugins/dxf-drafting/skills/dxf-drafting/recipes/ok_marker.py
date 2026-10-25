"""'OK per plan' level marker (user 2026-10-21, brenda_karka: red cloud on the `o.k block` of section 1-1 = o.k mark + 'לפי תכנית' (SIVAN) over the slab top, first "add this to all the sections", then he deleted it from 1-1 -> written ONCE per sheet with `--once CELL`, which sections_round uses; conventions/sections-workflow.md section 5, confirmed by him 2026-10-24).
The marker is the user's own block `o.k block` (layer 57_HATAH_ZIUN; MH triangle + 'o.k' DIM text + 'kph ,fbh,' SIVAN mirrored). Placement learned from his section 1-1: block bbox min = beam LEFT FACE + 1.9 in x, slab TOP in y
(i.e. the same offset from the beam's left face / top line in every section; the slab top is flush with the beam top). The beam left face = the second-smallest start x of the 9_KONTUR top lines (the right-hand slab piece starts at the face).
Reference = an existing `o.k block` INSERT in the cells (its offset is measured, not assumed); without one the block definition is used with the +1.9 / 0 offset. Idempotent: a cell that already holds the marker is skipped. `--once CELL` (user 2026-10-21: written ONCE on the sheet): keep / create it in that cell only and delete the duplicates.
  python ok_marker.py FILE --cells X0 Y0 N [--cell-w 400] [--cell-h 600] [--dry]     (X0 Y0 = bottom-left of the first cell of the row; N cells)
Snapshot first (.bak-okmarker-HHMMSS), in place. Importable: add_markers(doc, x0, y0, n, w, h) -> list of messages."""
import argparse, os, shutil, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ezdxf
from ezdxf import bbox
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

ASSET = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'o_k_block.dxf'); BLOCK = 'o.k block'; LAYER = '57_HATAH_ZIUN'; DX0 = 1.9; TEXT_LAYER = '54_HATAH_TEXT'; MH_X = 5.0      # stem 5 right of the beam's left face, every width (user 2026-10-25)


OUTLINE_LAYERS = ('9_KONTUR', '5_HATAH _KONTUR', '9_1_KONTUR')      # section outlines: LINEs (general / ledge beams) or polylines (cast / slab-edge sections, 2026-10-25 shlang)

def hsegs(doc, cx0, cy0, w, h):
    """horizontal outline segments (y, xmin, xmax) of the section in the cell"""
    out = []
    for e in doc.modelspace().query('LINE LWPOLYLINE'):
        if e.dxf.layer not in OUTLINE_LAYERS: continue
        if e.dxftype() == 'LINE': pts = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
        else:
            pts = [(q[0], q[1]) for q in e.get_points('xy')]
            if e.closed and pts: pts.append(pts[0])
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            if abs(y1 - y2) < 0.01 and x1 != x2 and cx0 < min(x1, x2) < cx0 + w and cy0 < y1 < cy0 + h: out.append((y1, min(x1, x2), max(x1, x2)))
    return out


def cell_geometry(doc, cx0, cy0, w, h):
    """(beam left face x, top y) of the section in the cell from its outline: the face = start x of the LOWEST horizontal segment (the beam soffit (0,0)-(B,0)), top = highest segment; None when there is no outline"""
    hz = hsegs(doc, cx0, cy0, w, h)
    if not hz: return None
    ylow = min(y for y, _, _ in hz); ytop = max(y for y, _, _ in hz)
    return min(x0_ for y, x0_, _ in hz if abs(y - ylow) < 0.5), ytop


def add_markers(doc, x0, y0, n, w=400.0, h=600.0, once=None):
    msp = doc.modelspace(); msgs = []
    if BLOCK not in doc.blocks and os.path.exists(ASSET):      # the user's block ships with the skill (assets/o_k_block.dxf)
        from ezdxf.addons.importer import Importer
        a_ = ezdxf.readfile(ASSET); imp = Importer(a_, doc); imp.import_block(BLOCK); imp.finalize(); msgs.append('block imported from assets/o_k_block.dxf')
    if BLOCK not in doc.blocks: return [f'block {BLOCK!r} is not defined in this file: nothing to place (take it from the user\'s template)']
    cells = [(x0 + k * w, y0) for k in range(n)]; have = {}
    for e in msp.query('INSERT'):
        if e.dxf.name != BLOCK: continue
        b = bbox.extents([e], fast=True)
        if not b.has_data: continue
        for k, (cx, cy) in enumerate(cells):
            if cx <= b.extmin.x <= cx + w and cy <= b.extmin.y <= cy + h: have[k] = (e, b)
    ref = next(iter(have.values()), None); geo = {k: cell_geometry(doc, cx, cy, w, h) for k, (cx, cy) in enumerate(cells)}
    k0 = next((k for k in have if geo[k]), None)             # a reference marker only counts in a cell that has an outline (app run 2026-10-23: marker in an empty cell -> TypeError)
    if ref and k0 is not None:                               # measured offset of the user's marker (bbox min) from the beam face / top
        gx, gy = geo[k0]; e0, b0 = have[k0]; ref = have[k0]; off = (b0.extmin.x - gx, b0.extmin.y - gy)
    else: ref = None; off = (DX0, 0.0)
    if once:                                           # user 2026-10-21: 'OK per plan' is written ONCE on the sheet: keep / create it in cell `once` (1-based), delete the others
        for k, (e, b) in list(have.items()):
            if k != once - 1: msp.delete_entity(e); msgs.append(f'cell {k + 1}: duplicate o.k marker removed'); del have[k]
    own = {k for e in msp.query('INSERT') if e.dxf.name == 'MH' for k, (cx, cy) in enumerate(cells) if cx <= e.dxf.insert.x <= cx + w and cy <= e.dxf.insert.y <= cy + h}      # user 2026-10-25 (test_sections 6): the general beam draws its OWN marker (MH + 'o.k' + 'per plan', SIVAN) in every section - he deleted the extra `o.k block` laid over it
    for k, (cx, cy) in enumerate(cells):
        if once and k != once - 1: continue
        if k in own and k not in have: msgs.append(f'cell {k + 1}: the section carries its own o.k marker (MH), block not added'); continue
        if k in have or geo[k] is None:
            if k not in have and geo[k] is None: msgs.append(f'cell {k + 1}: no section outline, skipped')
            continue
        gx, gy = geo[k]
        if ref: e = ref[0].copy(); msp.add_entity(e); cur = bbox.extents([e], fast=True); e.dxf.insert = (e.dxf.insert.x + (gx + off[0] - cur.extmin.x), e.dxf.insert.y + (gy + off[1] - cur.extmin.y), e.dxf.insert.z)
        else:
            e = msp.add_blockref(BLOCK, (0, 0), dxfattribs=dict(layer=LAYER)); cur = bbox.extents([e], fast=True); e.dxf.insert = (gx + off[0] - cur.extmin.x, gy + off[1] - cur.extmin.y, 0)
        msgs.append(f'cell {k + 1}: o.k marker at beam face {gx:.1f}, top {gy:.1f}')
    return msgs


def frame_cells(doc, box):
    """(cx, cy, w, h) of every 400-wide template cell of the closed 72_MISGERET_WIN row frames inside box = (x0, y0, W, H), left to right, top row first (a sheet has several rows)"""
    bx, by, bw, bh = box; out = []
    for e in doc.modelspace().query('LWPOLYLINE'):
        if e.dxf.layer != '72_MISGERET_WIN' or not e.closed: continue
        xs = [p[0] for p in e.get_points('xy')]; ys = [p[1] for p in e.get_points('xy')]; x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        if bx - 1 <= x0 and x1 <= bx + bw + 1 and by - 1 <= y0 and y1 <= by + bh + 1: out += [(x0 + 400.0 * k, y0, 400.0, y1 - y0) for k in range(max(1, round((x1 - x0) / 400.0)))]
    return sorted(out, key=lambda c: (-c[1], c[0]))


def add_own_markers(doc, x0, y0, n, w=400.0, h=600.0, cells=None):
    """user 2026-10-25 ("the cross-sections must bear the O.K. per plan mark"): EVERY section cell carries the marker the general beam draws itself - block MH on the beam top, 'o.k' over 'per plan' (both SIVAN mirrored), 2.8 / 2.0 right of the beam's left face (+18.3 when B >= 60, his 17-17).
    A cell that already has an MH or an `o.k block` is left alone; a cell without an outline is skipped. Ledge / cast / free-edge / step sections: face = soffit start, top = highest outline line (UNVERIFIED for them)."""
    msp = doc.modelspace(); msgs = []
    if 'MH' not in doc.blocks:
        from ezdxf.addons.importer import Importer
        a_ = ezdxf.readfile(ASSET); imp = Importer(a_, doc); imp.import_block('MH'); imp.finalize(); msgs.append('block MH imported')
    for k, (cx, cy, w, h) in enumerate(cells or [(x0 + k * w, y0, w, h) for k in range(n)]):
        geo = cell_geometry(doc, cx, cy, w, h)
        if geo is None: msgs.append(f'cell {k + 1}: no section outline, skipped'); continue
        gx, gy = geo
        if any(e.dxf.name == 'MH' and cx <= e.dxf.insert.x <= cx + w and cy <= e.dxf.insert.y <= cy + h for e in msp.query('INSERT')): continue
        for e in list(msp.query('INSERT')):      # the sheet's `o.k block` hides its triangle on the frozen layer 21_SIM (shlang 2026-10-25: sections looked unmarked): replaced by the visible own marker
            if e.dxf.name == BLOCK:
                b_ = bbox.extents([e], fast=True)
                if b_.has_data and cx <= b_.extmin.x <= cx + w and cy <= b_.extmin.y <= cy + h: msp.delete_entity(e); msgs.append(f'cell {k + 1}: o.k block replaced')
        lows = hsegs(doc, cx, cy, w, h); ylow = min(y for y, _, _ in lows); B = max(x2 - x1 for y, x1, x2 in lows if abs(y - ylow) < 0.5)
        msp.add_blockref('MH', (gx + MH_X, gy), dxfattribs=dict(layer='58_HATAH_SIM', xscale=-1.0, yscale=1.0))
        for raw, dy in (('kph ,fw', 7.3), ('/K/O', 14.3)):
            msp.add_text(raw, height=5.0, dxfattribs=dict(layer=TEXT_LAYER, style='SIVAN', width=0.7, text_generation_flag=2, insert=(gx + MH_X - 0.8, gy + dy, 0)))
        msgs.append(f'cell {k + 1}: o.k marker (MH + o.k + per plan) at beam face {gx:.1f}, top {gy:.1f}')
    return msgs


LEADER_LAYERS = ('56_HATAH_ZET',)      # note leaders (magenta)


def _tbox(t):
    """(x0, y0, x1, y1) of a TEXT from the SHX widths (mirrored notes run left from the insert)"""
    from shx_width import text_extent
    a, b = text_extent(t.dxf.style, t.dxf.text, 0.0, t.dxf.height, t.dxf.get('width', 1.0)); x, y, h = t.dxf.insert.x, t.dxf.insert.y, t.dxf.height
    return (x - b, y, x - a, y + h) if t.dxf.get('text_generation_flag', 0) & 2 else (x + a, y, x + b, y + h)


def _hit(a, b): return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def clear_markers(doc, cells, step=0.5, reach=80.0):
    """user 2026-10-25 ('5 from the left corner, not interfering with the other text'): the marker (MH + its two texts) stays 5 right of the beam face unless it would touch a note, a note leader or the section's other text; then it slides right in `step` cm up to `reach` to the first clear spot (none -> stays, reported). Returns messages."""
    msp = doc.modelspace(); msgs = []
    for k, (cx, cy, w, h) in enumerate(cells):
        inb = lambda x, y: cx <= x <= cx + w and cy <= y <= cy + h
        mhs = [e for e in msp.query('INSERT') if e.dxf.name == 'MH' and e.dxf.layer == '58_HATAH_SIM' and inb(e.dxf.insert.x, e.dxf.insert.y)]
        if not mhs: continue
        mh = mhs[0]; mx, my = mh.dxf.insert.x, mh.dxf.insert.y
        mine = [t for t in msp.query('TEXT') if t.dxf.text in ('kph ,fw', '/K/O') and abs(t.dxf.insert.x - mx) < 3 and 4 < t.dxf.insert.y - my < 17]
        others = [_tbox(t) for t in msp.query('TEXT') if t not in mine and inb(t.dxf.insert.x, t.dxf.insert.y) and t.dxf.layer == TEXT_LAYER]
        segs = []
        for e in msp.query('LINE LWPOLYLINE'):
            if e.dxf.layer not in LEADER_LAYERS: continue
            pts = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)] if e.dxftype() == 'LINE' else [(q[0], q[1]) for q in e.get_points('xy')]
            segs += [(a, b) for a, b in zip(pts, pts[1:]) if inb(*a) or inb(*b)]
        mb = bbox.extents([mh], fast=True); boxes0 = [(mb.extmin.x, mb.extmin.y, mb.extmax.x, mb.extmax.y)] + [_tbox(t) for t in mine]
        def clash(dx):
            bs = [(b[0] + dx, b[1], b[2] + dx, b[3]) for b in boxes0]
            for i_, b in enumerate(bs):
                if any(_hit(b, o) for o in others): return True
                if i_ == 0: continue      # the MH box (triangle + shelf) may be crossed by a leader; only its TEXTS must stay clear of them
                for (x1, y1), (x2, y2) in segs:
                    if any(b[0] <= x1 + (x2 - x1) * i / 40 <= b[2] and b[1] <= y1 + (y2 - y1) * i / 40 <= b[3] for i in range(41)): return True
            return False
        if not clash(0.0): continue
        dx = step
        while dx <= reach and clash(dx): dx += step
        if dx > reach: msgs.append(f'cell {k + 1}: marker touches other text / leaders and no clear spot within {reach:g} - left at 5 (check by eye)'); continue
        mh.dxf.insert = (mx + dx, my, mh.dxf.insert.z)
        for t in mine: t.dxf.insert = (t.dxf.insert.x + dx, t.dxf.insert.y, t.dxf.insert.z)
        msgs.append(f'cell {k + 1}: marker moved {dx:g} right (clear of notes / leaders)')
    return msgs


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--cells', nargs=3, type=float, default=[0, 0, 0], metavar=('X0', 'Y0', 'N')); ap.add_argument('--box', nargs=4, type=float, help='with --own: every 72_MISGERET_WIN cell frame inside this box (several rows)'); ap.add_argument('--cell-w', type=float, default=400.0); ap.add_argument('--cell-h', type=float, default=600.0); ap.add_argument('--once', type=int, default=None, metavar='CELL', help='write the marker ONLY in this cell (1-based), remove it elsewhere'); ap.add_argument('--own', action='store_true', help='EVERY cell gets the marker the general beam draws (MH + o.k + per plan); the default of sections_round'); ap.add_argument('--dry', action='store_true'); a = ap.parse_args()
    doc = ezdxf.readfile(a.file); msgs = add_own_markers(doc, a.cells[0], a.cells[1], int(a.cells[2]), a.cell_w, a.cell_h, frame_cells(doc, a.box) if a.box else None) if a.own else add_markers(doc, a.cells[0], a.cells[1], int(a.cells[2]), a.cell_w, a.cell_h, a.once); print('\n'.join(msgs) or 'nothing to do')
    if a.own and a.box: msgs += clear_markers(doc, frame_cells(doc, a.box))
    print('\n'.join(m for m in msgs if 'moved' in m or 'no clear' in m))
    if a.dry or not any(('marker at' in m or 'removed' in m or 'marker (MH' in m or 'moved' in m) for m in msgs): return
    shutil.copy2(a.file, f'{a.file}.bak-okmarker-{time.strftime("%H%M%S")}'); doc.saveas(a.file); print('saved', a.file)


if __name__ == '__main__': main()
