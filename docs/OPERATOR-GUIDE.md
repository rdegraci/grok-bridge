# Operator guide

How to run and use **grok-bridge** on the Mac mini as a human operator.

## What this is

A small terminal chat bridge to your Grok Bot **Grok Advisor** (and later other seats).

Typical use: **install on the Mac mini**, turn on **SSH (Remote Login)** in System Settings, **SSH in** from your laptop, then run **`grok-bridge start`** and **`grok-bridge-cli`** in that session to chat. Messages wake the bot via webhook; replies come back on localhost on the mini.

It is **not** the Grok Bot app. Rich UI, approvals, and site/git work stay elsewhere.

## Expectations (inbox, not fast chat)

Treat **grok-bridge** as an **SSH in/out-box**, not a low-latency chat UI.

| Surface | Use it for |
| --- | --- |
| **Grok Bot app on the Mac mini** | Interactive conversation when you want the fastest reply |
| **grok-bridge** | Remote inbox over SSH — same agent, extra hop (webhook wake → agent → `POST /replies` → CLI poll) |

After you send from the CLI, expect **tens of seconds** before a reply appears. That wait is mostly Grok Bot starting and answering, then posting back to the mini — not the local poll loop. The CLI prints `sent, waiting…` after the webhook is accepted so the gap is intentional.

When you need a snappy back-and-forth, use the Grok Bot app on the mini. Use the bridge when you are already SSHed in and want a simple in/out channel.

## Before you start

1. Mac mini is awake (prefer never-sleep for this machine).
2. Grok Bot is installed with **local computer access** enabled for this mini.
3. A Grok Bot named **Grok Advisor** exists (create it in the Grok Bot app if needed).
4. On **first chat** with Grok Advisor, allow it to **run commands locally on the Mac mini** when prompted. This is required so it can read `~/.config/grok-bridge/token`, talk through the bridge, and execute the operator’s command/request work on this machine.
5. A **webhook routine** on Grok Advisor exists (URL + sender key from the routine panel).  
   Prefer asking Grok Advisor to **generate** the webhook routine for you. An example routine text lives in [EXAMPLE-WEBHOOK.md](EXAMPLE-WEBHOOK.md) if you need a reference — treat it as a sample, not the preferred setup path.
6. **SSH (Remote Login)** is enabled on the mini: System Settings → General → Sharing → Remote Login.
7. Python 3.11+ and the package are installed once on the mini (see [Install](#install-once)).

## Install (once)

On the Mac mini:

```bash
cd /path/to/grok-bridge
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Keep using that venv (or ensure the `grok-bridge` / `grok-bridge-cli` scripts are on your `PATH`).

## Enable SSH (once)

On the Mac mini: **System Settings → General → Sharing → Remote Login** (on).

From your laptop you will use that to reach the mini and run the bridge CLI there.

## First-time configuration

1. Start once so example config is created:

   ```bash
   source /path/to/grok-bridge/.venv/bin/activate
   grok-bridge start
   ```

   If secrets are still placeholders, start will exit and tell you what to edit. That is expected.

2. Open the appdir:

   ```text
   ~/Library/Application Support/grok-bridge/
   ```

3. On first start, grok-bridge creates **`~/.config/grok-bridge/token`** (random Bearer token) if missing and loads it as `$GROK_BRIDGE_TOKEN`. You do not set this in `.env`.

4. Edit **`.env`** (webhook secrets only). Replace placeholders:

   | Variable | Meaning |
   | --- | --- |
   | `GROK_BRIDGE_ADVISOR_WEBHOOK_URL` | Webhook URL from the Advisor routine panel |
   | `GROK_BRIDGE_ADVISOR_WEBHOOK_AUTH` | Sender key (sent as `Authorization: Bearer …`) |

   Keep this file private (`chmod 600` if needed). Never commit it.

5. Optionally edit **`config.yaml`** (knobs):

   | Setting | Typical use |
   | --- | --- |
   | `server.port` | Default `18787` (change if something else owns the port) |
   | `cli.reply_timeout_sec` | How long the CLI waits for a reply (default `90`) |
   | `cli.poll_interval_sec` | How often to check for replies (default `1.5`) |

   Host must stay `127.0.0.1` (or `::1`). Do not open the server to the LAN.

6. Set up the **Grok Advisor** webhook routine:

   - Create (or use) a Grok Bot named **Grok Advisor**.
   - **Preferred:** ask Grok Advisor to generate a webhook routine that wakes on POST, reads `<webhook_event>.body`, answers in chat, and POSTs the same reply to the mini bridge `/replies` URL with the token from `~/.config/grok-bridge/token`.
   - **Reference only:** [EXAMPLE-WEBHOOK.md](EXAMPLE-WEBHOOK.md) shows example routine wording. Prefer the bot-generated routine; adjust port/host to match your `config.yaml` if needed.

   Do **not** paste the real bridge token into the routine text if the agent can read `~/.config/grok-bridge/token` or `$GROK_BRIDGE_TOKEN` instead.

   When you first talk to Grok Advisor in the app, approve **local command execution on the Mac mini** so it can read the token file and carry out shell/tool requests on this machine.


## Daily use

From your laptop, SSH into the Mac mini, then start the bridge and chat **in that SSH session**:

```bash
ssh mac-mini
source /path/to/grok-bridge/.venv/bin/activate

grok-bridge start          # if not already running
grok-bridge-cli
```

Do not run `grok-bridge-cli` on the laptop against a remote mini unless you have deliberately set up a tunnel; the supported path is CLI **on** the mini over SSH.

**After you leave SSH**

- **`grok-bridge start`** keeps the server running in the background on the mini. Exiting SSH does **not** stop it. Use `grok-bridge stop` in a later session (or reboot) when you want it down.
- **`grok-bridge-cli`** is foreground in that SSH session. Leaving SSH (or closing the terminal) ends the chat client only; the server stays up if you started it with `grok-bridge start`.
### Chat commands

| You type | What happens |
| --- | --- |
| `/chat advisor` | Select Advisor; show any queued replies for that bot |
| *(ordinary text)* | Send to the active bot; wait for a reply |
| `/status` | Show active bot, base URL, cursors, session log path |
| `/quit` | Leave the CLI (server keeps running) |

Example:

```text
> /chat advisor
[advisor] connected
> Summarize the next step for lorebuilder.
[advisor] …
> /quit
Session log: /Users/…/Library/Application Support/grok-bridge/logs/cli-….log
```

When finished for the day (optional):

```bash
grok-bridge stop
```

Leaving the server running is fine if the mini stays on.

## Where files live

**Bridge token**

| Path | Purpose |
| --- | --- |
| `~/.config/grok-bridge/token` | Auto-generated Bearer token (`$GROK_BRIDGE_TOKEN`) |

**Appdir**

```text
~/Library/Application Support/grok-bridge/
```

| Path | Purpose |
| --- | --- |
| `.env` | Webhook URL/auth secrets |
| `config.yaml` | Ports, timeouts, poll interval |
| `grok-bridge.pid` | Background server process id |
| `grok-bridge.log` | Server log |
| `logs/cli-….log` | One log per CLI session |

On exit, `grok-bridge-cli` always prints the **Session log:** path. Use that file when something goes wrong.

## Troubleshooting

| Symptom | What to try |
| --- | --- |
| `Cannot reach bridge server` | `grok-bridge start`. Check `grok-bridge.log`. Confirm port in `config.yaml` matches `cli.base_url`. |
| Auth failures on `/send` or `/replies` | Confirm `~/.config/grok-bridge/token` exists; restart so `$GROK_BRIDGE_TOKEN` is loaded. Agent must use the same token file. |
| `Advisor webhook missing` | Set `GROK_BRIDGE_ADVISOR_WEBHOOK_URL` and `_AUTH` in appdir `.env`. |
| `Webhook rejected` | Check sender key and URL in the routine panel; see server log. |
| `No reply within Ns` | Bot may have answered only in the Grok app. Check the routine (must `POST /replies`). Confirm local computer access. Open the session log and `grok-bridge.log`. |
| `failed to start` / address in use | Another process owns the port. Change `server.port` and `cli.base_url` in `config.yaml`, update the routine reply URL, then `grok-bridge restart`. |
| `already running` | Server is up. Use `grok-bridge-cli`, or `restart` if you changed config. |

### Quick health check

```bash
curl -sS http://127.0.0.1:18787/health
```

Expect: `{"ok":true,"v":1}` (use your configured port).

## Security habits

- Only use this over SSH on the mini (or local keyboard on that machine).
- Never put webhook keys or the bridge token file in git, chat dumps, or screenshots.
- Do not change bind host away from localhost.
- Rotate the webhook sender key if it may have leaked.

## Related docs

- [QUICK-START.md](QUICK-START.md) — shortest path to first chat  
- [EXAMPLE-WEBHOOK.md](EXAMPLE-WEBHOOK.md) — example webhook routine (prefer asking Grok Advisor to generate one)  
- [README.md](../README.md) — install overview and architecture  
- [LICENSE](../LICENSE) — MIT  

Design notes under `docs/cache/` (if present) are for developers, not day-to-day operation.
