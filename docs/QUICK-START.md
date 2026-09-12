# Quick start

Get **Grok Advisor** chat working on the Mac mini in a few minutes.

## Operator flow (summary)

1. **Install** grok-bridge on the Mac mini.  
2. **Turn on SSH** on the mini: System Settings → General → Sharing → **Remote Login**.  
3. **SSH into** the Mac mini from your laptop.  
4. In that SSH session run **`grok-bridge start`** then **`grok-bridge-cli`** to chat with Grok Bot.

**Expectations:** grok-bridge is an **SSH in/out-box**, not a fast chat UI. For the quickest replies, use the **Grok Bot app on the Mac mini**. From the CLI, expect tens of seconds after `sent, waiting…` while the agent runs and posts back.

Details below.

## 1. Create Grok Advisor

In the Grok Bot app on the Mac mini, create a bot named **Grok Advisor** (if it does not already exist). Enable **local computer access** for this Mac mini.

On **first chat** with Grok Advisor, allow it to **run commands locally on the Mac mini** when prompted. That permission is required so it can read `~/.config/grok-bridge/token`, use the bridge, and execute commands/requests for you on this machine.

## 2. Install on the Mac mini

On the Mac mini (console or an existing SSH session):

```bash
cd /path/to/grok-bridge
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## 3. Enable SSH (Remote Login)

On the Mac mini: **System Settings → General → Sharing → Remote Login** (turn on).

You can now reach the mini from your laptop with `ssh`.

## 4. SSH in and configure

From your laptop:

```bash
ssh mac-mini
source /path/to/grok-bridge/.venv/bin/activate
grok-bridge start
```

On first start, a random bridge token is written to `~/.config/grok-bridge/token` and loaded as `$GROK_BRIDGE_TOKEN`.

If start complains about webhook placeholders, edit on the mini:

```text
~/Library/Application Support/grok-bridge/.env
```

Set:

- `GROK_BRIDGE_ADVISOR_WEBHOOK_URL` — from the Grok Advisor routine panel  
- `GROK_BRIDGE_ADVISOR_WEBHOOK_AUTH` — sender key from the panel  

Optional knobs: `~/Library/Application Support/grok-bridge/config.yaml` (default port `18787`).

## 5. Webhook routine

**Preferred:** ask **Grok Advisor** to generate a webhook routine that wakes on POST, reads `<webhook_event>.body`, answers in chat, and POSTs the reply to the mini bridge `/replies` endpoint using the token in `~/.config/grok-bridge/token`.

**Reference only:** [EXAMPLE-WEBHOOK.md](EXAMPLE-WEBHOOK.md) contains example routine wording. Prefer a bot-generated webhook; use the example only if you need a starting point (adjust port to match `config.yaml`).

## 6. Chat (SSH session)

Still on the Mac mini over SSH:

```bash
source /path/to/grok-bridge/.venv/bin/activate
grok-bridge start    # if not already running
grok-bridge-cli
```

```text
> /chat advisor
> Hello
> /quit
```

```bash
grok-bridge stop    # optional
```

On exit, use **`/status`** if you need the session log path for debugging.

**SSH disconnect:** `grok-bridge start` leaves the server running on the mini after you exit SSH. `grok-bridge-cli` is only for that session — leaving SSH ends the chat client, not the background server. Run `grok-bridge stop` later when you want the server down.

## More detail

See [OPERATOR-GUIDE.md](OPERATOR-GUIDE.md).
