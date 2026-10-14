"""READ ANY BLOCK (user 2026-10-14: 'learn to read every block I give you next time').  python block_reader.py FILE [--box X0 Y0 X1 Y1] [--name NAME]
For every INSERT (optionally inside a box / one block name) report what it IS and how the dimension pipeline should treat it:
  element_group  plain geometry (polylines / lines / arcs / circles) on structural layers = plan elements hidden in a block (walls, piers, beams)  -> EXPLODE in a working copy, dimension the elements
  nested         a block whose entities include INSERTs of element groups                                                                        -> expand recursively
  symbol         attributes, text/hatch/dimension content, tiny or non-structural (hat, S_M, resh, north arrow, level marks)                          -> leave alone
  annotation / other                                                                                                                              -> leave alone
Library use:  classify(doc, block_name) -> dict | expand_groups(doc, ms, big=5000) -> saved INSERT attribs (working copy only) | restore_groups(doc, saved).
Layer role comes from the layer-name tokens of layer_roles.TOKENS (KIR/WALL/AMUD = wall, KORA = beam, KONTUR = outline, DASHED = hidden); a layer with no known token is reported, never guessed silently."""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ezdxf, ezdxf.bbox
from layer_roles import tokens
GEOM = ('LWPOLYLINE', 'POLYLINE', 'LINE', 'ARC', 'CIRCLE')
ROLE_OF = {'KIR': 'wall', 'WALL': 'wall', 'AMUD': 'column', 'KORA': 'beam', 'KONTUR': 'outline', 'DASHED': 'hidden', 'HIDDEN': 'hidden'}
WORKING_LAYER = {'wall': '82_KIR_OLE', 'column': '82_KIR_OLE', 'beam': '93_KORA'}      # layers the dimension pipeline reads (plan_elements WALL / KORA)
BLK = 'CLAUDE_BLK'
def role(layer):
    for t in tokens(layer):
        if t in ROLE_OF: return ROLE_OF[t]
    return None
def classify(doc, name, _seen=()):
    b = doc.blocks.get(name)
    if b is None: return dict(kind='missing', reason='no such block')
    ents = list(b); kinds = collections.Counter(e.dxftype() for e in ents); layers = collections.Counter(e.dxf.layer for e in ents)
    roles = collections.Counter(role(l) for l in layers.elements())
    info = dict(name=name, entities=len(ents), types=dict(kinds), layers=dict(layers), roles={str(k): v for k, v in roles.items()})
    if name in _seen: return dict(info, kind='other', reason='recursive block')
    has_att = any(e.dxftype() == 'ATTDEF' for e in ents)
    geom = [e for e in ents if e.dxftype() in GEOM]
    struct = [e for e in geom if role(e.dxf.layer) in ('wall', 'column', 'beam', 'outline', 'hidden')]
    kids = [e for e in ents if e.dxftype() == 'INSERT']
    if has_att or name.startswith('*') and not geom: return dict(info, kind='symbol', reason='attributes / anonymous (dimension, hatch) block')
    if kids and geom and len(struct) == len(geom) and len(geom) >= 1 or kids and not geom:
        sub = [classify(doc, k.dxf.name, _seen + (name,))['kind'] for k in kids]
        if all(s in ('element_group', 'nested') for s in sub): return dict(info, kind='nested', reason='contains element-group blocks: %s' % sorted(set(k.dxf.name for k in kids)))
    if len(geom) >= 5 and len(struct) == len(geom) and kinds.get('TEXT', 0) + kinds.get('MTEXT', 0) + kinds.get('HATCH', 0) <= len(geom) // 2:
        return dict(info, kind='element_group', reason='%d plain elements, all on structural layers (%s)' % (len(geom), ', '.join(sorted(layers))))
    if kinds.get('TEXT', 0) + kinds.get('MTEXT', 0) > len(geom): return dict(info, kind='annotation', reason='mostly text')
    if geom and len(struct) < len(geom): return dict(info, kind='symbol', reason='geometry on non-structural layers: %s' % sorted(set(e.dxf.layer for e in geom if role(e.dxf.layer) is None)))
    return dict(info, kind='symbol', reason='small block (%d plain entities)' % len(geom))
def expand_groups(doc, ms, big=5000.0, log=print, within=None):
    """WORKING COPY ONLY. Replace every element-group INSERT (recursively) by its transformed elements (tagged CLAUDE_BLK; wall / beam layers renamed to the pipeline's layers unless outline-sized). Returns the INSERT attribs to restore."""
    if BLK not in doc.appids: doc.appids.add(BLK)
    saved = []
    def put(e, depth=0):
        for v in e.virtual_entities():
            if v.dxftype() == 'INSERT':
                if classify(doc, v.dxf.name)['kind'] in ('element_group', 'nested') and depth < 6: put(v, depth + 1)
                continue
            if v.dxftype() not in GEOM: continue
            r = role(v.dxf.layer); wide = False
            if v.dxftype() == 'LWPOLYLINE':
                xs = [q[0] for q in v.get_points('xy')]; wide = max(xs) - min(xs) >= big
            if r in WORKING_LAYER and not wide: v.dxf.layer = WORKING_LAYER[r]
            ms.add_entity(v); v.set_xdata(BLK, [(1000, 'x')]); counts[0] += 1
    for e in list(ms.query('INSERT')):
        if e.attribs or classify(doc, e.dxf.name)['kind'] not in ('element_group', 'nested'): continue
        if within:                                                  # only blocks that touch the work plan (other plan copies in the file stay untouched)
            bb = ezdxf.bbox.extents([e])
            if not bb.has_data or bb.extmax.x < within[0] or bb.extmin.x > within[2] or bb.extmax.y < within[1] or bb.extmin.y > within[3]: continue
        counts = [0]; nm = e.dxf.name; saved.append(e.dxfattribs()); put(e); ms.delete_entity(e); log('block %s read as %s: %d elements in the working copy' % (nm, classify(doc, nm)['kind'], counts[0]))
    return saved
def restore_groups(doc, saved):
    ms = doc.modelspace()
    for e in list(ms):
        if e.has_xdata(BLK): ms.delete_entity(e)
    for a in saved:
        a = dict(a); a.pop('handle', None); a.pop('owner', None); nm = a.pop('name'); ins = a.pop('insert'); ms.add_blockref(nm, ins, dxfattribs=a)
def main():
    a = sys.argv[1:]; doc = ezdxf.readfile(a[0]); ms = doc.modelspace()
    box = [float(x) for x in a[a.index('--box') + 1:a.index('--box') + 5]] if '--box' in a else None
    only = a[a.index('--name') + 1] if '--name' in a else None
    seen = collections.defaultdict(list)
    for e in ms.query('INSERT'):
        if only and e.dxf.name != only: continue
        p = e.dxf.insert
        if box and not (box[0] <= p.x <= box[2] and box[1] <= p.y <= box[3]): continue
        seen[e.dxf.name].append(e)
    for n, es in sorted(seen.items(), key=lambda kv: -len(kv[1])):
        c = classify(doc, n); print('%-18s x%-4d %-13s %s' % (n[:18], len(es), c['kind'], c['reason'][:110]))
        if c['kind'] in ('element_group', 'nested'): print('   layers', c['layers'], 'types', c['types'])
if __name__ == '__main__': main()
