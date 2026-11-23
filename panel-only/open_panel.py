"""Open the designed VC control panel — two ways in, same panel.

Source: designed web UI at
``~/workspace/your_files/vc-control-panel/vc-control-panel.html``,
implemented in ``vc_control_panel.py``.

  1. Prefix (old repo panel, kept):  ``@Bot ?vc``
     — mention the bot + `` ?``, while connected to a voice channel.
  2. Slash (new, per user request): ``/vcpanel``
     — same checks, same panel, same View.

Both require: the user is a discord.Member in a server, is connected
to a normal voice channel, and passes ``can_control_voice_channel``
(server owner / Administrator / temp-VC owner / member with
``manage_channels``). The bot needs Manage Channels / Move Members /
Mute Members, plus the Voice States and Server Members intents.

Slash-command registration / sync
----------------------------------
``app_commands`` commands are only registered with Discord when the
command tree is synced. ``setup()`` below calls
``await bot.tree.sync()`` once when this cog is loaded, so ``/vcpanel``
is registered globally. Global commands can take up to ~1 hour to
appear in every server the first time; if you need it instantly, sync
to one guild instead in your bot's startup code, e.g.::

    guild = discord.Object(id=YOUR_GUILD_ID)
    await bot.tree.sync(guild=guild)

(or run it once from a ``?sync`` owner command). After the first
sync, later bot restarts do not need a re-sync unless commands change.
Do NOT call ``tree.sync()`` on every message / on_ready loop — Discord
rate-limits it.

Usage in a bot
--------------
    # in your bot's startup / main.py
    await bot.load_extension("open_panel")
    # or, if the file lives in a package: await bot.load_extension("bot.cogs.open_panel")

The text channel the panel was opened from is stored on the View so
Clear Chats knows which text channel to purge (see README.md).
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from permissions import can_control_voice_channel
from vc_control_panel import VCControlPanelView, create_control_embed


def is_owner_or_admin(member: discord.Member) -> bool:
    """True for the server owner or a member holding Administrator."""

    if member.guild is None:
        return False

    if member.guild.owner_id == member.id:
        return True

    return bool(member.guild_permissions.administrator)


async def _check_and_get_channel(
    member: discord.Member,
) -> discord.VoiceChannel | str:
    """Return the member's voice channel, or an error string."""
    voice_state = member.voice
    if voice_state is None or voice_state.channel is None:
        return "❌ You must be connected to a voice channel first."
    channel = voice_state.channel
    if not isinstance(channel, discord.VoiceChannel):
        return "❌ You must be connected to a normal voice channel."
    allowed, _ = can_control_voice_channel(
        member, channel, "manage_channels",
    )
    if not allowed:
        return "❌ You don't have permission to control this voice channel."
    return channel


class PanelOpener(commands.Cog):
    """Open the Heaven VC control panel — ``?vc`` and ``/vcpanel``."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # -- Prefix opener (old panel, kept) ---------------------------
    @commands.group(name="vc", invoke_without_command=True)
    async def vc(self, ctx: commands.Context) -> None:
        """Open the Heaven interactive VC control panel."""
        if not isinstance(ctx.author, discord.Member):
            await ctx.send("❌ This command can only be used inside a server.")
            return
        result = await _check_and_get_channel(ctx.author)
        if isinstance(result, str):
            await ctx.send(result)
            return
        text_channel = (
            ctx.channel if isinstance(ctx.channel, discord.TextChannel)
            else None
        )
        await ctx.send(
            embed=create_control_embed(result),
            view=VCControlPanelView(self.bot, text_channel),
        )

    # -- Slash opener (new) ----------------------------------------
    @app_commands.command(
        name="vcpanel",
        description="Open the Heaven VC control panel for your voice channel.",
    )
    async def vcpanel(self, interaction: discord.Interaction) -> None:
        """Slash command: /vcpanel — open the designed panel."""
        if not isinstance(interaction.user, discord.Member) or not is_owner_or_admin(
            interaction.user
        ):
            await interaction.response.send_message(
                "❌ Only the server owner or an administrator can use `/vcpanel`.",
                ephemeral=True,
            )
            return
        result = await _check_and_get_channel(interaction.user)
        if isinstance(result, str):
            await interaction.response.send_message(result, ephemeral=True)
            return
        text_channel = (
            interaction.channel
            if isinstance(interaction.channel, discord.TextChannel)
            else None
        )
        await interaction.response.send_message(
            embed=create_control_embed(result),
            view=VCControlPanelView(self.bot, text_channel),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PanelOpener(bot))
    # /vcpanel registration is handled by bot.py on_ready (global sync plus an
    # instant per-guild copy), so no sync is needed here.
