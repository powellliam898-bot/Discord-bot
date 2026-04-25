# Discord Bot

A simple Discord bot built with `discord.py`, providing a few moderation slash commands and a basic ping command.

## Tech Stack
- **Language:** Python 3.12
- **Library:** [discord.py](https://discordpy.readthedocs.io/) (v2.x)

## Project Layout
- `bot.py` — Main bot entry point. Defines the bot, events, prefix command (`!ping`), and slash commands (`/ping`, `/kick`, `/ban`, `/timeout`).
- `pyproject.toml` — Python package metadata and dependencies.

## Commands
- `!ping` — Prefix command, replies with "Pong!".
- `/ping` — Slash command, replies with latency in ms.
- `/kick <member> [reason]` — Kicks a member (requires Kick Members permission).
- `/ban <member> [reason]` — Bans a member (requires Ban Members permission).
- `/timeout <member> <seconds>` — Times out a member (requires Moderate Members permission).

## Configuration
The bot requires the following secret to be set in Replit Secrets:
- `DISCORD_BOT_TOKEN` — Your Discord bot token from the [Discord Developer Portal](https://discord.com/developers/applications).

## Running
The bot runs via the **Discord Bot** workflow:
```
python bot.py
```
Slash commands are synced globally on startup (this can take up to an hour to propagate to all servers the first time).

## Deployment
This bot is a long-running background process (it makes outbound websocket connections to Discord; it does not listen on any port). For production hosting, a Reserved VM Background Worker deployment is the appropriate option.

## Security Note
The original `newfile.py` had its bot token hardcoded and committed to git history. That token has been removed from the source, but anyone with access to git history can still see it — it should be reset in the Discord Developer Portal.
