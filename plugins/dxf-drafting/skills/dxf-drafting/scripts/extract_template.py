"""Extract the drawing inside a box of a DXF into a small template DXF with its origin moved to (0,0) (layers, styles, dimstyles, blocks come along).
  python extract_template.py SRC.dxf X0 X1 Y0 Y1 ORIGIN_X ORIGIN_Y OUT.dxf      (the user's 'claude' layer is never copied)"""
import sys, json, ezdxf
from ezdxf.addons.importer import Importer
from ezdxf.math import Matrix44
def main():
    src, x0, x1, y0, y1, ox, oy, out = sys.argv[1], *map(float, sys.argv[2:8]), sys.argv[8]
    s = ezdxf.readfile(src); t = ezdxf.new('R2018'); sel = []
    for e in s.modelspace():
        if e.dxf.layer == 'claude': continue
        try:
            p = e.dxf.start if e.dxftype() == 'LINE' else e.dxf.insert if e.dxftype() in ('TEXT', 'INSERT') else e.dxf.defpoint if e.dxftype() == 'DIMENSION' else e.get_points()[0] if e.dxftype() == 'LWPOLYLINE' else list(e.vertices)[0] if e.dxftype() == 'LEADER' else None
        except Exception: p = None
        if p is not None and x0 < p[0] < x1 and y0 < p[1] < y1: sel.append(e)
    imp = Importer(s, t); imp.import_tables(); imp.import_entities([e for e in sel if e.dxftype() != 'DIMENSION']); imp.finalize()
    m = Matrix44.translate(-ox, -oy, 0)
    for e in t.modelspace(): e.transform(m)
    dims = []                                               # the importer cannot copy DIMENSION entities: they go to a sidecar JSON and are re-created with add_linear_dim
    for e in sel:
        if e.dxftype() == 'DIMENSION':
            f = lambda v: [round(v.x - ox, 2), round(v.y - oy, 2)]
            dims.append(dict(base=f(e.dxf.defpoint), p1=f(e.dxf.defpoint2), p2=f(e.dxf.defpoint3), angle=e.dxf.get('angle', 0.0), text=e.dxf.text if e.dxf.text not in ('', '<>') else None, dimstyle=e.dxf.dimstyle, layer=e.dxf.layer))
    json.dump(dims, open(out.rsplit('.', 1)[0] + '.dims.json', 'w'), indent=1)
    t.saveas(out); print(len(sel), 'entities ->', out, '|', len(dims), 'dims in sidecar')
main()
