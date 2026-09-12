# grok-bridge

CLI bridge for chatting with [Grok Bot](https://grok.x.ai/) agents on a dedicated Mac mini via an SSH session.

**grok-bridge** lets you connect to your Mac mini remotely and work with your Grok Bot agents from a familiar terminal experience. Keep Grok Bot off your main laptop or workstation while still running it in a separate, always-available environment on your Mac mini.

### Expectations

This is an **SSH in/out-box**, not a fast chat UI. For the quickest replies, use the **Grok Bot app on the Mac mini**. Use **grok-bridge** when you are SSHed in and want a simple remote inbox — same agent, extra hop, so replies often take tens of seconds.

## Features

- Background server: `grok-bridge start|stop|restart`
- Interactive client: `grok-bridge-cli` (`/chat`, `/status`, `/quit`)
- Advisor webhook wake with JSON payload under `<webhook_event>.body`
- Shared reply queue tagged by `bot` (Advisor-only in v0.1)
- Config and secrets under macOS Application Support
- Per-session CLI logs; readline history under the appdir

## Requirements

- Python 3.11+
- macOS recommended (Application Support appdir; Mac mini + Grok Bot local computer access)
- A Grok Bot webhook routine for the Advisor seat

## Install

```bash
git clone https://github.com/rdegraci/grok-bridge
cd grok-bridge
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configuration

On first start, grok-bridge:

1. Creates a random Bearer token at `~/.config/grok-bridge/token` if missing, and loads it as `$GROK_BRIDGE_TOKEN`.
2. Copies example files into the appdir if missing:

| Appdir file | Source template | Purpose |
| --- | --- | --- |
| `.env` | packaged `examples/dot_env.example` | Webhook URL/auth only |
| `config.yaml` | packaged `examples/config.yaml.example` | Tunable knobs (host, port, poll/timeout) |

**Bridge token:** `~/.config/grok-bridge/token` (auto-generated; mode `600`)  
**macOS appdir:** `~/Library/Application Support/grok-bridge/`

Edit webhook secrets before a real chat:

```bash
open -e "$HOME/Library/Application Support/grok-bridge/.env"
```

Required `.env` values:

```bash
GROK_BRIDGE_ADVISOR_WEBHOOK_URL=…        # from the routine panel
GROK_BRIDGE_ADVISOR_WEBHOOK_AUTH=…       # sender key (Authorization: Bearer)
```

Default listen address: `http://127.0.0.1:18787` (override in `config.yaml`).

### Advisor routine (required)

In the webhook routine prompt, instruct the agent to:

1. Read chat fields from `<webhook_event>.body` (`bot`, `message_id`, `text`).
2. Answer `body.text`.
3. `POST http://127.0.0.1:18787/replies` with `Authorization: Bearer $GROK_BRIDGE_TOKEN` (read the token from `~/.config/grok-bridge/token` or the environment) and JSON including `"bot": "advisor"` and `"in_reply_to": "<body.message_id>"`.

Enable **local computer access** for Grok Bot on the Mac mini so the agent can reach localhost.

## Usage

1. Install grok-bridge **on the Mac mini**.  
2. Turn on **SSH** on the mini: System Settings → General → Sharing → **Remote Login**.  
3. **SSH into** the Mac mini from your laptop.  
4. In that session:

```bash
source /path/to/grok-bridge/.venv/bin/activate
grok-bridge start
grok-bridge-cli
```

```text
> /chat advisor
[advisor] connected
> What's the next step for the lorebuilder page?
sent, waiting…
[advisor] …
> /quit
```

```bash
grok-bridge stop
```

Exiting SSH does **not** stop a server started with `grok-bridge start`; only `grok-bridge stop` (or reboot) does. `grok-bridge-cli` ends when that SSH session ends.

| Command | Description |
| --- | --- |
| `grok-bridge start` | Start the FastAPI server in the background |
| `grok-bridge stop` | Stop the background server |
| `grok-bridge restart` | Stop then start |
| `grok-bridge-cli` | Foreground chat loop |

## Architecture

```text
SSH → Mac mini
        ├─ grok-bridge (daemon)     → 127.0.0.1 only
        └─ grok-bridge-cli
                │
                ├─ POST /send       → Grok Bot webhook (wake)
                └─ GET  /replies    ← agent POST /replies
```

- Wire body to the webhook is plain JSON (no envelope).
- Grok Bot presents an envelope to the agent; fields live under `body`.
- The CLI short-polls for replies (default timeout 90s). Expect tens of seconds
  of wait after `sent, waiting…` — that is agent time, not a stuck poll loop.

## Security

- Server **must** bind to loopback (`127.0.0.1` / `::1`) only.
- Keep `.env` and `~/.config/grok-bridge/token` mode `600`; never commit webhook keys or the bridge token.
- Do not paste the bridge token into the routine prompt; read `~/.config/grok-bridge/token` or `$GROK_BRIDGE_TOKEN`.
- No Node/npm toolchain; MVP is Python-only.

## Development

```bash
source .venv/bin/activate
pip install -e .
grok-bridge restart
```

Project layout uses `src/grok_bridge/`. Design notes may live under `docs/cache/` (often gitignored).

## License

MIT © 2026 Rodney Degracia. See [LICENSE](LICENSE).

## See also

- [Quick start](docs/QUICK-START.md) — shortest path to first chat  
- [Operator guide](docs/OPERATOR-GUIDE.md) — day-to-day use on the Mac mini
