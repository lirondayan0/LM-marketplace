# dxf-drafting

Claude Code plugin with the `dxf-drafting` skill: inspect DXF files, learn an office's drawing conventions
from finished examples, then dimension / annotate / draw sections / audit.

## Install
```
/plugin marketplace add lirondayan0/LM-marketplace
/plugin install dxf-drafting@lm-marketplace
```

## Requirements
Python 3.9+ on PATH, then: `pip install ezdxf matplotlib`
(`python -m pip install -r <plugin>/skills/dxf-drafting/requirements.txt`).

## Notes
- All scripts use paths relative to the skill folder; nothing is machine-specific.
- The skill's "self-improvement" notes (conventions, pitfalls) are written into the skill folder. In an installed
  plugin that folder is a cache and is replaced on update, so copy learned changes back to the repo.
