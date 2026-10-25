"""Rebuild assets/office_layers.json (from the office layer list, construction-layers skill SKILL.md) and assets/office_standards.dxf (tables-only DXF: linetypes, text styles, dimstyles + the blocks the recipes use,
copied from the user's reference drawing). Run once per machine / when the office standard changes:
    python build_office_assets.py [LAYERS_SKILL_MD] [REFERENCE.dxf]"""
import sys, os, re, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ezdxf
from ezdxf.addons import Importer
A = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets')
md = sys.argv[1] if len(sys.argv) > 1 else (glob.glob(os.path.expanduser('~/.claude/skills/synced/*/construction-layers/SKILL.md')) or [None])[0]
ref = sys.argv[2] if len(sys.argv) > 2 else glob.glob(os.path.expanduser('~/Desktop/AI/*/*/TEST_PLAN/brenda_karka.dxf'))[0]
BLOCKS = ['dot barzel', 'o.k block', 'MH', 'mif-hat', 'hat', 'S_M']
src = ezdxf.readfile(ref); tab = {}
if md:
    rows = re.findall(r'^\|\s*([^|\s][^|]*?)\s*\|\s*(\d+)\s*\|\s*([^|\s]+)\s*\|', open(md, encoding='utf-8').read(), re.M)
    tab = {n: dict(color=int(c), linetype=lt) for n, c, lt in rows}
for L in src.layers:       # layers the recipes draw on that the office list does not name (51_HATAH_DASHED, 2000_DOT_HELP_LINE, 72_MISGERET_WIN ...): colour + linetype of the reference drawing
    if L.dxf.name not in tab and L.dxf.name.split('_')[0] in ('51', '2000', '72', '57', '56', '53', '54', '10', '23'): tab[L.dxf.name] = dict(color=abs(L.dxf.color), linetype=L.dxf.linetype)
json.dump(tab, open(os.path.join(A, 'office_layers.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0); print(len(tab), 'layers')
tgt = ezdxf.new('R2018', setup=False)
imp = Importer(src, tgt)
for t in ('linetypes', 'styles', 'dimstyles'):
    try: imp.import_tables(t, replace=True)
    except Exception as e: print('table', t, e)
for b in BLOCKS:
    if b in src.blocks:
        try: imp.import_block(b, rename=False)
        except Exception as e: print('block', b, e)
imp.finalize(); tgt.saveas(os.path.join(A, 'office_standards.dxf')); print('saved', len(list(tgt.dimstyles)), 'dimstyles,', len(list(tgt.styles)), 'styles,', [b.name for b in tgt.blocks if not b.name.startswith('*')])
