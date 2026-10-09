# LM-marketplace

A Claude Code plugins marketplace.

## Use

```
/plugin marketplace add lirondayan0/LM-marketplace
/plugin install <plugin-name>@lm-marketplace
```

## Add a plugin

1. Put the plugin under `plugins/<plugin-name>/` (with `.claude-plugin/plugin.json`).
2. Add an entry to `.claude-plugin/marketplace.json`:

```json
{
  "name": "<plugin-name>",
  "source": "./plugins/<plugin-name>",
  "description": "What it does"
}
```
