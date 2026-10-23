"""Redraw general-beam sections IN PLACE inside their existing frames (user 2026-10-22: corrected slab thicknesses + restraint mesh for D >= 60).
Keeps each section's origin (beam bottom-left corner read from its outline), clears the frame region, draws general_beam.draw again, applies --detail.
  python redraw_general.py FILE SPEC.json [--dry]     SPEC = [{"n": 4, "B": 150, "H": 125, "Dl": 60, "Dr": 30, "dl": 0, "dr": 95, "stirrups": "transfer", "detail": "plan", "h_label": null}, ...]
Then run the finish passes on the sheet (sivan_text, leader_fit, rebar_color, align_row, cell_dupes, text_overlap, bar_arrays)."""
import argparse, json, os, sys, types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import ezdxf
from ezdxf import bbox
import ledge_beam as LB, general_beam as GB

def frames(doc):
    out = []
    for e in doc.modelspace().query('LWPOLYLINE'):
        if e.dxf.layer == '72_MISGERET_WIN':
            b = bbox.extents([e])
            if b.has_data and abs((b.extmax.x - b.extmin.x) - 4000) < 5 or (b.has_data and abs((b.extmax.x - b.extmin.x) - 400) < 5): out.append((b.extmin.x, b.extmin.y, b.extmax.x, b.extmax.y))
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('spec'); ap.add_argument('--dry', action='store_true'); ap.add_argument('--row', nargs=2, type=float, help='X0 Y0 of the sheet row (bottom-left of the first frame of each 4000 frame)', action='append')
    a = ap.parse_args(); LB.apply_profile('israeli-structural'); doc = ezdxf.readfile(a.file); msp = doc.modelspace(); Ly = LB.PROF['layers']; tmpl = LB.template_texts(doc)
    specs = json.load(open(a.spec, encoding='utf-8-sig')); fr = frames(doc)
    for s in specs:
        x0, y0, x1, y1 = s['frame']; B = s['B']
        lines = [e for e in msp.query('LINE') if e.dxf.layer == Ly['outline_new'] and abs(e.dxf.start.y - e.dxf.end.y) < 0.01 and abs(abs(e.dxf.end.x - e.dxf.start.x) - B) < 0.6 and x0 < e.dxf.start.x < x1 and y0 - 5 < e.dxf.start.y < y1]
        if not lines: print('no beam bottom line found for', s['n'], '- skipped'); continue
        bl = min(lines, key=lambda e: e.dxf.start.y); ox, oy = min(bl.dxf.start.x, bl.dxf.end.x) + s.get('dx', 0.0), bl.dxf.start.y      # dx = nudge inside the frame (4-4: the left mesh note must stay inside)
        n_del = LB.clear_cell(doc, (x0, y0 - 5, x1, y1))
        T0 = LB.PROF['title']
        for t in list(msp.query('TEXT')):
            if x0 < t.dxf.insert.x < x1 and y0 - 5 < t.dxf.insert.y < y1 and t.dxf.layer == Ly['text'] and (t.dxf.text.startswith(T0['prefix']) or t.dxf.text == T0['scale_text']['text']): msp.delete_entity(t)
        lab = {'B': None, 'H': s.get('h_label'), 'D': s.get('d_label'), 'B-6': None, 'H-6': (s['h_label'] + '-6') if s.get('h_label') else None}
        GB.draw(doc, B, max(s['Dl'], s['Dr']), s['H'], ox, oy, f"{s['n']}-{s['n']}", tmpl, lab, (B - 20) / 2 + 29.65, s['stirrups'], s['Dl'], s['Dr'], s.get('dl', 0.0), s.get('dr', 0.0))
        bx0 = ox - GB.CELL_U0 + (B - 20) / 2; by0 = oy - GB.CELL_V0
        LB.apply_detail(doc, types.SimpleNamespace(box=[bx0, by0, 400, 450], detail=s['detail'], name=f"{s['n']}-{s['n']}"))
        print(f"{s['n']}-{s['n']}: cleared {n_del}, origin ({ox:.1f}, {oy:.1f}) B={B} H={s['H']} Dl={s['Dl']} Dr={s['Dr']} dl={s.get('dl', 0)} dr={s.get('dr', 0)}")
    if a.dry: return
    LB.backup(a.file, 'redraw'); doc.saveas(a.file); print('saved', a.file, '| audit errors', len(ezdxf.readfile(a.file).audit().errors))

if __name__ == '__main__': main()