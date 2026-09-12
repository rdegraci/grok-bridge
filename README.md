# grok-bridge

Thin localhost bridge so you can chat with Grok Bot agents from an SSH session on a Mac mini.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

grok-bridge start   # seeds Application Support config on first run
# Edit secrets:
#   ~/Library/Application Support/grok-bridge/.env
# Tunable knobs:
#   ~/Library/Application Support/grok-bridge/config.yaml

grok-bridge-cli
grok-bridge stop
```

On first run, `dot_env.example` and `config.yaml.example` are copied into the appdir as `.env` and `config.yaml` if those files do not already exist.

## Commands

| Command | Purpose |
| --- | --- |
| `grok-bridge start\|stop\|restart` | Background FastAPI server on `127.0.0.1` |
| `grok-bridge-cli` | Interactive chat loop |

Default listen address: `127.0.0.1:18787` (override in `config.yaml`).

Appdir (macOS): `~/Library/Application Support/grok-bridge/`  
(PID, server log, CLI session logs, `.env`, `config.yaml`). The CLI prints its session log path on exit.

**Advisor routine:** read chat fields from `<webhook_event>.body` (not the top level). POST replies to `http://127.0.0.1:18787/replies` with `Authorization: Bearer $GROK_BRIDGE_TOKEN`.
