"""LAYER COLOURS of the generated sections (user 2026-10-21: "I organized the layer colours - next time you know how to do it yourself").
The user's own table, read from his saved file (diff against my snapshot): 57_HATAH_ZIUN = ACI 4 (rebar: dots, stirrups, bar lines = his 'blue'), 56_HATAH_ZET = 6 (leaders), 53_HATAH_MIDA = 2 (dims),
54_HATAH_TEXT = 3, 9_KONTUR = 3, 5_HATAH _KONTUR = 3, 72_MISGERET_WIN = 7. He REMOVED my per-entity colour overrides: entities stay BYLAYER (256); colour comes only from the LAYER.
This recipe sets those layer colours (layers that exist) and clears entity colour overrides on 57_HATAH_ZIUN inside the box. Run by ledge_beam.finish / sections_round.
  python rebar_color.py FILE --box X Y W H [--box ...] [--dry]
Snapshot first (.bak-rebarblue-HHMMSS), in place. Importable: colour_box(doc, box) -> count, set_layer_colors(doc) -> count."""
import argparse, os, shutil, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ezdxf

LAYER_COLORS = {'57_HATAH_ZIUN': 4, '56_HATAH_ZET': 6, '53_HATAH_MIDA': 2, '54_HATAH_TEXT': 3, '9_KONTUR': 3, '5_HATAH _KONTUR': 3, '72_MISGERET_WIN': 7}
LAYER, BLUE = '57_HATAH_ZIUN', 4      # the user's 'blue' = ACI 4 (light blue / cyan): he recoloured the stirrups inside a red cloud to 4 (2026-10-21); pure ACI 5 was rejected


def _pt(e):
    t = e.dxftype()
    if t == 'LINE': return e.dxf.start.x, e.dxf.start.y
    if t == 'LWPOLYLINE':
        p = next(iter(e.get_points('xy')), None); return p
    if t in ('INSERT', 'CIRCLE', 'ARC'): return (e.dxf.insert.x, e.dxf.insert.y) if t == 'INSERT' else (e.dxf.center.x, e.dxf.center.y)
    return None


def set_layer_colors(doc):
    n = 0
    for name, col in LAYER_COLORS.items():
        if name not in doc.layers:                       # a layer the recipes draw on but the file never defined renders colour 7: define it
            if any(e.dxf.layer == name for e in doc.modelspace()): doc.layers.add(name, color=col); n += 1
        elif doc.layers.get(name).dxf.color != col: doc.layers.get(name).dxf.color = col; n += 1
    return n


def colour_box(doc, box):
    """entities of the rebar layer inside box go BYLAYER (the layer carries the colour); layer colours set from the user's table"""
    x0, y0, w, h = box; n = set_layer_colors(doc)
    for e in doc.modelspace():
        if e.dxf.layer != LAYER: continue
        p = _pt(e)
        if p and x0 <= p[0] <= x0 + w and y0 <= p[1] <= y0 + h and e.dxf.get('color', 256) != 256: e.dxf.color = 256; n += 1
    return n


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--box', nargs=4, type=float, action='append', required=True); ap.add_argument('--dry', action='store_true'); a = ap.parse_args()
    doc = ezdxf.readfile(a.file); n = sum(colour_box(doc, b) for b in a.box); print(n, 'changes (layer colours + overrides cleared)')
    if a.dry or not n: return
    shutil.copy2(a.file, f'{a.file}.bak-rebarblue-{time.strftime("%H%M%S")}'); doc.saveas(a.file); print('saved', a.file)


if __name__ == '__main__': main()
