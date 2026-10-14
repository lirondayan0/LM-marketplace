"""Inspect engineering DXF files (Hebrew SHX text is decoded). Run from anywhere:
  python dxf_inspect.py FILE summary                 # units, layers in use, styles, decoded texts
  python dxf_inspect.py FILE find TEXT               # entities whose text contains TEXT (raw or decoded)
  python dxf_inspect.py FILE near X Y [R=300]        # entities inside a box of half-size R
  python dxf_inspect.py FILE png X0 X1 Y0 Y1 OUT     # render a region (LOOK at it)
  python dxf_inspect.py FILE layers                  # every defined layer: color, linetype, lock/freeze, usage
  python dxf_inspect.py FILE dims [X0 X1 Y0 Y1]      # every DIMENSION: style, layer, text override, measurement
  python dxf_inspect.py FILE dimstyles               # dimstyle variables that differ from Standard
  python block_reader.py FILE [--box X0 Y0 X1 Y1] [--name N]   # what each INSERT IS (element group / nested / symbol) - run on any block the user marks
  python dxf_inspect.py FILE blocks                  # block definitions + insert counts + attdefs
  python dxf_inspect.py FILE entity HANDLE           # dump every DXF attribute of one entity
  python dxf_inspect.py FILE audit                   # structural errors + convention smells
  python dxf_inspect.py FILE diff OTHER.dxf          # entities added/removed in OTHER vs FILE (LEARN from before/after)
  python dxf_inspect.py FILE layouts                 # layouts and entity counts
  python dxf_inspect.py FILE markup                  # the user's markup (if a layer 'claude' exists ONLY that layer is listed, any colour): red clouds, yellow boxes, white target cells, section cut marks (hat blocks)
"""
import os, sys
for _s in (sys.stdout, sys.stderr): _s.reconfigure(encoding='utf-8', errors='replace')   # Hebrew texts crashed print on a cp125x console
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dxflib import *

def summary(doc):
    msp = doc.modelspace()
    print('version', doc.dxfversion, '| INSUNITS', doc.header.get('$INSUNITS'), '| DIMSCALE', doc.header.get('$DIMSCALE'),
          '| LTSCALE', doc.header.get('$LTSCALE'), '| layouts', [l.name for l in doc.layouts])
    print('types', dict(collections.Counter(e.dxftype() for e in msp)))
    cnt = collections.Counter(e.dxf.layer for e in msp)
    print(f'layers in use ({len(cnt)} of {len(doc.layers)} defined):')
    for n, c in cnt.most_common():
        l = doc.layers.get(n); print(f'  {c:4d} {n}  color={l.color} lt={l.dxf.linetype}')
    print('dimstyles', [s.dxf.name for s in doc.dimstyles])
    print('text styles', {s.dxf.name: s.dxf.font for s in doc.styles})
    print('texts:')
    for e in msp:
        t = text_of(doc, e)
        if t and any(ch.isalpha() for ch in t[1]): print(f'  {t[1]!r} {e.dxf.layer} @{r(e.dxf.insert)}')

def find(doc, q):
    for e in doc.modelspace():
        t = text_of(doc, e)
        if t and (q in t[0] or q in t[1]): print(describe(doc, e))

def near(doc, x, y, R):
    for e in doc.modelspace():
        if in_box(e, x - R, x + R, y - R, y + R): print(describe(doc, e))

def layers(doc):
    cnt = collections.Counter(e.dxf.layer for e in doc.modelspace())
    for l in sorted(doc.layers, key=lambda l: l.dxf.name):
        print(f'{cnt[l.dxf.name]:4d} {l.dxf.name:30s} color={l.color:<4} lt={l.dxf.linetype:12s} '
              f'{"OFF " if not l.is_on() else ""}{"FROZEN " if l.is_frozen() else ""}{"LOCKED" if l.is_locked() else ""}')

def dims(doc, box=None):
    for e in doc.modelspace().query('DIMENSION'):
        if box and not in_box(e, *box): continue
        print(describe(doc, e), f'type={e.dimtype}', f'handle={e.dxf.handle}')

def dimstyles(doc):
    std = doc.dimstyles.get('Standard') if 'Standard' in doc.dimstyles else None
    base = std.dxf.all_existing_dxf_attribs() if std else {}
    for s in doc.dimstyles:
        a = s.dxf.all_existing_dxf_attribs()
        print(s.dxf.name, {k: v for k, v in a.items() if k.startswith('dim') and base.get(k) != v})

def blocks(doc):
    uses = collections.Counter(e.dxf.name for e in doc.modelspace().query('INSERT'))
    for b in doc.blocks:
        if b.name.startswith('*'): continue
        print(f'{uses[b.name]:4d} inserts  {b.name}  ents={len(b)} attdefs={[a.dxf.tag for a in b.query("ATTDEF")]}')

def entity(doc, h):
    e = doc.entitydb.get(h.upper())
    if not e: sys.exit('no such handle')
    for k, v in e.dxf.all_existing_dxf_attribs().items(): print(f'  {k} = {v!r}')

def audit(doc):
    aud = doc.audit()
    print(f'ezdxf audit: {len(aud.errors)} errors, {len(aud.fixes)} fixes')
    for x in aud.errors[:30]: print('  ERR', x.message)
    msp = doc.modelspace(); smells = collections.defaultdict(list); seen = collections.Counter()
    for e in msp:
        t = e.dxftype()
        if e.dxf.layer == '0': smells['on layer 0'].append(e)
        if t == 'LINE' and e.dxf.start.isclose(e.dxf.end): smells['zero-length line'].append(e)
        seen[describe(doc, e)] += 1
        if text_of(doc, e) and e.dxf.style not in doc.styles: smells['text with missing style'].append(e)
        if t == 'DIMENSION':
            if e.dxf.dimstyle not in doc.dimstyles: smells['dim with missing style'].append(e)
            if e.dxf.text not in ('', '<>'): smells['dim with TEXT OVERRIDE (may be stale)'].append(e)
    for k, v in smells.items(): print(f'  smell: {k}: {len(v)}  e.g. handles {[e.dxf.handle for e in v[:5]]}')
    d = {k: n for k, n in seen.items() if n > 1}
    if d: print(f'  smell: {sum(d.values()) - len(d)} duplicate entities, e.g. {list(d)[:3]}')
    used = {e.dxf.layer for e in msp}
    print(f'  info: {len([l for l in doc.layers if l.dxf.name not in used])} layers defined but unused in modelspace')

def markup(doc):
    """List the user's markup so a task can start from it: clouds (what to fix/place), yellow boxes (examples), white cells (targets), cut marks."""
    msp = doc.modelspace(); box = lambda e: bbox.extents([e])
    if 'claude' in [l.dxf.name.lower() for l in doc.layers]:      # agreement 2026-10-13: ALL user comments are on layer 'claude'; every other cloud is ignored
        names = {1: 'red', 2: 'yellow', 3: 'green', 4: 'cyan', 5: 'blue', 6: 'magenta', 7: 'white'}; n = 0
        print("layer 'claude' (the user's markup; other layers' clouds are ignored):")
        for e in msp:
            if e.dxf.layer.lower() != 'claude': continue
            b = box(e); col = e.dxf.color if e.dxf.color != 256 else doc.layers.get(e.dxf.layer).color
            txt = (e.dxf.text if e.dxftype() == 'TEXT' else e.text if e.dxftype() == 'MTEXT' else '')
            kind = e.dxftype() + (' cloud' if e.dxftype() == 'LWPOLYLINE' and any(abs(p[4]) > .01 for p in e.get_points('xyseb')) else '')
            print(f'  {e.dxf.handle} {kind} aci={col}({names.get(col, "114=green" if col == 114 else "?")}) x {b.extmin.x:.0f}..{b.extmax.x:.0f} y {b.extmin.y:.0f}..{b.extmax.y:.0f} {txt!r}'); n += 1
        print(f'  {n} entities'); return
    def rows(title, items):
        print(title)
        for h, lay, b in items: print(f'  {h} {lay} x {b.extmin.x:.0f}..{b.extmax.x:.0f}  y {b.extmin.y:.0f}..{b.extmax.y:.0f}  ({b.size.x:.0f} x {b.size.y:.0f})')
    clouds, yellow, white, marks = [], [], [], []
    for e in msp:
        t, col = e.dxftype(), e.dxf.color if e.dxf.color != 256 else doc.layers.get(e.dxf.layer).color
        if t == 'LWPOLYLINE':
            pts = list(e.get_points('xyseb'))
            if len(pts) >= 6 and any(abs(p[4]) > .01 for p in pts) and (col == 1 or e.dxf.layer in ('SHINUIM-TIKUNIM', '60_HATCH_ADAMA')): clouds.append((e.dxf.handle, e.dxf.layer, box(e)))
            elif e.closed and len(pts) == 4 and col == 2 and box(e).size.x > 100: yellow.append((e.dxf.handle, e.dxf.layer, box(e)))
            elif e.dxf.layer == '72_MISGERET_WIN': white.append((e.dxf.handle, e.dxf.layer, box(e)))
        elif t == 'LINE' and e.dxf.layer == '72_MISGERET_WIN': white.append((e.dxf.handle, e.dxf.layer, box(e)))
        elif t == 'INSERT' and e.dxf.name == 'hat' and e.attribs: marks.append((e.dxf.handle, 'section ' + e.attribs[0].dxf.text, box(e)))
    rows('red clouds:', clouds); rows('yellow boxes (examples):', yellow); rows('white cells/frames (targets):', white); rows('section cut marks (hat):', sorted(marks, key=lambda r: r[1]))

def layouts(doc):
    for l in doc.layouts: print(l.name, f'entities={len(l)}')

if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    f, cmd, *a = sys.argv[1:]
    doc = ezdxf.readfile(f)
    if cmd == 'summary': summary(doc)
    elif cmd == 'find': find(doc, a[0])
    elif cmd == 'near': near(doc, float(a[0]), float(a[1]), float(a[2]) if len(a) > 2 else 300)
    elif cmd == 'png': render_png(doc, [float(v) for v in a[:4]], a[4])
    elif cmd == 'layers': layers(doc)
    elif cmd == 'dims': dims(doc, [float(v) for v in a[:4]] if len(a) >= 4 else None)
    elif cmd == 'dimstyles': dimstyles(doc)
    elif cmd == 'blocks': blocks(doc)
    elif cmd == 'entity': entity(doc, a[0])
    elif cmd == 'audit': audit(doc)
    elif cmd == 'layouts': layouts(doc)
    elif cmd == 'markup': markup(doc)
    elif cmd == 'diff':
        added, removed = diff(doc, ezdxf.readfile(a[0]))
        print(f'+{len(added)} added, -{len(removed)} removed (in OTHER vs FILE)')
        for s in added: print('  +', s)
        for s in removed: print('  -', s)
    else: sys.exit(__doc__)
