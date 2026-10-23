"""Hebrew notes of the generated sections -> SIVAN font (user 2026-10-21, brenda_karka: red cloud on an unreadable HEBREW_NEW note 'c/g/ kph ,fw' next to the SIVAN ones).
Rule: every note that holds Hebrew letters (HEBREW_NEW / MIRYL) becomes the user's SIVAN note: style SIVAN, width 0.7, text_generation_flag 2 (mirrored, runs LEFT from the insert), same span on its shelf
(the insert stays: the mirrored note then stands ON its shelf, which ends at the old text start). Numbers / symbols ('2$8@20', '1:25', 'X$XX') are not Hebrew and stay. Then run leader_fit.py on the same box.
  python sivan_text.py FILE --box X Y W H [--box ...] [--dry]
Snapshot first (.bak-sivantext-HHMMSS), in place. Importable: convert_box(doc, box) -> list of change strings."""
import argparse, os, shutil, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import ezdxf
from dxflib import decode
from shx_width import text_extent

SRC = ('HEBREW_NEW', 'MIRYL'); WIDTH = 0.7
DIA_STYLE = 'HEBREW_NEW'      # user 2026-10-22 (section 2 of brenda_karka): bar notes with the diameter symbol ('2$10@15', 'X$XX') must be HEBREW_NEW - HEBTXT shows the wrong glyph for $


def is_hebrew(raw): return any('֐' <= c <= '׿' for c in decode(raw))


def convert_box(doc, box):
    x0, y0, w, h = box; out = []
    for e in doc.modelspace().query('TEXT'):
        d = e.dxf
        if '$' in d.text and d.style != DIA_STYLE and d.style != 'SIVAN' and x0 <= d.insert.x <= x0 + w and y0 <= d.insert.y <= y0 + h and not is_hebrew(d.text):
            out.append(f'{d.text!r} {d.style} -> {DIA_STYLE} (diameter symbol)'); d.style = DIA_STYLE; continue
        if d.style not in SRC or not (x0 <= d.insert.x <= x0 + w and y0 <= d.insert.y <= y0 + h) or not is_hebrew(d.text): continue
        ins = d.insert      # the note keeps its insert: a right-running note starts where its shelf ends, the mirrored SIVAN note then runs LEFT over that shelf (user's SIVAN examples: insert at the shelf end); leader_fit sets the shelf = text width
        old = d.style; d.style = 'SIVAN'; d.width = WIDTH; d.text_generation_flag = 2; d.insert = ins
        out.append(f'{d.text!r} {old} -> SIVAN at ({ins[0]:.1f}, {ins[1]:.1f})')
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--box', nargs=4, type=float, action='append', required=True); ap.add_argument('--dry', action='store_true'); a = ap.parse_args()
    doc = ezdxf.readfile(a.file); res = [c for b in a.box for c in convert_box(doc, b)]
    print('\n'.join(res) or 'nothing to change'); print(len(res), 'note(s)')
    if a.dry or not res: return
    shutil.copy2(a.file, f'{a.file}.bak-sivantext-{time.strftime("%H%M%S")}'); doc.saveas(a.file); print('saved', a.file)


if __name__ == '__main__': main()
