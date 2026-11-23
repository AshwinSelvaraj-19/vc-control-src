"""Bot entry point for the panel-only VC control build.

Run from this folder:

    python bot.py

The token is read from DISCORD_TOKEN in the environment, or from the
`.env` file next to this file (DISCORD_TOKEN=...). Slash commands are
synced per guild on startup so `/vcpanel` shows up immediately.

Bot permissions needed: Manage Channels, Move Members, Mute Members.
Enable the Server Members intent in the Discord developer portal for
accurate member lists inside voice channels (the bot retries without it
if the intent is switched off).
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

import discord
from discord.ext import commands

BASE_DIR = Path(__file__).resolve().parent

COGS = ("open_panel",)


def load_env_file(path: Path) -> None:
    """Minimal .env loader — KEY=value lines, no extra dependency."""

    if not path.is_file():
        return

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


class VCPanelBot(commands.Bot):
    """Loads the panel cog and syncs `/vcpanel` to every guild."""

    def __init__(self, *, intents: discord.Intents) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned_or("?"),
            intents=intents,
        )

    async def setup_hook(self) -> None:
        for cog in COGS:
            await self.load_extension(cog)

        self.tree.on_error = self.on_app_command_error

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: BaseException,
    ) -> None:
        """Log slash-command failures and tell the user, so a silent
        \"application did not respond\" cannot happen again."""

        command = getattr(interaction.command, "name", "?") if interaction.command else "?"
        logging.getLogger("vcp" + "anel").exception(
            "/%s failed for %s", command, interaction.user, exc_info=error,
        )

        message = f"❌ `/{command}` failed: {type(error).__name__}: {error}"

        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException:
            pass

    async def on_ready(self) -> None:
        print(f"✅ Logged in as {self.user} (id: {getattr(self.user, 'id', '?')})")

        local = [f"/{c.name}" for c in self.tree.get_commands()]
        print(f"Loaded commands: {', '.join(local) or 'none'}")

        # Global registration: covers every server and DMs if ever needed.
        try:
            global_synced = await self.tree.sync()
            names = ", ".join(f"/{c.name}" for c in global_synced) or "none"
            print(f"✅ Global sync registered: {names}")
        except discord.HTTPException as exc:
            print(f"⚠️ Global command sync failed: {exc}")

        # Per-guild copies so the commands show up immediately in each server
        # (global commands can take up to an hour to propagate).
        for guild in self.guilds:
            self.tree.copy_global_to(guild=guild)

            try:
                synced = await self.tree.sync(guild=guild)
            except discord.HTTPException as exc:
                print(f"⚠️ Could not sync slash commands in {guild.name}: {exc}")
                continue

            names = ", ".join(f"/{c.name}" for c in synced) or "none"
            print(f"✅ Synced {names} in {guild.name} ({guild.id})")

        print("Ready — use /vcpanel while connected to a voice channel.")


async def run_bot(token: str) -> None:
    intents = discord.Intents.default()
    intents.members = True

    bot = VCPanelBot(intents=intents)

    try:
        await bot.start(token)
    except discord.PrivilegedIntentsRequired:
        print(
            "⚠️ Server Members intent is disabled for this application — retrying "
            "without it. Enable it under Bot → Privileged Gateway Intents for "
            "accurate voice member lists."
        )
        fallback = VCPanelBot(intents=discord.Intents.default())
        await fallback.start(token)


def main() -> int:
    load_env_file(BASE_DIR / ".env")

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]

    try:
        handlers.append(logging.FileHandler(BASE_DIR / "bot.log", encoding="utf-8"))
    except OSError:
        pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        handlers=handlers,
    )

    token = os.environ.get("DISCORD_TOKEN", "").strip()

    if not token:
        print("❌ DISCORD_TOKEN is not set (put it in panel-only/.env).", file=sys.stderr)
        return 1

    try:
        asyncio.run(run_bot(token))
    except discord.LoginFailure:
        print("❌ Discord rejected the token — generate a new one in the developer portal.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Stopped.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
