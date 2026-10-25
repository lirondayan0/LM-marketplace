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

ASSET = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'o_k_block.dxf'); BLOCK = 'o.k block'; LAYER = '57_HATAH_ZIUN'; DX0 = 1.9


def cell_geometry(doc, cx0, cy0, w, h):
    """(beam left face x, top y) of the section in the cell from its 9_KONTUR lines: the face = start x of the LOWEST horizontal line (the beam soffit (0,0)-(B,0)), top = highest line; None when there is no outline"""
    hz = []
    for e in doc.modelspace().query('LINE'):
        if e.dxf.layer != '9_KONTUR': continue
        s, t = e.dxf.start, e.dxf.end
        if abs(s.y - t.y) < 0.01 and cx0 < min(s.x, t.x) < cx0 + w and cy0 < s.y < cy0 + h: hz.append((s.y, min(s.x, t.x), max(s.x, t.x)))
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
    for k, (cx, cy) in enumerate(cells):
        if once and k != once - 1: continue
        if k in have or geo[k] is None:
            if k not in have and geo[k] is None: msgs.append(f'cell {k + 1}: no section outline, skipped')
            continue
        gx, gy = geo[k]
        if ref: e = ref[0].copy(); msp.add_entity(e); cur = bbox.extents([e], fast=True); e.dxf.insert = (e.dxf.insert.x + (gx + off[0] - cur.extmin.x), e.dxf.insert.y + (gy + off[1] - cur.extmin.y), e.dxf.insert.z)
        else:
            e = msp.add_blockref(BLOCK, (0, 0), dxfattribs=dict(layer=LAYER)); cur = bbox.extents([e], fast=True); e.dxf.insert = (gx + off[0] - cur.extmin.x, gy + off[1] - cur.extmin.y, 0)
        msgs.append(f'cell {k + 1}: o.k marker at beam face {gx:.1f}, top {gy:.1f}')
    return msgs


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--cells', nargs=3, type=float, required=True, metavar=('X0', 'Y0', 'N')); ap.add_argument('--cell-w', type=float, default=400.0); ap.add_argument('--cell-h', type=float, default=600.0); ap.add_argument('--once', type=int, default=None, metavar='CELL', help='write the marker ONLY in this cell (1-based), remove it elsewhere'); ap.add_argument('--dry', action='store_true'); a = ap.parse_args()
    doc = ezdxf.readfile(a.file); msgs = add_markers(doc, a.cells[0], a.cells[1], int(a.cells[2]), a.cell_w, a.cell_h, a.once); print('\n'.join(msgs) or 'nothing to do')
    if a.dry or not any(('marker at' in m or 'removed' in m) for m in msgs): return
    shutil.copy2(a.file, f'{a.file}.bak-okmarker-{time.strftime("%H%M%S")}'); doc.saveas(a.file); print('saved', a.file)


if __name__ == '__main__': main()
