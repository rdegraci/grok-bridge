# grok-bridge

Thin localhost bridge so you can chat with Grok Bot agents from an SSH session on a Mac mini.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

cp env.example .env   # fill in secrets; chmod 600 .env
# optional: cp config.example.yaml config.yaml

grok-bridge start
grok-bridge-cli
grok-bridge stop
```

Design docs (local): `docs/cache/` (may be gitignored).

## Commands

| Command | Purpose |
| --- | --- |
| `grok-bridge start\|stop\|restart` | Background FastAPI server on `127.0.0.1` |
| `grok-bridge-cli` | Interactive chat loop |

Default listen address: `127.0.0.1:18787` (override via `config.yaml` or `GROK_BRIDGE_PORT`).

Logs live under `~/.grok-bridge/`. The CLI prints its session log path on exit.

**Advisor routine:** read chat fields from `<webhook_event>.body` (not the top level). POST replies to `http://127.0.0.1:18787/replies` with `Authorization: Bearer $GROK_BRIDGE_TOKEN`.
