"""Guess what an (unseen) layer means: name tokens + colour/linetype + what it holds + what it sits next to. Evidence-based, never a lookup of one office's names only.

  from layer_roles import guess_all
  rows = guess_all(doc, items)        # items = [(layer, kind, (x, y), info)] collected by plan_layers.py
Each row: (layer, role, confidence high/medium/low/unknown, evidence list). 'unknown' = ask the user (or look at a zoomed render) - never invent a role.
Token table = this office's transliterated Hebrew (construction-layers skill + what the user taught); extend TOKENS when the user teaches a new one
(and record it in knowledge/structural-plan-reading.md too).
"""
import re, collections

TOKENS = {  # token -> meaning
    'KORA': 'beam', 'KIR': 'wall', 'WALL': 'wall', 'AMUD': 'column', 'KONTUR': 'outline / slab edge (floor inside)', 'ESOD': 'foundation',
    'CLUNAS': 'pile', 'RAFSODA': 'raft', 'HAFIRA': 'excavation', 'HATCH': 'hatch fill', 'TEXT': 'text', 'TXT': 'text', 'MIDA': 'dimension',
    'DIMENSION': 'dimension', 'ZET': 'leader (note / rebar detail)', 'ZIUN': 'rebar', 'RASHAT': 'mesh',
    'DASHED': 'hidden line (above the slab when the plan is seen from below)', 'HIDDEN': 'hidden line', 'OLE': 'new element',
    'KAYAM': 'existing element', 'HARISA': 'to demolish', 'SIM': 'symbol', 'HATAH': 'section', 'LUHADIM': 'slab panels (planks) data',
    'OMASIM': 'loads', 'HEZ': 'arrow (panel span direction)', 'BLOKIM': 'floor layout blocks', 'HANAET': 'floor layout', 'GRID': 'grid',
    'AXIS': 'axis', 'FRAME': 'drawing frame', 'MISGERET': 'drawing frame', 'MAMAD': 'protected room', 'TIKRA': 'ceiling (architect)',
    'FURNITURE': 'furniture (architect, not structure)', 'DIRECTION': 'north / direction symbol', 'TIKUNIM': 'revision', 'SHINUIM': 'revision',
    'KAV': 'line', 'BINYAN': 'building line', 'PLADA': 'steel / plate slab', 'TAHTON': 'bottom', 'ILION': 'top', 'ILIONA': 'top',
    'TAHTONA': 'bottom', 'SLARI': 'solid slab', 'SLAB': 'slab', 'MABAT': 'view',
}
KIND_ROLE = {'TEXT': 'annotation text', 'DIMENSION': 'dimensions', 'LEADER': 'leaders', 'HATCH': 'hatch fills', 'INSERT': 'block symbols'}


def tokens(name):
    return [t for t in re.split(r'[^A-Za-z]+', name.upper()) if len(t) > 1]


def guess(doc, layer, rows, near):
    """rows: [(kind, (x, y), info)] of this layer; near: Counter of the nearest other layers (co-location)."""
    ev, role, conf = [], None, 'unknown'
    lay = doc.layers.get(layer)
    aci = lay.color if lay else None
    lt = (lay.dxf.linetype if lay else '').upper()
    tk = [t for t in tokens(layer) if t in TOKENS]
    if tk:
        role = ' / '.join(TOKENS[t] for t in tk[:3]); conf = 'medium'; ev.append(f'name tokens {tk}')
    kinds = collections.Counter(k for k, _, _ in rows)
    if kinds:
        main = kinds.most_common(1)[0][0]; ev.append(f'holds {dict(kinds)}')
        if not role:
            role = KIND_ROLE.get(main, 'geometry'); conf = 'low'
        elif ('TEXT' in tk and not (kinds.get('TEXT') or kinds.get('LEADER'))) or ('MIDA' in tk and not kinds.get('DIMENSION')):
            ev.append(f'NOTE: name says {role!r} but content is {dict(kinds)} - check by eye')
    if lt.startswith(('DASHED', 'HIDDEN')):
        ev.append(f'linetype {lt}: hidden = above the slab (plan seen from below)')
        if tk: conf = 'high'
    sizes = collections.Counter(i for k, _, i in rows if k == 'PL' and isinstance(i, tuple))
    if sizes: ev.append('common closed sizes ' + str(sizes.most_common(4)))
    txt = [i for k, _, i in rows if k == 'TEXT']
    if txt: ev.append('texts ' + ' | '.join(sorted(set(txt))[:6]))
    if near: ev.append('sits next to ' + ', '.join(f'{l} x{c}' for l, c in near.most_common(3)))
    if not tk and near and kinds:
        role = (role or '') + f' attached to {near.most_common(1)[0][0]} elements'; conf = 'low'
    if aci is not None: ev.append(f'ACI {aci}')
    if conf == 'medium' and any(t in tk for t in ('TEXT', 'MIDA', 'ZET', 'HATCH', 'KONTUR', 'KORA', 'KIR')) and kinds: conf = 'high'
    return role or 'unknown', conf, ev


def guess_all(doc, items, radius=150, sample=25):
    by = collections.defaultdict(list)
    for ly, kind, pos, info in items: by[ly].append((kind, pos, info))
    pts = [(pos, ly) for ly, kind, pos, info in items if pos]
    out = []
    for ly, rows in sorted(by.items()):
        near = collections.Counter()
        step = max(1, len(rows) // sample)
        for kind, pos, info in rows[::step]:
            if not pos: continue
            best = None
            for (p, l2) in pts:
                if l2 == ly: continue
                d = (p[0] - pos[0]) ** 2 + (p[1] - pos[1]) ** 2
                if d <= radius ** 2 and (best is None or d < best[0]): best = (d, l2)
            if best: near[best[1]] += 1
        out.append((ly,) + guess(doc, ly, rows, near))
    return out
