# How the user teaches: marks, clouds, colours (read this before touching any file he sends)
CURRENT. The user teaches by SHOWING: finished examples, clouds, X's, hand edits. Every mark below was learned from his own files; colours are HIS code and mean different things per task, so read the instruction he pasted with the file and the cloud's contents before applying a row.

## Channel and discipline
- **ALL comments are on layer `claude`** (any entity type / colour; agreement 2026-10-13). Ignore clouds on other layers (`SHINUIM-TIKUNIM`, `60_HATCH_ADAMA` = old revision clouds). `dxf_inspect.py FILE markup` lists the `claude` layer first - run it at the start of EVERY task and again after every save: he deletes / recolours / adds marks between turns, may name another file than the first one, and may not have saved yet (check mtime; ask for a DXF save).
- A mark encloses things by **bbox overlap, not start points**; a thin cloud sits ON the missing element (a bar row, a dimension text), not around the section. Read the contents (list the clouded entities) before acting.
- An EMPTY-looking cloud may hold a pasted picture (OLE2FRAME, extents inf): extract it (knowledge/pitfalls.md, group E, 'Clouds'). A cloud with no stated meaning that stays empty: report it, ask once, never guess.
- **A correction on one element is a rule for its whole family** (regenerate all siblings, diff again); the newest correction outranks older rules. Exception: when he limits it ('only these', 'otherwise as they are') change exactly the clouded entities.
- Ambiguous nouns ('section markers', 'dimension line', 'opening'): name what the newest cloud encloses first (e.g. 'section markers' once meant the obround openings, not the plan cut marks).
- A deletion cloud = delete that item and its family unless the rule says otherwise. A size set in a cloud is usually a dimension he moved: compare its defpoints / text midpoint with its siblings.
- Learn from hand edits: snapshot MY output right after every write, then diff his save against it (arrays exploded, dots as centre sets, `scripts/learn_diff.py`); what he added / deleted / moved IS the rule. Reproduce his hand version with the changed generator on a COPY before touching the rest. His hand-made sections are never redrawn.

## Marks
| Mark | Meaning |
|---|---|
| Yellow rectangle (ACI 2) | examples to study; finished elements inside (may be numbered differently from the elements to do) |
| Red cloud | something missing / wrong inside it, OR the target place for new work; render its bbox, say what you inferred. WITHOUT text: diff his save against my last output (`learn_diff.py`) - what he moved / deleted / added next to each cloud IS the comment (korchakk_25,10: elevation moved, second note deleted, 'o.k' line added); a big cloud from a plan mark down to a pasted finished section = 'this mark is that section' |
| Red X (two crossing 2-point polylines) | delete that element; match each X to the element whose bbox holds it, find the rule behind ALL X's and check it against every X first; leave the X's in place and report |
| White cells / frames (`72_MISGERET_WIN`) | target boxes for new drawings, take them in order |
| Block under a cloud | a group of elements: classify with `scripts/block_reader.py` (element_group / nested / symbol), never assume model space holds everything |
| `hat` pair with attribute number | section cut; `S` / `SS` / `ST` (old `*`) on layer `automatic_sections` = STAR MARKER, standing order 'make a section here' (sections-workflow.md) |
| XLINE on layer `claude_DIM` | standing order 'dimension line here' (plan-dimensions.md) |
| Closed region(s) on `claude_Kontur` | the boundary of the work: everything outside is ignored |
| Cloud on `claude_DIM` OUTSIDE the plan | a SAMPLE DIMENSION cloud: output layer / style (plan-dimensions.md section 2) |
| Text on `automatic_Roller_shutter` (`b/h`) | add the roller-shutter downstand of that size to the section at that beam / edge |
| 'casting completion' (השלמת יציקה) cloud / slope note + arrow ('יציקה בשיפוע') on a plan | solid slab there / sloped-slab label (sections-drawing.md) |

## Cloud colours by task (layer `claude`; the user recolours between saves)
**Plan dimensioning** (details plan-dimensions.md)
- red (ByLayer 256 / ACI 1) = missing sizes of the elements inside: add their faces INTO the nearest chain on his Xline (no new lines)
- orange ACI 32 = elements lacking dims (add to the nearest chain) / a finished example dimension or a note on a beam label
- blue ACI 177 = a STAIR drawn on `15_DASHED` (overall extents only); blue true-colour 2586299 (ACI 152) = extend the chain to the outline
- green ACI 116 = align with the Xline; green ACI 114 = informational opening mark (double-height space, never dimensioned); green = beams that support the floor (reading note)
- old code on the retired layer SHINUIM-TIKUNIM (2026-10-08): red = example to delete, blue ACI 4 = add / adjust, yellow ACI 2 = copy everywhere; use it only when no other instruction exists.
**Section drawing** (sections-*.md)
- red cloud = correct this; on a section sheet BLUE ACI 177 = the beam, PINK ACI 217 = the slab beside it (matters for SS notes)
- a red cloud on a bar end = extend it (XREF); on a note = move / fix it; on a deleted item = delete the family
- the white row is the template: sections are drawn into it, his clouds stay until he removes them.
